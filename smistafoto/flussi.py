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
from .volti import e_protagonista, protagonista, soglie, volto_ricorrente


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
        scelte = [(fonti_foto[i], e) for i, e in volto_ricorrente(per_foto, soglie(cfg)["ricorrente"])]
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

def e_unica(cfg, competizione):
    """True per le cartelle uniche (es. ALLENAMENTI): niente sottocartella per evento."""
    return competizione.upper() in {c.upper() for c in cfg.get("cartelle_uniche", [])}


def ricava_evento(cfg, sorgente):
    """Da .../MATCH/SERIEBKT/G10_Sudtirol_Cesena_1_1/Foto ricava
    competizione 'SERIE BKT' ed evento 'G10_SUDTIROL_CESENA'.
    Da .../ALLENAMENTI/2026_11_Novembre/20261102 ricava 'ALLENAMENTI' e la data '20261102'
    (per le cartelle uniche l'evento è la data, messa davanti al nome dei file)."""
    parti = [p for p in sorgente.split("/") if p]
    maiuscole = [p.upper() for p in parti]
    for unica in cfg.get("cartelle_uniche", []):
        if unica.upper() in maiuscole:
            dopo = parti[maiuscole.index(unica.upper()) + 1:]
            date = [m for p in dopo for m in re.findall(r"(?<!\d)(20\d{6})(?!\d)", p)]
            return unica.upper(), (date[-1] if date else "")
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
        unito = "".join(p)  # D'ANGELO -> dangelo, DALLA TORRE -> dallatorre
        if p and len(unito) >= 4 and (unito in parole or
                                      any(parole[i:i + len(p)] == p for i in range(len(parole)))):
            trovati.append(persona)
    return trovati


def descrivi_regola(r, soglia=None):
    parti = []
    if soglia is not None:
        parti.append(f"somiglianza ≥ {soglia:.2f}")
    if r.get("relativa_min"):
        parti.append(f"volto ≥ {round(100 * r['relativa_min'])}% del più grande della foto")
    if r.get("frazione_min"):
        parti.append(f"volto largo ≥ {100 * r['frazione_min']:.1f}% della foto")
    if r.get("nitidezza_min"):
        parti.append(f"nitidezza ≥ {round(r['nitidezza_min'])}")
    return " · ".join(parti) if parti else "qualsiasi volto riconosciuto"


