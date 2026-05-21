# Cafe POS — CLAUDE.md

## What this project is

A custom Point of Sale system for a cafe in Dubai, UAE. The cashier-facing UI is **100% Arabic** — no English text visible to staff. Code, comments, config keys, and developer files remain in English.

## Critical constraints — read before touching anything

### Database isolation
- This app uses **SQLite only** (`data/pos.db`). No PostgreSQL.
- The production Dell has another POS running on PostgreSQL. **Never** import, connect to, or reference PostgreSQL in any way. No `psycopg2`, no `pg_*`, no port 5432. If you accidentally introduce a PostgreSQL dependency, it could conflict with or damage the existing live POS system.
- SQLite WAL mode is enabled. Foreign keys are enforced at connection time.

### Target hardware
- **Dev machine:** Windows 11, Python 3.11 (`C:\Users\karam\AppData\Local\Programs\Python\Python311\`), plenty of RAM. VS Code "Antigravity" fork.
- **Production machine:** Dell desktop, **Windows 10 Pro 1703** (build 15063.1418, EOL), Core i5-6600, **4 GB RAM**, touchscreen. Has Edge Chromium installed. Has Java 8 (ignore it). Has PostgreSQL running another POS (DO NOT TOUCH).
- Both are Windows. Never use WSL, `apt`, Linux paths, or bash-only syntax. All commands must work in PowerShell or `cmd.exe`.

### Deployment model
- PyInstaller `--onefile --windowed` on the dev rig → single `cafe_pos.exe` (~22 MB)
- Copy `cafe_pos.exe` + `config.ini` + `data/` folder to USB → run on the Dell
- `install_on_dell.bat` handles: copy to `C:\CafePOS\`, Edge kiosk shortcut, Startup auto-launch, daily backup task
- **No Python runtime needed on the Dell** — the .exe is fully self-contained

### PyInstaller frozen paths
- When running as a `.exe`, `sys._MEIPASS` contains bundled assets (templates, static, fonts, config.ini)
- `data/` directory (pos.db, backups, seed XLSX) lives **next to the .exe**, not inside `_MEIPASS`
- `config.ini` next to the .exe overrides the bundled one (operator can edit it)
- All modules that reference files must check `getattr(sys, "frozen", False)` — see `app.py` and `src/database.py` for the pattern

## Tech stack (locked — do not propose alternatives)

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11 (pinned) | Win10 1703 compatible, no 3.12+ |
| Framework | Flask 3.0.3 | Lightweight for 4 GB RAM |
| Database | SQLite via SQLAlchemy 2.0.36 | File-based, no service, no PostgreSQL conflict |
| Frontend | Server-rendered HTML + HTMX 1.9.12 + vanilla JS | No React/Vue — too heavy |
| CSS | Plain CSS, `direction: rtl` | Native Arabic support |
| Fonts | Cairo (woff2 for browser, TTF for Pillow) | Arabic rendering offline |
| Printing | `pywin32` win32print (spooler) + raw ESC/POS bytes | Windows printer discovery + thermal receipt |
| Receipt rendering | Pillow → 576px PNG → ESC/POS raster | Guaranteed Arabic on thermal paper |
| Packaging | PyInstaller 6.10.0 `--onefile --windowed` | Single .exe, no runtime install |

All deps pinned with `==` in `requirements.txt`. Do not upgrade without testing on Win10 1703.

## Project structure

```
D:\POS\
├── app.py                  Flask entry + PyInstaller frozen-path handling
├── config.ini              Operator-editable config
├── requirements.txt        Pinned deps
├── build.bat               PyInstaller build script
├── install_on_dell.bat     Production deployment script
├── CLAUDE.md               This file
│
├── src/
│   ├── database.py         SQLAlchemy engine + session (SQLite only)
│   ├── models.py           ORM: Category, Item, Order, OrderLine, User, Permission, Printer, etc.
│   ├── printer.py          Win32 printer discovery + ESC/POS raw bytes + print queue
│   ├── receipt.py          Pillow receipt renderer (576px, Cairo font, QR)
│   ├── kitchen_ticket.py   Kitchen ticket renderer (non-beverage items only)
│   ├── reports.py          Sales/VAT analytics queries (SQLite only)
│   ├── email_report.py     SMTP daily summary (smtplib, no extra deps)
│   ├── seed_users.py       5 default users + permission matrix seeder
│   ├── translations/ar.py  ALL Arabic strings — templates never hardcode Arabic
│   └── routes/
│       ├── auth.py         PIN login/logout
│       ├── cashier.py      POS screen + HTMX order management
│       ├── backoffice.py   Item CRUD + XLSX re-import
│       ├── reports.py      Reports/analytics endpoints
│       └── settings.py     Cafe config, printers, users, permissions
│
├── templates/              Jinja2 (RTL Arabic, references `t.<key>` for strings)
│   ├── partials/           HTMX partial renders (order panel, items grid, modals)
│   └── ...
│
├── static/
│   ├── css/main.css        Global RTL styles + Cairo @font-face
│   ├── css/cashier.css     3-panel POS layout
│   ├── js/htmx.min.js     HTMX (bundled offline)
│   ├── js/cashier.js       Minimal POS helpers
│   └── fonts/              Cairo Arabic + Latin woff2
│
├── data/
│   ├── pos.db              SQLite database (gitignored, auto-created)
│   ├── backups/            Daily DB copies
│   └── seed/               XLSX item list
│
└── scripts/
    ├── import_items.py     XLSX → SQLite (idempotent)
    ├── backup_db.py        Daily backup utility
    └── test_printer.py     Standalone printer test
```

## Key design decisions

### VAT model — inclusive
Prices in the database (`items.price_inclusive`) are what the customer pays. They include 5% UAE VAT. Net + VAT are derived at order finalization:
```
total = sum(line.price_inclusive * qty)
subtotal = round(total / 1.05, 2)
vat_amount = total - subtotal
```
The cashier UI shows the sticker price. Receipts break out subtotal + VAT + total.

### Printers — Windows spooler, not TCP
The brief originally said "one IP in config.ini." The owner wants multi-printer with Windows auto-discovery. We use `win32print.EnumPrinters()` to find installed printers, then `win32print.WritePrinter()` to send raw ESC/POS bytes. Cash drawer kick is `ESC p 0 25 250` sent as raw bytes after the receipt cut.

### Users and permissions
5 seeded accounts (admin + 2 cashiers + 2 waiters). PIN-hashed login. Permission matrix (10 keys × 3 roles) editable in admin settings. Orders record who rang them up (`orders.cashier`).

### Arabic strings
Every Arabic string visible to users lives in `src/translations/ar.py` as a single dict `T`. Templates access it via `{{ t.key_name }}`. Never hardcode Arabic in templates or Python code outside `ar.py`.

## How to run (development)

```powershell
cd D:\POS
.\.venv\Scripts\Activate.ps1
python scripts\import_items.py   # first time only
python app.py
# → http://127.0.0.1:5000  (login: admin / 9999)
```

## How to build the .exe

```powershell
cd D:\POS
.\.venv\Scripts\Activate.ps1
.\build.bat
# Output: dist\cafe_pos.exe + dist\config.ini + dist\data\
```

## How to deploy to the Dell

1. Copy `dist\` folder contents to USB
2. On the Dell: copy to `C:\CafePOS\`
3. Run `install_on_dell.bat` (creates shortcuts, scheduled backup)
4. Reboot → POS auto-starts → Edge opens in kiosk mode

## Testing standalone (without Python)

A ready-to-run test build lives in `D:\POS_TEST\`:
```
D:\POS_TEST\
├── cafe_pos.exe         (double-click or run START.bat)
├── config.ini           (editable)
├── START.bat            (convenience launcher)
└── data\
    ├── pos.db           (pre-seeded: 195 items, 6 categories, 5 users)
    ├── seed\            (XLSX)
    └── backups\
```

## Rules for Claude Code

1. **SQLite only.** Never import or reference PostgreSQL.
2. **Pin every dep** with `==`. No "latest" surprises on Win10 1703.
3. **Arabic strings in `ar.py` only.** No hardcoded Arabic in templates.
4. **Test PyInstaller frozen paths** — any new file path must handle `sys.frozen`.
5. **Touch-optimized** — buttons ≥80px, text ≥18px, no hover-only interactions.
6. **No internet required** — everything offline. Email only at scheduled send time.
7. **4 GB RAM budget** — no heavy deps, no React/Vue, no large in-memory structures.
8. **Windows commands only** — PowerShell / cmd.exe. No bash, no WSL, no apt.
9. **Commit messages in English.** UI strings in Arabic.
10. **Errors to `data/error.log`** — never show Python tracebacks to staff.
