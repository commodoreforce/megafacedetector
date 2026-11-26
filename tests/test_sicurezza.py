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
DEST = "/2026-27/PLAYERS/BIANCHI/SERIE BKT/G10_SUDTIROL_CESENA/a.jpg"

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
deve_rifiutare("copia nella cartella del giocatore (livello sbagliato)", lambda: m.copia(SRC, "/2026-27/PLAYERS/BIANCHI/a.jpg"))
deve_rifiutare("copia in PLAYERS/BIANCHI/SERIE BKT (manca l'evento)", lambda: m.copia(SRC, "/2026-27/PLAYERS/BIANCHI/SERIE BKT/a.jpg"))
deve_rifiutare("copia con '..' per uscire da PLAYERS", lambda: m.copia(SRC, "/2026-27/PLAYERS/BIANCHI/../../MATCH/x/y/a.jpg"))
deve_rifiutare("copia con carattere jolly", lambda: m.copia("/2026-27/MATCH/*", DEST))
deve_rifiutare("copia verso un file che non è una foto", lambda: m.copia(SRC, "/2026-27/PLAYERS/BIANCHI/SERIE BKT/G10/x.txt"))
deve_rifiutare("origine dentro PLAYERS", lambda: m.copia("/2026-27/PLAYERS/NERI/MEDIADAY/a.jpg", DEST))
deve_rifiutare("creare cartella fuori da PLAYERS", lambda: m.crea_cartella("/2026-27/MATCH/NUOVA/X/Y"))
deve_rifiutare("creare cartella troppo in alto", lambda: m.crea_cartella("/2026-27/PLAYERS/BIANCHI"))
deve_rifiutare("radice di scrittura troppo generica", lambda: Mega("/"))
deve_rifiutare("radice di scrittura troppo generica 2", lambda: Mega("/2026-27"))

# 3b. cartelle uniche (ALLENAMENTI): solo file direttamente lì, mai altrove allo stesso livello
deve_passare("copia in PLAYERS/BIANCHI/ALLENAMENTI (cartella unica)", lambda: m.copia(SRC, "/2026-27/PLAYERS/BIANCHI/ALLENAMENTI/20261102_a.jpg"))
deve_passare("crea PLAYERS/BIANCHI/ALLENAMENTI", lambda: m.crea_cartella("/2026-27/PLAYERS/BIANCHI/ALLENAMENTI"))
deve_passare("copia in PLAYERS/_STAFF/VERDI/ALLENAMENTI", lambda: m.copia(SRC, "/2026-27/PLAYERS/_STAFF/VERDI/ALLENAMENTI/x.jpg"))
deve_rifiutare("copia in PLAYERS/BIANCHI/SERIE BKT senza evento", lambda: m.copia(SRC, "/2026-27/PLAYERS/BIANCHI/SERIE BKT/a.jpg"))
deve_rifiutare("copia in PLAYERS/BIANCHI/MEDIADAY (non è cartella unica)", lambda: m.copia(SRC, "/2026-27/PLAYERS/BIANCHI/MEDIADAY/a.jpg"))
deve_rifiutare("creare PLAYERS/BIANCHI/MEDIADAY", lambda: m.crea_cartella("/2026-27/PLAYERS/BIANCHI/MEDIADAY"))
deve_rifiutare("copia in PLAYERS/ALLENAMENTI/a.jpg", lambda: m.copia(SRC, "/2026-27/PLAYERS/ALLENAMENTI/a.jpg"))
deve_rifiutare("copia nella sorgente ALLENAMENTI", lambda: m.copia(SRC, "/2026-27/ALLENAMENTI/2026_11/a.jpg"))
deve_rifiutare("PLAYERS/_STAFF/ALLENAMENTI/x.jpg", lambda: m.copia(SRC, "/2026-27/PLAYERS/_STAFF/ALLENAMENTI/x.jpg"))
deve_rifiutare("staff senza evento: _STAFF/VERDI/SERIE BKT/a.jpg", lambda: m.copia(SRC, "/2026-27/PLAYERS/_STAFF/VERDI/SERIE BKT/a.jpg"))
deve_rifiutare("sottocartella dentro ALLENAMENTI", lambda: m.copia(SRC, "/2026-27/PLAYERS/BIANCHI/ALLENAMENTI/X/a.jpg"))
deve_passare("staff con evento", lambda: m.copia(SRC, "/2026-27/PLAYERS/_STAFF/VERDI/SERIE BKT/G10/a.jpg"))
deve_rifiutare("senza cartelle uniche configurate", lambda: Mega("/2026-27/PLAYERS").copia(SRC, "/2026-27/PLAYERS/BIANCHI/ALLENAMENTI/a.jpg"))

