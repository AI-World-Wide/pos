# -*- coding: utf-8 -*-
"""PDF report builder — bundles every report sheet into one PDF.

Used by the closing-day email so the owner has a full snapshot of the
shift in one attachment. Pure-Python via fpdf2 (~200KB, no native deps).

Arabic is rendered through Windows' Arial font (pre-installed on every
supported Windows version, including the target Win10 1703 Dell). If
the font is unavailable we fall back to the fpdf2 built-in Helvetica
which can't draw Arabic glyphs — the report still contains all the
numbers, just with mojibake instead of Arabic labels.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path

from fpdf import FPDF

from src.reports import (
    get_credit_summary,
    get_open_tables_summary,
    get_payment_breakdown,
    get_sales_by_cashier,
    get_sales_by_category,
    get_sales_by_hour,
    get_summary,
    get_top_items,
    get_all_orders_sheet,
)
from src.translations.ar import T

logger = logging.getLogger(__name__)

_FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("C:/Windows/Fonts/segoeui.ttf"),
    Path("C:/Windows/Fonts/tahoma.ttf"),
]


def _find_font() -> str | None:
    for p in _FONT_CANDIDATES:
        if p.exists():
            return str(p)
    return None


class ReportPDF(FPDF):
    def __init__(self, font_path: str | None):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=15)
        self._has_arabic = False
        if font_path:
            try:
                self.add_font("AR", "", font_path, uni=True)
                # Try the matching bold (arialbd.ttf, segoeuib.ttf, tahomabd.ttf)
                bold_path = Path(font_path)
                bold_candidates = [
                    bold_path.with_name(bold_path.stem + "bd" + bold_path.suffix),
                    bold_path.with_name(bold_path.stem + "b" + bold_path.suffix),
                    bold_path.with_name("arialbd.ttf"),
                ]
                self._has_bold = False
                for bc in bold_candidates:
                    if bc.exists():
                        self.add_font("AR", "B", str(bc), uni=True)
                        self._has_bold = True
                        break
                self._has_arabic = True
            except Exception as e:
                logger.error("PDF font load failed (%s); falling back to Helvetica", e)
        else:
            self._has_bold = True  # Helvetica has built-in B
        self._title_text = ""

    def use_font(self, size: int = 11, bold: bool = False):
        if self._has_arabic:
            style = "B" if (bold and self._has_bold) else ""
            self.set_font("AR", style, size)
        else:
            self.set_font("Helvetica", "B" if bold else "", size)

    def header(self):
        if self._title_text:
            self.use_font(11, bold=True)
            self.cell(0, 8, self._title_text, ln=1, align="C")
            self.ln(2)

    def footer(self):
        self.set_y(-12)
        self.use_font(8)
        self.cell(0, 6, f"{self.page_no()} / {{nb}}", align="C")

    def section_title(self, text: str):
        self.ln(4)
        self.use_font(13, bold=True)
        self.cell(0, 8, text, ln=1, align="R")
        self.use_font(10)

    def kv_table(self, rows: list[tuple[str, str]], col_widths=(80, 80)):
        self.use_font(10)
        for label, value in rows:
            self.cell(col_widths[0], 7, str(label), border=1, align="R")
            self.cell(col_widths[1], 7, str(value), border=1, ln=1, align="R")

    def grid_table(self, headers: list[str], rows: list[list[str]], widths: list[int] | None = None):
        if not headers:
            return
        if widths is None:
            page_w = self.w - 2 * self.l_margin
            widths = [page_w / len(headers)] * len(headers)
        self.use_font(10, bold=True)
        for h, w in zip(headers, widths):
            self.cell(w, 7, str(h), border=1, align="C")
        self.ln()
        self.use_font(10)
        for row in rows:
            for cell, w in zip(row, widths):
                self.cell(w, 6, str(cell), border=1, align="R")
            self.ln()


def _fmt_money(value: float) -> str:
    cur = T.get("currency", "AED")
    return f"{cur} {value:,.2f}"


def build_closing_report_pdf(period: str = "today") -> bytes:
    """Build a multi-section PDF report. Returns the PDF as bytes."""
    font_path = _find_font()
    pdf = ReportPDF(font_path)
    pdf.alias_nb_pages()
    pdf._title_text = T.get("reports_title", "Reports")
    pdf.add_page()

    # --- Summary
    summary = get_summary(period)
    pdf.section_title(T.get("reports_title", "Reports"))
    pdf.kv_table([
        (T.get("total_with_vat", "Total (incl VAT)"), _fmt_money(summary["total_with_vat"])),
        (T.get("subtotal_no_vat", "Subtotal (excl VAT)"), _fmt_money(summary["subtotal_no_vat"])),
        (T.get("vat_collected", "VAT"), _fmt_money(summary["vat_collected"])),
        (T.get("cash_total", "Cash total"), _fmt_money(summary["cash_total"])),
        (T.get("card_total", "Card total"), _fmt_money(summary["card_total"])),
        (T.get("order_count", "Orders"), str(summary["order_count"])),
        (T.get("avg_order_value", "Avg order"), _fmt_money(summary["avg_order_value"])),
    ])

    # --- Open / unpaid tables
    open_t = get_open_tables_summary(period)
    pdf.section_title(T.get("open_tables_section", "Open tables"))
    pdf.kv_table([
        (T.get("open_tables_count", "Count"), str(open_t["count"])),
        (T.get("open_tables_due", "Total due"), _fmt_money(open_t["total_due"])),
    ])
    if open_t["tables"]:
        pdf.ln(2)
        pdf.grid_table(
            [T.get("order_number", "#"), T.get("tables", "Table"),
             T.get("opened", "Opened"), T.get("total", "Total")],
            [[t["order_number"], f'{t["area_name"]} - {t["table_label"]}',
              t["opened"], _fmt_money(t["total"])] for t in open_t["tables"]],
        )

    # --- Payment breakdown (also from settled orders)
    payments = get_payment_breakdown(period)
    pdf.section_title(T.get("payment_method", "Payments"))
    pdf.kv_table([
        (T.get("cash_payments", "Cash") + f' ({payments["cash_count"]})', _fmt_money(payments["cash"])),
        (T.get("card_payments", "Card") + f' ({payments["card_count"]})', _fmt_money(payments["card"])),
    ])

    # --- Credit (unpaid in credit area)
    credit = get_credit_summary()
    if credit["count"] > 0:
        pdf.section_title(T.get("credit_area", "Credit area"))
        pdf.kv_table([
            (T.get("credit_tables", "Tables"), str(credit["count"])),
            (T.get("total_credit", "Total credit"), _fmt_money(credit["total"])),
        ])

    # --- Top items
    top = get_top_items(period, 20)
    if top:
        pdf.add_page()
        pdf.section_title(T.get("top_items", "Top items"))
        pdf.grid_table(
            [T.get("item", "Item"), T.get("qty", "Qty"), T.get("price", "Revenue")],
            [[i["name_ar"], str(i["qty"]), _fmt_money(i["revenue"])] for i in top],
            widths=[110, 30, 50],
        )

    # --- By category
    cats = get_sales_by_category(period)
    if cats:
        pdf.section_title(T.get("sales_by_category", "By category"))
        pdf.grid_table(
            [T.get("category", "Category"), T.get("qty", "Qty"), T.get("price", "Revenue")],
            [[c["name_ar"], str(c["qty"]), _fmt_money(c["revenue"])] for c in cats],
            widths=[110, 30, 50],
        )

    # --- By cashier
    cashiers = get_sales_by_cashier(period)
    if cashiers:
        pdf.section_title(T.get("sales_by_cashier", "By cashier"))
        pdf.grid_table(
            [T.get("receipt_cashier", "Cashier"), T.get("order_count", "Orders"), T.get("price", "Revenue")],
            [[c["cashier"], str(c.get("count", c.get("order_count", 0))), _fmt_money(c["revenue"])] for c in cashiers],
            widths=[110, 30, 50],
        )

    # --- By hour
    by_hour = get_sales_by_hour(period)
    if by_hour:
        pdf.section_title(T.get("sales_by_hour", "By hour"))
        pdf.grid_table(
            [T.get("sales_by_hour", "Hour"), T.get("order_count", "Orders"), T.get("price", "Revenue")],
            [[f'{h["hour"]}:00', str(h.get("order_count", h.get("count", 0))), _fmt_money(h["revenue"])] for h in by_hour],
            widths=[80, 50, 60],
        )

    # --- Orders sheet (full log) — separate page so it doesn't crowd above
    orders_sheet = get_all_orders_sheet(period)
    if orders_sheet:
        pdf.add_page()
        pdf.section_title(T.get("orders_sheet", "Orders log"))
        pdf.grid_table(
            [T.get("order_number", "#"), T.get("created_date", "Date"),
             T.get("tables", "Table"), T.get("status", "Status"),
             T.get("payment_method", "Method"), T.get("total", "Total")],
            [[o["order_number"], o.get("created_date", ""),
              f'{o.get("area_name", "")} - {o.get("table_label", "")}'.strip(" -"),
              o.get("status", ""), o.get("method", ""), _fmt_money(o.get("total", 0))]
             for o in orders_sheet],
            widths=[28, 28, 50, 30, 24, 30],
        )

    out = pdf.output(dest="S")
    # fpdf2 v2.x returns bytearray; normalize to bytes
    if isinstance(out, (bytearray, memoryview)):
        return bytes(out)
    if isinstance(out, str):
        return out.encode("latin-1")
    return out
