@echo off
cd /d "%~dp0"
if not exist data\BTCUSDT_15m.csv (
  echo Veri yok, once 2_backtest.bat calistir.
  pause
  exit /b 1
)
echo Mevcut veriyle backtest kosuluyor (indirme YOK)...
python scripts/run_backtest.py
pause
