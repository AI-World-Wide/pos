# -*- coding: utf-8 -*-
"""Floor plan / tables routes — area tabs, table grid, split, move, partial pay."""
from __future__ import annotations

from flask import Blueprint, abort, redirect, render_template, request, session, url_for
from sqlalchemy import func

from src.database import get_session
from src.models import Area, FloorTable, Order, OrderLine

bp = Blueprint("tables", __name__, url_prefix="/tables")


@bp.before_request
def _check_login():
    if not session.get("username"):
        return redirect(url_for("auth.login_page"))


@bp.get("/")
def floor_plan():
    db = get_session()
    try:
        areas = db.query(Area).filter(Area.visible == True).order_by(Area.sort_order).all()
        area_id = request.args.get("area", type=int)
        if not area_id and areas:
            area_id = areas[0].id

        current_area = db.get(Area, area_id) if area_id else None
        tables = []
        credit_stats = {"total": 0, "count": 0}

        if current_area:
            floor_tables = (
                db.query(FloorTable)
                .filter(FloorTable.area_id == area_id, FloorTable.visible == True)
                .order_by(FloorTable.number)
                .all()
            )
            for t in floor_tables:
                order = None
                order_total = 0
                if t.current_order_id:
                    order = db.get(Order, t.current_order_id)
                    if order and order.status in ("open", "sent"):
                        order_total = order.total or 0
                    else:
                        t.current_order_id = None
                        t.status = "free"
                        db.commit()
                        order = None

                tables.append({
                    "id": t.id,
                    "number": t.number,
                    "label_ar": t.label_ar,
                    "capacity": t.capacity,
                    "status": t.status,
                    "order_id": t.current_order_id,
                    "order_total": order_total,
                    "order_number": order.order_number if order else None,
                    "opened_at": order.created_at.isoformat() if order and order.created_at else None,
                })

        # Credit area stats
        credit_area = db.query(Area).filter(Area.is_credit == True).first()
        if credit_area:
            credit_tables_q = (
                db.query(FloorTable)
                .filter(FloorTable.area_id == credit_area.id, FloorTable.status == "occupied")
                .all()
            )
            for ct in credit_tables_q:
                if ct.current_order_id:
                    o = db.get(Order, ct.current_order_id)
                    if o and o.status in ("open", "sent"):
                        credit_stats["total"] += o.total or 0
                        credit_stats["count"] += 1

        return render_template("tables.html",
                               areas=[{"id": a.id, "name_ar": a.name_ar, "is_credit": a.is_credit} for a in areas],
                               current_area={"id": current_area.id, "name_ar": current_area.name_ar,
                                             "is_credit": current_area.is_credit} if current_area else None,
                               tables=tables,
                               credit_stats=credit_stats,
                               all_areas=[{"id": a.id, "name_ar": a.name_ar} for a in areas])
    finally:
        db.close()


@bp.get("/open/<int:table_id>")
@bp.post("/open/<int:table_id>")
def open_table(table_id: int):
    """Enter a table's cashier view. Only creates an order when first item is added."""
    db = get_session()
    try:
        table = db.get(FloorTable, table_id)
        if not table:
            abort(404)

        if table.status == "occupied" and table.current_order_id:
            # Already has an order — resume it
            session["current_order_id"] = table.current_order_id
        else:
            # No order yet — store the table_id in session so the cashier
            # creates the order (and marks the table occupied) only when
            # the first item is actually added.
            session.pop("current_order_id", None)
            session["pending_table_id"] = table.id

        return redirect(url_for("cashier.index"))
    finally:
        db.close()


