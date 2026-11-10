@echo off
chcp 65001 >nul
cd /d "%~dp0"
title LagDoctor - Autodiagnosi (sola lettura)

rem Servono i permessi di amministratore per leggere tutte le impostazioni e per PresentMon
net session >nul 2>nul
if errorlevel 1 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

where python >nul 2>nul
if errorlevel 1 (
    echo Python non e' installato: avvia prima AVVIA.bat una volta.
    pause
    exit /b
)

python -c "import psutil" >nul 2>nul
if errorlevel 1 (
    echo Manca il componente psutil: avvia prima AVVIA.bat una volta.
    pause
    exit /b
)

python autodiagnosi.py
echo.
pause