def _cerca_regole(gruppi, attuale):
    """Prova molte combinazioni di soglia e regola del protagonista e tiene le migliori:
    per ogni livello di 'lavoro trovato' quella con la precisione più alta.
    gruppi: una voce per partita {"nome", "volti", "nomi_foto", "vero", "margine"}:
    con più partite la regola scelta funziona su tutte, non solo su una."""
    chiavi, indice, righe = {}, [], []
    vero_idx = set()
    for g, gr in enumerate(gruppi):
        for persona, nome in gr["vero"]:
            vero_idx.add(chiavi.setdefault((g, persona, nome), len(chiavi)))
        for v in gr["volti"]:
            if "frazione" not in v or "secondo" not in v or v.get("solo_nome"):
                continue
            k = chiavi.setdefault((g, v["persona"], gr["nomi_foto"][v["foto"]]), len(chiavi))
            indice.append(k)
            righe.append((v["punteggio"], v["punteggio"] - v["secondo"] - gr["margine"],
                          v["relativa"], v["frazione"], v["nitidezza"]))
    if not righe or not vero_idx:
        return []
    M = np.array(righe, np.float64)
    K = np.array(indice)
    giusto = np.zeros(len(chiavi), bool)
    giusto[list(vero_idx)] = True
    gruppo_di = np.zeros(len(chiavi), int)
    for (g, _, _), k in chiavi.items():
        gruppo_di[k] = g
    vero_per_gruppo = np.bincount(gruppo_di[giusto], minlength=len(gruppi))

    att = attuale or {}
    soglie_t = sorted({x / 100 for x in range(30, 65, 5)} | ({att["soglia"]} if att.get("soglia") else set()))
    rel_v = sorted({0.0, 0.4, 0.6, 0.75, 0.9} | {att.get("relativa_min", 0.0)})
    fr_v = sorted({0.0, 0.015, 0.025, 0.04, 0.06} | {att.get("frazione_min", 0.0)})
    nit = np.sort(M[:, 4])
    nit_v = sorted({0.0, att.get("nitidezza_min", 0.0)} |
                   {round(float(nit[int(len(nit) * q)]), 1) for q in (0.2, 0.4, 0.6)})

    prove = []
    for t in soglie_t:
        base = (M[:, 0] >= t) & (M[:, 1] >= 0)
        for rel in rel_v:
            m1 = base & (M[:, 2] >= rel)
            for fr in fr_v:
                m2 = m1 & (M[:, 3] >= fr)
                for n in nit_v:
                    prese = np.unique(K[m2 & (M[:, 4] >= n)])
                    if not len(prese):
                        continue
                    ok = giusto[prese]
                    g = int(ok.sum())
                    per = []
                    if len(gruppi) > 1:
                        pg = np.bincount(gruppo_di[prese], minlength=len(gruppi))
                        gg = np.bincount(gruppo_di[prese[ok]], minlength=len(gruppi))
                        per = [{"partita": gruppi[i]["nome"],
                                "precisione": round(100 * gg[i] / max(1, pg[i])),
                                "copertura": round(100 * gg[i] / max(1, vero_per_gruppo[i]))}
                               for i in range(len(gruppi))]
                    prove.append({"soglia": t, "relativa_min": rel, "frazione_min": fr, "nitidezza_min": n,
                                  "proposte": int(len(prese)), "giuste": g,
                                  "precisione": round(100 * g / len(prese)),
                                  "copertura": round(100 * g / int(giusto.sum())),
                                  # con più partite conta anche la peggiore, non solo la media
                                  "peggiore": min([x["precisione"] for x in per], default=None),
                                  "per_partita": per})
    chiave = lambda p: (p["soglia"], p["relativa_min"], p["frazione_min"], p["nitidezza_min"])
    scelte, viste = [], set()
    for livello in (85, 75, 65, 55, 45, 35, 25):
        adatte = [p for p in prove if p["copertura"] >= livello]
        if not adatte:
            continue
        migliore = max(adatte, key=lambda p: (p["precisione"] + (p["peggiore"] or p["precisione"]),
                                              p["copertura"]))
        if chiave(migliore) not in viste:
            viste.add(chiave(migliore))
            scelte.append(migliore)
    if att:
        a = [p for p in prove if abs(p["soglia"] - att.get("soglia", -1)) < 1e-6
             and p["relativa_min"] == att.get("relativa_min", 0.0)
             and p["frazione_min"] == att.get("frazione_min", 0.0)
             and p["nitidezza_min"] == att.get("nitidezza_min", 0.0)]
        if a:
            a[0]["attuale"] = True
            if chiave(a[0]) not in viste:
                scelte.insert(0, a[0])
    for p in scelte:
        p["descrizione"] = descrivi_regola(p, p["soglia"])
    return scelte


def _vero(conn, lavoro, cartella_esistente):
    """Le assegnazioni (persona, nome file) fatte a mano per questa partita. Su MEGA legge soltanto."""
    insieme_nomi = {posixpath.basename(f["relativo"]) for f in lavoro["foto"]}
    con_data = {f["nome_dest"]: posixpath.basename(f["relativo"]) for f in lavoro["foto"]}
    vero = set()
    for persona, cartella in lavoro["cartelle_persone"].items():
        if lavoro.get("unica"):  # es. PLAYERS/BIANCHI/ALLENAMENTI: tutti i giorni insieme
            dest = posixpath.join(cartella, lavoro["competizione"])
        else:
            dest = posixpath.join(cartella, lavoro["competizione"], cartella_esistente)
        for n in conn.elenca_nomi(dest):
            if n in insieme_nomi:
                vero.add((persona, n))
            elif n in con_data:
                vero.add((persona, con_data[n]))
    return vero


