# -*- coding: utf-8 -*-
"""Settings routes — cafe info, printers, users, permissions, Gmail OAuth2 email."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from src.database import get_session
from src.models import Permission, Printer, Setting, User
from src.printer import discover_printers
from src.seed_users import PERMISSION_KEYS

bp = Blueprint("settings", __name__, url_prefix="/settings")

SETTING_KEYS = [
    "cafe_name_ar", "trn", "vat_rate", "kick_code",
]

EMAIL_SETTING_KEYS = [
    "gmail_client_id", "gmail_client_secret", "gmail_sender_email",
    "email_recipients",
    "report_on_close", "report_daily",
    "include_sales_summary", "include_top_items", "include_category_breakdown",
    "include_cashier_breakdown", "include_hourly_breakdown", "include_credit_summary",
]


def _get_setting(db, key, fallback=""):
    s = db.query(Setting).filter(Setting.key == key).first()
    return s.value if s and s.value else fallback


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

        import configparser
        from pathlib import Path
        cfg = configparser.ConfigParser()
        cfg.read(Path(__file__).resolve().parent.parent.parent / "config.ini", encoding="utf-8")

        defaults = {
            "cafe_name_ar": cfg.get("cafe", "name_ar", fallback="مقهى"),
            "trn": cfg.get("cafe", "trn", fallback=""),
            "vat_rate": cfg.get("vat", "rate", fallback="0.05"),
            "kick_code": cfg.get("printer", "kick_code", fallback="27,112,0,25,250"),
        }
        for k, v in defaults.items():
            if k not in settings:
                settings[k] = v

        # Gmail OAuth status
        gmail_connected = bool(settings.get("gmail_refresh_token"))

        discovered = discover_printers()
        # Map each saved printer name -> its purpose so the discovered-printer
        # dropdowns show the CURRENT mapping instead of always defaulting to
        # "receipt" (which made saved mappings look like they reset).
        purpose_by_name = {p.name: p.purpose for p in printers_db}

        all_perms = {}
        for p in db.query(Permission).all():
            all_perms.setdefault(p.role, {})[p.permission_key] = p.granted

        return render_template("settings.html",
                               settings=settings,
                               printers_db=printers_db,
                               discovered=discovered,
                               purpose_by_name=purpose_by_name,
                               users=users,
                               all_perms=all_perms,
                               perm_keys=PERMISSION_KEYS,
                               gmail_connected=gmail_connected)
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


@bp.post("/email/save")
def save_email_settings():
    db = get_session()
    try:
        for key in EMAIL_SETTING_KEYS:
            if key.startswith("include_") or key in ("report_on_close", "report_daily"):
                val = "1" if request.form.get(key) else "0"
            else:
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


def _oauth_redirect_uri():
    """Fixed redirect URI that matches Google Cloud Console config exactly."""
    return "http://localhost:5000/settings/oauth-callback"


@bp.get("/oauth-start")
def oauth_start():
    """Redirect to Google OAuth2 consent screen."""
    from src.email_report import get_oauth_url
    redirect_uri = _oauth_redirect_uri()
    auth_url = get_oauth_url(redirect_uri)
    if not auth_url:
        flash("Gmail client ID not configured", "error")
        return redirect(url_for("settings.index"))
    return redirect(auth_url)


@bp.get("/oauth-callback")
def oauth_callback():
    """Handle Google OAuth2 callback."""
    code = request.args.get("code")
    error = request.args.get("error")
    if error or not code:
        flash(f"OAuth error: {error or 'no code'}", "error")
        return redirect(url_for("settings.index"))

    from src.email_report import exchange_code_for_tokens
    redirect_uri = _oauth_redirect_uri()
    try:
        tokens = exchange_code_for_tokens(code, redirect_uri)
        if "access_token" in tokens:
            flash("email_connected", "success")
        else:
            flash(f"Token error: {tokens.get('error', 'unknown')}", "error")
    except Exception as e:
        flash(f"OAuth failed: {e}", "error")

    return redirect(url_for("settings.index"))


@bp.post("/oauth-disconnect")
def oauth_disconnect():
    db = get_session()
    try:
        for key in ["gmail_access_token", "gmail_refresh_token"]:
            s = db.query(Setting).filter(Setting.key == key).first()
            if s:
                s.value = ""
        db.commit()
        flash("Gmail disconnected", "success")
        return redirect(url_for("settings.index"))
    finally:
        db.close()


@bp.post("/email/test")
def test_email():
    from src.email_report import send_daily_report
    result = send_daily_report()
    flash(result, "success" if "success" in result.lower() else "error")
    return redirect(url_for("settings.index"))


@bp.post("/email/send-report")
def send_report():
    """Send email report for a specific time period."""
    from src.email_report import send_daily_report
    period = request.form.get("period", "today")
    result = send_daily_report(period)
    flash(result, "success" if "success" in result.lower() else "error")
    return redirect(url_for("settings.index"))


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
                username=username, name_ar=name_ar, role=role,
                pin_hash=generate_password_hash(pin), active=True,
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
    try:
        from src.printer import _get_printer_name, _send_raw_to_printer, _build_cut_command
        printer_name = _get_printer_name("receipt")
        if not printer_name:
            flash("No printer configured", "error")
            return redirect(url_for("settings.index"))
        data = b'\x1b\x40\x1b\x61\x01'
        data += "Cafe POS Test Print\n\nOK\n\n\n".encode("cp437", errors="replace")
        data += _build_cut_command()
        _send_raw_to_printer(printer_name, data)
        flash("Test print sent", "success")
    except Exception as e:
        flash(f"Print error: {e}", "error")
    return redirect(url_for("settings.index"))


@bp.post("/test-drawer")
def test_drawer():
    """Fire the cash-drawer kick on the configured drawer printer (or the
    receipt printer if no dedicated drawer printer is mapped)."""
    try:
        from src.printer import (
            _get_printer_name,
            _get_printer_name_strict,
            _send_raw_to_printer,
            _kick_drawer_bytes,
        )
        printer_name = _get_printer_name_strict("cash_drawer") or _get_printer_name("receipt")
        if not printer_name:
            flash("No printer configured", "error")
            return redirect(url_for("settings.index"))
        # ESC @ initialises the printer before the drawer pulse — some
        # printers ignore a bare pulse command sent cold.
        _send_raw_to_printer(printer_name, b"\x1b\x40" + _kick_drawer_bytes())
        flash(f"Drawer kick sent to: {printer_name}", "success")
    except Exception as e:
        flash(f"Drawer error: {e}", "error")
    return redirect(url_for("settings.index"))


@bp.post("/autodetect-drawer")
def autodetect_drawer():
    """Auto-find the printer the cash drawer is attached to, map it as the
    cash_drawer printer, and fire a test kick.

    A cash drawer has no independent connection — it plugs into a thermal
    printer's drawer port and is opened by an ESC/POS pulse. So "finding"
    the drawer means picking the most likely printer and pulsing it:
      1. an already-mapped cash_drawer printer, else
      2. the receipt printer, else
      3. the first enabled printer in the DB, else
      4. the first Windows-discovered printer.
    The chosen printer is saved as the cash_drawer mapping (auto-connect),
    then a kick is sent so the operator can confirm the drawer opened.
    """
    from src.printer import (
        _get_printer_name_strict,
        _send_raw_to_printer,
        _kick_drawer_bytes,
        discover_printers,
    )
    db = get_session()
    try:
        target = _get_printer_name_strict("cash_drawer")
        if not target:
            target = _get_printer_name_strict("receipt")
        if not target:
            first = db.query(Printer).filter(Printer.enabled == True).first()
            target = first.name if first else None
        if not target:
            discovered = discover_printers()
            target = discovered[0]["name"] if discovered else None

        if not target:
            flash("No printers found to connect the drawer to", "error")
            return redirect(url_for("settings.index"))

        # Auto-connect: save (or update) this printer as the cash_drawer.
        existing = db.query(Printer).filter(Printer.name == target).first()
        if existing:
            existing.purpose = "cash_drawer"
            existing.enabled = True
        else:
            db.add(Printer(name=target, purpose="cash_drawer", enabled=True))
        db.commit()

        # Test it.
        _send_raw_to_printer(target, b"\x1b\x40" + _kick_drawer_bytes())
        flash(f"Drawer connected to '{target}' and test kick sent", "success")
    except Exception as e:
        flash(f"Drawer auto-detect error: {e}", "error")
    finally:
        db.close()
    return redirect(url_for("settings.index"))
