@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo ============================================
echo   Ekran karti (NVIDIA) AI kurulumu
echo   Toplam ~10-12 GB indirme. Bir kez yapilir.
echo ============================================
if not exist .venv (
  echo Once KURULUM.bat calistirin.
  pause
  exit /b
)
where nvidia-smi >nul 2>&1
if errorlevel 1 (
  echo NVIDIA surucusu bulunamadi. nvidia.com/drivers adresinden guncel surucuyu kurun.
  pause
  exit /b
)
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
.venv\Scripts\python --version
findstr /r /c:"^version.*= *3\.12" .venv\pyvenv.cfg >nul
if errorlevel 1 (
  echo.
  echo Sanal ortam Python 3.12 degil. Once KURULUM.bat'i calistirin; o 3.12'ye gecirecek.
  pause
  exit /b
)

echo.
echo [1/3] PyTorch (CUDA) kuruluyor ~2.5 GB...
.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cu126 --disable-pip-version-check
if errorlevel 1 (
  echo.
  echo PyTorch kurulamadi. Python surumunuz icin hazir paket olmayabilir.
  echo Bu mesaji ve yukaridaki Python surumunu Claude'a iletin.
  pause
  exit /b
)
echo [2/3] Yapay zeka kutuphaneleri kuruluyor...
.venv\Scripts\python -m pip install numpy diffusers transformers accelerate safetensors spandrel huggingface_hub -q --disable-pip-version-check
if errorlevel 1 (
  echo Kutuphaneler kurulamadi. Hata mesajini Claude'a iletin.
  pause
  exit /b
)

echo [3/3] Modeller indiriliyor (~7 GB, internet hizina gore 10-40 dk)...
.venv\Scripts\python -c "from ofis import ai_gorsel as a; ok,ne=a.durum(); print('Ekran karti:', ne); assert ok; a._esrgan_yukle(); print('Netlestirme modeli hazir'); a._pipe_yukle(); print('Genisletme modeli hazir')"
if errorlevel 1 (
  echo Model indirme/yukleme basarisiz. Hata mesajini Claude'a iletin.
  pause
  exit /b
)
echo.
echo Kurulum tamam! Simdi AI_TEST.bat ile deneyin.
pause
