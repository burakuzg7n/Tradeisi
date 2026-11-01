@echo off
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo Plan B gunluk veri indiriliyor (sadece veri, strateji calismaz)...
python scripts\download_daily.py
if errorlevel 9009 py scripts\download_daily.py
echo.
pause
