# -*- coding: utf-8 -*-
"""Seed the 5 default user accounts + role-based permission matrix.

Default PINs (admin should change in Phase 4 settings):
- admin / 9999
- cashier1 / 1111
- cashier2 / 2222
- waiter1 / 3333
- waiter2 / 4444
"""
from __future__ import annotations

from werkzeug.security import generate_password_hash

from src.models import Permission, User

DEFAULT_USERS = [
    {"username": "admin",    "name_ar": "المدير",   "role": "admin",   "pin": "9999"},
    {"username": "cashier1", "name_ar": "كاشير 1",  "role": "cashier", "pin": "1111"},
    {"username": "cashier2", "name_ar": "كاشير 2",  "role": "cashier", "pin": "2222"},
    {"username": "waiter1",  "name_ar": "نادل 1",   "role": "waiter",  "pin": "3333"},
    {"username": "waiter2",  "name_ar": "نادل 2",   "role": "waiter",  "pin": "4444"},
]

PERMISSION_KEYS = [
    "take_order",
    "send_to_kitchen",
    "take_payment",
    "void_line",
    "apply_discount",
    "view_reports",
    "edit_items",
    "manage_users",
    "manage_settings",
    "manage_printers",
]

# Default permission matrix. Admin gets everything; cashier handles money;
# waiter takes orders + sends to kitchen but cannot settle payment.
ROLE_DEFAULTS = {
    "admin":   {k: True for k in PERMISSION_KEYS},
    "cashier": {
        "take_order": True, "send_to_kitchen": True, "take_payment": True,
        "void_line": True, "apply_discount": False, "view_reports": False,
        "edit_items": False, "manage_users": False, "manage_settings": False,
        "manage_printers": False,
    },
    "waiter": {
        "take_order": True, "send_to_kitchen": True, "take_payment": False,
        "void_line": False, "apply_discount": False, "view_reports": False,
        "edit_items": False, "manage_users": False, "manage_settings": False,
        "manage_printers": False,
    },
}


def seed_users_and_permissions(session) -> None:
    existing_usernames = {u.username for u in session.query(User).all()}
    for u in DEFAULT_USERS:
        if u["username"] in existing_usernames:
            continue
        session.add(User(
            username=u["username"],
            name_ar=u["name_ar"],
            role=u["role"],
            pin_hash=generate_password_hash(u["pin"]),
            active=True,
        ))

    existing_perms = {(p.role, p.permission_key) for p in session.query(Permission).all()}
    for role, perms in ROLE_DEFAULTS.items():
        for key, granted in perms.items():
            if (role, key) in existing_perms:
                continue
            session.add(Permission(role=role, permission_key=key, granted=granted))
