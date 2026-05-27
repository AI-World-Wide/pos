# -*- coding: utf-8 -*-
"""Email reports via Gmail OAuth2 (XOAUTH2 SMTP) or plain SMTP fallback.

Uses built-in smtplib + google-auth flow. No extra heavy deps.
Credentials stored in the settings DB table, NOT in config files or git.
"""
from __future__ import annotations

import base64
import json
import logging
import smtplib
import urllib.parse
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.database import SessionLocal
from src.models import Setting
from src.reports import (
    generate_csv,
    get_credit_summary,
    get_open_tables_summary,
    get_sales_by_cashier,
    get_sales_by_category,
    get_summary,
    get_top_items,
)
from src.translations.ar import T

logger = logging.getLogger(__name__)

# Gmail OAuth2 endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587

# Setting keys for email config
OAUTH_KEYS = [
    "gmail_client_id", "gmail_client_secret", "gmail_refresh_token",
    "gmail_access_token", "gmail_sender_email",
]
EMAIL_KEYS = [
    "email_recipients",  # comma-separated
    "report_on_close", "report_daily",
    "include_sales_summary", "include_top_items", "include_category_breakdown",
    "include_cashier_breakdown", "include_hourly_breakdown", "include_credit_summary",
]


def _get_setting(db, key: str) -> str:
    s = db.query(Setting).filter(Setting.key == key).first()
    return s.value if s and s.value else ""


def _set_setting(db, key: str, value: str):
    s = db.query(Setting).filter(Setting.key == key).first()
    if s:
        s.value = value
    else:
        db.add(Setting(key=key, value=value))


def get_oauth_url(redirect_uri: str) -> str | None:
    """Build the Google OAuth2 authorization URL."""
    db = SessionLocal()
    try:
        client_id = _get_setting(db, "gmail_client_id")
        if not client_id:
            return None
        params = urllib.parse.urlencode({
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "https://mail.google.com/",
            "access_type": "offline",
            "prompt": "consent",
        })
        return f"{GOOGLE_AUTH_URL}?{params}"
    finally:
        db.close()


