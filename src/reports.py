# -*- coding: utf-8 -*-
"""Reports + analytics calculations. All queries hit SQLite only."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, case

from src.database import SessionLocal
from src.models import Area, Category, FloorTable, Item, Order, OrderLine, Shift


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
    elif period == "last_month":
        # First day of last month to last day of last month
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        first_prev = last_prev.replace(day=1)
        return datetime(first_prev.year, first_prev.month, first_prev.day), \
               datetime(last_prev.year, last_prev.month, last_prev.day, 23, 59, 59)
    elif period == "last_week":
        # Monday-Sunday of last week
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        return datetime(start.year, start.month, start.day), \
               datetime(end.year, end.month, end.day, 23, 59, 59)
    else:  # today
        return datetime(today.year, today.month, today.day), datetime.now()


def get_summary(period: str = "today") -> dict:
    """Get sales summary for a period — VAT-inclusive prices.

    Returns:
      total_with_vat / total_sales: customer-paid total (VAT included)
      subtotal_no_vat: total minus VAT (the "net" sales)
      vat_collected: VAT portion of the sales
      cash_total / card_total: how much of total_with_vat came from each method
      order_count, avg_order_value
    """
    start, end = _date_range(period)
    db = SessionLocal()
    try:
        orders = (
            db.query(Order)
            .filter(Order.status == "settled", Order.created_at.between(start, end))
            .all()
        )
        total_sales = sum(o.total or 0 for o in orders)
        total_vat = sum(o.vat_amount or 0 for o in orders)
        subtotal = sum(o.subtotal or 0 for o in orders)
        cash_total = sum(o.total or 0 for o in orders if (o.payment_method or "").lower() == "cash")
        card_total = sum(o.total or 0 for o in orders if (o.payment_method or "").lower() == "card")
        count = len(orders)
        avg = total_sales / count if count else 0

        return {
            "total_sales": round(total_sales, 2),
            "total_with_vat": round(total_sales, 2),
            "subtotal_no_vat": round(subtotal, 2),
            "vat_collected": round(total_vat, 2),
            "cash_total": round(cash_total, 2),
            "card_total": round(card_total, 2),
            "order_count": count,
            "avg_order_value": round(avg, 2),
        }
    finally:
        db.close()


def get_open_tables_summary(period: str = "today") -> dict:
    """Count and total-due of currently OPEN (unpaid) tables.

    An open table is one with an order in status 'open' or 'sent'. The
    period filter is applied against the order's created_at, so the
    caller can ask "how many tables opened today are still unpaid?".

    Returns:
      count: number of open tables in the period
      total_due: sum of their current order totals (VAT-inclusive)
      tables: list of dicts with table label, total, order_number, opened
    """
    start, end = _date_range(period)
    db = SessionLocal()
    try:
        orders = (
            db.query(Order)
            .filter(
                Order.status.in_(("open", "sent")),
                Order.created_at.between(start, end),
            )
            .all()
        )
        total = 0.0
        details = []
        for o in orders:
            total += o.total or 0
            table_label = ""
            area_name = ""
            if o.table_id:
                ft = db.get(FloorTable, o.table_id)
                if ft:
                    table_label = str(ft.number)
                    area = db.get(Area, ft.area_id)
                    area_name = area.name_ar if area else ""
            details.append({
                "table_label": table_label,
                "area_name": area_name,
                "order_number": o.order_number,
                "total": round(o.total or 0, 2),
                "opened": o.created_at.strftime("%d/%m %H:%M") if o.created_at else "",
            })
        return {
            "count": len(details),
            "total_due": round(total, 2),
            "tables": details,
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
                Order.created_at.between(start, end),
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
                Order.created_at.between(start, end),
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
                func.strftime("%H", Order.created_at).label("hour"),
                func.count(Order.id).label("count"),
                func.sum(Order.total).label("revenue"),
            )
            .filter(Order.status == "settled", Order.created_at.between(start, end))
            .group_by(func.strftime("%H", Order.created_at))
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
            .filter(Order.status == "settled", Order.created_at.between(start, end))
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


def get_payment_breakdown(period: str = "today") -> dict:
    """Cash vs card vs credit breakdown."""
    start, end = _date_range(period)
    db = SessionLocal()
    try:
        orders = (
            db.query(Order)
            .filter(Order.status == "settled", Order.created_at.between(start, end))
            .all()
        )
        cash = sum(o.total for o in orders if o.payment_method == "cash")
        card = sum(o.total for o in orders if o.payment_method == "card")
        return {
            "cash": round(cash, 2),
            "card": round(card, 2),
            "cash_count": sum(1 for o in orders if o.payment_method == "cash"),
            "card_count": sum(1 for o in orders if o.payment_method == "card"),
        }
    finally:
        db.close()


def get_avg_items_per_order(period: str = "today") -> float:
    start, end = _date_range(period)
    db = SessionLocal()
    try:
        orders = (
            db.query(Order)
            .filter(Order.status == "settled", Order.created_at.between(start, end))
            .all()
        )
        if not orders:
            return 0
        total_items = 0
        for o in orders:
            total_items += sum(l.quantity for l in o.lines if not l.voided)
        return round(total_items / len(orders), 1)
    finally:
        db.close()


def get_peak_hour(period: str = "today") -> dict | None:
    by_hour = get_sales_by_hour(period)
    if not by_hour:
        return None
    peak = max(by_hour, key=lambda h: h["revenue"])
    slowest = min(by_hour, key=lambda h: h["revenue"])
    return {"peak": peak, "slowest": slowest}


def get_credit_summary() -> dict:
    """Total unpaid credit across all credit-area tables."""
    db = SessionLocal()
    try:
        credit_area = db.query(Area).filter(Area.is_credit == True).first()
        if not credit_area:
            return {"total": 0, "count": 0, "tables": []}
        tables = (
            db.query(FloorTable)
            .filter(FloorTable.area_id == credit_area.id, FloorTable.status == "occupied")
            .all()
        )
        total = 0
        details = []
        for t in tables:
            if t.current_order_id:
                o = db.get(Order, t.current_order_id)
                if o and o.status in ("open", "sent"):
                    total += o.total or 0
                    details.append({
                        "label": t.label_ar,
                        "total": round(o.total or 0, 2),
                        "order_number": o.order_number,
                        "created": o.created_at.strftime("%d/%m %H:%M") if o.created_at else "",
                    })
        return {"total": round(total, 2), "count": len(details), "tables": details}
    finally:
        db.close()


def get_daily_trend(days: int = 7) -> list[dict]:
    """Revenue per day for the last N days."""
    db = SessionLocal()
    try:
        result = []
        today = date.today()
        for i in range(days - 1, -1, -1):
            d = today - timedelta(days=i)
            start = datetime(d.year, d.month, d.day)
            end = datetime(d.year, d.month, d.day, 23, 59, 59)
            orders = (
                db.query(Order)
                .filter(Order.status == "settled", Order.created_at.between(start, end))
                .all()
            )
            revenue = sum(o.total for o in orders)
            result.append({
                "date": d.strftime("%d/%m"),
                "day_name": d.strftime("%A"),
                "revenue": round(revenue, 2),
                "orders": len(orders),
            })
        return result
    finally:
        db.close()


def get_current_shift_stats() -> dict | None:
    """Live stats for the currently open shift."""
    db = SessionLocal()
    try:
        shift = db.query(Shift).filter(Shift.status == "open").order_by(Shift.opened_at.desc()).first()
        if not shift:
            return None
        orders = db.query(Order).filter(Order.shift_id == shift.id, Order.status == "settled").all()
        return {
            "shift_id": shift.id,
            "opened_at": shift.opened_at.strftime("%d/%m/%Y %I:%M %p"),
            "total_sales": round(sum(o.total for o in orders), 2),
            "total_vat": round(sum(o.vat_amount for o in orders), 2),
            "order_count": len(orders),
            "opening_cash": shift.opening_cash,
        }
    finally:
        db.close()


def get_table_orders_history(period: str = "today") -> list[dict]:
    """All settled orders with their table info, for the orders log."""
    start, end = _date_range(period)
    db = SessionLocal()
    try:
        orders = (
            db.query(Order)
            .filter(Order.status == "settled", Order.created_at.between(start, end))
            .order_by(Order.created_at.desc())
            .all()
        )
        return _build_orders_list(db, orders)
    finally:
        db.close()


def get_all_orders_sheet(period: str = "today") -> list[dict]:
    """All orders (open, sent, settled, voided) for the sheet view.

    Default: from the last open shift time until now (or from start of day).
    Also supports standard periods.
    """
    from datetime import datetime
    start, end = _date_range(period)
    db = SessionLocal()
    try:
        orders = (
            db.query(Order)
            .filter(Order.created_at.between(start, end))
            .order_by(Order.created_at.desc())
            .all()
        )
        return _build_orders_list(db, orders, include_status=True)
    finally:
        db.close()


def _build_orders_list(db, orders, include_status: bool = False) -> list[dict]:
    """Shared helper to build order list dicts."""
    from datetime import datetime
    result = []
    for o in orders:
        table_label = ""
        area_name = ""
        if o.table_id:
            ft = db.get(FloorTable, o.table_id)
            if ft:
                table_label = str(ft.number)
                area = db.get(Area, ft.area_id)
                area_name = area.name_ar if area else ""

        items = [
            {"name_ar": l.item_name_ar, "qty": l.quantity,
             "unit_price": l.unit_price_inclusive, "total": l.line_total}
            for l in o.lines if not l.voided
        ]
        duration = ""
        if o.created_at and o.closed_at:
            diff = int((o.closed_at - o.created_at).total_seconds())
            h, m = divmod(diff // 60, 60)
            duration = f"{h}:{m:02d}"
        elif o.created_at:
            diff = int((datetime.now() - o.created_at).total_seconds())
            h, m = divmod(diff // 60, 60)
            duration = f"{h}:{m:02d}"

        entry = {
            "id": o.id,
            "order_number": o.order_number,
            "table_label": table_label,
            "area_name": area_name,
            "cashier": o.cashier or "",
            "created_at": o.created_at.strftime("%H:%M") if o.created_at else "",
            "created_date": o.created_at.strftime("%d/%m/%Y") if o.created_at else "",
            "closed_at": o.closed_at.strftime("%H:%M") if o.closed_at else "",
            "duration": duration,
            "subtotal": o.subtotal or 0,
            "vat": o.vat_amount or 0,
            "total": o.total or 0,
            "method": o.payment_method or "",
            "cash_received": o.cash_received or 0,
            "change": o.change_due or 0,
            "items": items,
            "item_count": sum(l.quantity for l in o.lines if not l.voided),
        }
        if include_status:
            entry["status"] = o.status
        result.append(entry)
    return result


def generate_orders_csv(period: str = "today") -> str:
    """Generate detailed CSV of all orders for export."""
    orders = get_all_orders_sheet(period)
    lines = ["Order Number,Date,Table,Area,Cashier,Status,Open,Close,Duration,Subtotal,VAT,Total,Payment,Items"]
    for o in orders:
        items_str = "; ".join(f"{i['name_ar']} x{i['qty']}" for i in o["items"])
        lines.append(
            f"{o['order_number']},{o['created_date']},"
            f"{o['table_label']},{o['area_name']},{o['cashier']},"
            f"{o.get('status', 'settled')},{o['created_at']},{o['closed_at']},"
            f"{o['duration']},{o['subtotal']:.2f},{o['vat']:.2f},{o['total']:.2f},"
            f"{o['method']},{items_str}"
        )
    return "\n".join(lines)


def generate_csv(period: str = "today") -> str:
    """Generate CSV report string."""
    start, end = _date_range(period)
    db = SessionLocal()
    try:
        orders = (
            db.query(Order)
            .filter(Order.status == "settled", Order.created_at.between(start, end))
            .order_by(Order.created_at)
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
