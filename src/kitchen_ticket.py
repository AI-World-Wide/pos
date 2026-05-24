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


def render_kitchen_ticket(order: Order, db, line_ids: list[int] | None = None) -> Image.Image:
    """Render kitchen ticket for non-beverage items."""
    W = TICKET_WIDTH
    MARGIN = 20

    font_title = _font(28, bold=True)
    font_item = _font(24, bold=True)
    font_normal = _font(18)

    # Get lines to print (only non-beverage items)
    if line_ids:
        lines = db.query(OrderLine).filter(OrderLine.id.in_(line_ids)).all()
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
        # Still create a minimal ticket
        kitchen_lines = [l for l in lines if not l.voided]

    # Calculate height
    h = 30 + 40 + 30 + 10 + len(kitchen_lines) * 40 + 30 + 30 + 30

    img = Image.new("RGB", (W, h), "white")
    draw = ImageDraw.Draw(img)
    y = 20

    def draw_center(text, font, y_pos):
        text = shape_ar(text)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) / 2, y_pos), text, fill="black", font=font)

    # Title
    draw_center("طلب مطبخ", font_title, y)
    y += 40

    # Order info
    now = datetime.now()
    draw_center(f"{order.order_number}  |  {now.strftime('%H:%M')}", font_normal, y)
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

    # Bottom separator
    y += 5
    draw.line([(MARGIN, y), (W - MARGIN, y)], fill="black", width=2)
    y += 20

    img = img.crop((0, 0, W, y + 10))
    return img
