@echo off
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo PLAN B v1 IN-SAMPLE (2020-2024) TEK ATIS kosuluyor. Tekrar kosulamaz.
python scripts\run_planb.py insample
echo.
pause