def _regola_attuale(cfg):
    sg, pr = soglie(cfg), protagonista(cfg)
    return {"soglia": sg["soglia_sicura"], **{k: pr[k] for k in ("relativa_min", "frazione_min", "nitidezza_min")}}


def calibra_insieme(cfg, conn, cartella_lavori, reg):
    """Cerca la regola migliore usando TUTTE le prove fatte (una per partita, la più recente).
    Su MEGA legge soltanto le cartelle già smistate a mano."""
    prove = {}
    for l in elenca_lavori(cartella_lavori):
        d = os.path.join(cartella_lavori, l["id"])
        lavoro, _ = carica_lavoro(d)
        if lavoro.get("prova_su") and lavoro["sorgente"] not in prove and \
                any("frazione" in v for v in lavoro["volti"]):
            prove[lavoro["sorgente"]] = lavoro
    if len(prove) < 2:
        raise RuntimeError("Servono almeno due prove (su partite diverse) fatte con la versione 2.1 o successiva.")
    reg.inizia_fase("Calcolo la regola su tutte le prove", len(prove))
    gruppi = []
    for i, lavoro in enumerate(prove.values(), 1):
        reg.passo(i, lavoro["evento"])
        reg.info(f"{lavoro['evento']}: leggo lo smistamento fatto a mano…")
        vero = _vero(conn, lavoro, lavoro["prova_su"])
        gruppi.append({"nome": lavoro["evento"], "volti": lavoro["volti"], "vero": vero,
                       "nomi_foto": {f["id"]: posixpath.basename(f["relativo"]) for f in lavoro["foto"]},
                       "margine": lavoro.get("margine", 0.0)})
    regole = _cerca_regole(gruppi, _regola_attuale(cfg))
    reg.ok(f"Regole calcolate su {len(gruppi)} partite: " + ", ".join(g["nome"] for g in gruppi) + ".")
    return {"regole": regole, "partite": [g["nome"] for g in gruppi]}


