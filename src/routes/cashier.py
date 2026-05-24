# -*- coding: utf-8 -*-
"""Cashier routes — full POS screen with HTMX-driven order management."""
from __future__ import annotations

from datetime import datetime, date

from flask import Blueprint, abort, jsonify, render_template, request, session
from werkzeug.security import check_password_hash

from src.database import get_session
from src.models import Category, Item, Order, OrderLine, User

bp = Blueprint("cashier", __name__)


def _current_order_number() -> str:
    today_str = date.today().strftime("%d/%m/%Y")
    db = get_session()
    try:
        count = (
            db.query(Order)
            .filter(Order.order_number.like(f"{today_str}-%"))
            .count()
        )
        return f"{today_str}-{count + 1:04d}"
    finally:
        db.close()


def _get_or_create_order(db) -> Order:
    """Get the active open order or create a new one.

    If a pending_table_id is in the session (from the tables view), the new
    order is linked to that table and the table is marked occupied.  This
    ensures tables stay 'free' until the first item is actually added.
    """
    from src.models import FloorTable

    order_id = session.get("current_order_id")
    order = None
    if order_id:
        order = db.get(Order, order_id)
        if order and order.status not in ("open", "sent"):
            order = None
    if order is None:
        table_id = session.pop("pending_table_id", None)

        # Link to current open shift if one exists
        from src.models import Shift
        shift = db.query(Shift).filter(Shift.status == "open").order_by(Shift.opened_at.desc()).first()

        order = Order(
            order_number=_current_order_number(),
            status="open",
            table_id=table_id,
            shift_id=shift.id if shift else None,
            cashier=session.get("username", "admin"),
        )
        db.add(order)
        db.flush()
        session["current_order_id"] = order.id

        # Mark the table as occupied now that items will be added
        if table_id:
            table = db.get(FloorTable, table_id)
            if table:
                table.current_order_id = order.id
                table.status = "occupied"
    return order


VAT_RATE = 0.05


def _apply_vat(base: float):
    """Add VAT on top of the item prices.

    The displayed item prices are kept as-is (subtotal), then 5% VAT is
    added to produce the total — i.e. the customer pays 5% more than the
    sticker price. Returns (subtotal, vat_amount, total).
    """
    subtotal = round(base, 2)
    vat = round(base * VAT_RATE, 2)
    total = round(subtotal + vat, 2)
    return subtotal, vat, total


