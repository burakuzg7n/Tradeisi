@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo ============================================================
echo   TRADEBOT - WEB PANELI
echo ============================================================
echo.
echo Panel adresi: http://127.0.0.1:8765
echo.
echo Tarayicida acmak icin 5 saniye bekleyip asagidaki baglantiya tiklayin.
echo Paneli kapatmak icin bu pencereyi kapatin.
echo.
start "" http://127.0.0.1:8765
python -m trader dashboard
pause
