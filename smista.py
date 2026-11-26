"""SMISTA FOTO · Cesena FC
Riconosce giocatori e staff nelle foto di partite e allenamenti caricate su MEGA
e le copia nelle cartelle personali (PLAYERS/<NOME>/<COMPETIZIONE>/<PARTITA>).

Si avvia con un doppio clic su Avvia_Mac.command o Avvia_Windows.bat:
si apre l'app nel browser. Questa finestra mostra lo stesso registro dell'app.

Questo file è il programma di avvio: apre l'app in un processo separato e, quando
l'app chiede di riavviarsi dopo aver scaricato una versione nuova («Aggiorna» nell'app),
aggiorna i componenti Python ad app chiusa e la riapre. Se l'aggiornamento non va a buon
fine torna alla versione di prima. Usa solo la libreria standard di Python, così non
tiene occupato nessun componente che l'aggiornamento deve sostituire.
"""

import json
import os
import subprocess
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)


def _app(apri):
    from smistafoto.app import avvia_app
    return avvia_app(QUI, apri=apri)


FILE_REQUISITI = os.path.join(QUI, ".requisiti_installati")


def _impronta_requisiti():
    import hashlib
    with open(os.path.join(QUI, "requirements.txt"), "rb") as f:
        return hashlib.sha256(f.read() + sys.version.encode()).hexdigest()


def _componenti():
    """pip install -r requirements.txt con il Python di Smista Foto. True se è andato bene.
    Se va bene si annota l'elenco installato, così al prossimo avvio non si ripete."""
    print("\n  Aggiorno i componenti di Smista Foto (può volerci qualche minuto)…\n")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-r", os.path.join(QUI, "requirements.txt"),
                        "--disable-pip-version-check", "--no-input", "-q"], cwd=QUI)
    if r.returncode == 0:
        with open(FILE_REQUISITI, "w") as f:
            f.write(_impronta_requisiti())
    return r.returncode == 0


def _componenti_se_cambiati():
    """All'avvio: se requirements.txt è cambiato dall'ultima installazione (aggiornamento fatto con
    gli script, con uno zip o a mano), installa i componenti prima di aprire l'app."""
    try:
        with open(FILE_REQUISITI) as f:
            if f.read().strip() == _impronta_requisiti():
                return
    except OSError:
        pass
    if not _componenti():
        print("  Non sono riuscito ad aggiornare i componenti: apro comunque Smista Foto.\n"
              "  Se qualcosa non funziona, controlla la connessione e riapri l'app.\n")


def _leggi_stato():
    from smistafoto.aggiornamento import FILE_STATO
    f = os.path.join(QUI, FILE_STATO)
    if not os.path.exists(f):
        return None, f
    try:
        with open(f, encoding="utf-8") as fh:
            return json.load(fh), f
    except Exception:
        return None, f


def _torna_indietro(stato, motivo):
    from smistafoto.aggiornamento import ripristina
    print(f"\n  {motivo}\n  Torno alla versione {stato.get('da', 'di prima')}…")
    ripristina(QUI, stato)
    _componenti()
    return f"annullato|{stato.get('da', '')}|{motivo}"


def controllore():
    from smistafoto.aggiornamento import CODICE_RIAVVIO
    _componenti_se_cambiati()
    apri, esito, appena_aggiornato = True, "", None
    while True:
        ambiente = dict(os.environ, SMISTA_ESITO_AGGIORNAMENTO=esito, SMISTA_CONTROLLORE="1")
        partenza = time.time()
        try:
            codice = subprocess.call([sys.executable, os.path.abspath(__file__), "--app"]
                                     + ([] if apri else ["--senza-finestra"]), env=ambiente)
        except KeyboardInterrupt:
            return 0
        apri, esito = False, ""
        stato, file_stato = _leggi_stato()
        if codice == CODICE_RIAVVIO and not stato:
            continue  # riavvio semplice
        if codice == CODICE_RIAVVIO:
            print(f"\n  Aggiornamento di Smista Foto: {stato.get('da')} → {stato.get('a')}")
            if _componenti():
                esito, appena_aggiornato = f"ok|{stato.get('a', '')}|", stato
            else:
                esito = _torna_indietro(stato, "Non riesco a scaricare i componenti (connessione?).")
                appena_aggiornato = None
                os.remove(file_stato)
            continue
        if appena_aggiornato and codice not in (0, CODICE_RIAVVIO) and time.time() - partenza < 60:
            # la versione nuova non parte: si torna a quella di prima
            esito = _torna_indietro(appena_aggiornato, "La nuova versione non si avvia su questo computer.")
            appena_aggiornato = None
            if os.path.exists(file_stato):
                os.remove(file_stato)
            continue
        if os.path.exists(file_stato) and codice != CODICE_RIAVVIO:
            os.remove(file_stato)  # aggiornamento riuscito e app chiusa normalmente
        return codice


if __name__ == "__main__":
    if "--app" in sys.argv:
        _app(apri="--senza-finestra" not in sys.argv)
        from smistafoto import app as _a
        sys.exit(getattr(_a, "CODICE_USCITA", 0))
    sys.exit(controllore() or 0)
