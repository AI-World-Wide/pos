# -*- coding: utf-8 -*-
"""Shift / day open-close routes."""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func

from src.database import get_session
from src.models import FloorTable, Order, Shift

bp = Blueprint("shift", __name__, url_prefix="/shift")


def get_current_shift(db) -> Shift | None:
    return db.query(Shift).filter(Shift.status == "open").order_by(Shift.opened_at.desc()).first()


@bp.get("/")
def index():
    if not session.get("username"):
        return redirect(url_for("auth.login_page"))
    db = get_session()
    try:
        current = get_current_shift(db)
        past_shifts = (
            db.query(Shift)
            .filter(Shift.status == "closed")
            .order_by(Shift.closed_at.desc())
            .limit(10)
            .all()
        )

        # Live stats for current shift
        live_stats = None
        if current:
            orders = (
                db.query(Order)
                .filter(Order.shift_id == current.id, Order.status == "settled")
                .all()
            )
            live_stats = {
                "total_sales": sum(o.total for o in orders),
                "total_vat": sum(o.vat_amount for o in orders),
                "order_count": len(orders),
                "cash_total": sum(o.total for o in orders if o.payment_method == "cash"),
                "card_total": sum(o.total for o in orders if o.payment_method == "card"),
            }

        # Open tables count
        open_tables = db.query(FloorTable).filter(FloorTable.status == "occupied").count()

        return render_template("shift.html",
                               current=current, live_stats=live_stats,
                               past_shifts=past_shifts, open_tables=open_tables)
    finally:
        db.close()


@bp.post("/open")
def open_day():
    if session.get("role") not in ("admin", "cashier"):
        return redirect(url_for("shift.index"))
    db = get_session()
    try:
        existing = get_current_shift(db)
        if existing:
            flash("day_already_open", "error")
            return redirect(url_for("shift.index"))

        opening_cash = float(request.form.get("opening_cash", 0))
        shift = Shift(
            opened_by=session.get("username"),
            opening_cash=opening_cash,
            status="open",
        )
        db.add(shift)
        db.commit()
        return redirect(url_for("shift.index"))
    finally:
        db.close()


@bp.post("/close")
def close_day():
    if session.get("role") not in ("admin", "cashier"):
        return redirect(url_for("shift.index"))
    db = get_session()
    try:
        current = get_current_shift(db)
        if not current:
            return redirect(url_for("shift.index"))

        # Closing the day no longer blocks on occupied tables and no longer
        # asks for closing cash — by design. Tables can keep their open
        # orders across day boundaries and will be settled whenever the
        # customer pays. The order's original creation date is what gets
        # attributed to the sales day in reports.

        # Calculate shift totals from orders that were CREATED inside this
        # shift, regardless of when they settle.
        orders = db.query(Order).filter(
            Order.shift_id == current.id, Order.status == "settled"
        ).all()

        current.closed_at = datetime.now()
        current.closed_by = session.get("username")
        current.closing_cash = 0
        current.total_sales = sum(o.total for o in orders)
        current.total_orders = len(orders)
        current.total_vat = sum(o.vat_amount for o in orders)
        current.status = "closed"
        db.commit()

        shift_id = current.id
    finally:
        db.close()

    # Send email report (outside the db block). Surface the result so the
    # operator can see whether it sent and why if it didn't.
    try:
        import logging
        from src.email_report import send_shift_report
        result = send_shift_report(shift_id)
        logging.getLogger(__name__).info("Shift close email: %s", result)
        flash(result, "success" if "success" in (result or "").lower() else "error")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Shift close email failed: %s", e)
        flash(f"Email error: {e}", "error")

    return redirect(url_for("shift.index"))
