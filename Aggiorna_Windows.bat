@echo off
rem Smista Foto - aggiornamento: scarica l'ultima versione da GitHub.
rem Le scelte fatte nell'app (cartella dati), le analisi e i primi piani restano.
chcp 65001 >nul
cd /d "%~dp0"
echo SMISTA FOTO - aggiornamento
if not exist .git (
  echo Questa cartella non e' stata scaricata con git.
  echo Scarica di nuovo lo zip da GitHub e sostituisci la cartella, tenendo la sottocartella "dati".
  pause
  exit /b 1
)
where git >nul 2>nul || (echo Git non e' installato: scaricalo da https://git-scm.com/download/win & pause & exit /b 1)
git diff --quiet -- config.json || (echo config.json era stato modificato a mano: lo riporto com'era. & git checkout -- config.json)
git fetch -q origin || (echo Non riesco a contattare GitHub: controlla la connessione e riprova. & pause & exit /b 1)
git merge-base --is-ancestor HEAD origin/main >nul 2>nul || (echo La cronologia del repository e' stata ripulita: allineo questa copia. Le cartelle dati, lavori e primi_piani restano. & git reset -q --hard origin/main)
git merge -q --ff-only origin/main || (echo Aggiornamento non riuscito: controlla la connessione e riprova. & pause & exit /b 1)
if exist .venv\Scripts\python.exe .venv\Scripts\python -m pip install -r requirements.txt -q
echo.
echo Fatto. Riavvia Smista Foto per usare la nuova versione.
pause