# 3c. area sponsor: stesse regole, solo dentro SPONSOR/<NOME>/<COMP>/<EVENTO> o SPONSOR/<NOME>/ALLENAMENTI
deve_rifiutare("sponsor prima di impostare la cartella SPONSOR", lambda: m.copia(SRC, "/2026-27/SPONSOR/AMADORI/SERIE BKT/G10/a.jpg"))
from smistafoto.mega import controlla_radice_sponsor  # noqa: E402
deve_rifiutare("cartella sponsor troppo generica", lambda: m.imposta_radice_sponsor("/2026-27"))
deve_rifiutare("cartella sponsor = radice", lambda: m.imposta_radice_sponsor("/"))
deve_rifiutare("cartella sponsor dentro PLAYERS", lambda: m.imposta_radice_sponsor("/2026-27/PLAYERS/SPONSOR"))
deve_rifiutare("cartella sponsor uguale a PLAYERS", lambda: m.imposta_radice_sponsor("/2026-27/PLAYERS"))
deve_rifiutare("cartella sponsor che contiene PLAYERS", lambda: Mega("/2026-27/X/PLAYERS").imposta_radice_sponsor("/2026-27/X"))
deve_rifiutare("cartella sponsor con jolly", lambda: m.imposta_radice_sponsor("/2026-27/SPONSOR*"))
m.imposta_radice_sponsor("/2026-27/SPONSOR")
deve_passare("copia in SPONSOR/AMADORI/SERIE BKT/G10_SUDTIROL_CESENA", lambda: m.copia(SRC, "/2026-27/SPONSOR/AMADORI/SERIE BKT/G10_SUDTIROL_CESENA/a.jpg"))
deve_passare("copia in SPONSOR/AMADORI/ALLENAMENTI", lambda: m.copia(SRC, "/2026-27/SPONSOR/AMADORI/ALLENAMENTI/20261102_a.jpg"))
deve_passare("crea SPONSOR/AMADORI/SERIE BKT/G10", lambda: m.crea_cartella("/2026-27/SPONSOR/AMADORI/SERIE BKT/G10"))
deve_rifiutare("copia in SPONSOR/AMADORI/a.jpg", lambda: m.copia(SRC, "/2026-27/SPONSOR/AMADORI/a.jpg"))
deve_rifiutare("copia in SPONSOR/a.jpg", lambda: m.copia(SRC, "/2026-27/SPONSOR/a.jpg"))
deve_rifiutare("copia in SPONSOR/AMADORI/SERIE BKT senza evento", lambda: m.copia(SRC, "/2026-27/SPONSOR/AMADORI/SERIE BKT/a.jpg"))
deve_rifiutare("sottocartella in SPONSOR/AMADORI/ALLENAMENTI", lambda: m.copia(SRC, "/2026-27/SPONSOR/AMADORI/ALLENAMENTI/X/a.jpg"))
deve_rifiutare("creare SPONSOR/NUOVO (solo cartelle evento)", lambda: m.crea_cartella("/2026-27/SPONSOR/NUOVO"))
deve_rifiutare("origine dentro SPONSOR", lambda: m.copia("/2026-27/SPONSOR/AMADORI/SERIE BKT/G01/a.jpg", DEST))
deve_rifiutare("SPONSOR con '..' verso PLAYERS", lambda: m.copia(SRC, "/2026-27/SPONSOR/../PLAYERS/a.jpg"))
deve_rifiutare("cartella simile ma diversa (SPONSOR2)", lambda: m.copia(SRC, "/2026-27/SPONSOR2/AMADORI/SERIE BKT/G10/a.jpg"))
deve_rifiutare("non-foto in SPONSOR", lambda: m.copia(SRC, "/2026-27/SPONSOR/AMADORI/SERIE BKT/G10/a.mp4"))
risposta_ls["/2026-27/SPONSOR/AMADORI/SERIE BKT/G10/b.jpg"] = (0, "b.jpg\n", "")
deve_rifiutare("sovrascrivere in SPONSOR", lambda: m.copia(SRC, "/2026-27/SPONSOR/AMADORI/SERIE BKT/G10/b.jpg"))
del risposta_ls["/2026-27/SPONSOR/AMADORI/SERIE BKT/G10/b.jpg"]

