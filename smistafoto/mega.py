"""Accesso alle cartelle su MEGA tramite MEGAcmd.

SICUREZZA DEL CLOUD — regole rigide, verificate prima di ogni comando:
  1. Si possono eseguire SOLO questi comandi MEGAcmd: whoami, ls, find (lettura),
     get, preview (download sul computer), mkdir, cp (creazione di cose nuove).
     Qualsiasi altro comando (rm, mv, put, sync, backup, share, export, import,
     transfers, ...) viene rifiutato dal programma prima di partire.
  2. Si scrive SOLO dentro la cartella dei giocatori (es. /2026-27/PLAYERS),
     e solo in sottocartelle di evento: PLAYERS/<NOME>/<COMPETIZIONE>/<EVENTO>/.
  3. Una copia non sovrascrive MAI: prima si verifica su MEGA che il file di
     destinazione non esista; se esiste, o se la verifica non è possibile,
     la copia non si fa.
  4. Percorsi con caratteri jolly (* ?) sono rifiutati, per evitare che un
     comando agisca su più file del previsto.
  5. Le cartelle di origine (MATCH/...) vengono solo lette e scaricate.
Nessuna funzione del programma cancella, sposta o rinomina file su MEGA.
"""

import os
import posixpath
import re
import shutil
import subprocess
import sys

ESTENSIONI_FOTO = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}

COMANDI_CONSENTITI = {"whoami", "ls", "find", "get", "preview", "mkdir", "cp"}
CARATTERI_VIETATI = set("*?")


class OperazioneVietata(RuntimeError):
    """Un'operazione che violerebbe le regole di sicurezza del cloud."""


def e_foto(percorso):
    return os.path.splitext(percorso)[1].lower() in ESTENSIONI_FOTO


def normalizza(percorso):
    """Accetta '2026-27/MATCH/...', '/2026-27/MATCH/...' oppure il percorso
    copiato dalla barra di MEGA ('Cloud drive > 2026-27 > MATCH > ...')."""
    p = percorso.strip().strip('"').strip("'").replace("\\", "/")
    parti = [x.strip() for x in p.split(">")] if ">" in p else p.split("/")
    parti = [x for x in parti if x and x.lower() not in ("cloud drive", "unità cloud")]
    return "/" + "/".join(parti)


def _decodifica(b):
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("cp1252", errors="replace")


def _pulito(percorso):
    """Percorso assoluto, senza '..' né caratteri jolly. Altrimenti errore."""
    if any(c in CARATTERI_VIETATI for c in percorso):
        raise OperazioneVietata(f"Percorso con caratteri non ammessi: {percorso}")
    parti = [p for p in percorso.split("/") if p]
    if any(p in (".", "..") for p in parti):
        raise OperazioneVietata(f"Percorso non ammesso: {percorso}")
    return "/" + "/".join(parti)


def _livelli_sotto(percorso, radice):
    """Quanti livelli sta 'percorso' sotto 'radice' (None se non ci sta dentro)."""
    p, r = _pulito(percorso).split("/")[1:], _pulito(radice).split("/")[1:]
    if len(p) <= len(r) or p[:len(r)] != r:
        return None
    return len(p) - len(r)


