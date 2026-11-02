@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Installazione Smista Foto ===
where py >nul 2>nul
if errorlevel 1 (
  echo.
  echo Python non e' installato.
  echo Scaricalo da https://www.python.org/downloads/ e durante l'installazione
  echo spunta "Add python.exe to PATH". Poi rilancia questo file.
  pause
  exit /b 1
)
py -3 -m venv .venv || (echo Errore nella creazione dell'ambiente & pause & exit /b 1)
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt || (echo Errore nell'installazione dei pacchetti & pause & exit /b 1)
echo.
echo Installazione completata. Ora usa "Avvia_Windows.bat".
pause
