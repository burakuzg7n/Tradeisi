@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

:MENU
cls
echo ============================================================
echo            FUZYON ARENA - KAGIT ISLEM (gercek emir yok)
echo ============================================================
python -m fusion aralik
echo.
echo   1) Kurulum (bir kerelik)
echo   2) Veri indir / guncelle (Binance, anahtar gerekmez)
echo   3) Backtest + panel
echo   4) CANLI kagit islem + panel (pencere acik kaldikca calisir)
echo   5) Yalniz panel
echo   6) Durum tablosu
echo   7) Demo (internetsiz, sentetik veri)
echo   8) Ayar dosyasi olustur
echo   9) Mum araligini sec (scalp: 1m 3m 5m 10m 15m / diger: 30m 1h 2h 4h 1d)
echo.
echo   0) Cikis
echo.
set "choice="
set /p choice="Seciminiz (0-9): "

if "%choice%"=="1" (python -m pip install numpy & python -m fusion kontrol & pause)
if "%choice%"=="2" (python -m fusion veri & pause)
if "%choice%"=="3" (python -m fusion backtest --panel & pause)
if "%choice%"=="4" (python -m fusion veri & python -m fusion canli & pause)
if "%choice%"=="5" (python -m fusion panel)
if "%choice%"=="6" (python -m fusion durum & pause)
if "%choice%"=="7" (python -m fusion demo & pause)
if "%choice%"=="8" (python -m fusion ayar & pause)
if "%choice%"=="9" goto ARALIK
if "%choice%"=="0" exit /b 0
goto MENU

:ARALIK
echo.
echo   Secenekler: 1m 3m 5m 10m 15m 30m 1h 2h 4h 1d
set "ar="
set /p ar="Aralik yazin (ornek 5m): "
if not "%ar%"=="" python -m fusion aralik %ar%
pause
goto MENU
