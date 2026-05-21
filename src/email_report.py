# -*- coding: utf-8 -*-
"""Daily email report via SMTP. Uses built-in smtplib — no extra deps.

Called by Windows Task Scheduler (or manually from settings).
Does NOT interact with PostgreSQL — reads from SQLite only.
"""
from __future__ import annotations

import configparser
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from src.reports import generate_csv, get_summary, get_top_items
from src.translations.ar import T

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.ini"


def _config() -> configparser.ConfigParser:
    c = configparser.ConfigParser()
    c.read(CONFIG_PATH, encoding="utf-8")
    return c


def send_daily_report() -> str:
    """Build and send the daily sales summary email. Returns status message."""
    cfg = _config()

    host = cfg.get("smtp", "host", fallback="")
    if not host:
        return "SMTP not configured"

    port = cfg.getint("smtp", "port", fallback=587)
    username = cfg.get("smtp", "username", fallback="")
    password = cfg.get("smtp", "password", fallback="")
    use_tls = cfg.getboolean("smtp", "use_tls", fallback=True)
    from_addr = cfg.get("smtp", "from_address", fallback=username)
    to_addr = cfg.get("smtp", "to_address", fallback="")

    if not to_addr:
        return "No recipient email configured"

    summary = get_summary("today")
    top = get_top_items("today", limit=10)
    csv_data = generate_csv("today")

    # Build HTML body
    html = f"""
    <html dir="rtl" lang="ar">
    <body style="font-family: Arial, sans-serif; direction: rtl;">
    <h2>{T['reports_title']} — {T['today']}</h2>
    <table style="border-collapse:collapse; width:100%; max-width:500px;">
      <tr><td style="padding:8px; border:1px solid #ddd;">{T['total_sales']}</td>
          <td style="padding:8px; border:1px solid #ddd;">{T['currency']} {summary['total_sales']:.2f}</td></tr>
      <tr><td style="padding:8px; border:1px solid #ddd;">{T['vat_collected']}</td>
          <td style="padding:8px; border:1px solid #ddd;">{T['currency']} {summary['vat_collected']:.2f}</td></tr>
      <tr><td style="padding:8px; border:1px solid #ddd;">{T['order_count']}</td>
          <td style="padding:8px; border:1px solid #ddd;">{summary['order_count']}</td></tr>
      <tr><td style="padding:8px; border:1px solid #ddd;">{T['avg_order_value']}</td>
          <td style="padding:8px; border:1px solid #ddd;">{T['currency']} {summary['avg_order_value']:.2f}</td></tr>
    </table>

    <h3>{T['top_items']}</h3>
    <table style="border-collapse:collapse; width:100%; max-width:500px;">
      <tr style="background:#2a2a2a; color:#fff;">
        <th style="padding:8px; border:1px solid #ddd;">{T['item']}</th>
        <th style="padding:8px; border:1px solid #ddd;">{T['qty']}</th>
        <th style="padding:8px; border:1px solid #ddd;">{T['price']}</th>
      </tr>
    """
    for item in top:
        html += f"""
      <tr>
        <td style="padding:6px; border:1px solid #ddd;">{item['name_ar']}</td>
        <td style="padding:6px; border:1px solid #ddd;">{item['qty']}</td>
        <td style="padding:6px; border:1px solid #ddd;">{T['currency']} {item['revenue']:.2f}</td>
      </tr>"""
    html += "</table></body></html>"

    # Build email
    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"Cafe POS — Daily Report"
    msg["From"] = from_addr
    msg["To"] = to_addr

    msg.attach(MIMEText(html, "html", "utf-8"))

    # Attach CSV
    csv_part = MIMEText(csv_data, "csv", "utf-8")
    csv_part.add_header("Content-Disposition", "attachment", filename="daily_report.csv")
    msg.attach(csv_part)

    try:
        if use_tls:
            server = smtplib.SMTP(host, port, timeout=30)
            server.starttls()
        else:
            server = smtplib.SMTP(host, port, timeout=30)

        if username and password:
            server.login(username, password)

        server.sendmail(from_addr, [to_addr], msg.as_string())
        server.quit()
        return "Email sent successfully"
    except Exception as e:
        return f"Email failed: {e}"


if __name__ == "__main__":
    print(send_daily_report())
