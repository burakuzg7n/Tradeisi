@echo off
cd /d "%~dp0"
if not exist .env (
  echo HATA: .env dosyasi yok. KURULUM.md Adim 4.
  pause
  exit /b 1
)
echo Demo calistirici basliyor (durdurmak icin Ctrl+C)...
python scripts/live_runner.py
pause
