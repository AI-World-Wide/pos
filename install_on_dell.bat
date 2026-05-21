@echo off
REM ============================================================
REM Cafe POS — Dell deployment installer
REM Run this on the production Dell (Windows 10 1703)
REM Creates C:\CafePOS\, Edge kiosk shortcut, auto-start
REM ============================================================

set INSTALL_DIR=C:\CafePOS
set SHORTCUT_NAME=Cafe POS

echo [1/5] Creating install directory...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%INSTALL_DIR%\data" mkdir "%INSTALL_DIR%\data"
if not exist "%INSTALL_DIR%\data\seed" mkdir "%INSTALL_DIR%\data\seed"
if not exist "%INSTALL_DIR%\data\backups" mkdir "%INSTALL_DIR%\data\backups"

echo [2/5] Copying files...
copy /y cafe_pos.exe "%INSTALL_DIR%\" >nul
copy /y config.ini "%INSTALL_DIR%\" >nul
if exist "data\seed\Item List_20-05-2026.xlsx" (
    copy /y "data\seed\Item List_20-05-2026.xlsx" "%INSTALL_DIR%\data\seed\" >nul
)

echo [3/5] Creating desktop shortcut for Edge kiosk mode...
REM Edge kiosk opens http://127.0.0.1:5000 in fullscreen
set EDGE_PATH="C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not exist %EDGE_PATH% set EDGE_PATH="C:\Program Files\Microsoft\Edge\Application\msedge.exe"

powershell -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $sc = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\%SHORTCUT_NAME%.lnk'); ^
   $sc.TargetPath = %EDGE_PATH%; ^
   $sc.Arguments = '--kiosk http://127.0.0.1:5000 --edge-kiosk-type=fullscreen --no-first-run'; ^
   $sc.WorkingDirectory = '%INSTALL_DIR%'; ^
   $sc.Save()"

echo [4/5] Creating startup shortcut (auto-start on boot)...
REM Place cafe_pos.exe shortcut in Startup folder so the server starts on boot
powershell -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $startup = $ws.SpecialFolders('Startup'); ^
   $sc = $ws.CreateShortcut($startup + '\CafePOS Server.lnk'); ^
   $sc.TargetPath = '%INSTALL_DIR%\cafe_pos.exe'; ^
   $sc.WorkingDirectory = '%INSTALL_DIR%'; ^
   $sc.WindowStyle = 7; ^
   $sc.Save()"

echo [5/5] Creating daily backup scheduled task...
REM Backs up pos.db every night at midnight via Task Scheduler
schtasks /create /tn "CafePOS Daily Backup" /tr "copy /y \"%INSTALL_DIR%\data\pos.db\" \"%INSTALL_DIR%\data\backups\pos-%%date:~-4,4%%-%%date:~-7,2%%-%%date:~-10,2%%.db\"" /sc daily /st 00:00 /f >nul 2>&1

echo.
echo ============================================================
echo INSTALLATION COMPLETE
echo.
echo What was set up:
echo   - Files installed to %INSTALL_DIR%
echo   - Desktop shortcut "%SHORTCUT_NAME%" (Edge kiosk mode)
echo   - Auto-start server on Windows boot
echo   - Daily database backup at midnight
echo.
echo To start now:
echo   1. Double-click cafe_pos.exe in %INSTALL_DIR%
echo   2. Wait 3 seconds for the server to start
echo   3. Double-click the "%SHORTCUT_NAME%" desktop shortcut
echo.
echo First-time setup:
echo   - Open http://127.0.0.1:5000 in any browser
echo   - Login as admin (PIN: 9999)
echo   - Go to Settings to configure printer and cafe info
echo   - Run the item importer if the menu needs refreshing
echo ============================================================
pause
