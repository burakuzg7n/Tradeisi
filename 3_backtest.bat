@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo ============================================================
echo   TRADEBOT - BACKTEST (2021-2024, tek atis / in-sample)
echo ============================================================
echo.
echo Strateji : sepet_momentum (capraz kesit momentum sepeti)
echo Evren    : 25 sembol, nokta-in-zaman hacim siralamasi
echo Equity   : 10000 USDT
echo Ucret    : maker %0.02 / taker %0.055 / slippage %0.03
echo.
echo ONEMLI: Tek atis protokolu. Bu kosu bir kez yapilir.
echo Sonuc ne cikarsa cikar; parametre degistirilmez.
echo.
python -m trader backtest --strategy sepet_momentum --exchange binance --start 2021-01-01 --end 2024-12-31 --stage insample --equity 10000
echo.
echo Raporlar: out\reports klasorunde (JSON + Markdown)
echo ============================================================
pause
