@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv (
  echo Once KURULUM.bat dosyasini calistirin.
  pause
  exit /b
)
set PYTHONIOENCODING=utf-8
echo Paketler kontrol ediliyor (ilk seferde tasarim motoru ~150 MB iner)...
.venv\Scripts\python -m pip install -r requirements.txt -q --disable-pip-version-check
.venv\Scripts\python -m playwright install chromium
echo Urun algilama modeli kontrol ediliyor (istege bagli)...
.venv\Scripts\python -m pip install "rembg[cpu]" -q --disable-pip-version-check || echo   rembg kurulamadi, yedek urun algilayici kullanilacak.
start "" http://localhost:8780
.venv\Scripts\python sunucu.py
pause
