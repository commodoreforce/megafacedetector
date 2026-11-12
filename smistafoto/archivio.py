"""Esporta e importa i volti imparati (cartelle dati/ e primi_piani/) in un unico file .zip,
per portarli su un altro computer senza rifare l'apprendimento.

Lavora solo sul computer: non usa MEGA e non ha nessun modo di raggiungerlo.
Il file contiene impronte dei volti delle persone: va spostato a mano (chiavetta,
cartella interna del club), mai su GitHub o in chat.
"""

import json
import os
import shutil
import stat
import time
import zipfile

MANIFESTO = "smistafoto_volti.json"
TIPO = "smistafoto-volti"
RADICI = ("dati", "primi_piani")
MAX_FILE = 50_000
MAX_BYTE = 4 * 1024 ** 3          # 4 GB scompattati: ben oltre qualunque archivio reale
SALTA_CARTELLE = {"tmp_imparare", "__pycache__"}


def _file_da_esportare(qui):
    for radice in RADICI:
        base = os.path.join(qui, radice)
        if not os.path.isdir(base):
            continue
        for cartella, sottocartelle, files in os.walk(base):
            sottocartelle[:] = [d for d in sottocartelle if d not in SALTA_CARTELLE and not d.startswith(".")]
            for nome in files:
                if nome.startswith("."):
                    continue
                completo = os.path.join(cartella, nome)
                if os.path.islink(completo) or not os.path.isfile(completo):
                    continue
                rel = os.path.relpath(completo, qui).replace(os.sep, "/")
                if radice == "primi_piani" and rel.count("/") < 2:
                    continue  # LEGGI.txt e simili: fanno parte del programma, non dei volti
                yield completo, rel


def esporta(qui, destinazione, versione_app="", persone=0, modello=""):
    """Scrive in `destinazione` uno zip con dati/ e primi_piani/. Ritorna il riepilogo."""
    n_file = n_pp = 0
    with zipfile.ZipFile(destinazione, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for completo, rel in _file_da_esportare(qui):
            # le foto sono già compresse: le salvo così come sono, è molto più veloce
            metodo = zipfile.ZIP_STORED if rel.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".npz")) else zipfile.ZIP_DEFLATED
            z.write(completo, rel, compress_type=metodo)
            n_file += 1
            if rel.startswith("primi_piani/") and rel.count("/") >= 2:
                n_pp += 1
        riepilogo = {"tipo": TIPO, "versione_app": versione_app, "creato_il": time.strftime("%Y-%m-%d %H:%M"),
                     "modello": modello, "persone": persone, "file": n_file, "primi_piani": n_pp}
        z.writestr(MANIFESTO, json.dumps(riepilogo, ensure_ascii=False, indent=2))
    if not n_file:
        os.remove(destinazione)
        raise RuntimeError("Su questo computer non ci sono ancora volti imparati da esportare.")
    return riepilogo


def _nome_sicuro(nome):
    """Il percorso dentro lo zip deve stare in dati/ o primi_piani/, senza trucchi."""
    if "\\" in nome or ":" in nome or nome.startswith("/") or "\x00" in nome:
        return False
    parti = nome.rstrip("/").split("/")
    if any(p in ("", ".", "..") for p in parti):
        return False
    return parti[0] in RADICI and len(parti) >= 2


