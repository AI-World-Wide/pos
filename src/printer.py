# -*- coding: utf-8 -*-
"""Printer module — Windows spooler + ESC/POS raw bytes.

Handles:
- Windows printer discovery via win32print
- Receipt image printing (Pillow PNG → ESC/POS image bytes)
- Kitchen ticket printing
- Cash drawer kick (ESC p 0 25 250)
- Print queue retry for offline printers

No direct PostgreSQL interaction. No hardcoded printer IPs.
"""
from __future__ import annotations

import configparser
import io
import logging
import struct
import threading
import time

from src.database import SessionLocal, RUNTIME_DIR, CONFIG_PATH as _DB_CONFIG_PATH
from src.models import Order, PrintQueue, Printer

logger = logging.getLogger(__name__)
PROJECT_ROOT = RUNTIME_DIR
CONFIG_PATH = _DB_CONFIG_PATH


def _config() -> configparser.ConfigParser:
    c = configparser.ConfigParser()
    c.read(CONFIG_PATH, encoding="utf-8")
    return c


def discover_printers() -> list[dict]:
    """Enumerate Windows-installed printers."""
    try:
        import win32print
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        printers = win32print.EnumPrinters(flags, None, 2)
        result = []
        for p in printers:
            result.append({
                "name": p["pPrinterName"],
                "status": p.get("Status", 0),
                "port": p.get("pPortName", ""),
            })
        return result
    except ImportError:
        logger.warning("pywin32 not available — printer discovery disabled")
        return []
    except Exception as e:
        logger.error("Printer discovery failed: %s", e)
        return []


def _get_printer_name(purpose: str = "receipt") -> str | None:
    """Get the configured Windows printer name for a given purpose."""
    db = SessionLocal()
    try:
        printer = (
            db.query(Printer)
            .filter(Printer.purpose == purpose, Printer.enabled == True)
            .first()
        )
        if printer:
            return printer.name
    finally:
        db.close()
    cfg = _config()
    return cfg.get("printer", "default_name", fallback="Bar")


def _get_printer_name_strict(purpose: str) -> str | None:
    """Like _get_printer_name but returns None if no printer is mapped for
    the purpose — no fallback to the default printer. Used for the cash
    drawer so the kick doesn't accidentally fire on the wrong device."""
    db = SessionLocal()
    try:
        printer = (
            db.query(Printer)
            .filter(Printer.purpose == purpose, Printer.enabled == True)
            .first()
        )
        return printer.name if printer else None
    finally:
        db.close()


def _send_raw_to_printer(printer_name: str, data: bytes) -> None:
    """Send raw bytes to a Windows printer via the spooler."""
    import win32print
    handle = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(handle, 1, ("POS Print", None, "RAW"))
        win32print.StartPagePrinter(handle)
        win32print.WritePrinter(handle, data)
        win32print.EndPagePrinter(handle)
        win32print.EndDocPrinter(handle)
    finally:
        win32print.ClosePrinter(handle)


def _kick_drawer_bytes() -> bytes:
    """Build ESC/POS cash drawer kick command from config."""
    cfg = _config()
    code_str = cfg.get("printer", "kick_code", fallback="27,112,0,25,250")
    parts = [int(x.strip()) for x in code_str.split(",")]
    return bytes(parts)


