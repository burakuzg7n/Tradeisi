@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo ============================================================
echo   TRADEBOT - KURULUM (bir kerelik)
echo ============================================================
echo.
echo Gerekli kutuphaneler kuruluyor...
echo.
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo [HATA] pip basarisiz. "py -m pip install -r requirements.txt" deneyin.
  pause
  exit /b 1
)

echo.
echo Kurulum kontrolu yapiliyor...
python -m trader kurulum
echo.
echo ============================================================
echo   KURULUM TAMAM. Sirada: 2_veri_indir.bat
echo ============================================================
pause
