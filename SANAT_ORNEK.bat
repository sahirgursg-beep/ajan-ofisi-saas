@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo Sanat Yonetmeni 3 yeni sablon tasarliyor (gercek urunlerle)...
.venv\Scripts\python -m pip install -r requirements.txt -q
.venv\Scripts\python -m playwright install chromium
.venv\Scripts\python sanat_ornek.py
pause
