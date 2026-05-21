# -*- coding: utf-8 -*-
"""Reports + analytics calculations. All queries hit SQLite only."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, case

from src.database import SessionLocal
from src.models import Category, Item, Order, OrderLine


def _date_range(period: str) -> tuple[datetime, datetime]:
    """Return (start, end) datetimes for a named period."""
    today = date.today()
    if period == "yesterday":
        d = today - timedelta(days=1)
        return datetime(d.year, d.month, d.day), datetime(d.year, d.month, d.day, 23, 59, 59)
    elif period == "week":
        start = today - timedelta(days=today.weekday())
        return datetime(start.year, start.month, start.day), datetime.now()
    elif period == "month":
        start = today.replace(day=1)
        return datetime(start.year, start.month, start.day), datetime.now()
    else:  # today
        return datetime(today.year, today.month, today.day), datetime.now()


def get_summary(period: str = "today") -> dict:
    """Get sales summary for a period."""
    start, end = _date_range(period)
    db = SessionLocal()
    try:
        orders = (
            db.query(Order)
            .filter(Order.status == "settled", Order.closed_at.between(start, end))
            .all()
        )
        total_sales = sum(o.total for o in orders)
        total_vat = sum(o.vat_amount for o in orders)
        count = len(orders)
        avg = total_sales / count if count else 0

        return {
            "total_sales": round(total_sales, 2),
            "vat_collected": round(total_vat, 2),
            "order_count": count,
            "avg_order_value": round(avg, 2),
        }
    finally:
        db.close()


def get_top_items(period: str = "today", limit: int = 10) -> list[dict]:
    """Top-selling items by quantity."""
    start, end = _date_range(period)
    db = SessionLocal()
    try:
        rows = (
            db.query(
                OrderLine.item_name_ar,
                func.sum(OrderLine.quantity).label("total_qty"),
                func.sum(OrderLine.line_total).label("total_revenue"),
            )
            .join(Order, Order.id == OrderLine.order_id)
            .filter(
                Order.status == "settled",
                Order.closed_at.between(start, end),
                OrderLine.voided == 0,
            )
            .group_by(OrderLine.item_name_ar)
            .order_by(func.sum(OrderLine.quantity).desc())
            .limit(limit)
            .all()
        )
        return [
            {"name_ar": r[0], "qty": int(r[1]), "revenue": round(float(r[2]), 2)}
            for r in rows
        ]
    finally:
        db.close()


def get_sales_by_category(period: str = "today") -> list[dict]:
    """Sales breakdown by category."""
    start, end = _date_range(period)
    db = SessionLocal()
    try:
        rows = (
            db.query(
                Category.name_ar,
                func.sum(OrderLine.quantity).label("qty"),
                func.sum(OrderLine.line_total).label("revenue"),
            )
            .join(Item, Item.id == OrderLine.item_id)
            .join(Category, Category.id == Item.category_id)
            .join(Order, Order.id == OrderLine.order_id)
            .filter(
                Order.status == "settled",
                Order.closed_at.between(start, end),
                OrderLine.voided == 0,
            )
            .group_by(Category.name_ar)
            .order_by(func.sum(OrderLine.line_total).desc())
            .all()
        )
        return [
            {"name_ar": r[0], "qty": int(r[1]), "revenue": round(float(r[2]), 2)}
            for r in rows
        ]
    finally:
        db.close()


def get_sales_by_hour(period: str = "today") -> list[dict]:
    """Sales by hour of day."""
    start, end = _date_range(period)
    db = SessionLocal()
    try:
        rows = (
            db.query(
                func.strftime("%H", Order.closed_at).label("hour"),
                func.count(Order.id).label("count"),
                func.sum(Order.total).label("revenue"),
            )
            .filter(Order.status == "settled", Order.closed_at.between(start, end))
            .group_by(func.strftime("%H", Order.closed_at))
            .order_by("hour")
            .all()
        )
        return [
            {"hour": r[0], "count": int(r[1]), "revenue": round(float(r[2]), 2)}
            for r in rows
        ]
    finally:
        db.close()


def get_sales_by_cashier(period: str = "today") -> list[dict]:
    """Sales by cashier."""
    start, end = _date_range(period)
    db = SessionLocal()
    try:
        rows = (
            db.query(
                Order.cashier,
                func.count(Order.id).label("count"),
                func.sum(Order.total).label("revenue"),
            )
            .filter(Order.status == "settled", Order.closed_at.between(start, end))
            .group_by(Order.cashier)
            .order_by(func.sum(Order.total).desc())
            .all()
        )
        return [
            {"cashier": r[0] or "—", "count": int(r[1]), "revenue": round(float(r[2]), 2)}
            for r in rows
        ]
    finally:
        db.close()


def generate_csv(period: str = "today") -> str:
    """Generate CSV report string."""
    start, end = _date_range(period)
    db = SessionLocal()
    try:
        orders = (
            db.query(Order)
            .filter(Order.status == "settled", Order.closed_at.between(start, end))
            .order_by(Order.closed_at)
            .all()
        )
        lines = ["Order Number,Date,Cashier,Subtotal,VAT,Total,Payment Method"]
        for o in orders:
            dt = o.closed_at.strftime("%Y-%m-%d %H:%M") if o.closed_at else ""
            lines.append(
                f"{o.order_number},{dt},{o.cashier or ''},"
                f"{o.subtotal:.2f},{o.vat_amount:.2f},{o.total:.2f},{o.payment_method or ''}"
            )
        return "\n".join(lines)
    finally:
        db.close()
