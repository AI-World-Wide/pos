# -*- coding: utf-8 -*-
"""Reports + analytics routes — enhanced with credit, shifts, trends."""
from __future__ import annotations

from flask import Blueprint, Response, redirect, render_template, request, session, url_for

from src.reports import (
    generate_csv,
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
    get_top_items,
)

bp = Blueprint("reports", __name__, url_prefix="/reports")


@bp.before_request
def _check_access():
    if not session.get("username"):
        return redirect(url_for("auth.login_page"))
    if session.get("role") != "admin" and not session.get("can_view_reports"):
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
                           shift_stats=shift_stats)


@bp.get("/csv")
def export_csv():
    period = request.args.get("period", "today")
    csv_data = generate_csv(period)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=report_{period}.csv"},
    )
