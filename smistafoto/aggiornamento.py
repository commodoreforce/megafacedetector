"""Aggiornamento di Smista Foto dall'app: scarica la nuova versione da GitHub.

Tocca SOLO i file del programma su questo computer. Non usa l'archivio del club e non
tocca le cartelle con i dati di chi lo usa (dati/, lavori/, primi_piani/, loghi/,
backup_volti/) né l'ambiente Python (.venv/).

Come funziona, in due tempi:
  1. qui, con l'app aperta: si scaricano i file nuovi (con git se la cartella è una
     copia git, altrimenti con lo zip di GitHub) e si annota come tornare indietro;
  2. nel programma di avvio (smista.py), ad app chiusa: si aggiornano i componenti
     Python (pip) e si riapre l'app. Se qualcosa va storto si torna alla versione di
     prima. I componenti si aggiornano ad app chiusa perché su Windows i file di un
     componente in uso (es. OpenCV) non si possono sostituire.
"""

import io
import json
import os
import re
import shutil
import ssl
import subprocess
import time
import urllib.request
import zipfile

REPOSITORY = "commodoreforce/megafacedetector"
RAMO = "main"
# per le prove si può indicare un'altra fonte (es. file:///percorso/): il codice nuovo arriva
# comunque da git (origin) o dallo zip, questa serve solo a leggere versione e novità
URL_FILE = os.environ.get("SMISTA_FONTE_AGGIORNAMENTI") or f"https://raw.githubusercontent.com/{REPOSITORY}/{RAMO}/"
URL_ZIP = f"https://codeload.github.com/{REPOSITORY}/zip/refs/heads/{RAMO}"
FILE_STATO = ".aggiornamento.json"
CARTELLA_BACKUP = ".aggiornamento_backup"
# cartelle e file di chi usa l'app: un aggiornamento non li tocca mai
PROTETTI = {"dati", "lavori", "primi_piani", "loghi", "backup_volti", ".venv", ".git",
            CARTELLA_BACKUP, "installazione.log", FILE_STATO}
CODICE_RIAVVIO = 75  # il programma di avvio aggiorna i componenti e riapre l'app


def numero(versione):
    return tuple(int(x) for x in re.findall(r"\d+", str(versione))[:3])


def _contesto_ssl():
    try:
        import certifi  # sul Mac il Python di python.org non ha i certificati di sistema
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _scarica(url, attesa=30, intestazioni=None):
    richiesta = urllib.request.Request(url, headers={"User-Agent": "SmistaFoto", "Cache-Control": "no-cache",
                                                     **(intestazioni or {})})
    if not url.startswith("https://"):
        with urllib.request.urlopen(url, timeout=attesa) as r:  # solo per le prove (file://)
            return r.read()
    with urllib.request.urlopen(richiesta, timeout=attesa, context=_contesto_ssl()) as r:
        return r.read()


def _file_pubblicato(percorso):
    """Un file della versione pubblicata. Prima dall'API di GitHub (sempre aggiornata),
    poi da raw.githubusercontent.com (può restare indietro di qualche minuto)."""
    if "SMISTA_FONTE_AGGIORNAMENTI" not in os.environ:
        try:
            return _scarica(f"https://api.github.com/repos/{REPOSITORY}/contents/{percorso}?ref={RAMO}",
                            intestazioni={"Accept": "application/vnd.github.raw"})
        except Exception:
            pass  # es. troppe richieste dalla stessa rete: va bene anche la copia in cache
    return _scarica(URL_FILE + percorso)


def novita(versione_attuale):
    """Controlla su GitHub se c'è una versione nuova. Solo lettura, nessun file cambiato."""
    testo = _file_pubblicato("smistafoto/__init__.py").decode("utf-8")
    m = re.search(r'VERSIONE\s*=\s*"([^"]+)"', testo)
    if not m:
        raise RuntimeError("Non riesco a leggere la versione pubblicata.")
    nuova = m.group(1)
    data = re.search(r'DATA_VERSIONE\s*=\s*"([^"]+)"', testo)
    cosa = []
    if numero(nuova) > numero(versione_attuale):
        try:
            leggimi = _file_pubblicato("README.md").decode("utf-8")
            sezione = leggimi.split("## Versioni", 1)[1]
            for riga in sezione.splitlines():
                v = re.match(r"^- \*\*([\d.]+)\*\*\s*(\([^)]*\))?:?\s*(.*)$", riga.strip())
                if v and numero(v.group(1)) > numero(versione_attuale):
                    cosa.append({"versione": v.group(1), "testo": v.group(3).strip()})
        except Exception:
            pass
    return {"attuale": versione_attuale, "nuova": nuova, "data": data.group(1) if data else "",
            "disponibile": numero(nuova) > numero(versione_attuale), "novita": cosa[:6]}


# ------------------------------------------------------------------ git

def trova_git():
    trovato = shutil.which("git")
    if trovato:
        return trovato
    for c in (r"C:\Program Files\Git\cmd\git.exe", r"C:\Program Files (x86)\Git\cmd\git.exe",
              os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Programs\Git\cmd\git.exe"),
              "/usr/bin/git", "/opt/homebrew/bin/git", "/usr/local/bin/git"):
        if c and os.path.isfile(c):
            return c
    return None


