# -*- coding: utf-8 -*-
"""Cashier routes — full POS screen with HTMX-driven order management."""
from __future__ import annotations

from datetime import datetime, date

from flask import Blueprint, abort, render_template, request, session

from src.database import get_session
from src.models import Category, Item, Order, OrderLine

bp = Blueprint("cashier", __name__)


def _current_order_number() -> str:
    today = date.today().isoformat()
    db = get_session()
    try:
        count = (
            db.query(Order)
            .filter(Order.order_number.like(f"{today}-%"))
            .count()
        )
        return f"{today}-{count + 1:04d}"
    finally:
        db.close()


def _get_or_create_order(db) -> Order:
    """Get the active open order or create a new one."""
    order_id = session.get("current_order_id")
    order = None
    if order_id:
        order = db.get(Order, order_id)
        if order and order.status not in ("open", "sent"):
            order = None
    if order is None:
        order = Order(
            order_number=_current_order_number(),
            status="open",
            cashier=session.get("username", "admin"),
        )
        db.add(order)
        db.flush()
        session["current_order_id"] = order.id
    return order


def _calc_totals(order: Order) -> None:
    """Recalculate totals from active lines. VAT-inclusive model."""
    total = sum(
        l.line_total for l in order.lines if not l.voided
    )
    order.total = round(total, 2)
    order.subtotal = round(total / 1.05, 2)
    order.vat_amount = round(order.total - order.subtotal, 2)


@bp.get("/")
def index():
    db = get_session()
    try:
        cats = (
            db.query(Category)
            .filter(Category.visible == 1)
            .order_by(Category.sort_order.asc())
            .all()
        )
        categories = [{"id": c.id, "name_ar": c.name_ar, "color": c.color} for c in cats]

        # Load first category's items by default
        first_cat = cats[0] if cats else None
        items = []
        active_cat_id = None
        if first_cat:
            active_cat_id = first_cat.id
            items = [
                {"id": i.id, "name_ar": i.name_ar, "price": i.price_inclusive}
                for i in db.query(Item)
                .filter(Item.category_id == first_cat.id, Item.visible == 1)
                .order_by(Item.sort_order.asc(), Item.name_ar.asc())
                .all()
            ]

        # Load current order
        order_data = _get_order_view_data(db)

        return render_template(
            "cashier.html",
            categories=categories,
            items=items,
            active_cat_id=active_cat_id,
            order=order_data,
        )
    finally:
        db.close()


@bp.get("/items/<int:cat_id>")
def get_items(cat_id: int):
    """HTMX: return items grid for a category."""
    db = get_session()
    try:
        cat = db.get(Category, cat_id)
        if not cat:
            abort(404)
        items = [
            {"id": i.id, "name_ar": i.name_ar, "price": i.price_inclusive}
            for i in db.query(Item)
            .filter(Item.category_id == cat_id, Item.visible == 1)
            .order_by(Item.sort_order.asc(), Item.name_ar.asc())
            .all()
        ]
        return render_template("partials/items_grid.html", items=items)
    finally:
        db.close()


@bp.post("/order/add/<int:item_id>")
def add_to_order(item_id: int):
    """HTMX: add item to current order or increment qty."""
    db = get_session()
    try:
        item = db.get(Item, item_id)
        if not item:
            abort(404)
        order = _get_or_create_order(db)

        # Check if item already in order (not voided)
        existing = next(
            (l for l in order.lines if l.item_id == item_id and not l.voided),
            None,
        )
        if existing:
            existing.quantity += 1
            existing.line_total = round(existing.quantity * existing.unit_price_inclusive, 2)
        else:
            line = OrderLine(
                order_id=order.id,
                item_id=item.id,
                item_name_ar=item.name_ar,
                quantity=1,
                unit_price_inclusive=item.price_inclusive,
                line_total=item.price_inclusive,
            )
            db.add(line)

        _calc_totals(order)
        db.commit()
        order_data = _get_order_view_data(db, order)
        return render_template("partials/order_panel.html", order=order_data)
    finally:
        db.close()


@bp.post("/order/qty/<int:line_id>/<action>")
def adjust_qty(line_id: int, action: str):
    """HTMX: increment, decrement, or void a line."""
    db = get_session()
    try:
        line = db.get(OrderLine, line_id)
        if not line:
            abort(404)
        order = db.get(Order, line.order_id)

        if action == "inc":
            line.quantity += 1
            line.line_total = round(line.quantity * line.unit_price_inclusive, 2)
        elif action == "dec":
            if line.quantity > 1:
                line.quantity -= 1
                line.line_total = round(line.quantity * line.unit_price_inclusive, 2)
            else:
                line.voided = 1
        elif action == "void":
            line.voided = 1

        _calc_totals(order)
        db.commit()
        order_data = _get_order_view_data(db, order)
        return render_template("partials/order_panel.html", order=order_data)
    finally:
        db.close()