@bp.post("/move/<int:table_id>")
def move_table(table_id: int):
    """Move a table's order to a specific target table or an area."""
    db = get_session()
    try:
        table = db.get(FloorTable, table_id)
        if not table or not table.current_order_id:
            return redirect(url_for("tables.floor_plan"))

        order = db.get(Order, table.current_order_id)
        target_area_id = request.form.get("target_area_id", type=int)
        target_table_id = request.form.get("target_table_id", type=int)
        source_area = table.area_id

        def _transfer_to(target_ft):
            target_ft.current_order_id = table.current_order_id
            target_ft.status = "occupied"
            if order:
                order.table_id = target_ft.id
            table.current_order_id = None
            table.status = "free"

        if target_table_id:
            # Direct table-to-table transfer (drag-drop or dropdown)
            target = db.get(FloorTable, target_table_id)
            if target and target.status == "free":
                _transfer_to(target)
                db.commit()

        elif target_area_id:
            target_area = db.get(Area, target_area_id)
            if not target_area:
                return redirect(url_for("tables.floor_plan", area=source_area))

            if target_area.is_credit:
                # Credit area: create a dynamic table slot
                max_num = db.query(func.max(FloorTable.number)).filter(
                    FloorTable.area_id == target_area.id
                ).scalar() or 0
                new_table = FloorTable(
                    area_id=target_area.id,
                    number=max_num + 1,
                    label_ar=str(max_num + 1),
                    capacity=table.capacity,
                    status="free",
                    visible=True,
                )
                db.add(new_table)
                db.flush()
                _transfer_to(new_table)
                db.commit()
            else:
                # Non-credit area: find first free table in that area
                free_target = (
                    db.query(FloorTable)
                    .filter(FloorTable.area_id == target_area.id,
                            FloorTable.status == "free",
                            FloorTable.visible == True)
                    .order_by(FloorTable.number)
                    .first()
                )
                if free_target:
                    _transfer_to(free_target)
                    db.commit()

        return redirect(url_for("tables.floor_plan", area=source_area))
    finally:
        db.close()


@bp.get("/split/<int:table_id>")
def split_form(table_id: int):
    """Show split items form."""
    db = get_session()
    try:
        table = db.get(FloorTable, table_id)
        if not table or not table.current_order_id:
            return redirect(url_for("tables.floor_plan"))
        order = db.get(Order, table.current_order_id)
        if not order:
            return redirect(url_for("tables.floor_plan"))

        lines = [
            {"id": l.id, "name_ar": l.item_name_ar, "qty": l.quantity,
             "unit_price": l.unit_price_inclusive, "line_total": l.line_total}
            for l in order.lines if not l.voided
        ]
        # Get free tables for split target
        free_tables = (
            db.query(FloorTable)
            .filter(FloorTable.status == "free", FloorTable.visible == True, FloorTable.id != table_id)
            .order_by(FloorTable.area_id, FloorTable.number)
            .all()
        )
        targets = [{"id": ft.id, "label": ft.label_ar, "area": ft.area.name_ar} for ft in free_tables]

        return render_template("split_table.html",
                               table={"id": table.id, "label_ar": table.label_ar},
                               order={"id": order.id, "order_number": order.order_number},
                               lines=lines, targets=targets)
    finally:
        db.close()


def _parse_move_quantities(source_order_id, db):
    """Read how many units of each line to move from the submitted form.

    Supports per-quantity inputs named `qty_<line_id>` (new UI). Falls back
    to whole-line checkboxes named `line_ids` (= move the entire line).
    Returns a dict {line_id: units_to_move} clamped to each line's quantity.
    """
    lines = {l.id: l for l in db.query(OrderLine).filter(
        OrderLine.order_id == source_order_id, OrderLine.voided == 0
    ).all()}
    qty_map = {}
    for lid, line in lines.items():
        n = request.form.get(f"qty_{lid}", type=int)
        if n is None:
            # checkbox fallback
            if lid in request.form.getlist("line_ids", type=int):
                n = line.quantity
            else:
                n = 0
        n = max(0, min(n or 0, line.quantity))
        if n > 0:
            qty_map[lid] = n
    return qty_map


def _move_units(db, qty_map, dest_order_id):
    """Move `n` units of each source line into dest_order.

    Whole line -> reassigned. Partial -> source qty reduced and a new line
    of `n` units created on the destination, preserving item + price + names.
    """
    for lid, n in qty_map.items():
        line = db.get(OrderLine, lid)
        if not line or n <= 0:
            continue
        if n >= line.quantity:
            line.order_id = dest_order_id
        else:
            line.quantity -= n
            line.line_total = round(line.quantity * line.unit_price_inclusive, 2)
            db.add(OrderLine(
                order_id=dest_order_id,
                item_id=line.item_id,
                item_name_ar=line.item_name_ar,
                item_name_en=line.item_name_en,
                quantity=n,
                unit_price_inclusive=line.unit_price_inclusive,
                line_total=round(n * line.unit_price_inclusive, 2),
                voided=0,
                sent_to_kitchen=line.sent_to_kitchen,
                note=line.note,
            ))
    db.flush()


def _recalc_order(db, order):
    """Recompute an order's subtotal/VAT/total from its active lines."""
    from src.routes.cashier import _apply_vat
    base = db.query(OrderLine).filter(
        OrderLine.order_id == order.id, OrderLine.voided == 0
    ).all()
    total_base = sum(l.line_total for l in base)
    order.subtotal, order.vat_amount, order.total = _apply_vat(total_base)
    return len(base)


