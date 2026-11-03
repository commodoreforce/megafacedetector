@echo off
rem Smista Foto - installazione guidata per Windows: doppio clic per avviarla.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installa_windows.ps1"
