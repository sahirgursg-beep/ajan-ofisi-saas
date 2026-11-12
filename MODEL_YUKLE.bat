@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   Yapay zeka dil modeli yukleniyor
echo ============================================
set "OLLAMA="
where ollama >nul 2>&1 && set "OLLAMA=ollama"
if not defined OLLAMA if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not defined OLLAMA (
  echo Ollama bulunamadi. Indirme sayfasi aciliyor; kurup bu dosyayi tekrar calistirin.
  start "" https://ollama.com/download/windows
  pause
  exit /b
)
for /f "delims=" %%m in ('.venv\Scripts\python -c "import json;print(json.load(open('config.json',encoding='utf-8'))['model'])"') do set "MODEL=%%m"
echo Model: %MODEL%  (yaklasik 4-5 GB, internet hizina gore surebilir)
"%OLLAMA%" pull %MODEL%
echo.
"%OLLAMA%" list
echo.
echo Bitti. Ofis ekranini (BASLAT.bat) kapatip yeniden acin.
pause
