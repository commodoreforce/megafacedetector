@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Prima lancia "Installa_Windows.bat".
  pause
  exit /b 1
)
.venv\Scripts\python smista.py
pause
