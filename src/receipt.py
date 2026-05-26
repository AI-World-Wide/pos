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

from src.database import RUNTIME_DIR, CONFIG_PATH as _DB_CONFIG_PATH
from src.models import Order, Setting
from src.translations.ar import T

import sys
if getattr(sys, "frozen", False):
    _BUNDLE = Path(sys._MEIPASS)
else:
    _BUNDLE = Path(__file__).resolve().parent.parent

PROJECT_ROOT = RUNTIME_DIR
CONFIG_PATH = _DB_CONFIG_PATH
RECEIPT_WIDTH = 576

# Arabic shaping: join letters into contextual forms (reshaper) and reorder
# for right-to-left display (bidi). Without this, Pillow draws Arabic as
# isolated, left-to-right glyphs — which is the garbled output on the printout.
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _HAS_AR_SHAPING = True
except Exception:  # pragma: no cover - shaping libs missing
    _HAS_AR_SHAPING = False


def shape_ar(text) -> str:
    """Reshape + bidi-reorder Arabic text for correct printed rendering.

    Numbers and Latin segments are preserved in their natural order by the
    bidi algorithm, so mixed strings (e.g. "التاريخ: 24/05/2026") render
    correctly. Safe to call on any string.
    """
    if text is None:
        return ""
    text = str(text)
    if not text or not _HAS_AR_SHAPING:
        return text
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text

