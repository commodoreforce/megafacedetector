"""Le operazioni del programma: imparare i volti, analizzare una cartella,
copiare le foto approvate, provare su una partita già smistata.
Ogni operazione racconta cosa sta facendo nel registro (reg)."""

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


# ---------------------------------------------------------------- persone

def elenca_persone(cfg, conn, esclusi=()):
    """Giocatori: cartelle dentro PLAYERS che non iniziano con '_'.
    Staff: cartelle dentro PLAYERS/_STAFF."""
    persone = []
    for tipo, base in (("giocatore", cfg["cartella_giocatori"]), ("staff", cfg["cartella_staff"])):
        for nome in conn.elenca_nomi(base):
            if nome.startswith("_") or "." in nome[-5:] or nome in esclusi:
                continue
            persone.append((nome, tipo, posixpath.join(base, nome)))
    return persone


def _campione(foto, quante, preferite):
    """Sceglie le foto da cui imparare: metà dalle cartelle preferite
    (es. MEDIADAY), il resto distribuito su tutta la stagione."""
    def distribuite(lista, k):
        if len(lista) <= k:
            return list(lista)
        passo = len(lista) / k
        return [lista[int(i * passo)] for i in range(k)]
    pref = [f for f in foto if any(p.upper() in f.upper() for p in preferite)]
    altre = [f for f in foto if f not in set(pref)]
    scelte = distribuite(pref, quante // 2)
    scelte += distribuite(altre, quante - len(scelte))
    return scelte


def impara(cfg, conn, volti, rif, cartella_dati, reg, tutti=False, solo=None, esclusi=()):
    reg.inizia_fase("Leggo l'elenco di giocatori e staff")
    reg.info(f"Leggo l'elenco delle cartelle in {cfg['cartella_giocatori']} e {cfg['cartella_staff']}…")
    persone = elenca_persone(cfg, conn, esclusi)
    if esclusi:
        reg.info("Escluse perché non sono persone: " + ", ".join(sorted(esclusi)) + ".")
    if not persone:
        reg.errore("Non trovo cartelle di giocatori o staff. Controlla i percorsi in config.json.")
        return
    n_g = sum(p[1] == "giocatore" for p in persone)
    if solo:
        da_fare = [p for p in persone if p[0] in solo]
    else:
        da_fare = [p for p in persone if tutti or p[0] not in rif.info]
    reg.info(f"Trovati {n_g} giocatori e {len(persone) - n_g} persone dello staff.")
    if not da_fare:
        reg.ok("Conosco già tutti. Niente da imparare.")
        return
    reg.info(f"Da imparare adesso: {len(da_fare)} persone. Per ognuna scarico circa "
             f"{cfg['foto_per_imparare']} anteprime (solo sul computer, poi le cancello).")
    cartella_tmp = os.path.join(cartella_dati, "tmp_imparare")
    primi_piani = os.path.join(os.path.dirname(cartella_dati), "primi_piani")
    deboli = []
    for n, (nome, tipo, cartella) in enumerate(da_fare, 1):
        reg.inizia_fase(f"Persona {n} di {len(da_fare)}: {nome}")
        reg.info(f"{nome} ({tipo}): cerco le sue foto su MEGA…")
        try:
            foto = conn.trova_foto(cartella)
        except RuntimeError as e:
            reg.avviso(f"{nome}: {e}")
            foto = []
        campione = _campione(foto, cfg["foto_per_imparare"], cfg["cartelle_preferite_per_imparare"])
        reg.info(f"{nome}: {len(foto)} foto in archivio, ne guardo {len(campione)}.")
        reg.inizia_fase(f"Persona {n} di {len(da_fare)}: {nome}", len(campione))
        per_foto, fonti_foto = [], []
        for i, remota in enumerate(campione, 1):
            reg.passo(i, posixpath.basename(remota))
            locale = conn.foto_per_imparare(remota, os.path.join(cartella_tmp, f"{i}{os.path.splitext(remota)[1]}"))
            if not locale:
                continue
            trovati, _ = volti.analizza(locale, minimo=24)
            per_foto.append([v["impronta"] for v in trovati[:4]])
            fonti_foto.append(remota)
            if conn.temporaneo:
                os.remove(locale)
        scelte = [(fonti_foto[i], e) for i, e in volto_ricorrente(per_foto)]
        extra = os.path.join(primi_piani, nome)  # primi piani forniti a mano
        if os.path.isdir(extra):
            for f in sorted(os.listdir(extra)):
                if e_foto(f):
                    trovati, _ = volti.analizza(os.path.join(extra, f), minimo=24)
                    if trovati:
                        scelte.append(("primi_piani/" + f, trovati[0]["impronta"]))
        rif.imposta(nome, tipo, cartella, [e for _, e in scelte], [p for p, _ in scelte])
        rif.salva()
        if len(scelte) < 4:
            deboli.append(nome)
            reg.avviso(f"{nome}: imparato solo da {len(scelte)} foto. Servono primi piani.")
        else:
            reg.ok(f"{nome}: imparato da {len(scelte)} foto.")
    shutil.rmtree(cartella_tmp, ignore_errors=True)
    reg.inizia_fase("Controllo finale")
    rapporto_riferimenti(rif, reg)
    reg.ok("Apprendimento finito.")


def deboli(rif):
    return sorted(n for n, m in rif.impronte.items() if len(m) < 4)


def rapporto_riferimenti(rif, reg):
    d = deboli(rif)
    if d:
        reg.avviso("Riferimenti deboli: " + ", ".join(d) + ". Aggiungi 3-5 primi piani "
                   "dall'«Elenco delle persone» (pulsante «Primi piani…»).")
    nomi = [n for n, m in rif.impronte.items() if len(m)]
    centri = {}
    for n in nomi:
        c = rif.impronte[n].mean(axis=0)
        centri[n] = c / (np.linalg.norm(c) + 1e-9)
    for i, a in enumerate(nomi):
        for b in nomi[i + 1:]:
            s = float(centri[a] @ centri[b])
            if s > 0.6:
                reg.avviso(f"{a} e {b} si assomigliano troppo ({s:.2f}): forse una delle due "
                           "cartelle contiene soprattutto foto dell'altro. Va controllato.")


# ---------------------------------------------------------------- evento

def ricava_evento(cfg, sorgente):
    """Da .../MATCH/SERIEBKT/G10_Sudtirol_Cesena_1_1/Foto ricava
    competizione 'SERIE BKT' ed evento 'G10_SUDTIROL_CESENA'."""
    parti = [p for p in sorgente.split("/") if p]
    maiuscole = [p.upper() for p in parti]
    if "MATCH" not in maiuscole or maiuscole.index("MATCH") + 2 >= len(parti):
        return "", ""
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


def _parole(testo):
    """'775A5502.Fantozzi_S.jpg' -> ['775a5502', 'fantozzi', 's', 'jpg']; senza accenti."""
    import unicodedata
    t = unicodedata.normalize("NFKD", testo).encode("ascii", "ignore").decode().lower()
    return [p for p in re.split(r"[^a-z0-9]+", t) if p]


def nomi_nel_file(nome_file, persone):
    """Persone il cui nome compare come parola intera nel nome del file
    (i fotografi a volte scrivono il cognome nel file)."""
    parole = _parole(os.path.splitext(nome_file)[0])
    trovati = []
    for persona in persone:
        p = _parole(persona)
        unito = "".join(p)  # D'URBANO -> durbano, DALLA VECCHIA -> dallavecchia
        if p and len(unito) >= 4 and (unito in parole or
                                      any(parole[i:i + len(p)] == p for i in range(len(parole)))):
            trovati.append(persona)
    return trovati


def _nome_destinazione(cfg, relativo):
    parti = relativo.split("/")
    if cfg["prefisso_fotografo"] and len(parti) > 1:
        return "_".join(parti[:-1]) + "_" + parti[-1]
    return parti[-1]


def trova_cartella_esistente(conn, rif, competizione, evento):
    """Cerca nelle cartelle dei giocatori la cartella della partita già smistata.
    Prima il nome esatto, poi una cartella che inizi con lo stesso numero di giornata."""
    giornata = evento.split("_")[0] + "_"
    candidati, guardati = {}, 0
    for nome, info in rif.info.items():
        if info.get("tipo") != "giocatore":
            continue
        guardati += 1
        for c in conn.elenca_nomi(posixpath.join(info["cartella"], competizione)):
            if c.upper() == evento.upper():
                return c
            if c.upper().startswith(giornata.upper()):
                candidati[c] = candidati.get(c, 0) + 1
        if (len(candidati) == 1 and sum(candidati.values()) >= 3) or guardati >= 10:
            break
    return max(candidati, key=candidati.get) if len(candidati) == 1 else ""


# ---------------------------------------------------------------- analisi

def analizza_cartella(cfg, conn, volti, rif, sorgente, competizione, evento,
                      cartella_lavori, reg, prova_su=None):
    if not rif.impronte:
        raise RuntimeError("Prima bisogna imparare i volti.")
    lavoro_dir = os.path.join(cartella_lavori, f"{evento}_{time.strftime('%Y%m%d-%H%M%S')}")
    mini_dir = os.path.join(lavoro_dir, "miniature")
    tmp_dir = os.path.join(lavoro_dir, "tmp")
    os.makedirs(mini_dir, exist_ok=True)

    reg.inizia_fase("Cerco le foto su MEGA")
    reg.info(f"Cerco le foto in {sorgente}…")
    remote = conn.trova_foto(sorgente)
    if not remote:
        raise RuntimeError("Nella cartella non ci sono foto.")
    sotto = sorted({posixpath.relpath(r, sorgente).split("/")[0]
                    for r in remote if "/" in posixpath.relpath(r, sorgente)})
    reg.info(f"Trovate {len(remote)} foto" + (f" (sottocartelle: {', '.join(sotto)})." if sotto else "."))
    reg.info("Scarico e analizzo una foto alla volta. Le foto restano sul computer solo il tempo dell'analisi.")

    soglia_s, soglia_d, margine = cfg["soglia_sicura"], cfg["soglia_dubbia"], cfg["margine"]
    foto, lista_volti, impronte = [], [], []
    reg.inizia_fase("Riconosco i volti", len(remote))
    illeggibili = nomi_trovati = 0
    for i, r in enumerate(remote, 1):
        rel = posixpath.relpath(r, sorgente)
        reg.passo(i, rel)
        locale = conn.scarica_file(r, os.path.join(tmp_dir, f"{i}{os.path.splitext(r)[1]}"))
        trovati, img = volti.analizza(locale) if locale else ([], None)
        if conn.temporaneo and locale and os.path.exists(locale):
            os.remove(locale)
        fid = len(foto)
        anteprima = f"f{fid}.jpg"
        if img is not None:
            _salva_ritaglio(img, None, os.path.join(mini_dir, anteprima), 520)
        else:
            illeggibili += 1
        foto.append({"id": fid, "remoto": r, "relativo": rel,
                     "nome_dest": _nome_destinazione(cfg, rel), "anteprima": anteprima})
        presenti = {}
        largo_max = trovati[0]["riquadro"][2] if trovati else 1
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
                    "punteggio": round(s1, 3), "larghezza": int(v["riquadro"][2]),
                    "relativa": round(v["riquadro"][2] / largo_max, 2),
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
        # nome scritto nel file dal fotografo: SOLO un suggerimento (a volte è sbagliato).
        # Non rende mai sicura un'assegnazione e non cambia quelle del riconoscimento.
        for persona in nomi_nel_file(posixpath.basename(r), rif.info):
            nomi_trovati += 1
            if any(v["foto"] == fid and v["persona"] == persona for v in lista_volti):
                continue  # il volto è già stato riconosciuto come quella persona
            vid = len(lista_volti)
            lista_volti.append({"id": vid, "foto": fid, "mini": anteprima, "stato": "dubbio",
                                "persona": persona, "punteggio": 0.0, "dal_nome": True,
                                "solo_nome": True, "alternative": []})
            impronte.append(np.zeros(128, np.float32))
        if i % 25 == 0:
            reg.info(f"Analizzate {i} foto su {len(remote)}…")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    if nomi_trovati:
        reg.info(f"In {nomi_trovati} casi il nome del file contiene un cognome: dove il volto non "
                 "l'ha confermato, la foto è tra quelle da verificare con il nome come suggerimento.")
    if illeggibili:
        reg.avviso(f"{illeggibili} foto non si sono potute aprire (formato non supportato o download fallito).")

    lavoro = {"sorgente": sorgente, "competizione": competizione, "evento": evento,
              "creato": time.strftime("%d/%m/%Y %H:%M"), "prova_su": prova_su,
              "persone": {n: i["tipo"] for n, i in sorted(rif.info.items())},
              "cartelle_persone": {n: i["cartella"] for n, i in rif.info.items()},
              "foto": foto, "volti": lista_volti, "copiato": False}
    with open(os.path.join(lavoro_dir, "lavoro.json"), "w", encoding="utf-8") as f:
        json.dump(lavoro, f, ensure_ascii=False)
    np.save(os.path.join(lavoro_dir, "impronte.npy"),
            np.asarray(impronte, np.float32).reshape(-1, 128))
    sicuri = [v for v in lista_volti if v["stato"] == "sicuro"]
    reg.ok(f"Analisi finita: {len(sicuri)} volti riconosciuti con sicurezza "
           f"({len({v['persona'] for v in sicuri})} persone), "
           f"{len(lista_volti) - len(sicuri)} da verificare.")
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


def elenca_lavori(cartella_lavori):
    """Le analisi salvate, dalla più recente."""
    if not os.path.isdir(cartella_lavori):
        return []
    lavori = []
    for d in os.listdir(cartella_lavori):
        p = os.path.join(cartella_lavori, d, "lavoro.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                l = json.load(f)
            prova = None
            pp = os.path.join(cartella_lavori, d, "prova.json")
            if os.path.exists(pp):
                with open(pp, encoding="utf-8") as f:
                    prova = json.load(f)
            lavori.append({"id": d, "evento": l["evento"], "competizione": l["competizione"],
                           "creato": l.get("creato", ""), "copiato": l.get("copiato", False),
                           "foto": len(l["foto"]), "prova": prova,
                           "ordine": os.path.getmtime(p)})
    return sorted(lavori, key=lambda x: -x["ordine"])


# ---------------------------------------------------------------- copia

def _piano(lavoro, decisioni):
    """{cartella di destinazione: [(foto, persona), ...]} dalle decisioni della revisione."""
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
    return piano


def simula_copia(conn, lavoro_dir, decisioni, reg):
    """SIMULAZIONE: fa tutti i controlli della copia vera ma su MEGA legge soltanto.
    Dice, foto per foto, cosa succederebbe."""
    lavoro, _ = carica_lavoro(lavoro_dir)
    piano = _piano(lavoro, decisioni)
    totale = sum(len(v) for v in piano.values())
    reg.info(f"SIMULAZIONE (non scrive niente su MEGA): controllo {totale} copie in {len(piano)} cartelle…")
    reg.inizia_fase("Simulazione della copia", totale)
    persone, righe, fatte = [], [], 0
    for cartella, elementi in sorted(piano.items()):
        persona = elementi[0][1]
        nuova = not conn.esiste(cartella)
        presenti = set() if nuova else set(conn.elenca_nomi(cartella))
        conta = {"copierebbe": 0, "salterebbe": 0, "bloccata": 0}
        for f, p in elementi:
            originale = posixpath.basename(f["relativo"])
            dest = posixpath.join(cartella, f["nome_dest"])
            try:
                conn.verifica_copia(f["remoto"], dest)
                if f["nome_dest"] in presenti or originale in presenti:
                    esito, chiave = "già presente: verrebbe saltata", "salterebbe"
                else:
                    esito, chiave = "verrebbe copiata", "copierebbe"
            except Exception as e:
                esito, chiave = f"bloccata dalle regole di sicurezza: {e}", "bloccata"
            conta[chiave] += 1
            righe.append([p, f["relativo"], dest, esito])
            fatte += 1
            reg.passo(fatte, f"{p}: {f['nome_dest']}")
        persone.append({"persona": persona, "cartella": cartella, "nuova": nuova, **conta})
        reg.info(f"{persona}: {conta['copierebbe']} da copiare, {conta['salterebbe']} già presenti"
                 + (", cartella nuova" if nuova else "") + (f", {conta['bloccata']} BLOCCATE" if conta["bloccata"] else "") + ".")
    with open(os.path.join(lavoro_dir, "simulazione.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["persona", "foto", "destinazione", "cosa succederebbe"])
        w.writerows(righe)
    ris = {"persone": persone,
           "copierebbe": sum(p["copierebbe"] for p in persone),
           "salterebbe": sum(p["salterebbe"] for p in persone),
           "bloccata": sum(p["bloccata"] for p in persone),
           "cartelle_nuove": sum(p["nuova"] for p in persone),
           "dettaglio": righe[:3000]}
    (reg.ok if not ris["bloccata"] else reg.avviso)(
        f"Simulazione finita: {ris['copierebbe']} foto verrebbero copiate, {ris['salterebbe']} saltate perché "
        f"già presenti, {ris['cartelle_nuove']} cartelle nuove, {ris['bloccata']} bloccate. Su MEGA non è cambiato nulla.")
    return ris


def esegui_copia(conn, rif, lavoro_dir, decisioni, reg):
    """decisioni: lista di {foto, persona, volto (facoltativo)}."""
    lavoro, impronte = carica_lavoro(lavoro_dir)
    if lavoro.get("copiato"):
        raise RuntimeError("Questa analisi è già stata copiata.")
    if lavoro.get("prova_su"):
        raise RuntimeError("Questa era una prova: non si copia. Avvia lo smistamento normale.")
    piano = _piano(lavoro, decisioni)
    totale = sum(len(v) for v in piano.values())
    reg.info(f"Copio {totale} foto nelle cartelle di {len(piano)} persone, "
             f"sottocartella {lavoro['competizione']}/{lavoro['evento']}.")
    reg.inizia_fase("Copio le foto su MEGA", totale)
    fatte = copiate = gia = 0
    errori, registro = [], []
    for cartella, elementi in piano.items():
        persona = elementi[0][1]
        try:
            presenti = set(conn.elenca_nomi(cartella))
            if not presenti:
                conn.crea_cartella(cartella)
        except Exception as e:  # cartella non consentita o MEGA irraggiungibile: salta il gruppo
            reg.errore(f"{persona}: non posso usare la cartella ({e}). Salto le sue foto.")
            for f, p in elementi:
                errori.append(f"{f['nome_dest']} → {p}: {e}")
                registro.append([p, f["relativo"], cartella, f"errore: {e}"])
                fatte += 1
            continue
        c0 = copiate
        for f, p in elementi:
            originale = posixpath.basename(f["relativo"])
            dest = posixpath.join(cartella, f["nome_dest"])
            if f["nome_dest"] in presenti or originale in presenti or conn.esiste(dest):
                esito = "già presente"
                gia += 1
            else:
                try:
                    conn.copia(f["remoto"], dest)  # rifiuta comunque se dest esiste
                    esito = "copiata"
                    copiate += 1
                except Exception as e:
                    esito = f"errore: {e}"
                    errori.append(f"{f['nome_dest']} → {p}: {e}")
            registro.append([p, f["relativo"], dest, esito])
            fatte += 1
            reg.passo(fatte, f"{p}: {f['nome_dest']}")
        reg.info(f"{persona}: {copiate - c0} foto copiate.")

    with open(os.path.join(lavoro_dir, "registro.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["persona", "foto", "destinazione", "esito"])
        w.writerows(registro)

    for d in decisioni:  # i volti confermati migliorano i riferimenti
        if d.get("volto") is not None and np.any(impronte[int(d["volto"])]):
            rif.aggiungi_conferma(d["persona"], impronte[int(d["volto"])],
                                  "conferma:" + lavoro["sorgente"])
    rif.salva()
    lavoro["copiato"] = True
    with open(os.path.join(lavoro_dir, "lavoro.json"), "w", encoding="utf-8") as fh:
        json.dump(lavoro, fh, ensure_ascii=False)

    for e in errori[:20]:
        reg.errore(e)
    (reg.ok if not errori else reg.avviso)(
        f"Copia finita: {copiate} copiate, {gia} già presenti (saltate), {len(errori)} errori.")
    return {"copiate": copiate, "gia_presenti": gia, "errori": errori}


# ---------------------------------------------------------------- prova

def confronta(conn, lavoro_dir, cartella_esistente, reg):
    """Confronta i risultati con lo smistamento già fatto a mano. Non copia nulla."""
    lavoro, _ = carica_lavoro(lavoro_dir)
    reg.inizia_fase("Confronto con lo smistamento a mano")
    reg.info(f"Leggo le cartelle {lavoro['competizione']}/{cartella_esistente} di ogni persona…")
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
        reg.errore("Non trovo foto di questa partita nelle cartelle delle persone: "
                   "controlla il nome della cartella già smistata.")
        return None
    giuste = sicuri & vero
    risultato = {
        "a_mano": len(vero), "proposte": len(sicuri), "giuste": len(giuste),
        "sbagliate": len(sicuri - vero),
        "precisione": round(100 * len(giuste) / max(1, len(sicuri))),
        "copertura": round(100 * len(giuste) / len(vero)),
        "tra_i_dubbi": len(dubbi & vero), "mancate": len(vero - sicuri - dubbi),
        "per_persona": [],
        # per ogni volto: "ok" se la stessa assegnazione c'è anche nello smistamento a mano
        "esiti": {str(v["id"]): ("ok" if (v["persona"], nomi_foto[v["foto"]]) in vero else "no")
                  for v in lavoro["volti"]},
    }
    sbagliate = [v for v in lavoro["volti"] if v["stato"] == "sicuro"
                 and (v["persona"], nomi_foto[v["foto"]]) not in vero and "relativa" in v]
    if sbagliate:
        piccoli = sum(v["relativa"] < 0.5 for v in sbagliate)
        risultato["sbagliate_sfondo"] = piccoli
        reg.info(f"Delle {len(sbagliate)} assegnazioni che non coincidono, {piccoli} sono volti piccoli "
                 "(meno di metà del volto più grande della foto): probabilmente persone sullo sfondo.")
    for persona in sorted({p for p, _ in vero | sicuri}):
        v = {n for p, n in vero if p == persona}
        s = {n for p, n in sicuri if p == persona}
        risultato["per_persona"].append({"persona": persona, "a_mano": len(v), "giuste": len(s & v),
                                         "sbagliate": len(s - v), "mancate": len(v - s)})
    with open(os.path.join(lavoro_dir, "prova.json"), "w", encoding="utf-8") as fh:
        json.dump(risultato, fh, ensure_ascii=False)
    with open(os.path.join(lavoro_dir, "prova.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["persona", "a mano", "giuste", "in più (sbagliate)", "mancate"])
        for r in risultato["per_persona"]:
            w.writerow([r["persona"], r["a_mano"], r["giuste"], r["sbagliate"], r["mancate"]])
        w.writerow([])
        w.writerow(["dettaglio errori: persona", "foto", "tipo"])
        for p, n in sorted(sicuri - vero):
            w.writerow([p, n, "proposta ma non c'è nello smistamento a mano"])
        for p, n in sorted(vero - sicuri):
            w.writerow([p, n, "c'è a mano ma lo script non l'ha messa tra le sicure"])
    reg.ok(f"Prova finita: {risultato['giuste']} giuste su {risultato['proposte']} proposte "
           f"({risultato['precisione']}% di precisione), {risultato['sbagliate']} sbagliate. "
           f"Trovato da solo il {risultato['copertura']}% del lavoro fatto a mano.")
    return risultato