# 4. mai sovrascrivere
risposta_ls[DEST] = (0, "a.jpg\n", "")
deve_rifiutare("destinazione già esistente", lambda: m.copia(SRC, DEST))
del risposta_ls[DEST]
risposta_ls[DEST] = (57, "", "errore di rete")
deve_rifiutare("esistenza non verificabile (errore di rete)", lambda: m.copia(SRC, DEST))
del risposta_ls[DEST]

# 5. il caso normale deve funzionare
eseguiti.clear()
deve_passare("copia corretta in PLAYERS/BIANCHI/SERIE BKT/G10_SUDTIROL_CESENA", lambda: m.copia(SRC, DEST))
deve_passare("copia corretta per lo staff", lambda: m.copia(SRC, "/2026-27/PLAYERS/_STAFF/VERDI/SERIE BKT/G10_SUDTIROL_CESENA/a.jpg"))
deve_passare("crea cartella evento", lambda: m.crea_cartella("/2026-27/PLAYERS/BIANCHI/SERIE BKT/G10_SUDTIROL_CESENA"))
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
          "cartelle_persone": {"BIANCHI": "/2026-27/PLAYERS/BIANCHI", "MATCH": "/2026-27/MATCH"},
          "foto": [{"id": 0, "remoto": SRC, "relativo": "a.jpg", "nome_dest": "a.jpg"}], "volti": []}
json.dump(lavoro, open(os.path.join(cartella_lavoro, "lavoro.json"), "w"))
np.save(os.path.join(cartella_lavoro, "impronte.npy"), np.zeros((0, 128), np.float32))
eseguiti.clear()
import io, contextlib  # noqa: E401,E402
with contextlib.redirect_stdout(io.StringIO()):
    ris = simula_copia(m, cartella_lavoro, [{"foto": 0, "persona": "BIANCHI"}, {"foto": 0, "persona": "MATCH"}], Registro())
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
        if "subprocess" in testo and nome not in ("mega.py", "finestra.py", "aggiornamento.py"):
            print(f"ERRORE: {nome} esegue comandi esterni")
            errori += 1
        if nome == "finestra.py" and "mega" in testo.lower().replace("non ha niente a che fare con mega", ""):
            print("ERRORE: finestra.py deve solo aprire il browser, non usare MEGA")
            errori += 1
        # operazioni su file del COMPUTER (mai su MEGA, che si raggiunge solo da mega.py):
        # flussi.py cancella le foto temporanee scaricate, volti.py salva il modello scaricato,
        # archivio.py e app.py sostituiscono dati/ e primi_piani/ quando si importano i volti
        for vietato in ("os.remove(", "shutil.rmtree(", "os.rename(", "os.replace("):
            if vietato in testo and nome not in ("flussi.py", "volti.py", "archivio.py", "app.py", "sponsor.py",
                                                 "aggiornamento.py"):
                print(f"ERRORE: {nome} contiene {vietato}")
                errori += 1

        if nome == "aggiornamento.py":
            # l'aggiornamento esegue solo git (sui file del programma) e mai i comandi di MEGAcmd
            chiamate = re.findall(r"subprocess\.(\w+)\(\[(\w+)", testo)
            if "mega-" in testo or any(c[1] != "git" for c in chiamate) or len(chiamate) != 1:
                print("ERRORE: aggiornamento.py deve eseguire solo git", chiamate)
                errori += 1
        if nome in ("archivio.py", "sponsor.py", "aggiornamento.py") and re.search(r"^\s*(from|import)\s+\S*mega", testo, re.M):
            print(f"ERRORE: {nome} non deve poter raggiungere MEGA")
            errori += 1