def controlla_archivio(percorso_zip):
    """Verifica il file senza scompattarlo. Ritorna (manifesto, membri da estrarre)."""
    if not zipfile.is_zipfile(percorso_zip):
        raise RuntimeError("Questo file non è un archivio di Smista Foto (non è uno .zip valido).")
    with zipfile.ZipFile(percorso_zip) as z:
        infos = z.infolist()
        nomi = {i.filename for i in infos}
        if MANIFESTO not in nomi:
            raise RuntimeError("Questo .zip non è stato creato con «Esporta i volti» di Smista Foto.")
        try:
            manifesto = json.loads(z.read(MANIFESTO).decode("utf-8"))
        except Exception:
            raise RuntimeError("L'archivio è rovinato: il riepilogo interno non si legge.")
        if manifesto.get("tipo") != TIPO:
            raise RuntimeError("Questo .zip non è stato creato con «Esporta i volti» di Smista Foto.")
        membri, totale = [], 0
        for i in infos:
            if i.filename == MANIFESTO or i.is_dir():
                continue
            if not _nome_sicuro(i.filename):
                raise RuntimeError(f"L'archivio contiene un percorso non ammesso ({i.filename}): non lo importo.")
            if stat.S_ISLNK(i.external_attr >> 16):
                raise RuntimeError("L'archivio contiene un collegamento simbolico: non lo importo.")
            totale += i.file_size
            membri.append(i)
        if len(membri) > MAX_FILE or totale > MAX_BYTE:
            raise RuntimeError("L'archivio è troppo grande per essere un'esportazione dei volti.")
        if not any(m.filename.startswith("dati/riferimenti") and m.filename.endswith(".json") for m in membri):
            raise RuntimeError("L'archivio non contiene volti imparati.")
        z.testzip()
    return manifesto, membri


def importa(qui, percorso_zip, cartella_backup, versione_app=""):
    """Sostituisce dati/ e primi_piani/ con il contenuto dell'archivio.
    Prima salva una copia di quelli attuali in `cartella_backup`."""
    manifesto, membri = controlla_archivio(percorso_zip)

    # 1. copia di sicurezza di quello che c'è adesso
    backup = None
    if any(True for _ in _file_da_esportare(qui)):
        os.makedirs(cartella_backup, exist_ok=True)
        backup = os.path.join(cartella_backup, time.strftime("volti_prima_di_importare_%Y%m%d-%H%M%S.zip"))
        esporta(qui, backup, versione_app)

    # 2. scompatto in una cartella temporanea, controllando ogni percorso
    tmp = os.path.join(qui, ".importazione_tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    try:
        radice_tmp = os.path.realpath(tmp)
        with zipfile.ZipFile(percorso_zip) as z:
            for m in membri:
                dest = os.path.realpath(os.path.join(tmp, *m.filename.split("/")))
                if not dest.startswith(radice_tmp + os.sep):
                    raise RuntimeError("Percorso non ammesso nell'archivio: importazione annullata.")
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with z.open(m) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out, 1024 * 1024)

        # 3. sostituisco: dati/ per intero, in primi_piani/ solo le cartelle delle persone
        vecchi = os.path.join(qui, ".dati_prima_di_importare")
        shutil.rmtree(vecchi, ignore_errors=True)
        dati = os.path.join(qui, "dati")
        if os.path.isdir(dati):
            os.replace(dati, vecchi)
        try:
            nuovi_dati = os.path.join(tmp, "dati")
            if os.path.isdir(nuovi_dati):
                os.replace(nuovi_dati, dati)
            else:
                os.makedirs(dati)
        except Exception:
            if os.path.isdir(vecchi) and not os.path.isdir(dati):
                os.replace(vecchi, dati)
            raise
        shutil.rmtree(vecchi, ignore_errors=True)

        pp = os.path.join(qui, "primi_piani")
        os.makedirs(pp, exist_ok=True)
        for d in os.listdir(pp):
            if os.path.isdir(os.path.join(pp, d)) and not os.path.islink(os.path.join(pp, d)):
                shutil.rmtree(os.path.join(pp, d))
        nuovi_pp = os.path.join(tmp, "primi_piani")
        if os.path.isdir(nuovi_pp):
            for d in os.listdir(nuovi_pp):
                if os.path.isdir(os.path.join(nuovi_pp, d)):
                    os.replace(os.path.join(nuovi_pp, d), os.path.join(pp, d))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"manifesto": manifesto, "backup": os.path.relpath(backup, qui) if backup else None}
