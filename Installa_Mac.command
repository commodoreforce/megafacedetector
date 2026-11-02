#!/bin/bash
cd "$(dirname "$0")"
echo "=== Installazione Smista Foto ==="
if ! command -v python3 >/dev/null 2>&1; then
  echo
  echo "Python non è installato. Scaricalo da https://www.python.org/downloads/ e rilancia questo file."
  read -p "Premi Invio per chiudere"
  exit 1
fi
python3 -m venv .venv || { echo "Errore nella creazione dell'ambiente"; read -p "Invio"; exit 1; }
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt || { echo "Errore nell'installazione dei pacchetti"; read -p "Invio"; exit 1; }
chmod +x Avvia_Mac.command
echo
echo "Installazione completata. Ora usa Avvia_Mac.command."
read -p "Premi Invio per chiudere"