def _git(git, qui, *argomenti, attesa=300):
    r = subprocess.run([git, *argomenti], cwd=qui, capture_output=True, timeout=attesa,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return r.returncode, r.stdout.decode("utf-8", "replace").strip(), r.stderr.decode("utf-8", "replace").strip()


def metodo(qui):
    if os.path.isdir(os.path.join(qui, ".git")) and trova_git():
        return "git"
    return "zip"


def _con_git(qui, reg):
    git = trova_git()
    rc, prima, _ = _git(git, qui, "rev-parse", "HEAD")
    if rc:
        raise RuntimeError("Non riesco a leggere la versione installata con git.")
    reg.info("Scarico la nuova versione da GitHub (git)…")
    rc, _, err = _git(git, qui, "fetch", "-q", "origin", RAMO)
    if rc:
        raise RuntimeError(f"Non riesco a contattare GitHub: {err[:200]}")
    # config.json non va modificato a mano: le scelte dell'app sono in dati/
    _git(git, qui, "checkout", "--", "config.json")
    rc, _, _ = _git(git, qui, "merge", "-q", "--ff-only", f"origin/{RAMO}")
    if rc:
        # cronologia ripulita su GitHub o file del programma modificati a mano:
        # si allinea alla versione pubblicata. Le cartelle dei dati non sono nel repository.
        rc, _, err = _git(git, qui, "reset", "-q", "--hard", f"origin/{RAMO}")
        if rc:
            raise RuntimeError(f"Aggiornamento con git non riuscito: {err[:200]}")
    return {"metodo": "git", "prima": prima}


def ripristina_git(qui, prima):
    git = trova_git()
    if git and prima:
        _git(git, qui, "reset", "-q", "--hard", prima)


# ------------------------------------------------------------------ zip

def _con_zip(qui, reg):
    reg.info("Scarico la nuova versione da GitHub (zip, circa 60 MB)…")
    dati = _scarica(URL_ZIP, attesa=600)
    with zipfile.ZipFile(io.BytesIO(dati)) as z:
        nomi = z.namelist()
        if not nomi:
            raise RuntimeError("Lo zip scaricato è vuoto.")
        radice = nomi[0].split("/")[0] + "/"
        if radice + "smista.py" not in nomi or radice + "smistafoto/__init__.py" not in nomi:
            raise RuntimeError("Lo zip scaricato non contiene Smista Foto.")
        backup = os.path.join(qui, CARTELLA_BACKUP)
        shutil.rmtree(backup, ignore_errors=True)
        os.makedirs(backup)
        nuovi, sostituiti = [], []
        radice_vera = os.path.realpath(qui)
        for info in z.infolist():
            if info.is_dir() or not info.filename.startswith(radice):
                continue
            rel = info.filename[len(radice):]
            parti = rel.split("/")
            if not rel or parti[0] in PROTETTI or any(p in ("", ".", "..") for p in parti) or "\\" in rel or ":" in rel:
                continue
            dest = os.path.realpath(os.path.join(qui, *parti))
            if not dest.startswith(radice_vera + os.sep):
                continue
            if os.path.exists(dest):  # copia di sicurezza per tornare indietro
                os.makedirs(os.path.dirname(os.path.join(backup, *parti)), exist_ok=True)
                shutil.copy2(dest, os.path.join(backup, *parti))
                sostituiti.append(rel)
            else:
                nuovi.append(rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with z.open(info) as src, open(dest + ".nuovo", "wb") as out:
                shutil.copyfileobj(src, out)
            os.replace(dest + ".nuovo", dest)
            if rel.endswith((".command", ".sh")):
                os.chmod(dest, 0o755)
    return {"metodo": "zip", "nuovi": nuovi, "sostituiti": sostituiti}


def ripristina_zip(qui, nuovi):
    backup = os.path.join(qui, CARTELLA_BACKUP)
    if os.path.isdir(backup):
        for cartella, _, files in os.walk(backup):
            for f in files:
                origine = os.path.join(cartella, f)
                dest = os.path.join(qui, os.path.relpath(origine, backup))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(origine, dest)
    for rel in nuovi or []:
        f = os.path.join(qui, *rel.split("/"))
        if os.path.isfile(f):
            os.remove(f)


# ------------------------------------------------------------------ insieme

def scarica_versione(qui, versione_attuale, reg):
    """Passo 1 (app aperta): file nuovi al loro posto e annotazione per tornare indietro.
    Restituisce la nuova versione. I componenti Python si aggiornano al riavvio."""
    info = novita(versione_attuale)
    if not info["disponibile"]:
        raise RuntimeError(f"Hai già l'ultima versione ({versione_attuale}).")
    with open(os.path.join(qui, "requirements.txt"), "rb") as f:
        requisiti_prima = f.read().decode("utf-8", "replace")
    m = metodo(qui)
    esito = _con_git(qui, reg) if m == "git" else _con_zip(qui, reg)
    with open(os.path.join(qui, "smistafoto", "__init__.py"), encoding="utf-8") as f:
        arrivata = re.search(r'VERSIONE\s*=\s*"([^"]+)"', f.read())
    esito.update(da=versione_attuale, a=arrivata.group(1) if arrivata else info["nuova"],
                 requisiti_prima=requisiti_prima, quando=time.strftime("%d/%m/%Y %H:%M"))
    with open(os.path.join(qui, FILE_STATO), "w", encoding="utf-8") as f:
        json.dump(esito, f, ensure_ascii=False)
    reg.ok(f"File della versione {esito['a']} scaricati ({m}). Ora aggiorno i componenti e riapro l'app.")
    return esito["a"]


def ripristina(qui, stato):
    """Torna ai file della versione di prima (usato dal programma di avvio se qualcosa va storto)."""
    if stato.get("metodo") == "git":
        ripristina_git(qui, stato.get("prima"))
    else:
        ripristina_zip(qui, stato.get("nuovi"))
