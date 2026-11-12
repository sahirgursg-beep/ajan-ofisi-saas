@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   Ajan Ofisi SaaS (gelistirme) - Kurulum (Python 3.12)
echo ============================================
rem Yapay zeka paketleri en yeni Python (3.14/3.15) icin henuz hazir degil; proje 3.12 ile calisir.

rem ---------- 1) Python 3.12 ----------
set "PY="
py -3.12 --version >nul 2>&1 && set "PY=py -3.12"
if not defined PY (
  echo [1/5] Python 3.12 kuruluyor ^(mevcut Python'unuza dokunulmaz^)...
  py install 3.12
  py -3.12 --version >nul 2>&1 && set "PY=py -3.12"
)
if not defined PY (
  echo.
  echo   Python 3.12 otomatik kurulamadi. Indirme sayfasi aciliyor:
  echo     "Python 3.12.x" icin "Windows installer (64-bit)" dosyasini indirip kurun.
  echo     Kurulumdan sonra bu pencereyi kapatip KURULUM.bat'i tekrar calistirin.
  start "" https://www.python.org/downloads/windows/
  pause
  exit /b
)
echo [1/5] Python hazir:
%PY% --version

rem ---------- 2) Sanal ortam (eski surumle kurulduysa yenisi acilir) ----------
if exist .venv\pyvenv.cfg (
  findstr /r /c:"^version.*= *3\.12" .venv\pyvenv.cfg >nul
  if errorlevel 1 (
    echo [2/5] Eski sanal ortam baska Python surumuyle kurulmus, yenisi aciliyor...
    if exist .venv_eski rmdir /s /q .venv_eski
    ren .venv .venv_eski
  )
)
if not exist .venv\Scripts\python.exe (
  echo [2/5] Sanal ortam olusturuluyor...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Sanal ortam olusturulamadi.
    pause
    exit /b
  )
)

rem ---------- 3) Paketler ----------
echo [3/5] Paketler yukleniyor...
.venv\Scripts\python -m pip install --upgrade pip -q
.venv\Scripts\python -m pip install -r requirements.txt -q --disable-pip-version-check
if errorlevel 1 (
  echo Paket kurulumu basarisiz oldu. Hata mesajini Claude'a iletin.
  pause
  exit /b
)
echo        Tasarim motoru (Chromium)...
.venv\Scripts\python -m playwright install chromium
echo        Urun algilama modeli (rembg)...
.venv\Scripts\python -m pip install "rembg[cpu]" -q --disable-pip-version-check || echo   rembg kurulamadi, yedek algilayici kullanilacak.

rem ---------- 4) Ollama + model ----------
set "OLLAMA="
where ollama >nul 2>&1 && set "OLLAMA=ollama"
if not defined OLLAMA if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not defined OLLAMA (
  echo [4/5] Ollama bulunamadi. Indirme sayfasi aciliyor, kurup bu dosyayi tekrar calistirin.
  start "" https://ollama.com/download/windows
  pause
  exit /b
)
for /f "delims=" %%m in ('.venv\Scripts\python -c "import json;print(json.load(open('config.json',encoding='utf-8'))['model'])"') do set "MODEL=%%m"
echo [4/5] Yapay zeka dil modeli kontrol ediliyor: %MODEL%
"%OLLAMA%" pull %MODEL%

rem ---------- 5) Son kontrol ----------
echo [5/5] Kontrol...
.venv\Scripts\python -c "import numpy, PIL, playwright, requests; print('Temel paketler tamam')"
echo.
echo ============================================
echo   Kurulum tamam!
echo   Ekran karti AI'si icin simdi AI_KURULUM.bat calistirin.
if exist .venv_eski echo   ^(Eski .venv_eski klasorunu artik silebilirsiniz, ~3 GB yer acar.^)
echo ============================================
pause
