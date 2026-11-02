#!/bin/bash
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Prima lancia Installa_Mac.command."
  read -p "Premi Invio per chiudere"
  exit 1
fi
.venv/bin/python smista.py
read -p "Premi Invio per chiudere"
