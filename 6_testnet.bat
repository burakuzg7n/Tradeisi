@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo ============================================================
echo   TRADEBOT - TESTNET (sahte para, gercek para degil)
echo ============================================================
echo.
echo Onceden: .env dosyasinda EXCHANGE_API_KEY ve
echo EXCHANGE_API_SECRET dolu olmali, TRADING_MODE=testnet yazmali.
echo.
echo BYBIT TESTNET API anahtari: https://testnet.bybit.com
echo   - API sekmesinden anahtar olusturun
echo   - "Contract - Orders & Positions" izni verin
echo   - "Withdraw" izni ASLA vermeyin
echo.
echo NOT: Protokol kapisi testnet icin backtest + hold-out
echo gecisini zorunlu kilar. Kapi kapaliysa program reddeder.
echo.
python -m trader canli --strategy sepet_momentum --mode testnet --equity 1000
echo.
pause
