"""SMISTA FOTO · Cesena FC
Riconosce giocatori e staff nelle foto di partite e allenamenti caricate su MEGA
e le copia nelle cartelle personali (PLAYERS/<NOME>/<COMPETIZIONE>/<PARTITA>).

Si avvia con un doppio clic su Avvia_Mac.command o Avvia_Windows.bat:
si apre l'app nel browser. Questa finestra mostra lo stesso registro dell'app.
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)

from smistafoto.app import avvia_app  # noqa: E402

if __name__ == "__main__":
    avvia_app(QUI)
