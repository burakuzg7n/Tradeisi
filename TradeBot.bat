@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

:MENU
cls
echo ============================================================
echo               TRADEBOT - MENU
echo ============================================================
echo.
echo   1) Kurulum kontrolu
echo   2) Veri indir (Binance, gunluk, 25 sembol)
echo   3) Backtest (2021-2024, tek atis)
echo   4) Paper trading (gercek para yok)
echo   5) Web paneli
echo   6) Testnet (sahte para)
echo   7) Anlik durum
echo   8) Protokol kapilari
echo.
echo   0) Cikis
echo.
set /p choice="Seciminiz (0-8): "

if "%choice%"=="1" call :run 1_kurulum.bat
if "%choice%"=="2" call :run 2_veri_indir.bat
if "%choice%"=="3" call :run 3_backtest.bat
if "%choice%"=="4" call :run 4_paper.bat
if "%choice%"=="5" call :run 5_panel.bat
if "%choice%"=="6" call :run 6_testnet.bat
if "%choice%"=="7" python -m trader durum & pause
if "%choice%"=="8" python -m trader kapilar & pause
if "%choice%"=="0" exit /b 0
goto MENU

:run
call %1
goto MENU
