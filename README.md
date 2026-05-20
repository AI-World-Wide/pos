# Cafe POS

Custom touchscreen Point of Sale for a Dubai cafe. 100% Arabic cashier UI, UAE 5% VAT, AED, ESC/POS receipt printing with cash drawer kick, single-`.exe` deployment to an old Windows 10 1703 Dell.

## Status

**Phase 1 — Skeleton + Data.** Currently delivers: project scaffold, SQLite schema, XLSX seed importer (195 items / 6 categories), placeholder RTL Arabic page. No order taking, printing, or payments yet — those land in Phases 2-3.

## Dev setup (Windows 11, PowerShell)

```powershell
cd D:\POS
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts\import_items.py
python app.py
```

Open <http://127.0.0.1:5000> in any browser.

If `Activate.ps1` is blocked:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Project layout

```
D:\POS\
├── app.py                  Flask entry point
├── config.ini              Editable config (printer, VAT rate, SMTP, cafe info)
├── requirements.txt        Pinned dependencies
├── build.bat               PyInstaller build script (Phase 6)
│
├── src/
│   ├── database.py         SQLAlchemy engine + session + init_db()
│   ├── models.py           Full ORM (items, orders, users, printers, ...)
│   ├── translations/ar.py  Single source of truth for Arabic strings
│   └── routes/cashier.py   Phase 1 placeholder routes
│
├── templates/              Jinja2 templates (RTL Arabic)
├── static/css/             Plain CSS with direction: rtl
├── static/fonts/           Cairo woff2 fonts
│
├── data/
│   ├── pos.db              SQLite database (auto-created, gitignored)
│   ├── backups/            Daily backups (Phase 4+)
│   └── seed/               XLSX seed file
│
└── scripts/
    └── import_items.py     XLSX → SQLite seeder (idempotent)
```

## Conventions

- **UI strings:** 100% Arabic, sourced from `src/translations/ar.py`. No hardcoded Arabic in templates.
- **Code / comments / commits:** English.
- **Prices:** stored as `price_inclusive` (VAT included). Net + VAT derived at order finalization.
- **Dependencies:** every package pinned with `==`.
- **No PostgreSQL connections** — there's another POS on the production Dell using its own PostgreSQL; do not touch it.

## Phases

| Phase | Scope |
|---|---|
| 1 | Skeleton, schema, XLSX import, RTL placeholder |
| 2 | Order taking, cart, totals (no printing) |
| 3 | Receipt + kitchen ticket printing, cash drawer kick |
| 4 | Back office, reports, analytics, daily email, login |
| 5 | Settings UI: cafe name, TRN, printer mapping, SMTP, logo |
| 6 | PyInstaller `.exe`, Edge kiosk shortcut, deploy to Dell |
