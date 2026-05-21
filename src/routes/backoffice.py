# -*- coding: utf-8 -*-
"""Back office routes — item CRUD + XLSX re-import."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from src.database import get_session
from src.models import Category, Item

bp = Blueprint("backoffice", __name__, url_prefix="/admin")


@bp.before_request
def _check_admin():
    if session.get("role") != "admin":
        return redirect(url_for("auth.login_page"))


@bp.get("/items")
def items_list():
    db = get_session()
    try:
        cats = db.query(Category).order_by(Category.sort_order).all()
        cat_id = request.args.get("cat", type=int)
        q = db.query(Item).order_by(Item.category_id, Item.sort_order, Item.name_ar)
        if cat_id:
            q = q.filter(Item.category_id == cat_id)
        items = q.all()
        return render_template("items_admin.html",
                               items=items, categories=cats, active_cat=cat_id)
    finally:
        db.close()


@bp.get("/items/add")
def item_add_form():
    db = get_session()
    try:
        cats = db.query(Category).order_by(Category.sort_order).all()
        return render_template("item_form.html", item=None, categories=cats)
    finally:
        db.close()


@bp.post("/items/add")
def item_add():
    db = get_session()
    try:
        item = Item(
            name_ar=request.form["name_ar"].strip(),
            name_en=request.form.get("name_en", "").strip() or None,
            price_inclusive=float(request.form["price"]),
            category_id=int(request.form["category_id"]),
            kitchen_station=request.form.get("kitchen_station", ""),
            visible=1 if request.form.get("visible") else 0,
        )
        db.add(item)
        db.commit()
        return redirect(url_for("backoffice.items_list"))
    finally:
        db.close()


@bp.get("/items/<int:item_id>/edit")
def item_edit_form(item_id: int):
    db = get_session()
    try:
        item = db.get(Item, item_id)
        if not item:
            return redirect(url_for("backoffice.items_list"))
        cats = db.query(Category).order_by(Category.sort_order).all()
        return render_template("item_form.html", item=item, categories=cats)
    finally:
        db.close()


@bp.post("/items/<int:item_id>/edit")
def item_edit(item_id: int):
    db = get_session()
    try:
        item = db.get(Item, item_id)
        if not item:
            return redirect(url_for("backoffice.items_list"))
        item.name_ar = request.form["name_ar"].strip()
        item.name_en = request.form.get("name_en", "").strip() or None
        item.price_inclusive = float(request.form["price"])
        item.category_id = int(request.form["category_id"])
        item.kitchen_station = request.form.get("kitchen_station", "")
        item.visible = 1 if request.form.get("visible") else 0
        db.commit()
        return redirect(url_for("backoffice.items_list"))
    finally:
        db.close()


@bp.post("/items/<int:item_id>/delete")
def item_delete(item_id: int):
    db = get_session()
    try:
        item = db.get(Item, item_id)
        if item:
            db.delete(item)
            db.commit()
        return redirect(url_for("backoffice.items_list"))
    finally:
        db.close()


@bp.post("/items/import")
def item_import():
    """Re-run the XLSX importer."""
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parent.parent.parent / "scripts" / "import_items.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode == 0:
        flash(result.stdout.strip(), "success")
    else:
        flash(result.stderr.strip()[:200], "error")
    return redirect(url_for("backoffice.items_list"))