def _calc_totals(order: Order) -> None:
    """Recalculate order totals — 5% VAT added on top of item prices."""
    base = sum(l.line_total for l in order.lines if not l.voided)
    order.subtotal, order.vat_amount, order.total = _apply_vat(base)


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

        # Auto-pay flag from split partial pay flow
        auto_pay = session.pop("auto_pay", False)

        return render_template(
            "cashier.html",
            categories=categories,
            items=items,
            active_cat_id=active_cat_id,
            order=order_data,
            auto_pay=auto_pay,
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
                item_name_en=item.name_en,
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
    """HTMX: increment, decrement, or void a line.

    Void/dec require admin PIN for non-admin users.
    Admin PIN is passed via X-Admin-Pin header from the modal.
    """
    db = get_session()
    try:
        line = db.get(OrderLine, line_id)
        if not line:
            abort(404)
        order = db.get(Order, line.order_id)

        if action == "inc":
            line.quantity += 1
            line.line_total = round(line.quantity * line.unit_price_inclusive, 2)
        elif action in ("dec", "void"):
            # Admin can do it directly; others need admin PIN
            is_admin = session.get("role") == "admin"
            if not is_admin:
                admin_pin = request.headers.get("X-Admin-Pin", "")
                if not admin_pin or not _verify_admin_pin(db, admin_pin):
                    order_data = _get_order_view_data(db, order)
                    return render_template("partials/order_panel.html", order=order_data)

            if action == "dec":
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


def _verify_admin_pin(db, pin: str) -> bool:
    """Check if the given PIN belongs to any active admin user."""
    admins = db.query(User).filter(User.role == "admin", User.active == True).all()
    for admin in admins:
        if check_password_hash(admin.pin_hash, pin):
            return True
    return False


@bp.post("/order/edit-price/<int:line_id>")
def edit_line_price(line_id: int):
    """HTMX: edit the price of ONE unit on a single order line.

    Per-occurrence pricing: if the line has qty > 1, one unit is split off
    into a new line at the new price; the original line keeps the original
    price with quantity decremented by 1. If qty == 1 the price is updated
    in place.

    Admins can do this directly; non-admin users must pass a valid admin
    PIN via the X-Admin-Pin header (set by the price-edit overlay).
    """
    db = get_session()
    try:
        line = db.get(OrderLine, line_id)
        if not line:
            abort(404)
        order = db.get(Order, line.order_id)

        is_admin = session.get("role") == "admin"
        if not is_admin:
            admin_pin = request.headers.get("X-Admin-Pin", "")
            if not admin_pin or not _verify_admin_pin(db, admin_pin):
                # Return 403 so the modal can show "wrong PIN" feedback
                abort(403)

        new_price = request.form.get("price", type=float)
        if new_price is None or new_price < 0:
            abort(400)
        new_price = round(new_price, 2)

        # No-op if the price didn't actually change.
        if abs(new_price - (line.unit_price_inclusive or 0)) < 0.005:
            order_data = _get_order_view_data(db, order)
            return render_template("partials/order_panel.html", order=order_data)

        if line.quantity > 1:
            # Split off one unit into a new line at the new price.
            new_line = OrderLine(
                order_id=line.order_id,
                item_id=line.item_id,
                item_name_ar=line.item_name_ar,
                item_name_en=line.item_name_en,
                quantity=1,
                unit_price_inclusive=new_price,
                line_total=new_price,
                voided=0,
                sent_to_kitchen=line.sent_to_kitchen,
            )
            db.add(new_line)
            line.quantity -= 1
            line.line_total = round(line.quantity * line.unit_price_inclusive, 2)
        else:
            line.unit_price_inclusive = new_price
            line.line_total = new_price

        _calc_totals(order)
        db.commit()
        order_data = _get_order_view_data(db, order)
        return render_template("partials/order_panel.html", order=order_data)
    finally:
        db.close()


@bp.post("/order/line-note/<int:line_id>")
def set_line_note(line_id: int):
    """HTMX: save a per-item note. Returns 204 so the input keeps focus."""
    db = get_session()
    try:
        line = db.get(OrderLine, line_id)
        if not line:
            return "", 404
        note = (request.form.get("note") or "").strip()
        line.note = note or None
        db.commit()
        return "", 204
    finally:
        db.close()


@bp.post("/order/note")
def set_order_note():
    """HTMX: save a note for the whole order/table. Returns 204."""
    db = get_session()
    try:
        order_id = session.get("current_order_id")
        order = db.get(Order, order_id) if order_id else None
        if order is None:
            return "", 204  # no active order yet — nothing to attach to
        note = (request.form.get("note") or "").strip()
        order.notes = note or None
        db.commit()
        return "", 204
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

        # Route each unsent line to its station and print one ticket per
        # station on its own printer (kitchen -> Bar, shisha -> Shisha).
        # Beverages ("none") never go to a prep station.
        try:
            from src.kitchen_ticket import line_station
            from src.printer import print_kitchen_ticket, print_shisha_ticket
            kitchen_ids, shisha_ids = [], []
            for l in unsent:
                station = line_station(db, l)
                if station == "shisha":
                    shisha_ids.append(l.id)
                elif station == "kitchen":
                    kitchen_ids.append(l.id)
            if kitchen_ids:
                print_kitchen_ticket(order.id, kitchen_ids)
            if shisha_ids:
                print_shisha_ticket(order.id, shisha_ids)
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
        order.closed_at = datetime.now()

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
        # No active order yet — but if a table was opened (pending_table_id),
        # still surface its label so the cashier knows which table they're on
        # before the first item is added.
        pending_id = session.get("pending_table_id")
        table_info = None
        if pending_id:
            from src.models import FloorTable, Area
            ft = db.get(FloorTable, pending_id)
            if ft:
                area = db.get(Area, ft.area_id)
                table_info = {
                    "table_id": ft.id,
                    "number": ft.number,
                    "area_name": area.name_ar if area else "",
                }
        return {
            "id": None,
            "order_number": "",
            "lines": [],
            "subtotal": 0,
            "vat_amount": 0,
            "total": 0,
            "status": "open",
            "table_id": pending_id,
            "table_info": table_info,
            "move_targets": [],
            "opened_at": None,
            "note": "",
        }
    lines = [
        {
            "id": l.id,
            "name_ar": l.item_name_ar,
            "qty": l.quantity,
            "unit_price": l.unit_price_inclusive,
            "line_total": l.line_total,
            "sent": l.sent_to_kitchen,
            "note": l.note or "",
        }
        for l in order.lines if not l.voided
    ]
    # Gather table info + areas for move dropdown
    table_info = None
    move_areas = []
    if order.table_id:
        from src.models import FloorTable, Area
        ft = db.get(FloorTable, order.table_id)
        if ft:
            area = db.get(Area, ft.area_id)
            table_info = {
                "table_id": ft.id,
                "number": ft.number,
                "area_name": area.name_ar if area else "",
            }
            # Free tables in other areas for the move dropdown
            free = (
                db.query(FloorTable, Area)
                .join(Area, Area.id == FloorTable.area_id)
                .filter(FloorTable.status == "free", FloorTable.visible == True,
                        FloorTable.id != ft.id)
                .order_by(Area.sort_order, FloorTable.number)
                .limit(50)
                .all()
            )
            move_areas = [
                {"table_id": t.id, "label": f"{a.name_ar} - {t.number}"}
                for t, a in free
            ]

    return {
        "id": order.id,
        "order_number": order.order_number,
        "lines": lines,
        "subtotal": order.subtotal or 0,
        "vat_amount": order.vat_amount or 0,
        "total": order.total or 0,
        "status": order.status,
        "table_id": order.table_id,
        "table_info": table_info,
        "move_targets": move_areas,
        "opened_at": order.created_at.isoformat() if order.created_at else None,
        "note": order.notes or "",
    }