@bp.post("/split/<int:table_id>")
def split_execute(table_id: int):
    """Execute split: move chosen quantities to a target table, or to payment."""
    db = get_session()
    try:
        table = db.get(FloorTable, table_id)
        if not table or not table.current_order_id:
            return redirect(url_for("tables.floor_plan"))

        source_order = db.get(Order, table.current_order_id)
        target_table_id = request.form.get("target_table_id", type=int)
        action = request.form.get("action", "split")

        qty_map = _parse_move_quantities(source_order.id, db)
        if not qty_map:
            return redirect(url_for("tables.split_form", table_id=table_id))

        from src.routes.cashier import _current_order_number
        from src.models import Shift
        shift = db.query(Shift).filter(Shift.status == "open").order_by(Shift.opened_at.desc()).first()

        if action == "partial_pay":
            partial_order = Order(
                order_number=_current_order_number(),
                status="open",
                table_id=table.id,
                shift_id=shift.id if shift else None,
                cashier=session.get("username", "admin"),
            )
            db.add(partial_order)
            db.flush()

            _move_units(db, qty_map, partial_order.id)
            _recalc_order(db, partial_order)
            remaining = _recalc_order(db, source_order)
            if not remaining:
                source_order.status = "voided"
                table.current_order_id = None
                table.status = "free"
            db.commit()

            session["current_order_id"] = partial_order.id
            session["auto_pay"] = True
            return redirect(url_for("cashier.index"))

        # --- Split to another table ---
        if not target_table_id:
            return redirect(url_for("tables.split_form", table_id=table_id))
        target_table = db.get(FloorTable, target_table_id)
        if not target_table or target_table.status != "free":
            return redirect(url_for("tables.split_form", table_id=table_id))

        new_order = Order(
            order_number=_current_order_number(),
            status="open",
            table_id=target_table.id,
            shift_id=shift.id if shift else None,
            cashier=session.get("username", "admin"),
        )
        db.add(new_order)
        db.flush()

        _move_units(db, qty_map, new_order.id)
        _recalc_order(db, new_order)
        remaining = _recalc_order(db, source_order)

        target_table.current_order_id = new_order.id
        target_table.status = "occupied"
        if not remaining:
            source_order.status = "voided"
            table.current_order_id = None
            table.status = "free"

        db.commit()
        return redirect(url_for("tables.floor_plan", area=table.area_id))
    finally:
        db.close()


@bp.post("/close/<int:table_id>")
def close_table(table_id: int):
    """Free a table (mark order as voided if empty or already settled)."""
    db = get_session()
    try:
        table = db.get(FloorTable, table_id)
        if not table:
            abort(404)
        table.current_order_id = None
        table.status = "free"
        db.commit()
        return redirect(url_for("tables.floor_plan", area=table.area_id))
    finally:
        db.close()


# --- Admin: manage areas and tables ---

@bp.post("/areas/add")
def add_area():
    if session.get("role") != "admin":
        return redirect(url_for("tables.floor_plan"))
    db = get_session()
    try:
        name_ar = request.form.get("name_ar", "").strip()
        name_en = request.form.get("name_en", "").strip()
        if name_ar and name_en:
            max_sort = db.query(func.max(Area.sort_order)).scalar() or 0
            db.add(Area(name_ar=name_ar, name_en=name_en, sort_order=max_sort + 1))
            db.commit()
        return redirect(url_for("tables.floor_plan"))
    finally:
        db.close()


@bp.post("/add/<int:area_id>")
def add_table_to_area(area_id: int):
    if session.get("role") != "admin":
        return redirect(url_for("tables.floor_plan"))
    db = get_session()
    try:
        area = db.get(Area, area_id)
        if not area:
            abort(404)
        max_num = db.query(func.max(FloorTable.number)).filter(
            FloorTable.area_id == area_id
        ).scalar() or 0
        label = request.form.get("label_ar", "").strip()
        if not label:
            label = f"طاولة {max_num + 1}"
        db.add(FloorTable(
            area_id=area_id, number=max_num + 1,
            label_ar=label, capacity=4, status="free", visible=True,
        ))
        db.commit()
        return redirect(url_for("tables.floor_plan", area=area_id))
    finally:
        db.close()


@bp.post("/delete/<int:table_id>")
def delete_table(table_id: int):
    if session.get("role") != "admin":
        return redirect(url_for("tables.floor_plan"))
    db = get_session()
    try:
        t = db.get(FloorTable, table_id)
        if t and t.status == "free":
            db.delete(t)
            db.commit()
        return redirect(url_for("tables.floor_plan", area=t.area_id if t else None))
    finally:
        db.close()