# Font paths — bundled Cairo TTF first, then system Arabic-capable fonts.
# Separate lists so bold actually renders bold (Cairo TTFs aren't bundled,
# so without a real bold face everything fell back to regular weight).
_FONT_REGULAR = [
    _BUNDLE / "static" / "fonts" / "Cairo-Regular.ttf",
    Path("C:/Windows/Fonts/segoeui.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
]
_FONT_BOLD = [
    _BUNDLE / "static" / "fonts" / "Cairo-Bold.ttf",
    Path("C:/Windows/Fonts/segoeuib.ttf"),  # Segoe UI Bold (has Arabic)
    Path("C:/Windows/Fonts/arialbd.ttf"),   # Arial Bold (has Arabic)
    Path("C:/Windows/Fonts/segoeui.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
]


def _find_font(bold: bool = False) -> str:
    """Find a usable font file path (real bold face when bold=True)."""
    for p in (_FONT_BOLD if bold else _FONT_REGULAR):
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
        "cafe_name_en": ("cafe", "name_en"),
        "trn": ("cafe", "trn"),
        "address": ("cafe", "address"),
        "vat_rate": ("vat", "rate"),
    }
    if key in section_map:
        sec, k = section_map[key]
        return cfg.get(sec, k, fallback=fallback)
    return fallback


def render_receipt(order: Order, db, as_invoice: bool = False) -> Image.Image:
    """Render a customer receipt (or invoice) as a Pillow Image (576px wide).

    as_invoice=True produces a pre-payment invoice: a "فاتورة / INVOICE"
    header is shown and the payment lines (cash received / change) are
    omitted, since the customer hasn't paid yet.
    """
    W = RECEIPT_WIDTH
    MARGIN = 20

    # Gather data
    cafe_name = _get_setting(db, "cafe_name_ar", T["cafe_name_default"])
    cafe_name_en = _get_setting(db, "cafe_name_en", "")
    trn = _get_setting(db, "trn", "100000000000000")
    address = _get_setting(db, "address", "")
    lines = [l for l in order.lines if not l.voided]

    # Table label (e.g. "منطقة 1 - 5"), if this order is on a table.
    table_label = ""
    if order.table_id:
        from src.models import FloorTable, Area
        ft = db.get(FloorTable, order.table_id)
        if ft:
            area = db.get(Area, ft.area_id)
            table_label = f"{area.name_ar} - {ft.number}" if area else str(ft.number)

    # Pre-calculate layout height. Fonts are large + bold for readability;
    # the 576px WIDTH is unchanged so it still fits the 80mm paper exactly.
    font_title = _font(40, bold=True)
    font_normal = _font(28, bold=True)
    font_small = _font(23, bold=True)
    font_header = _font(28, bold=True)
    font_total = _font(38, bold=True)

    # Estimate height (generous; cropped to content at the end)
    h = 40  # top padding
    h += 52  # cafe name (Arabic)
    h += 38  # cafe name (English)
    h += 50  # "Tax Invoice" header
    h += 34 * 3  # address (up to 2 lines) + TRN
    h += 10 + 2  # separator
    h += 38 * 4  # date, invoice no, table, cashier
    h += 10 + 2  # separator
    h += 38  # header row
    h += 10 + 2  # separator
    h += len(lines) * 70  # item lines (Arabic + English = 2 lines each)
    h += 10 + 2  # separator
    h += 38 * 4  # before-vat, vat, total incl vat, payable
    h += 10 + 2  # separator
    if order.payment_method == "cash":
        h += 38 * 2  # cash received, change
        h += 10 + 2
    h += 40 * 2  # thank you lines
    h += 40  # bottom padding
    h += 30  # bottom margin

    img = Image.new("RGB", (W, h), "white")
    draw = ImageDraw.Draw(img)
    y = 30

    def draw_center(text, font, y_pos):
        text = shape_ar(text)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) / 2, y_pos), text, fill="black", font=font)

    def draw_right(text, font, y_pos):
        text = shape_ar(text)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text((W - MARGIN - tw, y_pos), text, fill="black", font=font)

    def draw_left(text, font, y_pos):
        draw.text((MARGIN, y_pos), shape_ar(text), fill="black", font=font)

    def draw_line(y_pos):
        draw.line([(MARGIN, y_pos), (W - MARGIN, y_pos)], fill="#999999", width=1)
        return y_pos + 8

    def draw_row(right_text, left_text, font, y_pos):
        draw_right(right_text, font, y_pos)
        draw_left(left_text, font, y_pos)

    # Cafe name — Arabic then English
    draw_center(cafe_name, font_title, y)
    y += 52
    if cafe_name_en:
        draw_center(cafe_name_en, font_header, y)
        y += 38

    # Document title — "Tax Invoice" on the paid receipt, proforma otherwise.
    if as_invoice:
        draw_center("فاتورة / INVOICE", font_total, y)
        y += 50
    else:
        draw_center(f"{T['tax_invoice']} / TAX INVOICE", font_total, y)
        y += 50

    # Physical address (wrap to a second line if long) + TRN
    if address:
        if len(address) <= 38:
            draw_center(address, font_small, y)
            y += 32
        else:
            cut = address.rfind(",", 0, 38)
            cut = cut if cut > 0 else 38
            draw_center(address[:cut].strip(" ,"), font_small, y)
            y += 30
            draw_center(address[cut:].strip(" ,"), font_small, y)
            y += 32
    draw_center(f"TRN: {trn}", font_small, y)
    y += 32

    y = draw_line(y)

    # Date/time (exact), invoice no, order number, table, cashier
    now = order.closed_at or datetime.now()
    date_str = now.strftime("%d/%m/%Y  %I:%M %p")
    draw_row(f"{T['receipt_date']}: {date_str}", "", font_normal, y)
    y += 38

    draw_row(f"{T['invoice_no']}: {order.id}", "", font_normal, y)
    y += 38

    if table_label:
        draw_row(f"{T['tables']}: {table_label}", "", font_normal, y)
        y += 38

    draw_row(f"{T['receipt_cashier']}: {order.cashier or 'Admin'}", "", font_normal, y)
    y += 38

    y = draw_line(y)

    # Header
    draw_right(T["item"], font_header, y)
    draw_center(T["qty"], font_header, y)
    draw_left(T["price"], font_header, y)
    y += 40

    y = draw_line(y)

    # Items — Arabic name on the row, English name underneath
    for l in lines:
        draw_right(l.item_name_ar or "", font_normal, y)
        draw_center(str(l.quantity), font_normal, y)
        draw_left(f"{l.line_total:.2f}", font_normal, y)
        y += 36
        # English name (snapshot, else look up the live item)
        name_en = (l.item_name_en or "").strip()
        if not name_en and l.item_id:
            from src.models import Item
            it = db.get(Item, l.item_id)
            if it and it.name_en:
                name_en = it.name_en
        if name_en:
            draw_right(name_en, font_small, y)
            y += 32
        else:
            y += 4

    y = draw_line(y)

    # Totals — net (before VAT), VAT 5% value, total incl VAT, payable.
    draw_row(T["total_before_vat"], f"{T['currency']} {order.subtotal:.2f}", font_normal, y)
    y += 38
    draw_row(f"{T['vat_5']}", f"{T['currency']} {order.vat_amount:.2f}", font_normal, y)
    y += 38
    draw_row(T["total_incl_vat"], f"{T['currency']} {order.total:.2f}", font_normal, y)
    y += 38

    y = draw_line(y)

    draw_row(T["total_payable"], f"{T['currency']} {order.total:.2f}", font_total, y)
    y += 50

    y = draw_line(y)

    # Cash payment details (receipts only; an invoice isn't paid yet)
    if not as_invoice and order.payment_method == "cash" and order.cash_received:
        draw_row(T["cash_received"], f"{T['currency']} {order.cash_received:.2f}", font_normal, y)
        y += 38
        draw_row(T["change_due"], f"{T['currency']} {order.change_due:.2f}", font_normal, y)
        y += 38
        y = draw_line(y)

    # Footer: thank-you on receipts; "not a tax receipt" note on invoices.
    if as_invoice:
        draw_center("هذه فاتورة وليست إيصال دفع", font_small, y)
        y += 36
    else:
        draw_center(T["receipt_thanks_1"], font_normal, y)
        y += 40
        draw_center(T["receipt_thanks_2"], font_small, y)
        y += 36

    # Crop to actual content
    img = img.crop((0, 0, W, y + 20))
    return img