def _nome_destinazione(cfg, relativo, prefisso=""):
    parti = relativo.split("/")
    if cfg["prefisso_fotografo"] and len(parti) > 1:
        nome = "_".join(parti[:-1]) + "_" + parti[-1]
    else:
        nome = parti[-1]
    return prefisso + nome


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
    unica = e_unica(cfg, competizione)
    # nelle cartelle uniche i nomi si ripetono tra giorni diversi: la data va davanti
    prefisso = f"{evento}_" if unica else ""
    etichetta = f"{competizione}_{evento}" if unica else evento
    lavoro_dir = os.path.join(cartella_lavori, f"{etichetta}_{time.strftime('%Y%m%d-%H%M%S')}")
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

    sg = soglie(cfg)
    soglia_s, soglia_d, margine = sg["soglia_sicura"], sg["soglia_dubbia"], sg["margine"]
    reg.info(f"Riconoscimento con {volti.nome}: sicuro sopra {soglia_s:.2f} (con distacco {margine:.2f} "
             f"dal secondo), da verificare sopra {soglia_d:.2f}.")
    regola = protagonista(cfg)
    reg.info("Protagonista se: " + descrivi_regola(regola) + ".")
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
            _salva_ritaglio(img, None, os.path.join(mini_dir, anteprima), 1100)
        else:
            illeggibili += 1
        foto.append({"id": fid, "remoto": r, "relativo": rel,
                     "nome_dest": _nome_destinazione(cfg, rel, prefisso), "anteprima": anteprima})
        presenti = {}
        largo_max = trovati[0]["riquadro"][2] if trovati else 1
        for v in trovati:
            classifica = rif.classifica(v["impronta"])
            if not classifica or classifica[0][0] < soglia_d:
                continue  # sconosciuto (avversari, tifosi): non si salva nulla
            s1, n1 = classifica[0]
            s2 = classifica[1][0] if len(classifica) > 1 else 0.0
            stato = "sicuro" if s1 >= soglia_s and s1 - s2 >= margine else "dubbio"
            relativa = v["riquadro"][2] / largo_max
            if not e_protagonista(regola, relativa, v["frazione"], v["nitidezza"]):
                stato = "comparsa"  # riconosciuto, ma non protagonista: non si smista
            vid = len(lista_volti)
            mini = f"v{vid}.jpg"
            _salva_ritaglio(img, v["riquadro"], os.path.join(mini_dir, mini), 200)
            voce = {"id": vid, "foto": fid, "mini": mini, "stato": stato, "persona": n1,
                    "punteggio": round(s1, 3), "secondo": round(s2, 3), "larghezza": int(v["riquadro"][2]),
                    "relativa": round(relativa, 3), "frazione": round(v["frazione"], 4),
                    # dove sta il volto nella foto (frazioni): serve a evidenziarlo nell'anteprima
                    "box": [round(v["riquadro"][0] / img.shape[1], 4), round(v["riquadro"][1] / img.shape[0], 4),
                            round(v["riquadro"][2] / img.shape[1], 4), round(v["riquadro"][3] / img.shape[0], 4)],
                    "nitidezza": round(v["nitidezza"], 1),
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
            impronte.append(np.zeros(volti.dimensione, np.float32))
        if i % 25 == 0:
            reg.info(f"Analizzate {i} foto su {len(remote)}…")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    if nomi_trovati:
        reg.info(f"In {nomi_trovati} casi il nome del file contiene un cognome: dove il volto non "
                 "l'ha confermato, la foto è tra quelle da verificare con il nome come suggerimento.")
    if illeggibili:
        reg.avviso(f"{illeggibili} foto non si sono potute aprire (formato non supportato o download fallito).")

    lavoro = {"sorgente": sorgente, "competizione": competizione, "evento": evento, "unica": unica,
              "creato": time.strftime("%d/%m/%Y %H:%M"), "prova_su": prova_su,
              "modello": volti.nome, "margine": margine, "soglia_sicura": soglia_s,
              "protagonista": regola,
              "persone": {n: i["tipo"] for n, i in sorted(rif.info.items())},
              "cartelle_persone": {n: i["cartella"] for n, i in rif.info.items()},
              "foto": foto, "volti": lista_volti, "copiato": False}
    with open(os.path.join(lavoro_dir, "lavoro.json"), "w", encoding="utf-8") as f:
        json.dump(lavoro, f, ensure_ascii=False)
    np.save(os.path.join(lavoro_dir, "impronte.npy"),
            np.asarray(impronte, np.float32).reshape(len(impronte), volti.dimensione))
    sicuri = [v for v in lista_volti if v["stato"] == "sicuro"]
    comparse = sum(v["stato"] == "comparsa" for v in lista_volti)
    reg.ok(f"Analisi finita: {len(sicuri)} volti riconosciuti con sicurezza "
           f"({len({v['persona'] for v in sicuri})} persone), "
           f"{len(lista_volti) - len(sicuri) - comparse} da verificare, "
           f"{comparse} comparse (riconosciute ma non protagoniste: non si smistano).")
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
                           "sorgente": l.get("sorgente", ""), "unica": bool(l.get("unica")),
                           "da_decidere": sum(v["stato"] == "dubbio" for v in l["volti"]),
                           "sicure": sum(v["stato"] == "sicuro" for v in l["volti"]),
                           "creato": l.get("creato", ""), "copiato": l.get("copiato", False),
                           "foto": len(l["foto"]), "prova": prova,
                           "copiato_il": l.get("copiato_il", ""), "esito_copia": l.get("esito_copia"),
                           "ordine": os.path.getmtime(p)})
    return sorted(lavori, key=lambda x: -x["ordine"])


