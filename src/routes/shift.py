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
    if session.get("role") != "admin":
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
    if session.get("role") != "admin":
        return redirect(url_for("shift.index"))
    db = get_session()
    try:
        current = get_current_shift(db)
        if not current:
            return redirect(url_for("shift.index"))

        # Check for open tables
        open_tables = db.query(FloorTable).filter(FloorTable.status == "occupied").count()
        if open_tables > 0:
            flash("cannot_close_open_tables", "error")
            return redirect(url_for("shift.index"))

        closing_cash = float(request.form.get("closing_cash", 0))

        # Calculate shift totals
        orders = db.query(Order).filter(
            Order.shift_id == current.id, Order.status == "settled"
        ).all()

        current.closed_at = datetime.utcnow()
        current.closed_by = session.get("username")
        current.closing_cash = closing_cash
        current.total_sales = sum(o.total for o in orders)
        current.total_orders = len(orders)
        current.total_vat = sum(o.vat_amount for o in orders)
        current.status = "closed"
        db.commit()

        # Send email report if configured
        try:
            from src.email_report import send_shift_report
            send_shift_report(current.id)
        except Exception:
            pass

        return redirect(url_for("shift.index"))
    finally:
        db.close()
