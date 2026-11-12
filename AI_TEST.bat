@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo AI testi: 2 urun fotografi netlestirilip dikeye tamamlanacak (her biri ~1-2 dk)...
.venv\Scripts\python ai_test.py
pause
