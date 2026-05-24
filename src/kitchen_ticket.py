# -*- coding: utf-8 -*-
"""Kitchen ticket renderer — simpler layout, larger font, food items only.

Only items where category.is_beverage=0 get printed on kitchen tickets.
Beverage-only items print on the receipt only.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from src.models import Category, Item, Order, OrderLine

import sys
if getattr(sys, "frozen", False):
    _BUNDLE = Path(sys._MEIPASS)
else:
    _BUNDLE = Path(__file__).resolve().parent.parent

TICKET_WIDTH = 576

# Arabic shaping (join letters + RTL reorder) — see src/receipt.py.
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _HAS_AR_SHAPING = True
except Exception:  # pragma: no cover
    _HAS_AR_SHAPING = False


def shape_ar(text) -> str:
    """Reshape + bidi-reorder Arabic for correct printed rendering."""
    if text is None:
        return ""
    text = str(text)
    if not text or not _HAS_AR_SHAPING:
        return text
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    paths = [
        _BUNDLE / "static" / "fonts" / ("Cairo-Bold.ttf" if bold else "Cairo-Regular.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
    ]
    for p in paths:
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    return ImageFont.load_default()


def line_station(db, line) -> str:
    """Classify which station an order line belongs to.

    Returns:
      "none"    -> beverage / receipt-only, never sent to a prep station
      "shisha"  -> shisha items, print on the Shisha printer
      "kitchen" -> everything else (food), print on the Kitchen (Bar) printer
    """
    if not getattr(line, "item_id", None):
        return "kitchen"
    item = db.get(Item, line.item_id)
    if not item:
        return "kitchen"
    cat = db.get(Category, item.category_id)

    # 1) Beverages are receipt-only — never sent to a prep station. This
    #    takes priority over kitchen_station (seed data sets it to "Bar"
    #    on drinks too, which must not pull them onto the kitchen ticket).
    if cat and cat.is_beverage:
        return "none"

    # 2) Shisha — either an explicit per-item station or the Shisha category.
    station = (getattr(item, "kitchen_station", "") or "").strip().lower()
    if station in ("shisha", "شيشة"):
        return "shisha"
    if cat and ((cat.name_en or "").strip().lower() == "shisha" or "شيشة" in (cat.name_ar or "")):
        return "shisha"

    # 3) Everything else is food -> kitchen.
    return "kitchen"


def render_kitchen_ticket(order: Order, db, line_ids: list[int] | None = None,
                          title: str = "طلب مطبخ") -> Image.Image:
    """Render a prep-station ticket (kitchen or shisha).

    When `line_ids` is provided the caller has already chosen exactly which
    lines belong to this station, so they are rendered as-is (no beverage
    re-filter). When omitted, falls back to all unsent non-beverage lines.
    """
    W = TICKET_WIDTH
    MARGIN = 20

    font_title = _font(28, bold=True)
    font_item = _font(24, bold=True)
    font_normal = _font(18)

    if line_ids:
        # Preserve the caller's order; render exactly these lines.
        by_id = {l.id: l for l in db.query(OrderLine).filter(OrderLine.id.in_(line_ids)).all()}
        kitchen_lines = [by_id[i] for i in line_ids if i in by_id and not by_id[i].voided]
    else:
        lines = [l for l in order.lines if not l.voided and not l.sent_to_kitchen]
        # Filter out beverage-category items
        kitchen_lines = []
        for l in lines:
            if l.item_id:
                item = db.get(Item, l.item_id)
                if item:
                    cat = db.get(Category, item.category_id)
                    if cat and cat.is_beverage:
                        continue
            kitchen_lines.append(l)

    if not kitchen_lines:
        return Image.new("RGB", (W, 1), "white")

    font_note = _font(20)

    # Table label (e.g. "منطقة 1 - 5") for this order, if any.
    table_label = ""
    if getattr(order, "table_id", None):
        from src.models import FloorTable, Area
        ft = db.get(FloorTable, order.table_id)
        if ft:
            area = db.get(Area, ft.area_id)
            table_label = f"{area.name_ar} - {ft.number}" if area else str(ft.number)

    # Calculate height (generous; cropped to actual content at the end).
    # Each item may carry a note line, and the order may carry a table note.
    h = 30 + 40 + 30 + 30 + 30 + 10 + len(kitchen_lines) * 78 + 30 + 30 + 120

    img = Image.new("RGB", (W, h), "white")
    draw = ImageDraw.Draw(img)
    y = 20

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

    # Title
    draw_center(title, font_title, y)
    y += 40

    # Table name (prominent for the kitchen/shisha staff)
    if table_label:
        draw_center(table_label, font_item, y)
        y += 32

    # Order number + exact date and time
    now = datetime.now()
    draw_center(f"{order.order_number}", font_normal, y)
    y += 28
    draw_center(now.strftime("%d/%m/%Y  %I:%M %p"), font_normal, y)
    y += 30

    # Separator
    draw.line([(MARGIN, y), (W - MARGIN, y)], fill="black", width=2)
    y += 12

    # Items (larger font for kitchen readability)
    for l in kitchen_lines:
        name = shape_ar(l.item_name_ar or "")
        qty_text = f"×{l.quantity}"

        # Name on right, qty on left
        bbox = draw.textbbox((0, 0), name, font=font_item)
        tw = bbox[2] - bbox[0]
        draw.text((W - MARGIN - tw, y), name, fill="black", font=font_item)
        draw.text((MARGIN, y), qty_text, fill="black", font=font_item)
        y += 38

        # Per-item note (e.g. "بدون سكر") under the item, indented.
        note = (getattr(l, "note", None) or "").strip()
        if note:
            draw_right("- " + note, font_note, y)
            y += 30

    # Bottom separator
    y += 5
    draw.line([(MARGIN, y), (W - MARGIN, y)], fill="black", width=2)
    y += 14

    # Whole-table note (printed once, at the bottom).
    table_note = (getattr(order, "notes", None) or "").strip()
    if table_note:
        draw_right("ملاحظة: " + table_note, font_note, y)
        y += 30

    img = img.crop((0, 0, W, y + 10))
    return img
