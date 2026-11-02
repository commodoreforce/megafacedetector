"""SMISTA FOTO · Cesena FC
Riconosce giocatori e staff nelle foto di partite e allenamenti caricate su MEGA
e le copia nelle cartelle personali (PLAYERS/<NOME>/<COMPETIZIONE>/<PARTITA>).

Uso: doppio clic su "Avvia" (Windows: Avvia_Windows.bat, Mac: Avvia_Mac.command)
oppure da terminale:  python smista.py [impara|smista|prova|revisione] [percorso]
"""

import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

QUI = os.path.dirname(os.path.abspath(__file__))
DATI = os.path.join(QUI, "dati")
LAVORI = os.path.join(QUI, "lavori")
MODELLI = os.path.join(QUI, "modelli")


def carica_config():
    with open(os.path.join(QUI, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def chiedi(domanda, predefinito=""):
    r = input(f"{domanda}" + (f" [{predefinito}]" if predefinito else "") + ": ").strip()
    return r or predefinito


def prepara():
    from smistafoto.mega import collegamento
    from smistafoto.volti import Riferimenti, Volti
    cfg = carica_config()
    conn = collegamento(cfg)
    chi = conn.chi_sono()
    if not chi:
        print("MEGAcmd non è collegato a nessun account.\n"
              "Apri MEGAcmd, scrivi:  login <email del club>  e inserisci la password lì, poi riprova.")
        sys.exit(1)
    print(f"Collegato a: {chi}")
    return cfg, conn, Volti(MODELLI, cfg), Riferimenti(DATI)


def cmd_impara(tutti=False):
    from smistafoto.flussi import impara
    cfg, conn, volti, rif = prepara()
    impara(cfg, conn, volti, rif, DATI, tutti=tutti)


def _chiedi_evento(cfg, sorgente):
    from smistafoto.flussi import ricava_evento
    comp, evento = ricava_evento(cfg, sorgente)
    if comp:
        print(f"\nLe foto andranno in:  <NOME>/{comp}/{evento}")
        if chiedi("Va bene? (Invio = sì, n = cambio i nomi)").lower() != "n":
            return comp, evento
    comp = chiedi("Cartella della competizione (es. SERIE BKT, COPPA_ITALIA, ALLENAMENTI)", comp or "").upper()
    evento = chiedi("Nome della cartella dell'evento", evento or "").upper()
    return comp, evento


def _analizza(sorgente):
    from smistafoto.flussi import analizza_cartella
    from smistafoto.mega import normalizza
    cfg, conn, volti, rif = prepara()
    sorgente = normalizza(sorgente or chiedi(
        "\nIncolla il percorso della cartella da smistare\n(es. 2026-27/MATCH/SERIEBKT/G10_Sudtirol_Cesena_1_1/Foto)"))
    comp, evento = _chiedi_evento(cfg, sorgente)
    lavoro = analizza_cartella(cfg, conn, volti, rif, sorgente, comp, evento, LAVORI)
    return conn, rif, lavoro, evento


def cmd_smista(sorgente=None):
    from smistafoto.revisione import apri
    conn, rif, lavoro, _ = _analizza(sorgente)
    apri(conn, rif, lavoro)


def cmd_prova(sorgente=None):
    from smistafoto.flussi import confronta
    conn, _, lavoro, evento = _analizza(sorgente)
    esistente = chiedi("Come si chiama la cartella della partita già smistata a mano", evento)
    confronta(conn, lavoro, esistente)


def cmd_revisione():
    from smistafoto.flussi import ultimo_lavoro
    from smistafoto.revisione import apri
    lavoro = ultimo_lavoro(LAVORI)
    if not lavoro:
        print("Non c'è nessuna analisi in attesa di revisione.")
        return
    print(f"Riapro: {os.path.basename(lavoro)}")
    _, conn, _, rif = prepara()
    apri(conn, rif, lavoro)


def menu():
    print("\n=== SMISTA FOTO · Cesena FC ===")
    print("1) Impara i volti (prima volta, o quando arriva qualcuno di nuovo)")
    print("2) Smista una cartella di foto")
    print("3) Riapri la revisione dell'ultima analisi")
    print("4) Prova su una partita già smistata a mano (non copia nulla)")
    print("5) Reimpara tutti i volti da zero")
    print("0) Esci")
    scelta = input("Scelta: ").strip()
    azioni = {"1": cmd_impara, "2": cmd_smista, "3": cmd_revisione, "4": cmd_prova,
              "5": lambda: cmd_impara(tutti=True)}
    if scelta in azioni:
        azioni[scelta]()
    return scelta != "0"


def main():
    sys.path.insert(0, QUI)
    args = sys.argv[1:]
    try:
        if not args:
            while menu():
                pass
        else:
            comando, percorso = args[0], (args[1] if len(args) > 1 else None)
            {"impara": lambda: cmd_impara(), "reimpara": lambda: cmd_impara(True),
             "smista": lambda: cmd_smista(percorso), "prova": lambda: cmd_prova(percorso),
             "revisione": cmd_revisione}[comando]()
    except KeyboardInterrupt:
        print("\nInterrotto.")
    except (RuntimeError, KeyError) as e:
        print(f"\nErrore: {e}")


if __name__ == "__main__":
    main()
