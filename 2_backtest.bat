@echo off
cd /d "%~dp0"
echo Veri indiriliyor (2020+, BTC+ETH, ~10 dk)...
python scripts/download_data.py 2020-01-01
echo.
echo Backtest kosuluyor...
python scripts/run_backtest.py
pause
