@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo ============================================================
echo   TRADEBOT - PAPER TRADING (GERCEK PARA YOK)
echo ============================================================
echo.
echo Borsadan SADECE fiyat verisi okunur.
echo Emirler simule edilir - hicbir para harcanmaz.
echo Panel: http://127.0.0.1:8765  (5_panel.bat ile de acilabilir)
echo.
echo Durdurmak icin bu pencereyi kapatin veya Ctrl+C.
echo.
python -m trader paper --strategy sepet_momentum --exchange binance --equity 1000
echo.
echo Paper motoru durdu.
pause
