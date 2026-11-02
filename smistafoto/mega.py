"""Accesso alle cartelle: MEGA tramite MEGAcmd, oppure una cartella locale
(per chi usa la sincronizzazione di MEGA Desktop, e per i test)."""

import os
import posixpath
import shutil
import subprocess
import sys

ESTENSIONI_FOTO = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}


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


class Mega:
    """Usa i comandi di MEGAcmd (mega-find, mega-get, mega-cp...)."""

    temporaneo = True  # i file scaricati si possono cancellare dopo l'uso

    def __init__(self):
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

    def _esegui(self, comando, *argomenti):
        exe = os.path.join(self.cartella, "mega-" + comando + (".bat" if os.name == "nt" else ""))
        r = subprocess.run([exe, *argomenti], capture_output=True)
        return r.returncode, _decodifica(r.stdout), _decodifica(r.stderr)

    def chi_sono(self):
        rc, out, _ = self._esegui("whoami")
        return out.strip() if rc == 0 and "@" in out else None

    def elenca_nomi(self, cartella):
        """Nomi contenuti in una cartella (non ricorsivo). Cartella assente = []."""
        rc, out, _ = self._esegui("ls", cartella)
        if rc != 0:
            return []
        return [r.strip() for r in out.splitlines() if r.strip()]

    def trova_foto(self, cartella):
        """Tutte le foto dentro una cartella e le sue sottocartelle."""
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
            if e_foto(p):
                foto.append(p)
        return sorted(foto)

    def scarica_cartella(self, remota, locale):
        os.makedirs(locale, exist_ok=True)
        rc, _, err = self._esegui("get", remota, locale)
        if rc != 0:
            raise RuntimeError(f"Download non riuscito: {err.strip()}")
        return os.path.join(locale, posixpath.basename(remota.rstrip("/")))

    def foto_per_imparare(self, remota, file_locale):
        """Scarica l'anteprima (circa 1000 px, leggera); se manca, l'originale."""
        os.makedirs(os.path.dirname(file_locale), exist_ok=True)
        rc, _, _ = self._esegui("preview", remota, file_locale)
        if rc == 0 and os.path.exists(file_locale) and os.path.getsize(file_locale) > 0:
            return file_locale
        rc, _, _ = self._esegui("get", remota, file_locale)
        return file_locale if rc == 0 and os.path.exists(file_locale) else None

    def crea_cartella(self, cartella):
        self._esegui("mkdir", "-p", cartella)

    def copia(self, origine, destinazione):
        rc, _, err = self._esegui("cp", origine, destinazione)
        if rc != 0:
            raise RuntimeError(err.strip() or "copia non riuscita")


class CartellaLocale:
    """Stessa interfaccia, ma su una cartella del computer (MEGA Desktop sincronizzato)."""

    temporaneo = False  # i file sono gli originali: non si cancellano mai

    def __init__(self, radice):
        if not os.path.isdir(radice):
            raise RuntimeError(f"La cartella {radice} non esiste.")
        self.radice = radice

    def _vero(self, remoto):
        return os.path.join(self.radice, *[p for p in remoto.split("/") if p])

    def chi_sono(self):
        return "cartella locale " + self.radice

    def elenca_nomi(self, cartella):
        v = self._vero(cartella)
        return sorted(os.listdir(v)) if os.path.isdir(v) else []

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

    def scarica_cartella(self, remota, locale):
        return self._vero(remota)

    def foto_per_imparare(self, remota, file_locale):
        return self._vero(remota)

    def crea_cartella(self, cartella):
        os.makedirs(self._vero(cartella), exist_ok=True)

    def copia(self, origine, destinazione):
        shutil.copy2(self._vero(origine), self._vero(destinazione))


def collegamento(cfg):
    if cfg.get("modalita") == "cartella_locale":
        return CartellaLocale(cfg["radice_locale"])
    return Mega()
