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
m = Mega("/2026-27/PLAYERS")

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

# 6. controllo statico: nel codice nessuna chiamata a comandi diversi da quelli consentiti
cartella = os.path.join(os.path.dirname(QUI), "smistafoto")
for nome in os.listdir(cartella):
    if nome.endswith(".py"):
        testo = open(os.path.join(cartella, nome), encoding="utf-8").read()
        for c in re.findall(r'_esegui\(\s*"([a-z]+)"', testo):
            if c not in mega.COMANDI_CONSENTITI:
                print(f"ERRORE: {nome} usa il comando {c}")
                errori += 1
        if "subprocess" in testo and nome != "mega.py":
            print(f"ERRORE: {nome} esegue comandi esterni")
            errori += 1
        for vietato in ("os.remove(", "shutil.rmtree(", "os.rename(", "os.replace("):
            if vietato in testo and nome != "flussi.py":
                print(f"ERRORE: {nome} contiene {vietato}")
                errori += 1

print()
print("TUTTO OK" if not errori else f"{errori} PROBLEMI")
sys.exit(1 if errori else 0)
