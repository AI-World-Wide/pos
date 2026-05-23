@echo off
REM ============================================================
REM Cafe POS — PyInstaller build script
REM Run from project root: build.bat
REM Output: dist\cafe_pos.exe + dist\data\ folder
REM ============================================================

echo [1/4] Activating virtual environment...
call .venv\Scripts\activate.bat

echo [2/4] Cleaning previous build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/4] Running PyInstaller...
pyinstaller --noconfirm ^
    --onefile ^
    --windowed ^
    --name cafe_pos ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --add-data "config.ini;." ^
    --add-data "data\seed;data\seed" ^
    --hidden-import=src ^
    --hidden-import=src.database ^
    --hidden-import=src.models ^
    --hidden-import=src.printer ^
    --hidden-import=src.receipt ^
    --hidden-import=src.kitchen_ticket ^
    --hidden-import=src.reports ^
    --hidden-import=src.email_report ^
    --hidden-import=src.seed_users ^
    --hidden-import=src.translations ^
    --hidden-import=src.translations.ar ^
    --hidden-import=src.routes ^
    --hidden-import=src.routes.auth ^
    --hidden-import=src.routes.cashier ^
    --hidden-import=src.routes.backoffice ^
    --hidden-import=src.routes.reports ^
    --hidden-import=src.routes.settings ^
    --hidden-import=src.routes.shift ^
    --hidden-import=src.routes.tables ^
    --hidden-import=src.seed_tables ^
    --hidden-import=win32print ^
    --hidden-import=win32api ^
    app.py

if errorlevel 1 (
    echo.
    echo BUILD FAILED — check the output above for errors.
    pause
    exit /b 1
)

echo [4/4] Copying data folder...
if not exist dist\data mkdir dist\data
if not exist dist\data\seed mkdir dist\data\seed
if not exist dist\data\backups mkdir dist\data\backups
copy "data\seed\Item List_20-05-2026.xlsx" "dist\data\seed\" >nul
copy config.ini dist\ >nul

echo.
echo ============================================================
echo BUILD COMPLETE
echo.
echo Output:
echo   dist\cafe_pos.exe     (main executable)
echo   dist\config.ini       (editable configuration)
echo   dist\data\seed\       (XLSX seed file)
echo   dist\data\backups\    (daily backup folder)
echo.
echo To deploy:
echo   1. Copy dist\ folder to USB
echo   2. On the Dell: copy to C:\CafePOS\
echo   3. Run install_on_dell.bat
echo ============================================================
pause
