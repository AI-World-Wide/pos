# -*- coding: utf-8 -*-
"""Authentication routes — PIN login for 5 seeded users."""
from __future__ import annotations

from flask import Blueprint, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from src.database import get_session
from src.models import Permission, User

bp = Blueprint("auth", __name__)


@bp.get("/login")
def login_page():
    db = get_session()
    try:
        users = db.query(User).filter(User.active == True).order_by(User.id).all()
        return render_template("login.html", users=[
            {"id": u.id, "username": u.username, "name_ar": u.name_ar, "role": u.role}
            for u in users
        ], error=None)
    finally:
        db.close()


@bp.post("/login")
def login_submit():
    db = get_session()
    try:
        user_id = request.form.get("user_id")
        pin = request.form.get("pin", "")

        user = db.get(User, int(user_id)) if user_id else None
        if not user or not check_password_hash(user.pin_hash, pin):
            users = db.query(User).filter(User.active == True).order_by(User.id).all()
            return render_template("login.html", users=[
                {"id": u.id, "username": u.username, "name_ar": u.name_ar, "role": u.role}
                for u in users
            ], error="wrong_pin")

        # Load permissions
        perms = {
            p.permission_key: p.granted
            for p in db.query(Permission).filter(Permission.role == user.role).all()
        }

        session["user_id"] = user.id
        session["username"] = user.username
        session["name_ar"] = user.name_ar
        session["role"] = user.role
        session["can_view_reports"] = perms.get("view_reports", False)
        session["can_edit_items"] = perms.get("edit_items", False)
        session["can_manage_users"] = perms.get("manage_users", False)
        session["can_manage_settings"] = perms.get("manage_settings", False)
        session["can_take_payment"] = perms.get("take_payment", False)
        session["can_void_line"] = perms.get("void_line", False)

        return redirect(url_for("cashier.index"))
    finally:
        db.close()


@bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login_page"))