def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict:
    """Exchange the OAuth2 authorization code for tokens."""
    db = SessionLocal()
    try:
        client_id = _get_setting(db, "gmail_client_id")
        client_secret = _get_setting(db, "gmail_client_secret")

        data = urllib.parse.urlencode({
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }).encode()

        req = urllib.request.Request(GOOGLE_TOKEN_URL, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urllib.request.urlopen(req, timeout=30) as resp:
            tokens = json.loads(resp.read().decode())

        _set_setting(db, "gmail_access_token", tokens.get("access_token", ""))
        _set_setting(db, "gmail_refresh_token", tokens.get("refresh_token", ""))
        db.commit()
        return tokens
    finally:
        db.close()


def _refresh_access_token() -> str | None:
    """Refresh the Gmail access token using the stored refresh token."""
    db = SessionLocal()
    try:
        client_id = _get_setting(db, "gmail_client_id")
        client_secret = _get_setting(db, "gmail_client_secret")
        refresh_token = _get_setting(db, "gmail_refresh_token")

        if not all([client_id, client_secret, refresh_token]):
            return None

        data = urllib.parse.urlencode({
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }).encode()

        req = urllib.request.Request(GOOGLE_TOKEN_URL, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urllib.request.urlopen(req, timeout=30) as resp:
            tokens = json.loads(resp.read().decode())

        access_token = tokens.get("access_token", "")
        _set_setting(db, "gmail_access_token", access_token)
        db.commit()
        return access_token
    except Exception as e:
        logger.error("Token refresh failed: %s", e)
        return None
    finally:
        db.close()


def _xoauth2_string(user: str, access_token: str) -> str:
    """Build the XOAUTH2 SASL string."""
    auth = f"user={user}\x01auth=Bearer {access_token}\x01\x01"
    return base64.b64encode(auth.encode()).decode()


def _smtp_send_once(sender: str, access_token: str, to_list: list[str], msg) -> tuple[bool, str]:
    """One SMTP attempt with a given access token. Returns (ok, detail).

    Checks the XOAUTH2 AUTH response code explicitly — an expired token
    fails here (not later as a generic error), so the caller can refresh
    and retry deterministically.
    """
    server = None
    try:
        server = smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, timeout=30)
        server.ehlo()
        server.starttls()
        server.ehlo()
        xoauth2 = _xoauth2_string(sender, access_token)
        code, resp = server.docmd("AUTH", "XOAUTH2 " + xoauth2)
        # 334 = server sent a base64 error challenge; ack with empty line to
        # get the final status code.
        if code == 334:
            code, resp = server.docmd("")
        if code != 235:
            return False, f"AUTH {code}: {resp.decode(errors='replace') if isinstance(resp, bytes) else resp}"
        server.sendmail(sender, to_list, msg.as_string())
        return True, "Email sent successfully"
    except Exception as e:
        return False, str(e)
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass


def _send_gmail(
    to_list: list[str],
    subject: str,
    html_body: str,
    csv_attachment: str | None = None,
    pdf_attachment: bytes | None = None,
    pdf_filename: str = "report.pdf",
) -> str:
    """Send email via Gmail SMTP with XOAUTH2.

    Bulletproof token handling: the Gmail access token expires ~1 hour
    after it's issued, so we ALWAYS mint a fresh one from the long-lived
    refresh token right before sending. This means the operator connects
    Gmail once and never has to re-authenticate (as long as the OAuth app
    is published / "In production" in Google Cloud, refresh tokens don't
    expire). Optional CSV + PDF attachments are supported.
    """
    db = SessionLocal()
    try:
        sender = _get_setting(db, "gmail_sender_email")
        refresh_token = _get_setting(db, "gmail_refresh_token")
        stored_token = _get_setting(db, "gmail_access_token")
    finally:
        db.close()

    if not sender:
        return "Gmail not configured — connect Gmail in Settings"
    if not refresh_token and not stored_token:
        return "Gmail not connected — open Settings and press Connect Gmail"

    # Always refresh first so every send uses a valid (fresh) access token.
    access_token = _refresh_access_token() or stored_token
    if not access_token:
        return "Gmail auth failed — please reconnect Gmail in Settings"

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(to_list)
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    if csv_attachment:
        csv_part = MIMEText(csv_attachment, "csv", "utf-8")
        csv_part.add_header("Content-Disposition", "attachment", filename="report.csv")
        msg.attach(csv_part)
    if pdf_attachment:
        from email.mime.application import MIMEApplication
        pdf_part = MIMEApplication(pdf_attachment, _subtype="pdf")
        pdf_part.add_header("Content-Disposition", "attachment", filename=pdf_filename)
        msg.attach(pdf_part)

    ok, detail = _smtp_send_once(sender, access_token, to_list, msg)
    if ok:
        return "Email sent successfully"

    # One more try with a freshly refreshed token (covers a token that
    # expired in the seconds between refresh and send, or a stale one).
    logger.warning("Gmail send failed (%s); refreshing token and retrying", detail)
    new_token = _refresh_access_token()
    if new_token and new_token != access_token:
        ok, detail = _smtp_send_once(sender, new_token, to_list, msg)
        if ok:
            return "Email sent successfully"

    return f"Email error: {detail}"


def _build_report_html(period: str = "today", includes: dict | None = None, force_full_summary: bool = False) -> str:
    """Build HTML email body based on selected report sections.

    The PRIMARY summary table always includes every key analytics number
    when `force_full_summary` is True (closing-day email). Otherwise it
    respects the `include_sales_summary` toggle for backwards-compatible
    scheduled reports.
    """
    if includes is None:
        includes = {k: True for k in [
            "include_sales_summary", "include_top_items", "include_category_breakdown",
            "include_cashier_breakdown", "include_credit_summary",
        ]}

    html = f'<html dir="rtl" lang="ar"><body style="font-family:Arial,sans-serif;direction:rtl;">'
    html += f'<h2>{T["reports_title"]}</h2>'

    show_summary = force_full_summary or includes.get("include_sales_summary")
    if show_summary:
        summary = get_summary(period)
        open_t = get_open_tables_summary(period)
        html += '<table style="border-collapse:collapse;width:100%;max-width:560px;margin-bottom:20px">'
        rows = [
            (T.get("total_with_vat", T["total_sales"]), f'{T["currency"]} {summary["total_with_vat"]:.2f}'),
            (T.get("subtotal_no_vat", "Subtotal"), f'{T["currency"]} {summary["subtotal_no_vat"]:.2f}'),
            (T["vat_collected"], f'{T["currency"]} {summary["vat_collected"]:.2f}'),
            (T.get("cash_total", T.get("cash_payments", "Cash")), f'{T["currency"]} {summary["cash_total"]:.2f}'),
            (T.get("card_total", T.get("card_payments", "Card")), f'{T["currency"]} {summary["card_total"]:.2f}'),
            (T["order_count"], str(summary["order_count"])),
            (T["avg_order_value"], f'{T["currency"]} {summary["avg_order_value"]:.2f}'),
            (T.get("open_tables_count", "Open tables"), str(open_t["count"])),
            (T.get("open_tables_due", "Open tables due"), f'{T["currency"]} {open_t["total_due"]:.2f}'),
        ]
        for label, val in rows:
            html += f'<tr><td style="padding:8px;border:1px solid #ddd">{label}</td>'
            html += f'<td style="padding:8px;border:1px solid #ddd"><strong>{val}</strong></td></tr>'
        html += '</table>'

    if includes.get("include_top_items"):
        top = get_top_items(period, 10)
        if top:
            html += f'<h3>{T["top_items"]}</h3><table style="border-collapse:collapse;width:100%;max-width:500px;margin-bottom:20px">'
            html += f'<tr style="background:#2a2a2a;color:#fff"><th style="padding:8px;border:1px solid #ddd">{T["item"]}</th>'
            html += f'<th style="padding:8px;border:1px solid #ddd">{T["qty"]}</th>'
            html += f'<th style="padding:8px;border:1px solid #ddd">{T["price"]}</th></tr>'
            for i in top:
                html += f'<tr><td style="padding:6px;border:1px solid #ddd">{i["name_ar"]}</td>'
                html += f'<td style="padding:6px;border:1px solid #ddd">{i["qty"]}</td>'
                html += f'<td style="padding:6px;border:1px solid #ddd">{T["currency"]} {i["revenue"]:.2f}</td></tr>'
            html += '</table>'

    if includes.get("include_category_breakdown"):
        cats = get_sales_by_category(period)
        if cats:
            html += f'<h3>{T["sales_by_category"]}</h3><table style="border-collapse:collapse;width:100%;max-width:500px;margin-bottom:20px">'
            for c in cats:
                html += f'<tr><td style="padding:6px;border:1px solid #ddd">{c["name_ar"]}</td>'
                html += f'<td style="padding:6px;border:1px solid #ddd">{T["currency"]} {c["revenue"]:.2f}</td></tr>'
            html += '</table>'

    if includes.get("include_cashier_breakdown"):
        cashiers = get_sales_by_cashier(period)
        if cashiers:
            html += f'<h3>{T["sales_by_cashier"]}</h3><table style="border-collapse:collapse;width:100%;max-width:500px;margin-bottom:20px">'
            for c in cashiers:
                html += f'<tr><td style="padding:6px;border:1px solid #ddd">{c["cashier"]}</td>'
                html += f'<td style="padding:6px;border:1px solid #ddd">{c["count"]} orders</td>'
                html += f'<td style="padding:6px;border:1px solid #ddd">{T["currency"]} {c["revenue"]:.2f}</td></tr>'
            html += '</table>'

    if includes.get("include_credit_summary"):
        credit = get_credit_summary()
        if credit["count"] > 0:
            html += f'<h3>{T["credit_area"]}</h3>'
            html += f'<p>{T["total_credit"]}: <strong>{T["currency"]} {credit["total"]:.2f}</strong> ({credit["count"]} {T["credit_tables"]})</p>'

    html += '</body></html>'
    return html


def send_daily_report(period: str = "today", force_full_summary: bool = False, include_pdf: bool = False) -> str:
    """Send the configured daily report.

    `force_full_summary`: ignore the include_sales_summary toggle and put
    every analytics number in the primary table (used by closing email).
    `include_pdf`: also attach a full multi-section PDF report.
    """
    db = SessionLocal()
    try:
        recipients_str = _get_setting(db, "email_recipients")
        if not recipients_str:
            return "No recipients configured"
        recipients = [e.strip() for e in recipients_str.split(",") if e.strip()]
        if not recipients:
            return "No recipients configured"

        includes = {}
        for key in EMAIL_KEYS:
            if key.startswith("include_"):
                includes[key] = _get_setting(db, key) == "1"
    finally:
        db.close()

    html = _build_report_html(period, includes, force_full_summary=force_full_summary)
    csv = generate_csv(period)

    pdf_bytes = None
    pdf_filename = "report.pdf"
    if include_pdf:
        try:
            from src.pdf_report import build_closing_report_pdf
            pdf_bytes = build_closing_report_pdf(period)
            from datetime import date as _date
            pdf_filename = f"cafe_pos_report_{_date.today().isoformat()}.pdf"
        except Exception as e:
            logger.error("PDF build failed: %s", e)

    return _send_gmail(
        recipients,
        "Cafe POS — Daily Report",
        html,
        csv_attachment=csv,
        pdf_attachment=pdf_bytes,
        pdf_filename=pdf_filename,
    )


def send_shift_report(shift_id: int) -> str:
    """Send report when a shift/day is closed.

    Sent IMMEDIATELY when the day is closed (not on any timer). The email
    body's primary table contains every analytics number, and a full PDF
    of every report sheet is attached.
    """
    db = SessionLocal()
    try:
        on_close = _get_setting(db, "report_on_close")
        if on_close != "1":
            return "Report on close disabled"
    finally:
        db.close()
    return send_daily_report("today", force_full_summary=True, include_pdf=True)
