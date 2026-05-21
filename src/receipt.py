# -*- coding: utf-8 -*-
"""Receipt renderer — Pillow → 576px-wide PNG for ESC/POS image printing.

Uses Cairo Arabic font for guaranteed Arabic rendering on the receipt.
Receipt width: 576 pixels (72mm at 203 DPI for 80mm thermal paper).
"""
from __future__ import annotations

import configparser
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from src.models import Order, Setting
from src.translations.ar import T

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.ini"
RECEIPT_WIDTH = 576

# Font paths — try bundled Cairo TTF first, fall back to system Arabic fonts
_FONT_PATHS = [
    PROJECT_ROOT / "static" / "fonts" / "Cairo-Regular.ttf",
    PROJECT_ROOT / "static" / "fonts" / "Cairo-Bold.ttf",
    Path("C:/Windows/Fonts/segoeui.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
]


def _find_font(bold: bool = False) -> str:
    """Find a usable font file path."""
    preferred = _FONT_PATHS[1] if bold else _FONT_PATHS[0]
    if preferred.exists():
        return str(preferred)
    for p in _FONT_PATHS:
        if p.exists():
            return str(p)
    return "arial"  # PIL fallback


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = _find_font(bold)
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _get_setting(db, key: str, fallback: str = "") -> str:
    s = db.query(Setting).filter(Setting.key == key).first()
    if s and s.value:
        return s.value
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH, encoding="utf-8")
    section_map = {
        "cafe_name_ar": ("cafe", "name_ar"),
        "trn": ("cafe", "trn"),
        "vat_rate": ("vat", "rate"),
    }
    if key in section_map:
        sec, k = section_map[key]
        return cfg.get(sec, k, fallback=fallback)
    return fallback


def render_receipt(order: Order, db) -> Image.Image:
    """Render a full customer receipt as a Pillow Image (576px wide)."""
    W = RECEIPT_WIDTH
    MARGIN = 20
    TW = W - MARGIN * 2  # text width

    # Gather data
    cafe_name = _get_setting(db, "cafe_name_ar", T["cafe_name_default"])
    trn = _get_setting(db, "trn", "100000000000000")
    lines = [l for l in order.lines if not l.voided]

    # Pre-calculate layout height
    font_title = _font(28, bold=True)
    font_normal = _font(18)
    font_small = _font(14)
    font_header = _font(16, bold=True)
    font_total = _font(22, bold=True)

    # Estimate height
    h = 40  # top padding
    h += 40  # cafe name
    h += 30  # TRN
    h += 10 + 2  # separator
    h += 25 * 3  # date, order number, cashier
    h += 10 + 2  # separator
    h += 25  # header row
    h += 10 + 2  # separator
    h += len(lines) * 25  # item lines
    h += 10 + 2  # separator
    h += 25 * 3  # subtotal, vat, total
    h += 10 + 2  # separator
    if order.payment_method == "cash":
        h += 25 * 2  # cash received, change
        h += 10 + 2
    h += 30 * 2  # thank you lines
    h += 40  # bottom padding
    h += 220  # QR code space
    h += 30  # bottom margin

    img = Image.new("RGB", (W, h), "white")
    draw = ImageDraw.Draw(img)
    y = 30

    def draw_center(text, font, y_pos):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) / 2, y_pos), text, fill="black", font=font)

    def draw_right(text, font, y_pos):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text((W - MARGIN - tw, y_pos), text, fill="black", font=font)

    def draw_left(text, font, y_pos):
        draw.text((MARGIN, y_pos), text, fill="black", font=font)

    def draw_line(y_pos):
        draw.line([(MARGIN, y_pos), (W - MARGIN, y_pos)], fill="#999999", width=1)
        return y_pos + 8

    def draw_row(right_text, left_text, font, y_pos):
        draw_right(right_text, font, y_pos)
        draw_left(left_text, font, y_pos)

    # Cafe name
    draw_center(cafe_name, font_title, y)
    y += 40

    # TRN
    draw_center(f"TRN: {trn}", font_small, y)
    y += 25

    y = draw_line(y)

    # Date/time
    now = order.closed_at or datetime.utcnow()
    date_str = now.strftime("%d/%m/%Y  %I:%M %p")
    draw_row(f"{T['receipt_date']}: {date_str}", "", font_normal, y)
    y += 25

    draw_row(f"{T['receipt_number']}: {order.order_number}", "", font_normal, y)
    y += 25

    draw_row(f"{T['receipt_cashier']}: {order.cashier or 'Admin'}", "", font_normal, y)
    y += 25

    y = draw_line(y)

    # Header
    draw_right(T["item"], font_header, y)
    draw_center(T["qty"], font_header, y)
    draw_left(T["price"], font_header, y)
    y += 25

    y = draw_line(y)

    # Items
    for l in lines:
        draw_right(l.item_name_ar or "", font_normal, y)
        draw_center(str(l.quantity), font_normal, y)
        draw_left(f"{l.line_total:.2f}", font_normal, y)
        y += 25

    y = draw_line(y)

    # Totals
    draw_row(T["subtotal"], f"{T['currency']} {order.subtotal:.2f}", font_normal, y)
    y += 25
    draw_row(T["vat_5"], f"{T['currency']} {order.vat_amount:.2f}", font_small, y)
    y += 25

    y = draw_line(y)

    draw_row(T["total"], f"{T['currency']} {order.total:.2f}", font_total, y)
    y += 35

    y = draw_line(y)

    # Cash payment details
    if order.payment_method == "cash" and order.cash_received:
        draw_row(T["cash_received"], f"{T['currency']} {order.cash_received:.2f}", font_normal, y)
        y += 25
        draw_row(T["change_due"], f"{T['currency']} {order.change_due:.2f}", font_normal, y)
        y += 25
        y = draw_line(y)

    # Thank you
    draw_center(T["receipt_thanks_1"], font_normal, y)
    y += 28
    draw_center(T["receipt_thanks_2"], font_small, y)
    y += 25

    y = draw_line(y)

    # QR code (VAT compliance info)
    try:
        import qrcode
        qr_data = f"Cafe POS|TRN:{trn}|Order:{order.order_number}|Total:{order.total:.2f}|VAT:{order.vat_amount:.2f}"
        qr = qrcode.make(qr_data)
        qr = qr.resize((180, 180))
        qr_x = (W - 180) // 2
        img.paste(qr, (qr_x, y + 5))
        y += 200
    except Exception:
        pass

    # Crop to actual content
    img = img.crop((0, 0, W, y + 20))
    return img
