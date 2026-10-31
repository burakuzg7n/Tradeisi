@echo off
cd /d "%~dp0"
echo V2 IN-SAMPLE (2020-2024) TEK ATIS kosuluyor. Tekrar kosulamaz.
python scripts/run_v2.py insample
pause
