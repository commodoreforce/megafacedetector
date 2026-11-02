"""Le operazioni del programma: imparare i volti, analizzare una cartella,
copiare le foto approvate, provare su una partita già smistata."""

import csv
import json
import os
import posixpath
import re
import shutil
import time

import numpy as np
from PIL import Image

from .mega import e_foto
from .volti import volto_ricorrente


def _barra(i, n, testo=""):
    print(f"\r  {i}/{n} {testo[:50]:<50}", end="", flush=True)
    if i == n:
        print()


# ---------------------------------------------------------------- persone

def elenca_persone(cfg, conn):
    """Giocatori: cartelle dentro PLAYERS che non iniziano con '_'.
    Staff: cartelle dentro PLAYERS/_STAFF."""
    persone = []
    for tipo, base in (("giocatore", cfg["cartella_giocatori"]), ("staff", cfg["cartella_staff"])):
        for nome in conn.elenca_nomi(base):
            if nome.startswith("_") or "." in nome[-5:]:
                continue
            persone.append((nome, tipo, posixpath.join(base, nome)))
    return persone


def _campione(foto, quante, preferite, escludi=()):
    """Sceglie le foto da cui imparare: metà dalle cartelle preferite
    (es. MEDIADAY), il resto distribuito su tutta la stagione."""
    def distribuite(lista, k):
        if len(lista) <= k:
            return list(lista)
        passo = len(lista) / k
        return [lista[int(i * passo)] for i in range(k)]
    foto = [f for f in foto if not any(e.upper() in f.upper() for e in escludi)]
    pref = [f for f in foto if any(p.upper() in f.upper() for p in preferite)]
    altre = [f for f in foto if f not in set(pref)]
    scelte = distribuite(pref, quante // 2)
    scelte += distribuite(altre, quante - len(scelte))
    return scelte


def impara(cfg, conn, volti, rif, cartella_dati, tutti=False):
    persone = elenca_persone(cfg, conn)
    if not persone:
        print("Non trovo cartelle di giocatori o staff. Controlla i percorsi in config.json.")
        return
    da_fare = [p for p in persone if tutti or p[0] not in rif.info]
    print(f"Persone trovate: {len(persone)}. Da imparare adesso: {len(da_fare)}.")
    cartella_tmp = os.path.join(cartella_dati, "tmp_imparare")
    primi_piani = os.path.join(os.path.dirname(cartella_dati), "primi_piani")
    for n, (nome, tipo, cartella) in enumerate(da_fare, 1):
        print(f"\n[{n}/{len(da_fare)}] {nome} ({tipo})")
        try:
            foto = conn.trova_foto(cartella)
        except RuntimeError as e:
            print("  ", e)
            foto = []
        campione = _campione(foto, cfg["foto_per_imparare"], cfg["cartelle_preferite_per_imparare"],
                            cfg.get("escludi_da_imparare", []))
        per_foto = []
        for i, remota in enumerate(campione, 1):
            _barra(i, len(campione), posixpath.basename(remota))
            locale = conn.foto_per_imparare(remota, os.path.join(cartella_tmp, f"{i}{os.path.splitext(remota)[1]}"))
            if not locale:
                continue
            trovati, _ = volti.analizza(locale, minimo=24)
            per_foto.append([v["impronta"] for v in trovati[:4]])
            if conn.temporaneo:
                os.remove(locale)
        scelte = volto_ricorrente(per_foto)
        # primi piani forniti a mano: primi_piani/COGNOME/*.jpg
        extra = os.path.join(primi_piani, nome)
        if os.path.isdir(extra):
            for f in sorted(os.listdir(extra)):
                if e_foto(f):
                    trovati, _ = volti.analizza(os.path.join(extra, f), minimo=24)
                    if trovati:
                        scelte.append(trovati[0]["impronta"])
        rif.imposta(nome, tipo, cartella, scelte)
        rif.salva()
        print(f"  imparato da {len(scelte)} foto")
    shutil.rmtree(cartella_tmp, ignore_errors=True)
    rapporto_riferimenti(rif)


def rapporto_riferimenti(rif):
    deboli = [n for n, m in rif.impronte.items() if len(m) < 4]
    if deboli:
        print("\nRiferimenti deboli (meno di 4 foto utili): " + ", ".join(sorted(deboli)))
        print("Metti 3-5 primi piani di ciascuno in primi_piani/COGNOME/ e rilancia 'Impara'.")
    nomi = [n for n, m in rif.impronte.items() if len(m)]
    centri = {}
    for n in nomi:
        c = rif.impronte[n].mean(axis=0)
        centri[n] = c / (np.linalg.norm(c) + 1e-9)
    sospetti = [(a, b, float(centri[a] @ centri[b])) for i, a in enumerate(nomi)
                for b in nomi[i + 1:] if centri[a] @ centri[b] > 0.6]
    for a, b, s in sospetti:
        print(f"Attenzione: {a} e {b} si assomigliano troppo ({s:.2f}). "
              "Forse una delle due cartelle ha imparato il volto sbagliato.")


# ---------------------------------------------------------------- evento

def ricava_evento(cfg, sorgente):
    """Da .../MATCH/SERIEBKT/G10_Sudtirol_Cesena_1_1/Foto ricava
    competizione 'SERIE BKT' ed evento 'G10_SUDTIROL_CESENA'."""
    parti = [p for p in sorgente.split("/") if p]
    maiuscole = [p.upper() for p in parti]
    if "MATCH" not in maiuscole or maiuscole.index("MATCH") + 2 >= len(parti):
        return None, None
    i = maiuscole.index("MATCH")
    comp = parti[i + 1]
    chiave = re.sub(r"[\s_\-]", "", comp.upper())
    comp = cfg["competizioni"].get(chiave, comp.upper())
    evento = parti[i + 2]
    if cfg["nome_partita"]["togli_risultato"]:
        evento = re.sub(r"[_\s]+\d+[_\-]\d+$", "", evento)
    if cfg["nome_partita"]["maiuscolo"]:
        evento = evento.upper()
    return comp, evento


def _nome_destinazione(cfg, relativo):
    parti = relativo.split("/")
    if cfg["prefisso_fotografo"] and len(parti) > 1:
        return "_".join(parti[:-1]) + "_" + parti[-1]
    return parti[-1]


# ---------------------------------------------------------------- analisi

def analizza_cartella(cfg, conn, volti, rif, sorgente, competizione, evento, cartella_lavori):
    if not rif.impronte:
        raise RuntimeError("Prima bisogna imparare i volti (voce 1 del menu).")
    lavoro_dir = os.path.join(cartella_lavori, f"{evento}_{time.strftime('%Y%m%d-%H%M')}")
    mini_dir = os.path.join(lavoro_dir, "miniature")
    os.makedirs(mini_dir, exist_ok=True)

    print("Cerco le foto...")
    remote = conn.trova_foto(sorgente)
    if not remote:
        raise RuntimeError("Nella cartella non ci sono foto.")
    print(f"{len(remote)} foto. Le scarico (può volerci un po')...")
    radice_locale = conn.scarica_cartella(sorgente, os.path.join(lavoro_dir, "scaricate"))

    soglia_s, soglia_d, margine = cfg["soglia_sicura"], cfg["soglia_dubbia"], cfg["margine"]
    foto, lista_volti, impronte = [], [], []
    print("Riconosco i volti...")
    for i, r in enumerate(remote, 1):
        _barra(i, len(remote), posixpath.basename(r))
        rel = posixpath.relpath(r, sorgente)
        locale = os.path.join(radice_locale, *rel.split("/"))
        trovati, img = volti.analizza(locale)
        fid = len(foto)
        anteprima = f"f{fid}.jpg"
        if img is not None:
            _salva_ritaglio(img, None, os.path.join(mini_dir, anteprima), 520)
        foto.append({"id": fid, "remoto": r, "relativo": rel,
                     "nome_dest": _nome_destinazione(cfg, rel), "anteprima": anteprima})
        presenti = {}
        for v in trovati:
            classifica = rif.classifica(v["impronta"])
            if not classifica or classifica[0][0] < soglia_d:
                continue  # sconosciuto (avversari, tifosi): non si salva nulla
            s1, n1 = classifica[0]
            s2 = classifica[1][0] if len(classifica) > 1 else 0.0
            stato = "sicuro" if s1 >= soglia_s and s1 - s2 >= margine else "dubbio"
            vid = len(lista_volti)
            mini = f"v{vid}.jpg"
            _salva_ritaglio(img, v["riquadro"], os.path.join(mini_dir, mini), 200)
            voce = {"id": vid, "foto": fid, "mini": mini, "stato": stato, "persona": n1,
                    "punteggio": round(s1, 3),
                    "alternative": [[n, round(s, 3)] for s, n in classifica[1:3] if s >= soglia_d - 0.05]}
            if stato == "sicuro":
                if n1 in presenti:  # la stessa persona due volte nella stessa foto
                    altro = lista_volti[presenti[n1]]
                    perdente = voce if altro["punteggio"] >= s1 else altro
                    perdente["stato"] = "dubbio"
                    if perdente is altro:
                        presenti[n1] = vid
                else:
                    presenti[n1] = vid
            lista_volti.append(voce)
            impronte.append(v["impronta"])

    lavoro = {"sorgente": sorgente, "competizione": competizione, "evento": evento,
              "radice_locale": radice_locale, "temporaneo": conn.temporaneo,
              "persone": {n: i["tipo"] for n, i in sorted(rif.info.items())},
              "cartelle_persone": {n: i["cartella"] for n, i in rif.info.items()},
              "foto": foto, "volti": lista_volti, "copiato": False}
    with open(os.path.join(lavoro_dir, "lavoro.json"), "w", encoding="utf-8") as f:
        json.dump(lavoro, f, ensure_ascii=False)
    np.save(os.path.join(lavoro_dir, "impronte.npy"),
            np.asarray(impronte, np.float32).reshape(-1, 128))
    sicuri = sum(v["stato"] == "sicuro" for v in lista_volti)
    print(f"Fatto: {sicuri} volti riconosciuti con sicurezza, "
          f"{len(lista_volti) - sicuri} da verificare.")
    return lavoro_dir


def _salva_ritaglio(img, riquadro, percorso, lato):
    if riquadro:
        x, y, w, h = riquadro
        m = 0.45
        H, W = img.shape[:2]
        x0, y0 = max(0, int(x - w * m)), max(0, int(y - h * m))
        x1, y1 = min(W, int(x + w * (1 + m))), min(H, int(y + h * (1 + m)))
        img = img[y0:y1, x0:x1]
    im = Image.fromarray(img[:, :, ::-1])
    im.thumbnail((lato, lato))
    im.save(percorso, quality=82)


def carica_lavoro(lavoro_dir):
    with open(os.path.join(lavoro_dir, "lavoro.json"), encoding="utf-8") as f:
        lavoro = json.load(f)
    return lavoro, np.load(os.path.join(lavoro_dir, "impronte.npy"))


def ultimo_lavoro(cartella_lavori, anche_copiati=False):
    if not os.path.isdir(cartella_lavori):
        return None
    lavori = sorted((os.path.join(cartella_lavori, d) for d in os.listdir(cartella_lavori)),
                    key=os.path.getmtime, reverse=True)
    for d in lavori:
        p = os.path.join(d, "lavoro.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                if anche_copiati or not json.load(f).get("copiato"):
                    return d
    return None


# ---------------------------------------------------------------- copia

def esegui_copia(conn, rif, lavoro_dir, decisioni, stato):
    """decisioni: lista di {foto, persona, volto (facoltativo)}.
    stato: dizionario aggiornato durante la copia (lo legge la pagina)."""
    lavoro, impronte = carica_lavoro(lavoro_dir)
    foto = {f["id"]: f for f in lavoro["foto"]}
    piano, visti = {}, set()
    for d in decisioni:
        chiave = (int(d["foto"]), d["persona"])
        if chiave in visti or d["persona"] not in lavoro["cartelle_persone"]:
            continue
        visti.add(chiave)
        cartella = posixpath.join(lavoro["cartelle_persone"][d["persona"]],
                                  lavoro["competizione"], lavoro["evento"])
        piano.setdefault(cartella, []).append((foto[chiave[0]], d["persona"]))
    stato.update(totale=sum(len(v) for v in piano.values()), fatte=0,
                 copiate=0, gia_presenti=0, errori=[])
    registro = []
    for cartella, elementi in piano.items():
        presenti = set(conn.elenca_nomi(cartella))
        if not presenti:
            conn.crea_cartella(cartella)
        for f, persona in elementi:
            esito = "copiata"
            originale = posixpath.basename(f["relativo"])
            if f["nome_dest"] in presenti or originale in presenti:
                esito = "già presente"
                stato["gia_presenti"] += 1
            else:
                try:
                    conn.copia(f["remoto"], posixpath.join(cartella, f["nome_dest"]))
                    stato["copiate"] += 1
                except Exception as e:
                    esito = f"errore: {e}"
                    stato["errori"].append(f"{f['nome_dest']} → {persona}: {e}")
            registro.append([persona, f["relativo"], posixpath.join(cartella, f["nome_dest"]), esito])
            stato["fatte"] += 1

    with open(os.path.join(lavoro_dir, "registro.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["persona", "foto", "destinazione", "esito"])
        w.writerows(registro)

    # i volti confermati migliorano i riferimenti per la prossima volta
    for d in decisioni:
        if d.get("volto") is not None:
            rif.aggiungi_conferma(d["persona"], impronte[int(d["volto"])])
    rif.salva()

    lavoro["copiato"] = True
    with open(os.path.join(lavoro_dir, "lavoro.json"), "w", encoding="utf-8") as fh:
        json.dump(lavoro, fh, ensure_ascii=False)
    if lavoro.get("temporaneo"):
        shutil.rmtree(os.path.join(lavoro_dir, "scaricate"), ignore_errors=True)
    stato["finito"] = True


# ---------------------------------------------------------------- prova

def confronta(conn, lavoro_dir, cartella_esistente):
    """Confronta i risultati con lo smistamento già fatto a mano. Non copia nulla."""
    lavoro, _ = carica_lavoro(lavoro_dir)
    nomi_foto = {f["id"]: posixpath.basename(f["relativo"]) for f in lavoro["foto"]}
    insieme_nomi = set(nomi_foto.values())
    vero = set()
    for persona, cartella in lavoro["cartelle_persone"].items():
        dest = posixpath.join(cartella, lavoro["competizione"], cartella_esistente)
        for n in conn.elenca_nomi(dest):
            if n in insieme_nomi:
                vero.add((persona, n))
    sicuri = {(v["persona"], nomi_foto[v["foto"]]) for v in lavoro["volti"] if v["stato"] == "sicuro"}
    dubbi = {(v["persona"], nomi_foto[v["foto"]]) for v in lavoro["volti"] if v["stato"] == "dubbio"} - sicuri

    if not vero:
        print("Non trovo foto di questa partita nelle cartelle dei giocatori: controlla il nome della cartella.")
        return
    giuste = sicuri & vero
    print("\n=== RISULTATO DELLA PROVA ===")
    print(f"Assegnazioni fatte a mano:            {len(vero)}")
    print(f"Proposte sicure dello script:         {len(sicuri)}")
    print(f"  di cui giuste:                      {len(giuste)} "
          f"({100 * len(giuste) / max(1, len(sicuri)):.0f}% di precisione)")
    print(f"  sbagliate (persona sbagliata):      {len(sicuri - vero)}")
    print(f"Trovate automaticamente:              {100 * len(giuste) / len(vero):.0f}% del lavoro fatto a mano")
    print(f"Altre trovate tra i dubbi:            {len(dubbi & vero)}")
    print(f"Mancate del tutto:                    {len(vero - sicuri - dubbi)}")

    righe = []
    for persona in sorted({p for p, _ in vero | sicuri}):
        v = {n for p, n in vero if p == persona}
        s = {n for p, n in sicuri if p == persona}
        righe.append([persona, len(v), len(s & v), len(s - v), len(v - s)])
    with open(os.path.join(lavoro_dir, "prova.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["persona", "a mano", "giuste", "in più (sbagliate)", "mancate"])
        w.writerows(righe)
        w.writerow([])
        w.writerow(["dettaglio errori: persona", "foto", "tipo"])
        for p, n in sorted(sicuri - vero):
            w.writerow([p, n, "proposta ma non c'è nello smistamento a mano"])
        for p, n in sorted(vero - sicuri):
            w.writerow([p, n, "c'è a mano ma lo script non l'ha messa tra le sicure"])
    print(f"\nDettaglio per persona: {os.path.join(lavoro_dir, 'prova.csv')}")
