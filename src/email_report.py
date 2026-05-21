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


def _send_gmail(to_list: list[str], subject: str, html_body: str, csv_attachment: str | None = None) -> str:
    """Send email via Gmail SMTP with XOAUTH2."""
    db = SessionLocal()
    try:
        sender = _get_setting(db, "gmail_sender_email")
        access_token = _get_setting(db, "gmail_access_token")
    finally:
        db.close()

    if not sender or not access_token:
        return "Gmail not configured"

    # Try with current token; refresh if needed
    for attempt in range(2):
        try:
            msg = MIMEMultipart("mixed")
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = ", ".join(to_list)
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            if csv_attachment:
                csv_part = MIMEText(csv_attachment, "csv", "utf-8")
                csv_part.add_header("Content-Disposition", "attachment", filename="report.csv")
                msg.attach(csv_part)

            server = smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, timeout=30)
            server.starttls()
            xoauth2 = _xoauth2_string(sender, access_token)
            server.docmd("AUTH", f"XOAUTH2 {xoauth2}")
            server.sendmail(sender, to_list, msg.as_string())
            server.quit()
            return "Email sent successfully"
        except smtplib.SMTPAuthenticationError:
            if attempt == 0:
                access_token = _refresh_access_token()
                if not access_token:
                    return "Gmail auth failed — please reconnect"
            else:
                return "Gmail auth failed after refresh"
        except Exception as e:
            return f"Email error: {e}"

    return "Email failed"


def _build_report_html(period: str = "today", includes: dict | None = None) -> str:
    """Build HTML email body based on selected report sections."""
    if includes is None:
        includes = {k: True for k in [
            "include_sales_summary", "include_top_items", "include_category_breakdown",
            "include_cashier_breakdown", "include_credit_summary",
        ]}

    html = f'<html dir="rtl" lang="ar"><body style="font-family:Arial,sans-serif;direction:rtl;">'
    html += f'<h2>{T["reports_title"]}</h2>'

    if includes.get("include_sales_summary"):
        summary = get_summary(period)
        html += '<table style="border-collapse:collapse;width:100%;max-width:500px;margin-bottom:20px">'
        for label, val in [
            (T["total_sales"], f'{T["currency"]} {summary["total_sales"]:.2f}'),
            (T["vat_collected"], f'{T["currency"]} {summary["vat_collected"]:.2f}'),
            (T["order_count"], str(summary["order_count"])),
            (T["avg_order_value"], f'{T["currency"]} {summary["avg_order_value"]:.2f}'),
        ]:
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


def send_daily_report(period: str = "today") -> str:
    """Send the configured daily report."""
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

    html = _build_report_html(period, includes)
    csv = generate_csv(period)
    return _send_gmail(recipients, f"Cafe POS — Daily Report", html, csv)


def send_shift_report(shift_id: int) -> str:
    """Send report when a shift/day is closed."""
    db = SessionLocal()
    try:
        on_close = _get_setting(db, "report_on_close")
        if on_close != "1":
            return "Report on close disabled"
    finally:
        db.close()
    return send_daily_report("today")