# ---------------------------------------------------------------- stato delle cartelle

def panoramica(cfg, conn, rif, cartella_lavori, cartella_dati, reg, campione=12):
    """Elenca le cartelle caricate dai fotografi (partite e allenamenti) e dice per ognuna
    se è già stata smistata: con Smista Foto su questo computer, oppure perché la cartella
    della partita esiste già nelle cartelle dei giocatori (a mano o da un altro computer).
    Su MEGA legge soltanto. Per non leggere tutte le persone ne guarda un campione."""
    stagione_partite = cfg.get("cartella_partite") or posixpath.join(
        posixpath.dirname(cfg["cartella_giocatori"].rstrip("/")), "MATCH")
    stagione_all = cfg.get("cartella_allenamenti") or posixpath.join(
        posixpath.dirname(cfg["cartella_giocatori"].rstrip("/")), "ALLENAMENTI")
    locali = {}
    for l in elenca_lavori(cartella_lavori):
        if l["prova"]:
            continue
        att = locali.get(l["sorgente"])
        if not att or (l["copiato"] and not att["copiato"]):
            locali[l["sorgente"]] = l
    giocatori = [i for i in rif.info.values() if i.get("tipo") == "giocatore"]
    passo_c = max(1, len(giocatori) // campione)
    giocatori = giocatori[::passo_c][:campione]

    reg.inizia_fase("Leggo le cartelle dei fotografi")
    reg.info(f"Leggo le cartelle in {stagione_partite} e {stagione_all}…")
    voci = []
    # --- partite: MATCH/<competizione>/<partita>/Foto
    comp_dest = {}
    try:
        competizioni, _ = conn.elenca_cartelle(stagione_partite)
    except RuntimeError as e:
        reg.avviso(str(e))
        competizioni = []
    for comp in competizioni:
        try:
            partite, _ = conn.elenca_cartelle(posixpath.join(stagione_partite, comp))
        except RuntimeError:
            continue
        for p in partite:
            base = posixpath.join(stagione_partite, comp, p)
            dest_comp, evento = ricava_evento(cfg, posixpath.join(base, "Foto"))
            comp_dest.setdefault(dest_comp, set())
            voci.append({"tipo": "partita", "gruppo": comp, "nome": p, "cartella": base,
                         "sorgente": posixpath.join(base, "Foto"), "comp": dest_comp, "evento": evento})
    # --- allenamenti: ALLENAMENTI/<mese>/<giorno>
    try:
        mesi, _ = conn.elenca_cartelle(stagione_all)
    except RuntimeError as e:
        reg.avviso(str(e))
        mesi = []
    unica_all = next((c for c in cfg.get("cartelle_uniche", []) if c.upper() == "ALLENAMENTI"), None)
    for mese in mesi:
        try:
            giorni, _ = conn.elenca_cartelle(posixpath.join(stagione_all, mese))
        except RuntimeError:
            continue
        for g in giorni:
            sorg = posixpath.join(stagione_all, mese, g)
            dest_comp, data = ricava_evento(cfg, sorg)
            voci.append({"tipo": "allenamento", "gruppo": mese, "nome": g, "cartella": sorg,
                         "sorgente": sorg, "comp": dest_comp, "evento": data})

    # --- cosa c'è già nelle cartelle dei giocatori (campione)
    reg.inizia_fase("Controllo le cartelle dei giocatori", len(giocatori))
    eventi_presenti = {c: {} for c in comp_dest}
    date_presenti = {}
    for i, g in enumerate(giocatori, 1):
        reg.passo(i, posixpath.basename(g["cartella"]))
        for c in comp_dest:
            for ev in conn.elenca_nomi(posixpath.join(g["cartella"], c)):
                eventi_presenti[c][ev.upper()] = eventi_presenti[c].get(ev.upper(), 0) + 1
        if unica_all:
            for n in conn.elenca_nomi(posixpath.join(g["cartella"], unica_all)):
                m = re.match(r"^(20\d{6})_", n)
                if m:
                    date_presenti[m.group(1)] = date_presenti.get(m.group(1), 0) + 1

    for v in voci:
        l = locali.get(v["sorgente"]) or locali.get(v["cartella"])
        v["giocatori_con_foto"] = 0
        if v["tipo"] == "partita":
            presenti = eventi_presenti.get(v["comp"], {})
            giornata = (v["evento"].split("_")[0] + "_") if v["evento"] else None
            v["giocatori_con_foto"] = presenti.get(v["evento"].upper(), 0) or max(
                [n for k, n in presenti.items() if giornata and k.startswith(giornata)] or [0])
        elif v["evento"]:
            v["giocatori_con_foto"] = date_presenti.get(v["evento"], 0)
        if l and l["copiato"]:
            v["stato"], v["lavoro"] = "copiata", l["id"]
            v["copiato_il"], v["esito_copia"] = l.get("copiato_il") or l["creato"], l.get("esito_copia")
        elif l:
            v["stato"], v["lavoro"] = "da_confermare", l["id"]
        elif v["giocatori_con_foto"]:
            v["stato"] = "presente"
        else:
            v["stato"] = "da_fare"
    ris = {"controllato_il": time.strftime("%d/%m/%Y %H:%M"), "campione": len(giocatori), "voci": voci}
    with open(os.path.join(cartella_dati, "panoramica.json"), "w", encoding="utf-8") as fh:
        json.dump(ris, fh, ensure_ascii=False)
    n = {s: sum(v["stato"] == s for v in voci) for s in ("copiata", "presente", "da_confermare", "da_fare")}
    reg.ok(f"Cartelle controllate: {len(voci)}. Copiate con Smista Foto: {n['copiata']}, già nelle cartelle "
           f"dei giocatori: {n['presente']}, da confermare: {n['da_confermare']}, da smistare: {n['da_fare']}.")
    return ris


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
        cartella = posixpath.join(lavoro["cartelle_persone"][d["persona"]], lavoro["competizione"],
                                  *([] if lavoro.get("unica") else [lavoro["evento"]]))
        piano.setdefault(cartella, []).append((foto[chiave[0]], d["persona"]))
    return piano


def _stessa_foto_gia_presente(conn, lavoro, f, presenti, cache):
    """Nelle cartelle uniche il nome originale (IMG_5169.jpg) può essere di un altro giorno:
    la foto è già presente solo se c'è con lo stesso nome E la stessa dimensione."""
    originale = posixpath.basename(f["relativo"])
    if not lavoro.get("unica"):
        return originale in presenti
    if originale not in presenti:
        return False
    cartella_dest = presenti.get("__cartella__")
    if cartella_dest not in cache:
        cache[cartella_dest] = conn.dimensioni(cartella_dest)
    sorgente = posixpath.dirname(f["remoto"])
    if sorgente not in cache:
        cache[sorgente] = conn.dimensioni(sorgente)
    a, b = cache[cartella_dest].get(originale), cache[sorgente].get(originale)
    return a is not None and a == b


def simula_copia(conn, lavoro_dir, decisioni, reg):
    """SIMULAZIONE: fa tutti i controlli della copia vera ma su MEGA legge soltanto.
    Dice, foto per foto, cosa succederebbe."""
    lavoro, _ = carica_lavoro(lavoro_dir)
    piano = _piano(lavoro, decisioni)
    totale = sum(len(v) for v in piano.values())
    reg.info(f"SIMULAZIONE (non scrive niente su MEGA): controllo {totale} copie in {len(piano)} cartelle…")
    reg.inizia_fase("Simulazione della copia", totale)
    persone, righe, fatte, cache = [], [], 0, {}
    for cartella, elementi in sorted(piano.items()):
        persona = elementi[0][1]
        nuova = not conn.esiste(cartella)
        presenti = {} if nuova else dict.fromkeys(conn.elenca_nomi(cartella))
        presenti["__cartella__"] = cartella
        conta = {"copierebbe": 0, "salterebbe": 0, "bloccata": 0}
        for f, p in elementi:
            originale = posixpath.basename(f["relativo"])
            dest = posixpath.join(cartella, f["nome_dest"])
            try:
                conn.verifica_copia(f["remoto"], dest)
                if f["nome_dest"] in presenti or _stessa_foto_gia_presente(conn, lavoro, f, presenti, cache):
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
    cache = {}
    fatte = copiate = gia = 0
    errori, registro = [], []
    for cartella, elementi in piano.items():
        persona = elementi[0][1]
        try:
            presenti = dict.fromkeys(conn.elenca_nomi(cartella))
            if not presenti:
                conn.crea_cartella(cartella)
            presenti["__cartella__"] = cartella
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
            # nelle cartelle uniche lo stesso nome originale può essere di un altro giorno:
            # lì conta solo il nome con la data
            presente = f["nome_dest"] in presenti or _stessa_foto_gia_presente(conn, lavoro, f, presenti, cache)
            if presente or conn.esiste(dest):
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
    import platform
    lavoro["copiato_il"] = time.strftime("%d/%m/%Y %H:%M")
    lavoro["esito_copia"] = {"copiate": copiate, "gia_presenti": gia, "errori": len(errori),
                             "persone": len(piano), "computer": platform.node() or ""}
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
    vero = _vero(conn, lavoro, cartella_esistente)
    sicuri = {(v["persona"], nomi_foto[v["foto"]]) for v in lavoro["volti"] if v["stato"] == "sicuro"}
    dubbi = {(v["persona"], nomi_foto[v["foto"]]) for v in lavoro["volti"] if v["stato"] == "dubbio"} - sicuri
    comparse = {(v["persona"], nomi_foto[v["foto"]]) for v in lavoro["volti"] if v["stato"] == "comparsa"}
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
        "tra_i_dubbi": len(dubbi & vero), "mancate": len(vero - sicuri - dubbi - comparse),
        "tra_le_comparse": len((comparse - sicuri - dubbi) & vero),
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
    # taratura: con soglie diverse, quante proposte giuste e sbagliate si avrebbero
    misurabili = [v for v in lavoro["volti"] if "secondo" in v and not v.get("solo_nome")]
    if misurabili:
        regola = lavoro.get("protagonista") or {}
        risultato["regole"] = _cerca_regole(
            [{"nome": lavoro["evento"], "volti": misurabili, "nomi_foto": nomi_foto, "vero": vero,
              "margine": lavoro.get("margine", 0.0)}],
            {"soglia": lavoro.get("soglia_sicura", 0), "relativa_min": regola.get("relativa_min", 0.0),
             "frazione_min": regola.get("frazione_min", 0.0), "nitidezza_min": regola.get("nitidezza_min", 0.0)})
        if risultato["regole"]:
            m = max(risultato["regole"], key=lambda p: p["precisione"] + p["copertura"] / 2)
            reg.info(f"Regola consigliata: {m['descrizione']} → precisione {m['precisione']}%, "
                     f"lavoro trovato {m['copertura']}%.")
        risultato["taratura"] = []
        risultato["soglia_attuale"] = lavoro.get("soglia_sicura")
        margine = lavoro.get("margine", 0.0)
        for t in [x / 100 for x in range(20, 75, 5)]:
            prese = {(v["persona"], nomi_foto[v["foto"]]) for v in misurabili
                     if v["punteggio"] >= t and v["punteggio"] - v["secondo"] >= margine}
            g = len(prese & vero)
            risultato["taratura"].append({"soglia": t, "proposte": len(prese), "giuste": g,
                                          "precisione": round(100 * g / max(1, len(prese))),
                                          "copertura": round(100 * g / len(vero))})
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