def _image_to_escpos_raster(img) -> bytes:
    """Convert a Pillow Image to ESC/POS raster bitmap bytes."""
    from PIL import Image

    # Convert to 1-bit BW
    bw = img.convert("1")
    width, height = bw.size
    # ESC/POS raster: GS v 0
    # Width in bytes = ceil(width/8)
    w_bytes = (width + 7) // 8
    pixels = bw.load()

    buf = io.BytesIO()
    # GS v 0 m xL xH yL yH
    buf.write(b'\x1d\x76\x30\x00')
    buf.write(struct.pack('<HH', w_bytes, height))

    for y in range(height):
        row = bytearray(w_bytes)
        for x in range(width):
            # PIL 1-bit: 0=black, 255=white. ESC/POS: 1=black, 0=white
            if pixels[x, y] == 0:
                row[x // 8] |= (0x80 >> (x % 8))
        buf.write(bytes(row))

    return buf.getvalue()


def _build_cut_command() -> bytes:
    """ESC/POS partial cut."""
    return b'\x1d\x56\x01'  # GS V 1 = partial cut


def print_receipt_and_kick(order_id: int) -> None:
    """Render receipt image, print it, cut, and kick the cash drawer."""
    _queue_print(order_id, "receipt")


def print_kitchen_ticket(order_id: int, line_ids: list[int] | None = None) -> None:
    """Print kitchen ticket for unsent items."""
    _queue_print(order_id, "kitchen", line_ids=line_ids)


def _queue_print(order_id: int, print_type: str, line_ids: list[int] | None = None) -> None:
    """Add to print queue and attempt immediate print."""
    db = SessionLocal()
    try:
        pq = PrintQueue(
            order_id=order_id,
            type=print_type,
            status="pending",
        )
        db.add(pq)
        db.commit()
        pq_id = pq.id
    finally:
        db.close()

    # Attempt immediate print in background thread
    threading.Thread(
        target=_attempt_print,
        args=(pq_id, line_ids),
        daemon=True,
    ).start()


def _attempt_print(pq_id: int, line_ids: list[int] | None = None) -> None:
    """Try to print; on failure, mark for retry."""
    db = SessionLocal()
    try:
        pq = db.get(PrintQueue, pq_id)
        if not pq or pq.status == "printed":
            return

        order = db.get(Order, pq.order_id)
        if not order:
            pq.status = "failed"
            pq.error_message = "Order not found"
            db.commit()
            return

        try:
            if pq.type == "receipt":
                from src.receipt import render_receipt
                img = render_receipt(order, db)
                printer_name = _get_printer_name("receipt")
            else:
                from src.kitchen_ticket import render_kitchen_ticket
                img = render_kitchen_ticket(order, db, line_ids)
                printer_name = _get_printer_name("kitchen") or _get_printer_name("receipt")

            if not printer_name:
                raise RuntimeError("No printer configured")

            data = b'\x1b\x40'  # ESC @ = initialize printer
            data += _image_to_escpos_raster(img)
            data += b'\n\n\n'
            data += _build_cut_command()

            # Kick the cash drawer only for cash payments. Card / credit /
            # other methods must NOT open the drawer.
            kick_drawer = (
                pq.type == "receipt"
                and (order.payment_method or "cash").lower() == "cash"
            )
            kick_data = _kick_drawer_bytes() if kick_drawer else b""

            # If a dedicated "cash_drawer" printer is configured, fire the
            # kick to that printer separately; otherwise piggy-back on the
            # receipt printer.
            drawer_printer = _get_printer_name_strict("cash_drawer") if kick_drawer else None
            if drawer_printer and drawer_printer != printer_name:
                _send_raw_to_printer(printer_name, data)
                _send_raw_to_printer(drawer_printer, kick_data)
            else:
                _send_raw_to_printer(printer_name, data + kick_data)

            pq.status = "printed"
            pq.attempts += 1
            db.commit()

        except Exception as e:
            logger.error("Print failed (pq=%d): %s", pq_id, e)
            pq.status = "failed"
            pq.attempts += 1
            pq.error_message = str(e)[:500]
            db.commit()
    except Exception as e:
        logger.error("Print queue error: %s", e)
    finally:
        db.close()


def retry_failed_prints() -> None:
    """Retry failed prints — called periodically."""
    db = SessionLocal()
    try:
        failed = (
            db.query(PrintQueue)
            .filter(PrintQueue.status == "failed", PrintQueue.attempts < 5)
            .all()
        )
        for pq in failed:
            pq.status = "pending"
            db.commit()
            _attempt_print(pq.id)
    finally:
        db.close()


def _start_retry_loop():
    """Background thread: retry failed prints every 30 seconds."""
    def _loop():
        while True:
            time.sleep(30)
            try:
                retry_failed_prints()
            except Exception as e:
                logger.error("Retry loop error: %s", e)
    t = threading.Thread(target=_loop, daemon=True)
    t.start()
