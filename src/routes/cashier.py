# -*- coding: utf-8 -*-
"""Phase 1 cashier routes — placeholder.

- GET /         → list 6 categories with item counts
- GET /cat/<id> → list items in a category

Real cashier UX (item buttons, cart, payment) lands in Phase 2-3.
"""
from __future__ import annotations

from flask import Blueprint, abort, render_template
from sqlalchemy import func

from src.database import get_session
from src.models import Category, Item

bp = Blueprint("cashier", __name__)


@bp.get("/")
def index():
    session = get_session()
    try:
        rows = (
            session.query(Category, func.count(Item.id))
            .outerjoin(Item, Item.category_id == Category.id)
            .filter(Category.visible == 1)
            .group_by(Category.id)
            .order_by(Category.sort_order.asc())
            .all()
        )
        categories = [
            {"id": c.id, "name_ar": c.name_ar, "item_count": count}
            for c, count in rows
        ]
        return render_template("cashier.html", categories=categories, category=None, items=None)
    finally:
        session.close()


@bp.get("/cat/<int:cat_id>")
def category(cat_id: int):
    session = get_session()
    try:
        cat = session.get(Category, cat_id)
        if cat is None or cat.visible != 1:
            abort(404)
        items = (
            session.query(Item)
            .filter(Item.category_id == cat_id, Item.visible == 1)
            .order_by(Item.sort_order.asc(), Item.name_ar.asc())
            .all()
        )
        items_view = [
            {"id": i.id, "name_ar": i.name_ar, "price": i.price_inclusive}
            for i in items
        ]
        category_view = {"id": cat.id, "name_ar": cat.name_ar}
        return render_template(
            "cashier.html",
            categories=None,
            category=category_view,
            items=items_view,
        )
    finally:
        session.close()
