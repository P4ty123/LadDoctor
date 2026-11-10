@echo off
chcp 65001 >nul
cd /d "%~dp0"
title LagDoctor

rem Servono i permessi di amministratore per misurare i frame
net session >nul 2>nul
if errorlevel 1 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

where python >nul 2>nul
if errorlevel 1 (
    echo Python non e' installato. Lo installo ora con winget...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    echo.
    echo Python installato. CHIUDI questa finestra e fai di nuovo doppio clic su AVVIA.bat
    pause
    exit /b
)

python -c "import psutil" >nul 2>nul
if errorlevel 1 (
    echo Installo il componente psutil, solo la prima volta...
    python -m pip install --quiet psutil
)

python -m lagdoctor.main
pause
