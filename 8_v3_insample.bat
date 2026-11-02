@echo off
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo V3 IN-SAMPLE (2021-2024) TEK ATIS kosuluyor. Tekrar kosulamaz. Birkac dakika surebilir.
python scripts\run_v3.py insample
echo.
pause
