# -*- coding: utf-8 -*-
"""Reports + analytics routes — enhanced with credit, shifts, trends."""
from __future__ import annotations

from flask import Blueprint, Response, redirect, render_template, request, session, url_for

from src.reports import (
    generate_csv,
    generate_orders_csv,
    get_all_orders_sheet,
    get_avg_items_per_order,
    get_credit_summary,
    get_current_shift_stats,
    get_daily_trend,
    get_payment_breakdown,
    get_peak_hour,
    get_sales_by_cashier,
    get_sales_by_category,
    get_sales_by_hour,
    get_summary,
    get_table_orders_history,
    get_top_items,
)

bp = Blueprint("reports", __name__, url_prefix="/reports")


@bp.before_request
def _check_access():
    if not session.get("username"):
        return redirect(url_for("auth.login_page"))
    if session.get("role") != "admin":
        return redirect(url_for("cashier.index"))


@bp.get("/")
def index():
    period = request.args.get("period", "today")
    summary = get_summary(period)
    top = get_top_items(period)
    by_cat = get_sales_by_category(period)
    by_hour = get_sales_by_hour(period)
    by_cashier = get_sales_by_cashier(period)
    payments = get_payment_breakdown(period)
    avg_items = get_avg_items_per_order(period)
    peak = get_peak_hour(period)
    credit = get_credit_summary()
    trend = get_daily_trend(7)
    shift_stats = get_current_shift_stats()
    table_orders = get_table_orders_history(period)
    orders_sheet = get_all_orders_sheet(period)

    return render_template("reports.html",
                           period=period,
                           summary=summary,
                           top_items=top,
                           by_category=by_cat,
                           by_hour=by_hour,
                           by_cashier=by_cashier,
                           payments=payments,
                           avg_items=avg_items,
                           peak=peak,
                           credit=credit,
                           trend=trend,
                           shift_stats=shift_stats,
                           table_orders=table_orders,
                           orders_sheet=orders_sheet)


@bp.get("/csv")
def export_csv():
    period = request.args.get("period", "today")
    csv_data = generate_csv(period)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=report_{period}.csv"},
    )


@bp.get("/orders-csv")
def export_orders_csv():
    """Export the full orders sheet as CSV."""
    period = request.args.get("period", "today")
    csv_data = generate_orders_csv(period)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=orders_{period}.csv"},
    )


@bp.post("/orders-email")
def email_orders_sheet():
    """Email the orders sheet CSV to configured recipients."""
    from src.email_report import _send_gmail, _get_setting
    from src.database import SessionLocal
    period = request.form.get("period", "today")
    csv_data = generate_orders_csv(period)

    db = SessionLocal()
    try:
        recipients_str = _get_setting(db, "email_recipients")
    finally:
        db.close()

    if not recipients_str:
        from flask import flash
        flash("No recipients configured", "error")
        return redirect(url_for("reports.index", period=period))

    recipients = [e.strip() for e in recipients_str.split(",") if e.strip()]
    html = '<html dir="rtl"><body style="font-family:Arial;direction:rtl"><h2>سجل الطلبات</h2><p>مرفق ملف CSV بسجل الطلبات</p></body></html>'
    result = _send_gmail(recipients, f"Cafe POS — Orders Sheet ({period})", html, csv_data)

    from flask import flash
    flash(result, "success" if "success" in result.lower() else "error")
    return redirect(url_for("reports.index", period=period))
