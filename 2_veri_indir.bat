@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo ============================================================
echo   TRADEBOT - VERI INDIRME
echo ============================================================
echo.
echo Borsa: Binance (public API, anahtar gerekmez)
echo Donem: 2021-01-01 -> bugun
echo Sembol sayisi: 26
echo.
echo Bu islem birkac dakika surer. Veri "data" klasorune kaydedilir.
echo.
python -m trader veri --exchange binance --timeframe 1d --start 2021-01-01 --funding
if errorlevel 1 (
  echo.
  echo [HATA] Veri indirilemedi. Internet baglantinizi kontrol edin.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo   VERI HAZIR. Sirada: 3_backtest.bat
echo ============================================================
pause
