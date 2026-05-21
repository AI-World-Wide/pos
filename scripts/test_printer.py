# -*- coding: utf-8 -*-
"""Standalone printer test — sends a test page to the configured Windows printer.

Run:  python scripts/test_printer.py
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.printer import _get_printer_name, _send_raw_to_printer, _build_cut_command, discover_printers


def main():
    print("=== Cafe POS Printer Test ===\n")

    print("Discovering Windows printers...")
    printers = discover_printers()
    if printers:
        for p in printers:
            print(f"  Found: {p['name']} (port: {p['port']})")
    else:
        print("  No printers found.")

    printer_name = _get_printer_name("receipt")
    print(f"\nConfigured receipt printer: {printer_name}")

    if not printer_name:
        print("ERROR: No printer configured. Check config.ini or settings.")
        return

    print(f"Sending test print to '{printer_name}'...")
    try:
        data = b'\x1b\x40'  # ESC @ = initialize
        data += b'\x1b\x61\x01'  # center align
        data += b'\n'
        data += "=== Cafe POS ===\n".encode("cp437", errors="replace")
        data += "Printer Test OK\n".encode("cp437", errors="replace")
        data += "Arabic: Test\n".encode("cp437", errors="replace")
        data += "\n\n\n".encode()
        data += _build_cut_command()

        _send_raw_to_printer(printer_name, data)
        print("SUCCESS — test page sent.")
    except Exception as e:
        print(f"FAILED: {e}")


if __name__ == "__main__":
    main()