@bp.post("/order/send")
def send_to_kitchen():
    """Mark unsent lines as sent + trigger kitchen print (Phase 3)."""
    db = get_session()
    try:
        order = _get_or_create_order(db)
        unsent = [l for l in order.lines if not l.voided and not l.sent_to_kitchen]

        if not unsent:
            order_data = _get_order_view_data(db, order)
            return render_template("partials/order_panel.html", order=order_data)

        for line in unsent:
            line.sent_to_kitchen = 1
        order.status = "sent"
        db.commit()

        # Phase 3: trigger kitchen ticket print
        try:
            from src.printer import print_kitchen_ticket
            print_kitchen_ticket(order.id, [l.id for l in unsent])
        except Exception:
            pass  # Print failures handled by print queue

        order_data = _get_order_view_data(db, order)
        return render_template("partials/order_panel.html", order=order_data)
    finally:
        db.close()


@bp.post("/order/pay")
def pay_order():
    """Show payment modal."""
    db = get_session()
    try:
        order = _get_or_create_order(db)
        _calc_totals(order)
        db.commit()
        return render_template("partials/payment_modal.html", order={
            "id": order.id,
            "total": order.total,
            "subtotal": order.subtotal,
            "vat_amount": order.vat_amount,
        })
    finally:
        db.close()


@bp.post("/order/settle")
def settle_order():
    """Complete payment, print receipt, kick drawer."""
    db = get_session()
    try:
        order_id = session.get("current_order_id")
        if not order_id:
            return "", 400
        order = db.get(Order, order_id)
        if not order:
            return "", 400

        method = request.form.get("method", "cash")
        cash_received = float(request.form.get("cash_received", 0))

        _calc_totals(order)
        order.payment_method = method
        if method == "cash":
            order.cash_received = cash_received
            order.change_due = round(cash_received - order.total, 2)
        else:
            order.cash_received = order.total
            order.change_due = 0
        order.status = "settled"
        order.closed_at = datetime.utcnow()

        # Mark any remaining unsent lines as sent
        for line in order.lines:
            if not line.voided and not line.sent_to_kitchen:
                line.sent_to_kitchen = 1

        db.commit()

        # Phase 3: print receipt + kick drawer
        try:
            from src.printer import print_receipt_and_kick
            print_receipt_and_kick(order.id)
        except Exception:
            pass  # Print failures handled by print queue

        # Clear current order
        session.pop("current_order_id", None)

        # Return success + new empty order panel
        order_data = _get_order_view_data(db)
        return render_template("partials/payment_success.html",
                               change=order.change_due if method == "cash" else 0,
                               order=order_data)
    finally:
        db.close()


@bp.post("/order/hold")
def hold_order():
    """Hold (park) current order and start fresh."""
    db = get_session()
    try:
        order_id = session.get("current_order_id")
        if order_id:
            order = db.get(Order, order_id)
            if order and order.status in ("open", "sent"):
                order.status = "open"  # keep as open but clear from session
                db.commit()
        session.pop("current_order_id", None)
        order_data = _get_order_view_data(db)
        return render_template("partials/order_panel.html", order=order_data)
    finally:
        db.close()


@bp.get("/order/held")
def held_orders():
    """HTMX: list held/open orders for resumption."""
    db = get_session()
    try:
        orders = (
            db.query(Order)
            .filter(Order.status.in_(["open", "sent"]))
            .filter(Order.id != session.get("current_order_id"))
            .order_by(Order.created_at.desc())
            .all()
        )
        held = []
        for o in orders:
            active_lines = [l for l in o.lines if not l.voided]
            if active_lines:
                held.append({
                    "id": o.id,
                    "order_number": o.order_number,
                    "total": o.total,
                    "line_count": len(active_lines),
                    "created_at": o.created_at,
                })
        return render_template("partials/held_orders.html", held=held)
    finally:
        db.close()


@bp.post("/order/resume/<int:order_id>")
def resume_order(order_id: int):
    """Resume a held order."""
    db = get_session()
    try:
        order = db.get(Order, order_id)
        if not order or order.status not in ("open", "sent"):
            abort(404)
        session["current_order_id"] = order.id
        order_data = _get_order_view_data(db, order)
        return render_template("partials/order_panel.html", order=order_data)
    finally:
        db.close()


@bp.post("/order/cancel")
def cancel_order():
    """Void entire current order."""
    db = get_session()
    try:
        order_id = session.get("current_order_id")
        if order_id:
            order = db.get(Order, order_id)
            if order and order.status in ("open", "sent"):
                order.status = "voided"
                for line in order.lines:
                    line.voided = 1
                db.commit()
        session.pop("current_order_id", None)
        order_data = _get_order_view_data(db)
        return render_template("partials/order_panel.html", order=order_data)
    finally:
        db.close()


def _get_order_view_data(db, order=None) -> dict:
    """Build the view dict for the order panel."""
    if order is None:
        order_id = session.get("current_order_id")
        if order_id:
            order = db.get(Order, order_id)
    if order is None or order.status not in ("open", "sent"):
        return {
            "id": None,
            "order_number": "",
            "lines": [],
            "subtotal": 0,
            "vat_amount": 0,
            "total": 0,
            "status": "open",
        }
    lines = [
        {
            "id": l.id,
            "name_ar": l.item_name_ar,
            "qty": l.quantity,
            "unit_price": l.unit_price_inclusive,
            "line_total": l.line_total,
            "sent": l.sent_to_kitchen,
        }
        for l in order.lines if not l.voided
    ]
    return {
        "id": order.id,
        "order_number": order.order_number,
        "lines": lines,
        "subtotal": order.subtotal or 0,
        "vat_amount": order.vat_amount or 0,
        "total": order.total or 0,
        "status": order.status,
    }