class Mega:
    """Usa i comandi di MEGAcmd, con le regole di sicurezza descritte sopra."""

    temporaneo = True  # i file scaricati sul computer si cancellano dopo l'uso

    def __init__(self, radice_scrittura):
        # tutte le scritture devono stare sotto questa cartella (PLAYERS)
        self.radice_scrittura = _pulito(radice_scrittura)
        if self.radice_scrittura.count("/") < 2:
            raise OperazioneVietata("La cartella dei giocatori in config.json è troppo generica.")
        self.cartella = self._trova_megacmd()
        if not self.cartella:
            raise RuntimeError(
                "Non trovo MEGAcmd. Installalo da https://mega.io/cmd e riprova.")

    @staticmethod
    def _trova_megacmd():
        nome = "mega-find.bat" if os.name == "nt" else "mega-find"
        trovato = shutil.which(nome)
        if trovato:
            return os.path.dirname(trovato)
        candidati = []
        if os.name == "nt":
            candidati.append(os.path.join(os.environ.get("LOCALAPPDATA", ""), "MEGAcmd"))
            candidati.append(r"C:\Program Files\MEGAcmd")
        elif sys.platform == "darwin":
            candidati.append("/Applications/MEGAcmd.app/Contents/MacOS")
        candidati += ["/usr/bin", "/usr/local/bin"]
        for c in candidati:
            if os.path.exists(os.path.join(c, nome)):
                return c
        return None

    def _esegui(self, comando, *argomenti, attesa=900):
        if comando not in COMANDI_CONSENTITI:
            raise OperazioneVietata(f"Comando MEGA non consentito: {comando}")
        # opzioni ammesse: solo -p per mkdir e -l per ls (elenco dettagliato, sola lettura)
        ammesse = {"mkdir": {"-p"}, "ls": {"-l"}}.get(comando, set())
        if any(str(a).startswith("-") and a not in ammesse for a in argomenti):
            raise OperazioneVietata(f"Opzione non consentita per {comando}: {argomenti}")
        exe = os.path.join(self.cartella, "mega-" + comando + (".bat" if os.name == "nt" else ""))
        try:
            # i comandi di MEGAcmd chiamano a loro volta mega-exec: la loro cartella
            # deve essere nel PATH, altrimenti sul Mac rispondono "command not found"
            ambiente = dict(os.environ)
            ambiente["PATH"] = self.cartella + os.pathsep + ambiente.get("PATH", "")
            r = subprocess.run([exe, *argomenti], capture_output=True, timeout=attesa, env=ambiente)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"MEGA non risponde da {attesa // 60} minuti ({comando}). "
                               "Controlla la connessione e che MEGAcmd sia aperto.")
        return r.returncode, _decodifica(r.stdout), _decodifica(r.stderr)

    def _controlla_scrittura(self, percorso, livelli_minimi):
        n = _livelli_sotto(percorso, self.radice_scrittura)
        if n is None or n < livelli_minimi:
            raise OperazioneVietata(
                f"Scrittura fuori dalle cartelle consentite: {percorso} "
                f"(consentito solo dentro {self.radice_scrittura}/<NOME>/<COMPETIZIONE>/<EVENTO>)")

    # ---------------------------------------------------------------- lettura

    def chi_sono(self):
        """L'email dell'account collegato, o None. La risposta grezza di MEGAcmd
        resta in self.risposta_whoami, per capire cosa non va."""
        rc, out, err = self._esegui("whoami", attesa=120)
        testo = (out + "\n" + err).strip()
        self.risposta_whoami = f"codice {rc}: {testo[:300]}"
        email = re.search(r"[\w.+\-]+@[\w\-]+\.[\w.\-]+", testo)
        return email.group(0) if email and "not logged" not in testo.lower() else None

    def elenca_nomi(self, cartella):
        """Nomi contenuti in una cartella (non ricorsivo). Cartella assente = []."""
        rc, out, _ = self._esegui("ls", _pulito(cartella))
        if rc != 0:
            return []
        # MEGAcmd può stampare un'intestazione con il percorso ("/2026-27/PLAYERS:"): non è un nome
        return [r.strip() for r in out.splitlines()
                if r.strip() and not (r.strip().endswith(":") and "/" in r)]

    def elenca_cartelle(self, cartella):
        """Per sfogliare: (sottocartelle, numero di foto) di una cartella. Solo lettura."""
        rc, out, err = self._esegui("ls", "-l", _pulito(cartella), attesa=120)
        if rc != 0:
            raise RuntimeError(f"Non riesco ad aprire {cartella}: {(err or out).strip()[:200]}")
        cartelle, foto = [], 0
        for riga in out.splitlines():
            m = re.match(r"^(\S{4})\s+\S+\s+\S+\s+\d{2}\w{3}\d{4} \d{2}:\d{2}:\d{2}\s+(.+)$", riga.strip())
            if not m:
                continue
            if m.group(1).startswith("d"):
                cartelle.append(m.group(2))
            elif e_foto(m.group(2)):
                foto += 1
        return cartelle, foto

    def esiste(self, percorso):
        """True se il percorso esiste su MEGA. In caso di dubbio risponde True,
        così la copia non parte."""
        rc, out, err = self._esegui("ls", _pulito(percorso))
        if rc == 0:
            return True
        testo = (out + err).lower()
        return not any(s in testo for s in ("couldn't find", "not found", "no such", "non trovat"))

    def trova_foto(self, cartella):
        """Tutte le foto dentro una cartella e le sue sottocartelle."""
        cartella = _pulito(cartella)
        rc, out, err = self._esegui("find", cartella)
        if rc != 0:
            raise RuntimeError(f"MEGA non trova la cartella {cartella}: {err.strip()}")
        base = cartella.lstrip("/")
        foto = []
        for riga in out.splitlines():
            riga = riga.strip()
            if not riga:
                continue
            if riga.startswith("/"):
                p = riga
            elif riga.startswith(base):
                p = "/" + riga
            else:
                p = posixpath.join(cartella, riga)
            if e_foto(p) and not any(c in CARATTERI_VIETATI for c in p):
                foto.append(p)
        return sorted(foto)

    # ---------------------------------------------- download (solo sul computer)

    def scarica_file(self, remota, file_locale):
        """Scarica un file sul computer. Restituisce il percorso, o None se non riesce."""
        os.makedirs(os.path.dirname(file_locale), exist_ok=True)
        rc, _, _ = self._esegui("get", _pulito(remota), file_locale)
        return file_locale if rc == 0 and os.path.exists(file_locale) else None

    def foto_per_imparare(self, remota, file_locale):
        """Scarica l'anteprima (circa 1000 px, leggera); se manca, l'originale.
        mega-preview senza opzioni scarica soltanto: non modifica il file su MEGA."""
        remota = _pulito(remota)
        os.makedirs(os.path.dirname(file_locale), exist_ok=True)
        rc, _, _ = self._esegui("preview", remota, file_locale)
        if rc == 0 and os.path.exists(file_locale) and os.path.getsize(file_locale) > 0:
            return file_locale
        rc, _, _ = self._esegui("get", remota, file_locale)
        return file_locale if rc == 0 and os.path.exists(file_locale) else None

    # ---------------------------------------- scrittura (solo creazione di cose nuove)

    def crea_cartella(self, cartella):
        # PLAYERS/<NOME>/<COMPETIZIONE>/<EVENTO>  -> almeno 3 livelli sotto PLAYERS
        self._controlla_scrittura(cartella, 3)
        self._esegui("mkdir", "-p", _pulito(cartella))

    def verifica_copia(self, origine, destinazione):
        """Le stesse regole della copia, senza copiare: usata anche dalla simulazione."""
        origine, destinazione = _pulito(origine), _pulito(destinazione)
        # PLAYERS/<NOME>/<COMPETIZIONE>/<EVENTO>/<file> -> almeno 4 livelli
        self._controlla_scrittura(destinazione, 4)
        if _livelli_sotto(origine, self.radice_scrittura) is not None:
            raise OperazioneVietata("Le foto di origine non possono stare dentro PLAYERS.")
        if not e_foto(destinazione):
            raise OperazioneVietata(f"La destinazione non è una foto: {destinazione}")
        return origine, destinazione

    def copia(self, origine, destinazione):
        """Copia un file dentro MEGA. Rifiuta se la destinazione esiste già."""
        origine, destinazione = self.verifica_copia(origine, destinazione)
        if self.esiste(destinazione):
            raise OperazioneVietata(f"Esiste già, non sovrascrivo: {destinazione}")
        rc, _, err = self._esegui("cp", origine, destinazione)
        if rc != 0:
            raise RuntimeError(err.strip() or "copia non riuscita")


