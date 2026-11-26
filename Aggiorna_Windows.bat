@echo off
rem Smista Foto - aggiornamento da GitHub. Di solito non serve: dentro l'app c'e' il pulsante
rem "Aggiorna" in basso a sinistra. Questo file resta per i casi in cui l'app non si apre.
rem Le scelte fatte nell'app (cartella dati), le analisi, i primi piani e i loghi restano.
rem Tutto e' in un blocco tra parentesi: Windows lo legge per intero prima di eseguirlo,
rem cosi' l'aggiornamento puo' sostituire anche questo file senza problemi.
(
  chcp 65001 >nul
  cd /d "%~dp0"
  echo SMISTA FOTO - aggiornamento
  if not exist .git (
    echo Questa cartella non e' stata scaricata con git: aggiorna dall'app, con il pulsante "Aggiorna" in basso a sinistra.
    pause
    exit /b 1
  )
  where git >nul 2>nul || (echo Git non e' installato: aggiorna dall'app, con il pulsante "Aggiorna" in basso a sinistra. & pause & exit /b 1)
  git diff --quiet -- config.json || (echo config.json era stato modificato a mano: lo riporto com'era. & git checkout -- config.json)
  git fetch -q origin || (echo Non riesco a contattare GitHub: controlla la connessione e riprova. & pause & exit /b 1)
  git merge-base --is-ancestor HEAD origin/main >nul 2>nul || (echo La cronologia del repository e' stata ripulita: allineo questa copia. Le cartelle dati, lavori, primi_piani e loghi restano. & git reset -q --hard origin/main)
  git merge -q --ff-only origin/main || (echo Aggiornamento non riuscito: controlla la connessione e riprova. & pause & exit /b 1)
  if exist .venv\Scripts\python.exe .venv\Scripts\python -m pip install -r requirements.txt -q --disable-pip-version-check
  echo.
  echo Fatto. Riapri Smista Foto per usare la nuova versione.
  pause
  exit /b
)
