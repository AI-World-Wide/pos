# -*- coding: utf-8 -*-
"""Floor plan / tables routes — area tabs, table grid, split, move, partial pay."""
from __future__ import annotations

from datetime import datetime

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


@bp.post("/open/<int:table_id>")
def open_table(table_id: int):
    """Open a table — create new order and assign it."""
    db = get_session()
    try:
        table = db.get(FloorTable, table_id)
        if not table:
            abort(404)

        if table.status == "occupied" and table.current_order_id:
            # Already open — go to cashier for this order
            session["current_order_id"] = table.current_order_id
            return redirect(url_for("cashier.index"))

        # Create new order
        from src.routes.cashier import _current_order_number
        order = Order(
            order_number=_current_order_number(),
            status="open",
            table_id=table.id,
            cashier=session.get("username", "admin"),
        )
        db.add(order)
        db.flush()

        table.current_order_id = order.id
        table.status = "occupied"
        db.commit()

        session["current_order_id"] = order.id
        return redirect(url_for("cashier.index"))
    finally:
        db.close()


@bp.post("/move/<int:table_id>")
def move_table(table_id: int):
    """Move a table (its order) to a different area."""
    db = get_session()
    try:
        table = db.get(FloorTable, table_id)
        if not table or not table.current_order_id:
            return redirect(url_for("tables.floor_plan"))

        target_area_id = request.form.get("target_area_id", type=int)
        target_table_id = request.form.get("target_table_id", type=int)

        if target_table_id:
            # Move to a specific table
            target = db.get(FloorTable, target_table_id)
            if target and target.status == "free":
                target.current_order_id = table.current_order_id
                target.status = "occupied"
                # Update order's table_id
                order = db.get(Order, table.current_order_id)
                if order:
                    order.table_id = target.id
                table.current_order_id = None
                table.status = "free"
                db.commit()
        elif target_area_id:
            # Move to credit or another area — create a new table slot if needed
            target_area = db.get(Area, target_area_id)
            if target_area and target_area.is_credit:
                # For credit: create a dynamic table entry
                max_num = db.query(func.max(FloorTable.number)).filter(
                    FloorTable.area_id == target_area.id
                ).scalar() or 0
                new_table = FloorTable(
                    area_id=target_area.id,
                    number=max_num + 1,
                    label_ar=f"{table.label_ar} → آجل",
                    capacity=table.capacity,
                    status="occupied",
                    current_order_id=table.current_order_id,
                )
                db.add(new_table)
                db.flush()
                order = db.get(Order, table.current_order_id)
                if order:
                    order.table_id = new_table.id
                table.current_order_id = None
                table.status = "free"
                db.commit()

        return redirect(url_for("tables.floor_plan", area=table.area_id))
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


@bp.post("/split/<int:table_id>")
def split_execute(table_id: int):
    """Execute split: move selected lines to a new order on target table."""
    db = get_session()
    try:
        table = db.get(FloorTable, table_id)
        if not table or not table.current_order_id:
            return redirect(url_for("tables.floor_plan"))

        source_order = db.get(Order, table.current_order_id)
        target_table_id = request.form.get("target_table_id", type=int)
        line_ids = request.form.getlist("line_ids", type=int)
        action = request.form.get("action", "split")  # split or partial_pay

        if action == "partial_pay" and line_ids:
            # Pay for selected items only
            selected_total = sum(
                l.line_total for l in source_order.lines
                if l.id in line_ids and not l.voided
            )
            # Mark them as a separate settled micro-order
            from src.routes.cashier import _current_order_number, _calc_totals
            partial_order = Order(
                order_number=_current_order_number(),
                status="settled",
                table_id=table.id,
                cashier=session.get("username", "admin"),
                payment_method=request.form.get("method", "cash"),
                closed_at=datetime.utcnow(),
            )
            db.add(partial_order)
            db.flush()

            for l in source_order.lines:
                if l.id in line_ids and not l.voided:
                    l.order_id = partial_order.id
            _calc_totals(partial_order)
            partial_order.cash_received = partial_order.total
            partial_order.change_due = 0

            # Recalc source
            _calc_totals(source_order)
            # If source has no more active lines, free the table
            active = [l for l in source_order.lines if not l.voided]
            if not active:
                source_order.status = "voided"
                table.current_order_id = None
                table.status = "free"

            db.commit()
            return redirect(url_for("tables.floor_plan", area=table.area_id))

        if not target_table_id or not line_ids:
            return redirect(url_for("tables.split_form", table_id=table_id))

        target_table = db.get(FloorTable, target_table_id)
        if not target_table:
            return redirect(url_for("tables.floor_plan"))

        # Create new order for the target table
        from src.routes.cashier import _current_order_number, _calc_totals
        new_order = Order(
            order_number=_current_order_number(),
            status="open",
            table_id=target_table.id,
            cashier=session.get("username", "admin"),
        )
        db.add(new_order)
        db.flush()

        # Move selected lines to new order
        for l in source_order.lines:
            if l.id in line_ids and not l.voided:
                l.order_id = new_order.id

        _calc_totals(new_order)
        _calc_totals(source_order)

        target_table.current_order_id = new_order.id
        target_table.status = "occupied"

        # If source has no more active lines, free the source table
        active = [l for l in source_order.lines if not l.voided]
        if not active:
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
