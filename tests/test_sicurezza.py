"""Verifica le regole di sicurezza del cloud senza toccare MEGA:
i comandi MEGAcmd vengono intercettati e registrati, non eseguiti.

Uso:  python tests/test_sicurezza.py
"""

import os
import re
import subprocess
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(QUI))

from smistafoto import mega  # noqa: E402
from smistafoto.mega import Mega, OperazioneVietata  # noqa: E402

eseguiti = []
risposta_ls = {}  # percorso -> (returncode, stdout, stderr)


class Finto:
    def __init__(self, rc=0, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out.encode(), err.encode()


def finto_run(argomenti, capture_output=True, timeout=None, env=None):
    comando = os.path.basename(argomenti[0]).replace(".bat", "").replace("mega-", "")
    eseguiti.append((comando, *argomenti[1:]))
    if comando == "ls":
        rc, out, err = risposta_ls.get(argomenti[1], (1, "", "[API:err] Couldn't find " + argomenti[1]))
        return Finto(rc, out, err)
    return Finto(0, "ok")


subprocess.run = finto_run
Mega._trova_megacmd = staticmethod(lambda: "/finto")
m = Mega("/2026-27/PLAYERS", ["ALLENAMENTI"])

errori = 0


def deve_rifiutare(descrizione, funzione):
    global errori
    prima = len(eseguiti)
    try:
        funzione()
    except OperazioneVietata:
        scritti = [c for c in eseguiti[prima:] if c[0] in ("cp", "mkdir")]
        if scritti:
            print("ERRORE (ha scritto prima di rifiutare):", descrizione, scritti)
            errori += 1
        else:
            print("ok  rifiutato:", descrizione)
        return
    print("ERRORE (non rifiutato):", descrizione)
    errori += 1


def deve_passare(descrizione, funzione):
    global errori
    try:
        funzione()
        print("ok  consentito:", descrizione)
    except Exception as e:
        print("ERRORE (rifiutato per sbaglio):", descrizione, e)
        errori += 1


SRC = "/2026-27/MATCH/SERIEBKT/G10/Foto/a.jpg"
DEST = "/2026-27/PLAYERS/CIOFI/SERIE BKT/G10_SUDTIROL_CESENA/a.jpg"

# 1. comandi non consentiti
for c in ["rm", "mv", "put", "sync", "backup", "share", "export", "import", "transfers",
          "logout", "deleteversions", "rmdir", "attr", "userattr", "passwd", "cancel"]:
    deve_rifiutare(f"comando {c}", lambda c=c: m._esegui(c, "/2026-27"))

# 2. opzioni non consentite
deve_rifiutare("preview -s (caricherebbe un'anteprima)", lambda: m._esegui("preview", "-s", SRC, "/tmp/x"))
deve_rifiutare("cp con opzione", lambda: m._esegui("cp", "--use-pcre", SRC, DEST))
deve_rifiutare("ls -R", lambda: m._esegui("ls", "-R", "/"))
deve_rifiutare("cp con -l", lambda: m._esegui("cp", "-l", SRC, DEST))
deve_rifiutare("mkdir con -l", lambda: m._esegui("mkdir", "-l", "/a"))
deve_rifiutare("get con -p", lambda: m._esegui("get", "-p", SRC, "/tmp/x"))
deve_rifiutare("mkdir con opzione diversa da -p", lambda: m._esegui("mkdir", "-x", "/a"))

# 3. scritture fuori posto
deve_rifiutare("copia dentro MATCH", lambda: m.copia(SRC, "/2026-27/MATCH/SERIEBKT/G10/Foto/b.jpg"))
deve_rifiutare("copia nella radice", lambda: m.copia(SRC, "/a.jpg"))
deve_rifiutare("copia direttamente in PLAYERS", lambda: m.copia(SRC, "/2026-27/PLAYERS/a.jpg"))
deve_rifiutare("copia nella cartella del giocatore (livello sbagliato)", lambda: m.copia(SRC, "/2026-27/PLAYERS/CIOFI/a.jpg"))
deve_rifiutare("copia in PLAYERS/CIOFI/SERIE BKT (manca l'evento)", lambda: m.copia(SRC, "/2026-27/PLAYERS/CIOFI/SERIE BKT/a.jpg"))
deve_rifiutare("copia con '..' per uscire da PLAYERS", lambda: m.copia(SRC, "/2026-27/PLAYERS/CIOFI/../../MATCH/x/y/a.jpg"))
deve_rifiutare("copia con carattere jolly", lambda: m.copia("/2026-27/MATCH/*", DEST))
deve_rifiutare("copia verso un file che non è una foto", lambda: m.copia(SRC, "/2026-27/PLAYERS/CIOFI/SERIE BKT/G10/x.txt"))
deve_rifiutare("origine dentro PLAYERS", lambda: m.copia("/2026-27/PLAYERS/SHPENDI/MEDIADAY/a.jpg", DEST))
deve_rifiutare("creare cartella fuori da PLAYERS", lambda: m.crea_cartella("/2026-27/MATCH/NUOVA/X/Y"))
deve_rifiutare("creare cartella troppo in alto", lambda: m.crea_cartella("/2026-27/PLAYERS/CIOFI"))
deve_rifiutare("radice di scrittura troppo generica", lambda: Mega("/"))
deve_rifiutare("radice di scrittura troppo generica 2", lambda: Mega("/2026-27"))

# 3b. cartelle uniche (ALLENAMENTI): solo file direttamente lì, mai altrove allo stesso livello
deve_passare("copia in PLAYERS/CIOFI/ALLENAMENTI (cartella unica)", lambda: m.copia(SRC, "/2026-27/PLAYERS/CIOFI/ALLENAMENTI/20261102_a.jpg"))
deve_passare("crea PLAYERS/CIOFI/ALLENAMENTI", lambda: m.crea_cartella("/2026-27/PLAYERS/CIOFI/ALLENAMENTI"))
deve_passare("copia in PLAYERS/_STAFF/DIAMANTI/ALLENAMENTI", lambda: m.copia(SRC, "/2026-27/PLAYERS/_STAFF/DIAMANTI/ALLENAMENTI/x.jpg"))
deve_rifiutare("copia in PLAYERS/CIOFI/SERIE BKT senza evento", lambda: m.copia(SRC, "/2026-27/PLAYERS/CIOFI/SERIE BKT/a.jpg"))
deve_rifiutare("copia in PLAYERS/CIOFI/MEDIADAY (non è cartella unica)", lambda: m.copia(SRC, "/2026-27/PLAYERS/CIOFI/MEDIADAY/a.jpg"))
deve_rifiutare("creare PLAYERS/CIOFI/MEDIADAY", lambda: m.crea_cartella("/2026-27/PLAYERS/CIOFI/MEDIADAY"))
deve_rifiutare("copia in PLAYERS/ALLENAMENTI/a.jpg", lambda: m.copia(SRC, "/2026-27/PLAYERS/ALLENAMENTI/a.jpg"))
deve_rifiutare("copia nella sorgente ALLENAMENTI", lambda: m.copia(SRC, "/2026-27/ALLENAMENTI/2026_11/a.jpg"))
deve_rifiutare("PLAYERS/_STAFF/ALLENAMENTI/x.jpg", lambda: m.copia(SRC, "/2026-27/PLAYERS/_STAFF/ALLENAMENTI/x.jpg"))
deve_rifiutare("staff senza evento: _STAFF/DIAMANTI/SERIE BKT/a.jpg", lambda: m.copia(SRC, "/2026-27/PLAYERS/_STAFF/DIAMANTI/SERIE BKT/a.jpg"))
deve_rifiutare("sottocartella dentro ALLENAMENTI", lambda: m.copia(SRC, "/2026-27/PLAYERS/CIOFI/ALLENAMENTI/X/a.jpg"))
deve_passare("staff con evento", lambda: m.copia(SRC, "/2026-27/PLAYERS/_STAFF/DIAMANTI/SERIE BKT/G10/a.jpg"))
deve_rifiutare("senza cartelle uniche configurate", lambda: Mega("/2026-27/PLAYERS").copia(SRC, "/2026-27/PLAYERS/CIOFI/ALLENAMENTI/a.jpg"))

# 4. mai sovrascrivere
risposta_ls[DEST] = (0, "a.jpg\n", "")
deve_rifiutare("destinazione già esistente", lambda: m.copia(SRC, DEST))
del risposta_ls[DEST]
risposta_ls[DEST] = (57, "", "errore di rete")
deve_rifiutare("esistenza non verificabile (errore di rete)", lambda: m.copia(SRC, DEST))
del risposta_ls[DEST]

# 5. il caso normale deve funzionare
eseguiti.clear()
deve_passare("copia corretta in PLAYERS/CIOFI/SERIE BKT/G10_SUDTIROL_CESENA", lambda: m.copia(SRC, DEST))
deve_passare("copia corretta per lo staff", lambda: m.copia(SRC, "/2026-27/PLAYERS/_STAFF/DIAMANTI/SERIE BKT/G10_SUDTIROL_CESENA/a.jpg"))
deve_passare("crea cartella evento", lambda: m.crea_cartella("/2026-27/PLAYERS/CIOFI/SERIE BKT/G10_SUDTIROL_CESENA"))
cp = [c for c in eseguiti if c[0] == "cp"]
if cp[0] != ("cp", SRC, DEST):
    print("ERRORE: comando cp inatteso", cp[0])
    errori += 1

# 6. la simulazione su MEGA legge soltanto
import json, tempfile  # noqa: E401,E402
import numpy as np  # noqa: E402
from smistafoto.flussi import simula_copia  # noqa: E402
from smistafoto.registro import Registro  # noqa: E402

cartella_lavoro = tempfile.mkdtemp()
lavoro = {"sorgente": "/2026-27/MATCH/SERIEBKT/G10/Foto", "competizione": "SERIE BKT", "evento": "G10_X",
          "cartelle_persone": {"CIOFI": "/2026-27/PLAYERS/CIOFI", "MATCH": "/2026-27/MATCH"},
          "foto": [{"id": 0, "remoto": SRC, "relativo": "a.jpg", "nome_dest": "a.jpg"}], "volti": []}
json.dump(lavoro, open(os.path.join(cartella_lavoro, "lavoro.json"), "w"))
np.save(os.path.join(cartella_lavoro, "impronte.npy"), np.zeros((0, 128), np.float32))
eseguiti.clear()
import io, contextlib  # noqa: E401,E402
with contextlib.redirect_stdout(io.StringIO()):
    ris = simula_copia(m, cartella_lavoro, [{"foto": 0, "persona": "CIOFI"}, {"foto": 0, "persona": "MATCH"}], Registro())
comandi = {c[0] for c in eseguiti}
if comandi - {"ls"}:
    print("ERRORE: la simulazione ha usato", comandi)
    errori += 1
elif ris["copierebbe"] != 1 or ris["bloccata"] != 1:
    print("ERRORE: risultato della simulazione inatteso", ris["copierebbe"], ris["bloccata"])
    errori += 1
else:
    print("ok  simulazione: solo letture (ls), 1 copia prevista, 1 bloccata fuori da PLAYERS")

# 7. controllo statico: nel codice nessuna chiamata a comandi diversi da quelli consentiti
cartella = os.path.join(os.path.dirname(QUI), "smistafoto")
for nome in os.listdir(cartella):
    if nome.endswith(".py"):
        testo = open(os.path.join(cartella, nome), encoding="utf-8").read()
        for c in re.findall(r'_esegui\(\s*"([a-z]+)"', testo):
            if c not in mega.COMANDI_CONSENTITI:
                print(f"ERRORE: {nome} usa il comando {c}")
                errori += 1
        if "subprocess" in testo and nome not in ("mega.py", "finestra.py"):
            print(f"ERRORE: {nome} esegue comandi esterni")
            errori += 1
        if nome == "finestra.py" and "mega" in testo.lower().replace("non ha niente a che fare con mega", ""):
            print("ERRORE: finestra.py deve solo aprire il browser, non usare MEGA")
            errori += 1
        # operazioni su file del COMPUTER (mai su MEGA, che si raggiunge solo da mega.py):
        # flussi.py cancella le foto temporanee scaricate, volti.py salva il modello scaricato
        for vietato in ("os.remove(", "shutil.rmtree(", "os.rename(", "os.replace("):
            if vietato in testo and nome not in ("flussi.py", "volti.py"):
                print(f"ERRORE: {nome} contiene {vietato}")
                errori += 1

print()
print("TUTTO OK" if not errori else f"{errori} PROBLEMI")
sys.exit(1 if errori else 0)