# 8. il repository è pubblico: nessuna email reale nei file
ammesse = {"noreply@anthropic.com", "nome@dominio.it"}
radice = os.path.dirname(QUI)
for cartella_, _, nomi in os.walk(radice):
    if any(x in cartella_ for x in (".git", ".venv", "dati", "lavori", "__pycache__", "modelli")):
        continue
    for n in nomi:
        if not n.endswith((".py", ".js", ".html", ".css", ".md", ".json", ".txt", ".command", ".bat", ".ps1")):
            continue
        testo = open(os.path.join(cartella_, n), encoding="utf-8", errors="ignore").read()
        for e in set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z.]{2,}", testo)) - ammesse:
            print(f"ERRORE: email nel repository pubblico: {e} ({n})")
            errori += 1

# 9. esporta/importa i volti: solo dentro dati/ e primi_piani/, mai fuori
import tempfile, zipfile, json as _json  # noqa: E401,E402
from smistafoto import archivio  # noqa: E402

with tempfile.TemporaryDirectory() as t:
    a, b = os.path.join(t, "a"), os.path.join(t, "b")
    for base in (a, b):
        os.makedirs(os.path.join(base, "primi_piani"))
        open(os.path.join(base, "primi_piani", "LEGGI.txt"), "w").write("x")
    os.makedirs(os.path.join(a, "dati", "tmp_imparare"))
    os.makedirs(os.path.join(a, "primi_piani", "BIANCHI"))
    open(os.path.join(a, "dati", "riferimenti_auraface.json"), "w").write('{"BIANCHI": {}}')
    open(os.path.join(a, "dati", "tmp_imparare", "x.jpg"), "w").write("tmp")
    open(os.path.join(a, "primi_piani", "BIANCHI", "1.jpg"), "w").write("foto")
    os.makedirs(os.path.join(b, "dati"))
    open(os.path.join(b, "dati", "riferimenti_auraface.json"), "w").write('{"VECCHIO": {}}')
    os.makedirs(os.path.join(b, "primi_piani", "VECCHIO"))
    z = os.path.join(t, "volti.zip")
    archivio.esporta(a, z, persone=1)
    nomi = zipfile.ZipFile(z).namelist()
    if any("tmp_imparare" in n for n in nomi):
        print("ERRORE: l'esportazione contiene file temporanei"); errori += 1
    archivio.importa(b, z, os.path.join(b, "backup_volti"))
    ok = (open(os.path.join(b, "dati", "riferimenti_auraface.json")).read() == '{"BIANCHI": {}}'
          and os.path.exists(os.path.join(b, "primi_piani", "BIANCHI", "1.jpg"))
          and not os.path.exists(os.path.join(b, "primi_piani", "VECCHIO"))
          and os.path.exists(os.path.join(b, "primi_piani", "LEGGI.txt"))
          and len(os.listdir(os.path.join(b, "backup_volti"))) == 1)
    print("ok  esporta e importa i volti, con copia di sicurezza" if ok else "ERRORE: esporta/importa i volti")
    errori += 0 if ok else 1
    manifesto = _json.dumps({"tipo": archivio.TIPO})
    for nome_cattivo in ("../fuori.txt", "dati/../../fuori.txt", "/etc/fuori", "config.json",
                         "smistafoto/mega.py", "C:/fuori.txt", "dati\\..\\fuori.txt"):
        cattivo = os.path.join(t, "cattivo.zip")
        with zipfile.ZipFile(cattivo, "w") as zz:
            zz.writestr(archivio.MANIFESTO, manifesto)
            zz.writestr("dati/riferimenti_auraface.json", "{}")
            zz.writestr(nome_cattivo, "x")
        deve_rifiutare_archivio = True
        try:
            archivio.importa(b, cattivo, os.path.join(b, "backup_volti"))
        except RuntimeError:
            deve_rifiutare_archivio = False
        if deve_rifiutare_archivio or os.path.exists(os.path.join(t, "fuori.txt")):
            print("ERRORE: archivio manomesso accettato:", nome_cattivo); errori += 1
        else:
            print("ok  rifiutato archivio con", nome_cattivo)
    if open(os.path.join(b, "dati", "riferimenti_auraface.json")).read() != '{"BIANCHI": {}}':
        print("ERRORE: un archivio rifiutato ha cambiato i volti"); errori += 1

# 10. aggiornamento con lo zip di GitHub: non tocca mai le cartelle dei dati, rifiuta percorsi
#     che escono dalla cartella e si può annullare
from smistafoto import aggiornamento  # noqa: E402
import io  # noqa: E402

