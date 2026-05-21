# -*- coding: utf-8 -*-
"""Settings routes — cafe info, printers, users, permissions, SMTP."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from src.database import get_session
from src.models import Permission, Printer, Setting, User
from src.printer import discover_printers
from src.seed_users import PERMISSION_KEYS

bp = Blueprint("settings", __name__, url_prefix="/settings")

SETTING_KEYS = [
    "cafe_name_ar", "trn", "vat_rate",
    "smtp_host", "smtp_port", "smtp_username", "smtp_password",
    "smtp_use_tls", "smtp_from", "smtp_to",
    "kick_code",
]


@bp.before_request
def _check_admin():
    if session.get("role") != "admin":
        return redirect(url_for("auth.login_page"))


@bp.get("/")
def index():
    db = get_session()
    try:
        settings = {s.key: s.value for s in db.query(Setting).all()}
        printers_db = db.query(Printer).order_by(Printer.name).all()
        users = db.query(User).order_by(User.id).all()

        # Merge config.ini defaults with DB settings
        import configparser
        from pathlib import Path
        cfg = configparser.ConfigParser()
        cfg.read(Path(__file__).resolve().parent.parent.parent / "config.ini", encoding="utf-8")

        defaults = {
            "cafe_name_ar": cfg.get("cafe", "name_ar", fallback="مقهى"),
            "trn": cfg.get("cafe", "trn", fallback=""),
            "vat_rate": cfg.get("vat", "rate", fallback="0.05"),
            "kick_code": cfg.get("printer", "kick_code", fallback="27,112,0,25,250"),
            "smtp_host": cfg.get("smtp", "host", fallback=""),
            "smtp_port": cfg.get("smtp", "port", fallback="587"),
            "smtp_username": cfg.get("smtp", "username", fallback=""),
            "smtp_password": cfg.get("smtp", "password", fallback=""),
            "smtp_from": cfg.get("smtp", "from_address", fallback=""),
            "smtp_to": cfg.get("smtp", "to_address", fallback=""),
        }
        for k, v in defaults.items():
            if k not in settings:
                settings[k] = v

        # Discover Windows printers
        discovered = discover_printers()

        # Permission matrix
        all_perms = {}
        for p in db.query(Permission).all():
            all_perms.setdefault(p.role, {})[p.permission_key] = p.granted

        return render_template("settings.html",
                               settings=settings,
                               printers_db=printers_db,
                               discovered=discovered,
                               users=users,
                               all_perms=all_perms,
                               perm_keys=PERMISSION_KEYS)
    finally:
        db.close()


@bp.post("/save")
def save_settings():
    db = get_session()
    try:
        for key in SETTING_KEYS:
            val = request.form.get(key, "").strip()
            existing = db.query(Setting).filter(Setting.key == key).first()
            if existing:
                existing.value = val
            else:
                db.add(Setting(key=key, value=val))
        db.commit()
        flash("settings_saved", "success")
        return redirect(url_for("settings.index"))
    finally:
        db.close()


@bp.post("/printers/add")
def add_printer():
    db = get_session()
    try:
        name = request.form.get("printer_name", "").strip()
        purpose = request.form.get("purpose", "receipt")
        if name:
            existing = db.query(Printer).filter(Printer.name == name).first()
            if not existing:
                db.add(Printer(name=name, purpose=purpose, enabled=True))
            else:
                existing.purpose = purpose
                existing.enabled = True
            db.commit()
        return redirect(url_for("settings.index"))
    finally:
        db.close()


@bp.post("/printers/<int:pid>/delete")
def delete_printer(pid: int):
    db = get_session()
    try:
        p = db.get(Printer, pid)
        if p:
            db.delete(p)
            db.commit()
        return redirect(url_for("settings.index"))
    finally:
        db.close()


@bp.post("/users/add")
def add_user():
    db = get_session()
    try:
        username = request.form.get("username", "").strip()
        name_ar = request.form.get("name_ar", "").strip()
        role = request.form.get("role", "cashier")
        pin = request.form.get("pin", "0000")
        if username and name_ar:
            db.add(User(
                username=username,
                name_ar=name_ar,
                role=role,
                pin_hash=generate_password_hash(pin),
                active=True,
            ))
            db.commit()
        return redirect(url_for("settings.index"))
    finally:
        db.close()


@bp.post("/users/<int:uid>/update")
def update_user(uid: int):
    db = get_session()
    try:
        user = db.get(User, uid)
        if user:
            user.name_ar = request.form.get("name_ar", user.name_ar).strip()
            user.role = request.form.get("role", user.role)
            user.active = bool(request.form.get("active"))
            new_pin = request.form.get("pin", "").strip()
            if new_pin:
                user.pin_hash = generate_password_hash(new_pin)
            db.commit()
        return redirect(url_for("settings.index"))
    finally:
        db.close()


@bp.post("/permissions/save")
def save_permissions():
    db = get_session()
    try:
        for role in ["admin", "cashier", "waiter"]:
            for key in PERMISSION_KEYS:
                field = f"perm_{role}_{key}"
                granted = bool(request.form.get(field))
                existing = (
                    db.query(Permission)
                    .filter(Permission.role == role, Permission.permission_key == key)
                    .first()
                )
                if existing:
                    existing.granted = granted
                else:
                    db.add(Permission(role=role, permission_key=key, granted=granted))
        db.commit()
        flash("settings_saved", "success")
        return redirect(url_for("settings.index"))
    finally:
        db.close()


@bp.post("/test-print")
def test_print():
    """Send a test receipt to the configured printer."""
    try:
        from src.printer import _get_printer_name, _send_raw_to_printer, _build_cut_command
        printer_name = _get_printer_name("receipt")
        if not printer_name:
            flash("No printer configured", "error")
            return redirect(url_for("settings.index"))

        # Simple test: ESC @ + some text + cut
        data = b'\x1b\x40'  # init
        data += b'\x1b\x61\x01'  # center align
        data += "Cafe POS Test Print\n".encode("cp437", errors="replace")
        data += "Arabic test: OK\n".encode("cp437", errors="replace")
        data += b'\n\n'
        data += _build_cut_command()
        _send_raw_to_printer(printer_name, data)
        flash("Test print sent", "success")
    except Exception as e:
        flash(f"Print error: {e}", "error")
    return redirect(url_for("settings.index"))


@bp.post("/test-email")
def test_email():
    """Send a test daily report email."""
    from src.email_report import send_daily_report
    result = send_daily_report()
    flash(result, "success" if "success" in result.lower() else "error")
    return redirect(url_for("settings.index"))
