@echo off
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo V3 veri indiriliyor: 5 coin, 15 dakika (sadece veri, strateji calismaz)...
python scripts\download_v3.py
echo.
pause
