@echo off
cd /d "%~dp0"
echo Kutuphaneler kuruluyor...
python -m pip install -r requirements.txt
if errorlevel 1 py -m pip install -r requirements.txt
echo.
echo KURULUM TAMAM.
pause
