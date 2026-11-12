#!/bin/bash
# Smista Foto · aggiornamento (Mac). Scarica l'ultima versione da GitHub.
# Le scelte fatte nell'app (cartella dati/), le analisi e i primi piani restano.
cd "$(dirname "$0")" || exit 1
G=$'\033[1m'; V=$'\033[32m'; R=$'\033[31m'; N=$'\033[0m'
echo "${G}SMISTA FOTO · aggiornamento${N}"
if [ ! -d .git ]; then
  echo "${R}Questa cartella non è stata scaricata con git.${N}"
  echo "Scarica di nuovo lo zip da GitHub e sostituisci la cartella (tieni la sottocartella «dati»)."
  read -r -p "Premi Invio per chiudere." _; exit 1
fi
PRIMA=$(grep -o '"[0-9.]*"' smistafoto/__init__.py | head -1)
if ! git diff --quiet -- config.json; then
  echo "config.json era stato modificato a mano: lo riporto com'era (le scelte dell'app sono in dati/)."
  git checkout -- config.json
fi
git fetch -q origin || { echo "${R}Non riesco a contattare GitHub.${N} Controlla la connessione e riprova."; read -r -p "Premi Invio per chiudere." _; exit 1; }
if ! git merge-base --is-ancestor HEAD origin/main 2>/dev/null; then
  # la cronologia su GitHub è stata ripulita: allineo questa copia.
  # dati/, lavori/ e primi_piani/ non fanno parte del repository e restano intatti.
  echo "La cronologia del repository è stata ripulita: allineo questa copia (le tue cartelle dati, lavori e primi_piani restano)."
  git reset -q --hard origin/main
fi
if git merge -q --ff-only origin/main; then
  DOPO=$(grep -o '"[0-9.]*"' smistafoto/__init__.py | head -1)
  [ -x .venv/bin/python ] && .venv/bin/python -m pip install -r requirements.txt -q
  echo; echo "${V}${G}Fatto: versione ${PRIMA//\"/} → ${DOPO//\"/}.${N} Riavvia Smista Foto per usarla."
else
  echo "${R}Aggiornamento non riuscito.${N} Controlla la connessione e riprova."
fi
read -r -p "Premi Invio per chiudere." _
