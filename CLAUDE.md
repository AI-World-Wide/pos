# Cafe POS — CLAUDE.md

## What this project is

A custom Point of Sale system for a cafe in Dubai, UAE. The cashier-facing UI is **100% Arabic** — no English text visible to staff. Code, comments, config keys, and developer files remain in English.

## Critical constraints — read before touching anything

### Database isolation
- This app uses **SQLite only** (`data/pos.db`). **NEVER** import, connect to, or reference PostgreSQL in any way. No `psycopg2`, no `pg_*`, no port 5432. The production Dell runs another POS on PostgreSQL — any interference could damage the live system.
- SQLite WAL mode is enabled. Foreign keys enforced at connection time.

### Target hardware
- **Dev machine:** Windows 11, Python 3.11 (`C:\Users\karam\AppData\Local\Programs\Python\Python311\`), plenty of RAM.
- **Production machine:** Dell desktop, **Windows 10 Pro 1703** (build 15063.1418, EOL), Core i5-6600, **4 GB RAM**, touchscreen. Has Edge Chromium. Has PostgreSQL running another POS (DO NOT TOUCH).
- Both are Windows. Never use WSL, `apt`, Linux paths, or bash-only syntax.

### Deployment model
- PyInstaller `--onefile --console` on dev rig → `cafe_pos.exe` (~22 MB)
- Copy `cafe_pos.exe` + `config.ini` + `data/` folder to USB → run on Dell
- When frozen (`sys.frozen`), `sys._MEIPASS` has bundled assets (templates, static, fonts); `data/` lives **next to the .exe**
- `config.ini` next to .exe overrides the bundled one

### Two folders
- **`D:\POS\`** — source code, git repo, dev environment with `.venv`
- **`D:\POS_TEST\`** — standalone test build (exe + config + seeded DB), no Python needed. Run `START.bat` to test.

## Tech stack (locked — do not propose alternatives)

| Layer | Choice |
|---|---|
| Language | Python 3.11 (pinned) |
| Framework | Flask 3.0.3 |
| Database | SQLite via SQLAlchemy 2.0.36 |
| Frontend | Server-rendered HTML + HTMX 1.9.12 + vanilla JS |
| CSS | Plain CSS, `direction: rtl` |
| Fonts | Cairo (woff2 browser, TTF for Pillow receipts) |
| Printing | `pywin32` win32print (spooler) + raw ESC/POS bytes |
| Receipt rendering | Pillow → 576px PNG → ESC/POS raster |
| Packaging | PyInstaller 6.10.0 `--onefile --console` |

All deps pinned with `==` in `requirements.txt`.

## Project structure

```
D:\POS\
├── app.py                  Flask entry + PyInstaller frozen-path handling
├── config.ini              Operator-editable config
├── requirements.txt        Pinned deps
├── build.bat / install_on_dell.bat
│
├── src/
│   ├── database.py         SQLAlchemy engine + session (SQLite only, frozen-aware paths)
│   ├── models.py           ORM: Category, Item, Order, OrderLine, User, Permission,
│   │                       Printer, Area, FloorTable, Shift, Setting, PrintQueue
│   ├── printer.py          Win32 printer discovery + ESC/POS + print queue + retry
│   ├── receipt.py          Pillow receipt renderer (576px, Cairo font, QR)
│   ├── kitchen_ticket.py   Kitchen ticket renderer (non-beverage items only)
│   ├── reports.py          Analytics queries (sales, categories, hours, cashiers,
│   │                       payment breakdown, credit summary, daily trend, orders log)
│   ├── email_report.py     Gmail OAuth2 (XOAUTH2 SMTP) email reports
│   ├── seed_users.py       5 default users + permission matrix
│   ├── seed_tables.py      5 areas (3×15 tables + 6 cabins + credit area)
│   ├── translations/ar.py  ALL Arabic UI strings — templates NEVER hardcode Arabic
│   └── routes/
│       ├── auth.py         PIN login/logout (numpad UI)
│       ├── cashier.py      3-panel POS: categories | items | order cart (HTMX)
│       ├── tables.py       Floor plan: areas, table grid, open/split/move/close
│       ├── shift.py        Day open/close with cash counts
│       ├── backoffice.py   Item CRUD + XLSX re-import
│       ├── reports.py      Reports/analytics page
│       └── settings.py     Cafe config, printers, users, permissions, Gmail OAuth2
│
├── templates/              Jinja2 (RTL Arabic, `{{ t.key }}` for strings)
│   ├── partials/           HTMX fragments (order panel, items grid, modals)
│   └── ...
│
├── static/css/             main.css (global), cashier.css (3-panel POS layout)
├── static/js/              htmx.min.js, cashier.js (timers, auto-scroll)
├── static/fonts/           Cairo Arabic + Latin woff2
│
├── data/
│   ├── pos.db              SQLite (gitignored, auto-created)
│   ├── seed/               XLSX item list (195 items, 6 categories)
│   └── backups/
│
└── scripts/
    ├── import_items.py     XLSX → SQLite (idempotent)
    ├── backup_db.py        Daily backup
    └── test_printer.py     Printer test
```

## Key design decisions

### VAT model — inclusive
`items.price_inclusive` = what the customer pays (includes 5% VAT). At order close:
```
total = sum(line.price_inclusive * qty)
subtotal = round(total / 1.05, 2)
vat_amount = total - subtotal
```

### Order numbers
Format: `dd/mm/yyyy-NNNN` (e.g. `22/05/2026-0001`). Sequential per day.

### Tables / Floor plan
- 5 seeded areas: منطقة 1 (15), منطقة 2 (15), منطقة 3 (15), الكبائن (6), الآجل (credit, dynamic)
- Tables show just the number (e.g. "5"), no prefix text
- Table name in cashier view: "منطقة 1 - 5"
- Opening a table does NOT create an order — order is only created when the first item is added (`pending_table_id` in session)
- Live timer on table cards (elapsed from `order.created_at`, format `HH:MM:SS`, persists across restarts)
- Drag-and-drop transfer: drag occupied → drop on free (any area)
- Move dropdown in cashier order panel (lists all free tables across all areas)
- Split items: select items → move to another table OR partial pay (redirects to payment modal)
- Credit area: dynamic table slots, yellow banner showing total unpaid

### Shift management
- Admin opens day (enters opening cash) → shift tracks all orders
- Cannot close day if tables are still occupied
- Closing triggers email report if configured
- Past shifts listed with full stats

### Permissions
- Admin: full access (add/delete items, void, edit prices, manage users/settings/printers)
- Cashier: take orders, send to kitchen, take payment, view reports
- Waiter: take orders, send to kitchen only
- Delete/void/price-edit buttons are admin-only in the UI

### Printing
- Windows printer auto-discovery via `win32print.EnumPrinters()`
- Printer→purpose mapping in Settings (receipt / kitchen / shisha)
- Receipt: Pillow PNG → ESC/POS raster → `win32print.WritePrinter()`
- Cash drawer kick: raw ESC/POS bytes after receipt cut
- Print queue with 30-second background retry for offline printers

### Email
- Gmail OAuth2 (XOAUTH2 SMTP) — credentials stored in Settings DB, NOT in files
- Configurable: which sections to include, recipients list, triggers (on day close / daily)
- OAuth callback: `http://localhost:5000/settings/oauth-callback`

## How to run (development)

```powershell
cd D:\POS
.\.venv\Scripts\Activate.ps1
python scripts\import_items.py   # first time only
python app.py
# → http://127.0.0.1:5000  (admin / PIN 9999)
```

## How to build and deploy

```powershell
cd D:\POS
.\.venv\Scripts\Activate.ps1
.\build.bat
# Output: dist\cafe_pos.exe
# Copy dist\ + config.ini + data\ to D:\POS_TEST\ or USB
```

## Default accounts

| User | PIN | Role |
|---|---|---|
| المدير (admin) | 9999 | Admin |
| كاشير 1 | 1111 | Cashier |
| كاشير 2 | 2222 | Cashier |
| نادل 1 | 3333 | Waiter |
| نادل 2 | 4444 | Waiter |

## Rules for Claude Code

1. **SQLite only.** Never import or reference PostgreSQL.
2. **Pin every dep** with `==`. No "latest" on Win10 1703.
3. **Arabic strings in `ar.py` only.** No hardcoded Arabic in templates.
4. **Test PyInstaller frozen paths** — any new file path must handle `sys.frozen`.
5. **Touch-optimized** — buttons ≥80px, text ≥18px, no hover-only interactions.
6. **No internet required** — everything offline except email at send time.
7. **4 GB RAM budget** — no heavy deps, no React/Vue.
8. **Windows commands only** — PowerShell / cmd.exe. No bash, no WSL.
9. **Commit messages in English.** UI strings in Arabic.
10. **Errors to `data/error.log`** — never show Python tracebacks to staff.
11. **After code changes**: rebuild exe (`build.bat`), copy to `D:\POS_TEST\`, reseed DB if schema changed.
12. **Order panel keys**: always include `table_id`, `table_info`, `move_targets`, `opened_at` in `_get_order_view_data()` return dict — templates depend on them.
