#!/bin/bash
# Smista Foto · avvio (Mac). Tieni aperta questa finestra finché usi l'app.
cd "$(dirname "$0")" || exit 1
printf '\033]0;Smista Foto (lascia aperta questa finestra)\007'
if [ ! -x .venv/bin/python ]; then
  echo "Smista Foto non è ancora installato su questo Mac."
  echo "Fai doppio clic su «Installa_Mac.command», in questa stessa cartella."
  read -r -p "Premi Invio per chiudere." _
  exit 1
fi
.venv/bin/python smista.py
echo
read -r -p "Smista Foto è chiuso. Premi Invio per chiudere questa finestra." _
