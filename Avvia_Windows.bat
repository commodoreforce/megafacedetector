@echo off
rem Smista Foto - avvio. Tieni aperta questa finestra finche' usi l'app.
chcp 65001 >nul
title Smista Foto (lascia aperta questa finestra)
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Smista Foto non e' ancora installato su questo computer.
  echo Fai doppio clic su "Installa_Windows.bat", in questa stessa cartella.
  pause
  exit /b 1
)
.venv\Scripts\python smista.py
echo.
echo Smista Foto e' chiuso.
pause