with tempfile.TemporaryDirectory() as t:
    qui = os.path.join(t, "app")
    os.makedirs(os.path.join(qui, "smistafoto")); os.makedirs(os.path.join(qui, "dati")); os.makedirs(os.path.join(qui, "loghi", "AMADORI"))
    open(os.path.join(qui, "smista.py"), "w").write("vecchio")
    open(os.path.join(qui, "smistafoto", "__init__.py"), "w").write('VERSIONE = "1.0"\n')
    open(os.path.join(qui, "requirements.txt"), "w").write("numpy\n")
    open(os.path.join(qui, "dati", "riferimenti_auraface.json"), "w").write("VOLTI")
    open(os.path.join(qui, "loghi", "AMADORI", "logo.png"), "w").write("LOGO")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zz:
        for n, c in [("smista.py", "nuovo"), ("smistafoto/__init__.py", 'VERSIONE = "9.9"\n'), ("requirements.txt", "numpy\nnuovo\n"),
                     ("smistafoto/nuovo.py", "x"), ("dati/riferimenti_auraface.json", "SOVRASCRITTO"),
                     ("loghi/AMADORI/logo.png", "SOVRASCRITTO"), (".venv/x", "x"), ("../fuori.txt", "x"), ("smistafoto/../../fuori2.txt", "x")]:
            zz.writestr("megafacedetector-main/" + n, c)
    originale_scarica, originale_metodo = aggiornamento._scarica, aggiornamento.metodo
    aggiornamento._scarica = lambda url, attesa=30: (buf.getvalue() if "codeload" in url else
                                                     b'VERSIONE = "9.9"\n' if "__init__" in url else b"## Versioni\n- **9.9** (oggi): prova\n")
    aggiornamento.metodo = lambda q: "zip"

    class Muto:
        def __getattr__(self, n): return lambda *a, **k: None
    arrivata = aggiornamento.scarica_versione(qui, "1.0", Muto())
    leggi = lambda *p: open(os.path.join(qui, *p)).read()
    ok = (arrivata == "9.9" and leggi("smista.py") == "nuovo" and leggi("dati", "riferimenti_auraface.json") == "VOLTI"
          and leggi("loghi", "AMADORI", "logo.png") == "LOGO" and not os.path.exists(os.path.join(qui, ".venv"))
          and not os.path.exists(os.path.join(t, "fuori.txt")) and not os.path.exists(os.path.join(t, "fuori2.txt")))
    print("ok  aggiornamento: file nuovi al loro posto, dati e loghi intatti, percorsi esterni rifiutati" if ok else "ERRORE: aggiornamento zip")
    errori += 0 if ok else 1
    stato = _json.load(open(os.path.join(qui, aggiornamento.FILE_STATO), encoding="utf-8"))
    aggiornamento.ripristina(qui, stato)
    ok = (leggi("smista.py") == "vecchio" and leggi("requirements.txt") == "numpy\n"
          and not os.path.exists(os.path.join(qui, "smistafoto", "nuovo.py")) and leggi("dati", "riferimenti_auraface.json") == "VOLTI")
    print("ok  aggiornamento annullato: torna alla versione di prima" if ok else "ERRORE: ripristino dell'aggiornamento")
    errori += 0 if ok else 1
    aggiornamento._scarica, aggiornamento.metodo = originale_scarica, originale_metodo
for voce in sorted(aggiornamento.PROTETTI - {".git", "installazione.log", ".venv", aggiornamento.CARTELLA_BACKUP, aggiornamento.FILE_STATO}):
    gi_testo = open(os.path.join(radice, ".gitignore"), encoding="utf-8").read()
    if voce + "/" not in gi_testo and voce + "/*/" not in gi_testo:
        print("ERRORE: cartella protetta non esclusa da git:", voce); errori += 1

gi = open(os.path.join(radice, ".gitignore"), encoding="utf-8").read().split()
for voce in ("dati/", "lavori/", "primi_piani/*/", "loghi/", "backup_volti/", "SmistaFoto_volti_*.zip",
             ".aggiornamento.json", ".aggiornamento_backup/", ".requisiti_installati"):
    if voce not in gi:
        print("ERRORE: .gitignore non esclude", voce); errori += 1

print()
print("TUTTO OK" if not errori else f"{errori} PROBLEMI")
sys.exit(1 if errori else 0)