class CartellaLocale:
    """SOLO PER I TEST: stessa interfaccia, su una cartella del computer.
    Anche qui non si cancella e non si sovrascrive nulla."""

    temporaneo = False  # i file sono gli originali: non si cancellano mai

    def __init__(self, radice, radice_scrittura):
        if not os.path.isdir(radice):
            raise RuntimeError(f"La cartella {radice} non esiste.")
        self.radice = radice
        self.radice_scrittura = _pulito(radice_scrittura)

    def _vero(self, remoto):
        return os.path.join(self.radice, *_pulito(remoto).split("/")[1:])

    def chi_sono(self):
        return "cartella locale " + self.radice

    def elenca_nomi(self, cartella):
        v = self._vero(cartella)
        return sorted(os.listdir(v)) if os.path.isdir(v) else []

    def esiste(self, percorso):
        return os.path.exists(self._vero(percorso))

    def elenca_cartelle(self, cartella):
        v = self._vero(cartella)
        if not os.path.isdir(v):
            raise RuntimeError(f"Non riesco ad aprire {cartella}")
        nomi = sorted(os.listdir(v))
        return ([n for n in nomi if os.path.isdir(os.path.join(v, n))],
                sum(1 for n in nomi if e_foto(n)))

    def trova_foto(self, cartella):
        v = self._vero(cartella)
        if not os.path.isdir(v):
            raise RuntimeError(f"Cartella non trovata: {cartella}")
        foto = []
        for dirpath, _, files in os.walk(v):
            for f in files:
                if e_foto(f):
                    rel = os.path.relpath(os.path.join(dirpath, f), self.radice)
                    foto.append("/" + rel.replace(os.sep, "/"))
        return sorted(foto)

    def scarica_file(self, remota, file_locale):
        return self._vero(remota)

    def foto_per_imparare(self, remota, file_locale):
        return self._vero(remota)

    def crea_cartella(self, cartella):
        n = _livelli_sotto(cartella, self.radice_scrittura)
        if n is None or n < 3:
            raise OperazioneVietata(f"Scrittura fuori dalle cartelle consentite: {cartella}")
        os.makedirs(self._vero(cartella), exist_ok=True)

    def verifica_copia(self, origine, destinazione):
        n = _livelli_sotto(destinazione, self.radice_scrittura)
        if n is None or n < 4:
            raise OperazioneVietata(f"Scrittura fuori dalle cartelle consentite: {destinazione}")
        if _livelli_sotto(origine, self.radice_scrittura) is not None:
            raise OperazioneVietata("Le foto di origine non possono stare dentro PLAYERS.")
        if not e_foto(destinazione):
            raise OperazioneVietata(f"La destinazione non è una foto: {destinazione}")
        return origine, destinazione

    def copia(self, origine, destinazione):
        self.verifica_copia(origine, destinazione)
        with open(self._vero(origine), "rb") as src, open(self._vero(destinazione), "xb") as dst:
            shutil.copyfileobj(src, dst)  # "x": fallisce se il file esiste già


def collegamento(cfg):
    if cfg.get("modalita") == "cartella_locale":
        return CartellaLocale(cfg["radice_locale"], cfg["cartella_giocatori"])
    return Mega(cfg["cartella_giocatori"])
