"""Smista Foto come app nel browser: un piccolo server sul computer
(raggiungibile solo da questo computer) con pulsanti, avanzamento e registro."""

import json
import os
import posixpath
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import DATA_VERSIONE, VERSIONE
from .flussi import (analizza_cartella, carica_lavoro, confronta, deboli, elenca_lavori,
                     esegui_copia, impara, ricava_evento, simula_copia, trova_cartella_esistente)
from .mega import collegamento, normalizza
from .registro import Registro
from .revisione import pagina_revisione
from .volti import Riferimenti, Volti, nome_modello, scarica_auraface

PORTA = 8765


class App:
    def __init__(self, qui):
        self.qui = qui
        self.dati = os.path.join(qui, "dati")
        self.lavori = os.path.join(qui, "lavori")
        with open(os.path.join(qui, "config.json"), encoding="utf-8") as f:
            self.cfg = json.load(f)
        self.reg = Registro()
        self.conn = self.volti = None
        self.modello = nome_modello(self.cfg)
        self.rif = Riferimenti(self.dati, self.modello, 512 if self.modello == "auraface" else 128)
        self.account = None
        self.problema = "Controllo del collegamento in corso…"
        self.attivita = {"tipo": None, "in_corso": False, "lavoro": None, "risultato": None, "errore": None}
        self._lucchetto = threading.Lock()
        self._cache_lavori = (0, [], None)
        self._ultimo_controllo = 0
        self.file_esclusi = os.path.join(self.dati, "esclusi.json")
        self.esclusi = []
        if os.path.exists(self.file_esclusi):
            with open(self.file_esclusi, encoding="utf-8") as f:
                self.esclusi = json.load(f)
        self.primi_piani = os.path.join(qui, "primi_piani")

    # ------------------------------------------------------------ attività

    def avvia(self, tipo, funzione):
        with self._lucchetto:
            if self.attivita["in_corso"]:
                raise RuntimeError("C'è già un'attività in corso: aspetta che finisca.")
            self.attivita = {"tipo": tipo, "in_corso": True, "lavoro": None, "risultato": None,
                             "errore": None, "inizio": time.time()}

        def esegui():
            try:
                funzione()
            except Exception as e:
                self.attivita["errore"] = str(e)
                self.reg.errore(f"Interrotto: {e}")
                traceback.print_exc()
            finally:
                self.attivita["in_corso"] = False
                self.reg.inizia_fase("")
        threading.Thread(target=esegui, daemon=True).start()

    def _serve_collegamento(self):
        if not self.account:
            raise RuntimeError(self.problema or "MEGA non è collegato.")
        if self.volti is None:
            raise RuntimeError("Il modello di riconoscimento non è pronto: guarda il registro e premi «Riprova».")

    def collega(self, silenzioso=False):
        self._ultimo_controllo = time.time()

        def lavoro():
            self.reg.inizia_fase("Controllo il collegamento")
            if not silenzioso:
                self.reg.info("Controllo che MEGAcmd sia installato e collegato…")
            self.account, self.problema = None, None
            try:
                self.conn = collegamento(self.cfg)
            except Exception as e:
                self.problema = str(e)
                if not silenzioso:
                    self.reg.errore(self.problema)
                return
            chi = self.conn.chi_sono()
            if not chi:
                self.problema = ("MEGAcmd risponde ma non risulta collegato a un account. Nella finestra di "
                                 "MEGAcmd scrivi login seguito dall'email del club e la password. "
                                 "Il semaforo diventa verde da solo entro qualche secondo.")
                if not silenzioso:
                    self.reg.errore(self.problema)
                    self.reg.info("Risposta di MEGAcmd: " + getattr(self.conn, "risposta_whoami", "?"))
                return
            self.account = chi
            self.reg.ok(f"Collegato a MEGA come {chi}.")
            if self.volti is None:
                try:
                    if self.modello == "auraface":
                        scarica_auraface(os.path.join(self.qui, "modelli"), self.reg)
                    self.reg.info("Carico il modello di riconoscimento dei volti…")
                    self.volti = Volti(os.path.join(self.qui, "modelli"), self.cfg)
                    self.reg.ok(f"Modello di riconoscimento: {self.volti.nome}.")
                except Exception as e:
                    self.problema = f"Non riesco a preparare il modello di riconoscimento: {e}"
                    self.reg.errore(self.problema)
                    self._ultimo_controllo = time.time() + 10 ** 9  # niente ricontrolli automatici
                    return
            n = len(self.rif.info)
            if n:
                self.reg.info(f"Conosco già {n} persone.")
            elif self.modello != "sface" and os.path.exists(os.path.join(self.dati, "riferimenti.json")):
                self.reg.avviso(f"Il modello di riconoscimento è cambiato ({self.volti.nome}): i volti vanno "
                                "imparati di nuovo. Premi «Impara i volti nuovi» (circa 10-20 minuti).")
            else:
                self.reg.info("Non conosco ancora nessun volto: premi «Impara i volti».")
        self.avvia("collegamento", lavoro)

    def impara(self, tutti, solo=None):
        self._serve_collegamento()
        self.avvia("impara", lambda: impara(self.cfg, self.conn, self.volti, self.rif, self.dati,
                                            self.reg, tutti=tutti, solo=solo, esclusi=self.esclusi))

    def escludi(self, nome, escluso):
        if self.attivita["in_corso"]:
            raise RuntimeError("C'è un'attività in corso: aspetta che finisca.")
        if escluso and nome not in self.esclusi:
            self.esclusi.append(nome)
            self.rif.rimuovi(nome)
            self.rif.salva()
            self.reg.info(f"{nome} escluso: non verrà più considerato una persona.")
        elif not escluso and nome in self.esclusi:
            self.esclusi.remove(nome)
            self.reg.info(f"{nome} di nuovo incluso: premi «Impara i volti nuovi» per impararlo.")
        with open(self.file_esclusi, "w", encoding="utf-8") as f:
            json.dump(sorted(self.esclusi), f, ensure_ascii=False)

    def salva_primo_piano(self, persona, nome_file, dati):
        if persona not in self.rif.info:
            raise RuntimeError("Persona sconosciuta.")
        nome_file = os.path.basename(nome_file.replace("\\", "/"))
        if os.path.splitext(nome_file)[1].lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            raise RuntimeError(f"{nome_file}: servono foto JPG, PNG o WEBP.")
        if not dati or len(dati) > 40 * 1024 * 1024:
            raise RuntimeError(f"{nome_file}: file vuoto o troppo grande.")
        cartella = os.path.join(self.primi_piani, persona)
        os.makedirs(cartella, exist_ok=True)
        with open(os.path.join(cartella, nome_file), "wb") as f:
            f.write(dati)
        self.reg.info(f"{persona}: aggiunto il primo piano {nome_file} (salvato solo su questo computer).")

    def _lista_persone(self):
        righe = []
        for nome, info in self.rif.info.items():
            pp = os.path.join(self.primi_piani, nome)
            n_pp = len([f for f in os.listdir(pp) if not f.startswith(".")]) if os.path.isdir(pp) else 0
            righe.append({"nome": nome, "tipo": info.get("tipo"), "foto": int(len(self.rif.impronte.get(nome, []))),
                          "primi_piani": n_pp})
        righe.sort(key=lambda r: (r["foto"] >= 4, r["tipo"] != "giocatore", r["nome"]))
        return righe

    def controlla(self, percorso, prova):
        self._serve_collegamento()
        if self.attivita["in_corso"]:
            raise RuntimeError("C'è già un'attività in corso: aspetta che finisca.")
        sorgente = normalizza(percorso)
        if sorgente == "/":
            raise RuntimeError("Scrivi il percorso della cartella delle foto.")
        comp, evento = ricava_evento(self.cfg, sorgente)
        esistente = trova_cartella_esistente(self.conn, self.rif, comp, evento) if prova and comp else ""
        return {"sorgente": sorgente, "competizione": comp, "evento": evento, "esistente": esistente}

    def smista(self, sorgente, comp, evento, prova_su=None):
        self._serve_collegamento()
        comp, evento = comp.strip().upper(), evento.strip().upper()
        if not comp or not evento:
            raise RuntimeError("Indica competizione e nome della partita.")

        def lavoro():
            rif = self.rif
            if prova_su:
                self.reg.info(f"PROVA (non copia nulla): confronto con lo smistamento a mano in "
                              f"<NOME>/{comp}/{prova_su}.")
                rif, tolte = self.rif.senza(f"/{comp}/{prova_su}/")
                self.reg.info(f"Per una prova onesta ignoro {tolte} volti imparati proprio da questa partita.")
            else:
                self.reg.info(f"Le foto andranno in <NOME>/{comp}/{evento}, ma solo dopo la tua revisione.")
            d = analizza_cartella(self.cfg, self.conn, self.volti, rif, normalizza(sorgente), comp, evento,
                                  self.lavori, self.reg, prova_su=prova_su)
            self.attivita["lavoro"] = os.path.basename(d)
            if prova_su:
                self.attivita["risultato"] = confronta(self.conn, d, prova_su, self.reg)
            else:
                self.reg.info("Ora apri la revisione per controllare e confermare.")
        self.avvia("prova" if prova_su else "smista", lavoro)

    def copia(self, lavoro_id, decisioni):
        self._serve_collegamento()
        d = self._cartella_lavoro(lavoro_id)

        def lavoro():
            self.attivita["lavoro"] = lavoro_id
            self.attivita["risultato"] = esegui_copia(self.conn, self.rif, d, decisioni, self.reg)
        self.avvia("copia", lavoro)

    def simula(self, lavoro_id, decisioni):
        self._serve_collegamento()
        d = self._cartella_lavoro(lavoro_id)

        def lavoro():
            self.attivita["lavoro"] = lavoro_id
            self.attivita["risultato"] = simula_copia(self.conn, d, decisioni, self.reg)
        self.avvia("simulazione", lavoro)

    def applica_regola(self, r):
        if self.attivita["in_corso"]:
            raise RuntimeError("C'è un'attività in corso: aspetta che finisca.")
        valori = {k: float(r[k]) for k in ("soglia", "relativa_min", "frazione_min", "nitidezza_min")}
        if not (0.1 <= valori["soglia"] <= 0.9 and 0 <= valori["relativa_min"] <= 1
                and 0 <= valori["frazione_min"] <= 0.5 and 0 <= valori["nitidezza_min"] <= 100000):
            raise RuntimeError("Valori della regola non validi.")
        percorso = os.path.join(self.qui, "config.json")
        with open(percorso, encoding="utf-8") as f:
            cfg = json.load(f)
        cfg.setdefault("soglie", {}).setdefault(self.modello, {})["soglia_sicura"] = valori["soglia"]
        cfg["protagonista"] = {k: valori[k] for k in ("relativa_min", "frazione_min", "nitidezza_min")}
        with open(percorso, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        self.cfg = cfg
        if self.volti:
            self.volti.cfg = cfg
        from .flussi import descrivi_regola
        self.reg.ok("Nuova regola salvata: " + descrivi_regola(cfg["protagonista"], valori["soglia"])
                    + ". Vale dalla prossima analisi.")

    def sfoglia(self, percorso):
        self._serve_collegamento()
        base = self.cfg.get("cartella_partite") or posixpath.join(
            posixpath.dirname(self.cfg["cartella_giocatori"].rstrip("/")), "MATCH")
        stagione = posixpath.dirname(base.rstrip("/")) or "/"
        p = normalizza(percorso) if percorso else base
        if not (p + "/").startswith(stagione.rstrip("/") + "/"):
            p = base  # si sfoglia solo dentro la stagione
        cartelle, foto = self.conn.elenca_cartelle(p)
        return {"percorso": p, "su": posixpath.dirname(p) if p.rstrip("/") != stagione.rstrip("/") else None,
                "cartelle": cartelle, "foto": foto}

    def _cartella_lavoro(self, lavoro_id):
        esistenti = os.listdir(self.lavori) if os.path.isdir(self.lavori) else []
        if lavoro_id not in esistenti:
            raise RuntimeError("Analisi non trovata.")
        return os.path.join(self.lavori, lavoro_id)

    def stato(self, dalla):
        # finché MEGA non è collegato, ricontrolla da solo ogni 15 secondi
        if not self.account and not self.attivita["in_corso"] and time.time() - self._ultimo_controllo > 15:
            try:
                self.collega(silenzioso=True)
            except RuntimeError:
                pass
        if self.attivita["in_corso"] and self.attivita["tipo"] == "collegamento":
            semaforo = "giallo"
        else:
            semaforo = "verde" if self.account else "rosso"
        g = sum(1 for i in self.rif.info.values() if i.get("tipo") == "giocatore")
        a = dict(self.attivita)
        if a.get("inizio"):
            a["secondi"] = int(time.time() - a["inizio"])
        return {"versione": VERSIONE, "data_versione": DATA_VERSIONE,
                "modello": self.volti.nome if self.volti else self.modello,
                "account": self.account, "problema": self.problema, "semaforo": semaforo,
                "persone": {"giocatori": g, "staff": len(self.rif.info) - g, "deboli": deboli(self.rif)},
                "elenco": self._lista_persone(), "esclusi": sorted(self.esclusi),
                "attivita": a, "registro": self.reg.stato(dalla),
                "lavori": self._lavori()}

    def _lavori(self):
        ora = time.time()
        if ora - self._cache_lavori[0] > 5 or self.attivita["in_corso"] != self._cache_lavori[2]:
            self._cache_lavori = (ora, elenca_lavori(self.lavori)[:15], self.attivita["in_corso"])
        return self._cache_lavori[1]


def avvia_app(qui):
    app = App(qui)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORTA), _gestore(app))
    except OSError:
        print(f"Smista Foto è già aperto: apro la pagina http://127.0.0.1:{PORTA}/")
        webbrowser.open(f"http://127.0.0.1:{PORTA}/")
        return
    url = f"http://127.0.0.1:{PORTA}/"
    print(f"\n=== SMISTA FOTO · Cesena FC · versione {VERSIONE} ===")
    print(f"L'app si apre nel browser: {url}")
    print("Lascia aperta questa finestra finché usi Smista Foto. Qui sotto trovi lo stesso registro dell'app.\n")
    app.collega()
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    app.server = server
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
    print("Smista Foto chiuso.")


def _gestore(app):
    class Gestore(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _invia(self, corpo, tipo="application/json; charset=utf-8", codice=200):
            if isinstance(corpo, (dict, list)):
                corpo = json.dumps(corpo, ensure_ascii=False)
            if isinstance(corpo, str):
                corpo = corpo.encode("utf-8")
            self.send_response(codice)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(corpo)

        def _corpo(self):
            n = int(self.headers.get("Content-Length", 0) or 0)
            return json.loads(self.rfile.read(n) or b"{}")

        def do_GET(self):
            u = urlparse(self.path)
            parti = [p for p in u.path.split("/") if p]
            try:
                if not parti:
                    self._invia(HOME, "text/html; charset=utf-8")
                elif parti == ["api", "stato"]:
                    dalla = int(parse_qs(u.query).get("dalla", ["0"])[0])
                    self._invia(app.stato(dalla))
                elif parti[0] == "l" and len(parti) == 2:
                    d = app._cartella_lavoro(parti[1])
                    lavoro, _ = carica_lavoro(d)
                    prova = None
                    if os.path.exists(os.path.join(d, "prova.json")):
                        with open(os.path.join(d, "prova.json"), encoding="utf-8") as fh:
                            prova = json.load(fh)
                    self._invia(pagina_revisione(parti[1], lavoro, prova), "text/html; charset=utf-8")
                elif parti[0] == "l" and len(parti) == 4 and parti[2] == "m":
                    d = app._cartella_lavoro(parti[1])
                    f = os.path.join(d, "miniature", os.path.basename(parti[3]))
                    if not os.path.exists(f):
                        return self._invia(b"", "text/plain", 404)
                    with open(f, "rb") as fh:
                        self._invia(fh.read(), "image/jpeg")
                else:
                    self._invia(b"", "text/plain", 404)
            except Exception as e:
                self._invia({"errore": str(e)}, codice=400)

        def do_POST(self):
            parti = [p for p in urlparse(self.path).path.split("/") if p]
            try:
                if parti == ["api", "primopiano"]:
                    q = parse_qs(urlparse(self.path).query)
                    n = int(self.headers.get("Content-Length", 0) or 0)
                    app.salva_primo_piano(q["persona"][0], q["nome"][0], self.rfile.read(n))
                    return self._invia({"ok": True})
                c = self._corpo()
                if parti == ["api", "collega"]:
                    app.collega()
                    r = {"ok": True}
                elif parti == ["api", "impara"]:
                    app.impara(bool(c.get("tutti")), c.get("solo"))
                    r = {"ok": True}
                elif parti == ["api", "regola"]:
                    app.applica_regola(c)
                    r = {"ok": True}
                elif parti == ["api", "sfoglia"]:
                    r = app.sfoglia(c.get("percorso", ""))
                elif parti == ["api", "escludi"]:
                    app.escludi(c["nome"], bool(c["escluso"]))
                    r = {"ok": True}
                elif parti == ["api", "controlla"]:
                    r = app.controlla(c.get("percorso", ""), bool(c.get("prova")))
                elif parti == ["api", "smista"]:
                    app.smista(c["sorgente"], c["competizione"], c["evento"])
                    r = {"ok": True}
                elif parti == ["api", "prova"]:
                    if not c.get("esistente", "").strip():
                        raise RuntimeError("Indica la cartella della partita già smistata a mano.")
                    app.smista(c["sorgente"], c["competizione"], c["evento"], prova_su=c["esistente"].strip())
                    r = {"ok": True}
                elif len(parti) == 3 and parti[0] == "l" and parti[2] == "simula":
                    app.simula(parti[1], c["decisioni"])
                    r = {"ok": True}
                elif len(parti) == 3 and parti[0] == "l" and parti[2] == "conferma":
                    app.copia(parti[1], c["decisioni"])
                    r = {"ok": True}
                elif parti == ["api", "esci"]:
                    threading.Thread(target=app.server.shutdown, daemon=True).start()
                    r = {"ok": True}
                else:
                    return self._invia({"errore": "sconosciuto"}, codice=404)
                self._invia(r)
            except Exception as e:
                self._invia({"errore": str(e)}, codice=400)
    return Gestore


STILE = r"""
:root{--fondo:#f4f4f0;--carta:#fff;--testo:#16161c;--tenue:#6b6b75;--bordo:#dcdcd4;--primo:#0a0a0c;--primo-t:#fff;
--ok:#1e7a3c;--okf:#e3f3e7;--avv:#9a5b00;--avvf:#fff2dc;--err:#b3261e;--errf:#fde8e6;--accento:#0a0a0c}
@media (prefers-color-scheme:dark){:root{--fondo:#111114;--carta:#1b1b20;--testo:#f4f4f0;--tenue:#9a9aa6;--bordo:#2e2e36;
--primo:#f4f4f0;--primo-t:#0a0a0c;--ok:#5fd07f;--okf:#16301f;--avv:#ffb347;--avvf:#33270f;--err:#ff8a80;--errf:#3a1714;--accento:#f4f4f0}}
*{box-sizing:border-box}
body{margin:0;background:var(--fondo);color:var(--testo);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
button,input,select{font:inherit;color:inherit}
button{border-radius:8px;border:1px solid var(--bordo);background:var(--carta);padding:9px 14px;cursor:pointer;font-weight:600}
button.primo{background:var(--primo);color:var(--primo-t);border-color:var(--primo)}
button:disabled{opacity:.45;cursor:default}
input{width:100%;border:1px solid var(--bordo);border-radius:8px;padding:9px 11px;background:var(--carta)}
a{color:inherit}
"""

HOME = r"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smista Foto</title><style>""" + STILE + r"""
header{background:#0a0a0c;color:#f4f4f0;padding:16px 24px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
header h1{margin:0;font-size:20px;letter-spacing:.08em}
header .ver{font-size:12px;border:1px solid #55555f;border-radius:20px;padding:2px 10px;color:#c8c8d0}
header .conto{margin-left:auto;font-size:14px;display:flex;align-items:center;gap:12px}
.semaforo{display:flex;gap:5px;background:#1d1d22;border:1px solid #33333b;border-radius:20px;padding:5px 8px}
.semaforo i{width:14px;height:14px;border-radius:50%;background:#3a3a42}
.semaforo.rosso .r{background:#ff4d40;box-shadow:0 0 8px #ff4d40}
.semaforo.giallo .g{background:#ffc531;box-shadow:0 0 8px #ffc531}
.semaforo.verde .v{background:#4ddc6f;box-shadow:0 0 8px #4ddc6f}
.conto b{display:block;font-size:14px}.conto small{color:#a0a0aa;font-size:12px}
main{max-width:1180px;margin:0 auto;padding:20px 24px 80px;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);gap:18px}
@media (max-width:900px){main{grid-template-columns:1fr}}
.carta{background:var(--carta);border:1px solid var(--bordo);border-radius:12px;padding:18px}
.carta h2{margin:0 0 4px;font-size:17px}
.nota{color:var(--tenue);font-size:13.5px;margin:0 0 12px}
.riga{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:10px}
.problema{background:var(--errf);color:var(--err);border-radius:8px;padding:10px 12px;margin-top:10px}
.problema button{margin-top:8px}
.grandi{display:flex;gap:18px;margin:6px 0 4px}
.grandi div{font-size:13px;color:var(--tenue)}.grandi b{display:block;font-size:26px;color:var(--testo);line-height:1.1}
.avviso{background:var(--avvf);color:var(--avv);border-radius:8px;padding:8px 11px;font-size:13.5px;margin-top:10px}
.dest{background:var(--fondo);border-radius:8px;padding:12px;margin-top:12px}
.dest .percorso{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13.5px;word-break:break-all}
.campi{display:grid;grid-template-columns:1fr 1.4fr;gap:8px;margin-top:8px}
.campi label{font-size:12px;color:var(--tenue)}
.col-sx{display:flex;flex-direction:column;gap:18px}
.att{display:flex;flex-direction:column;min-height:520px}
.fase{font-weight:700;font-size:16px;min-height:24px}
.barra{height:10px;background:var(--fondo);border-radius:6px;overflow:hidden;margin:8px 0 4px}
.barra i{display:block;height:100%;background:var(--accento);width:0;transition:width .4s}
.det{font-size:12.5px;color:var(--tenue);min-height:18px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.registro{flex:1;margin-top:12px;background:var(--fondo);border-radius:8px;padding:10px 12px;overflow:auto;max-height:420px;font-size:13.5px}
.registro p{margin:0 0 4px;display:flex;gap:8px}
.registro .ora{color:var(--tenue);font-variant-numeric:tabular-nums;flex:none}
.registro .ok{color:var(--ok)}.registro .avviso{color:var(--avv)}.registro .errore{color:var(--err);font-weight:600}
.esito{margin-top:12px}
.sfoglia{border:1px solid var(--bordo);border-radius:10px;margin-top:12px;overflow:hidden}
.briciole{background:var(--fondo);padding:8px 12px;font-size:13px;display:flex;flex-wrap:wrap;gap:4px;align-items:center}
.briciole a{cursor:pointer;text-decoration:underline}
.cartelle{max-height:300px;overflow:auto}
.cartelle div{padding:9px 12px;border-top:1px solid var(--bordo);cursor:pointer;display:flex;gap:8px;align-items:center}
.cartelle div:hover{background:var(--fondo)}
.cartelle div.foto{font-weight:700}
.cartelle .vuota{color:var(--tenue);cursor:default}
#sfogliaAz{padding:0 12px 12px}
#elenco table td{vertical-align:middle}
#elenco .az{display:flex;gap:6px;justify-content:flex-end;flex-wrap:wrap}
#elenco button{padding:5px 10px;font-size:13px;font-weight:500}
.debole{color:var(--avv);font-weight:600}
.tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:8px 0}
.tiles div{background:var(--fondo);border-radius:8px;padding:10px;font-size:12.5px;color:var(--tenue)}
.tiles b{display:block;font-size:22px;color:var(--testo)}
table{width:100%;border-collapse:collapse;font-size:13.5px}
td,th{padding:7px 6px;border-bottom:1px solid var(--bordo);text-align:left}
th{font-weight:600;color:var(--tenue);font-size:12px}
.etich{font-size:12px;border-radius:20px;padding:2px 9px;white-space:nowrap}
.etich.da{background:var(--avvf);color:var(--avv)}.etich.fatto{background:var(--okf);color:var(--ok)}.etich.prova{background:var(--fondo);color:var(--tenue)}
footer{max-width:1180px;margin:0 auto;padding:0 24px 30px;color:var(--tenue);font-size:13px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
</style></head><body>
<header><h1>SMISTA FOTO</h1><span>Cesena FC</span><span class="ver" id="ver"></span>
<span class="conto" title="Collegamento a MEGA"><span class="semaforo" id="semaforo"><i class="r"></i><i class="g"></i><i class="v"></i></span><span><b id="conto">Controllo MEGA…</b><small id="contoSub"></small></span></span></header>
<main>
<div class="col-sx">
 <section class="carta">
  <h2>1 · Volti di giocatori e staff</h2>
  <p class="nota">Lo script impara i volti dalle cartelle in PLAYERS e PLAYERS/_STAFF. Va fatto la prima volta e quando arriva qualcuno di nuovo. Su MEGA legge soltanto.</p>
  <div class="grandi"><div><b id="nG">0</b>giocatori</div><div><b id="nS">0</b>staff</div></div>
  <div id="deboli"></div>
  <div class="riga"><button class="primo" id="bImpara">Impara i volti nuovi</button><button id="bReimpara">Reimpara tutti da zero</button></div>
  <details id="elencoBox" style="margin-top:14px"><summary style="cursor:pointer;font-weight:600" id="elencoTit">Elenco delle persone</summary>
   <p class="nota" style="margin:8px 0">In alto chi ha poche foto. <b>Primi piani</b>: scegli 3-5 foto in cui si vede bene il volto, poi premi «Reimpara». <b>Escludi</b>: per le cartelle che non sono persone (es. 00VARIE).</p>
   <div id="elenco"></div></details>
  <div id="problema"></div>
 </section>
 <section class="carta">
  <h2>2 · Smista una partita</h2>
  <p class="nota">Scegli su MEGA la cartella <b>Foto</b> della partita: competizione › partita › Foto.</p>
  <div class="riga" style="margin-top:0"><button class="primo" id="bSfoglia">Sfoglia le cartelle su MEGA…</button></div>
  <div id="sfoglia" hidden class="sfoglia">
   <div class="briciole" id="briciole"></div>
   <div id="cartelle" class="cartelle"></div>
   <div class="riga" id="sfogliaAz"></div>
  </div>
  <details style="margin-top:10px"><summary class="nota" style="cursor:pointer;margin:0">oppure incolla il percorso a mano</summary>
  <input id="percorso" style="margin-top:8px" placeholder="2026-27/MATCH/SERIEBKT/G10_Sudtirol_Cesena_1_1/Foto">
  <div class="riga"><button id="bControlla">Controlla</button></div></details>
  <div id="dest" hidden class="dest">
   <div class="nota" style="margin:0">Cartella scelta:</div>
   <div class="percorso" id="destOrig" style="margin-bottom:8px"></div>
   <div class="nota" style="margin:0">Le foto riconosciute andranno in:</div>
   <div class="percorso" id="destPercorso"></div>
   <div class="campi"><div><label>Competizione</label><input id="comp"></div><div><label>Partita</label><input id="evento"></div></div>
   <div class="riga"><button class="primo" id="bSmista">Avvia lo smistamento</button></div>
   <p class="nota" style="margin:8px 0 0">Non copia niente finché non confermi nella pagina di revisione.</p>
   <details style="margin-top:12px"><summary style="cursor:pointer;font-weight:600">Prova su una partita già smistata a mano</summary>
    <p class="nota" style="margin:6px 0">Confronta il risultato con lo smistamento fatto a mano. Non copia nulla.</p>
    <label class="nota">Cartella della partita nelle cartelle dei giocatori</label><input id="esistente">
    <div class="riga"><button id="bProva">Fai la prova</button></div></details>
  </div>
 </section>
 <section class="carta"><h2>Analisi recenti</h2><div id="lavori"><p class="nota">Nessuna analisi.</p></div></section>
</div>
<section class="carta att">
 <h2>Cosa sta facendo</h2>
 <div class="fase" id="fase">In attesa</div>
 <div class="barra"><i id="barra"></i></div>
 <div class="det" id="det"></div>
 <div class="esito" id="esito"></div>
 <div class="registro" id="registro"></div>
</section>
</main>
<footer><span>Lascia aperta la finestra del Terminale finché usi Smista Foto.</span><button id="bEsci">Chiudi Smista Foto</button></footer>
<script>
const $=s=>document.querySelector(s);
const esc=t=>String(t??"").replace(/[&<>"']/g,c=>"&#"+c.charCodeAt(0)+";");
let righe=0, S=null, ultimoEsito="";
async function api(url,dati){const r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(dati||{})});
  const j=await r.json();if(!r.ok)throw new Error(j.errore||"errore");return j}
function avvisa(e){alert(e.message||e)}
async function aggiorna(){
  let s;try{s=await(await fetch("/api/stato?dalla="+righe)).json()}catch(e){$("#fase").textContent="Smista Foto è chiuso. Riaprilo dal suo file di avvio.";return}
  S=s;$("#ver").textContent="versione "+s.versione+" · "+s.modello;
  $("#semaforo").className="semaforo "+s.semaforo;
  $("#conto").textContent={verde:"MEGA collegato",giallo:"Controllo MEGA…",rosso:"MEGA non collegato"}[s.semaforo];
  $("#contoSub").textContent=s.account||(s.semaforo=="rosso"?"ricontrollo da solo ogni 15 secondi":"");
  $("#problema").innerHTML=s.problema&&(!s.account||s.problema.startsWith("Non riesco a preparare"))?`<div class="problema">${esc(s.problema)}<br><button id="bRiprova">Riprova</button></div>`:"";
  if($("#bRiprova"))$("#bRiprova").onclick=()=>api("/api/collega").catch(avvisa);
  $("#nG").textContent=s.persone.giocatori;$("#nS").textContent=s.persone.staff;
  $("#deboli").innerHTML=s.persone.deboli.length?`<div class="avviso">Riconoscimento debole per: <b>${s.persone.deboli.map(esc).join(", ")}</b>. Apri «Elenco delle persone» qui sotto e premi «Primi piani…» accanto al nome.</div>`:"";
  const a=s.attivita, occ=a.in_corso||!s.account;
  for(const b of ["#bImpara","#bReimpara","#bControlla","#bSmista","#bProva","#bSfoglia"])$(b).disabled=occ;
  const r=s.registro;
  $("#fase").textContent=a.in_corso?(r.fase||"Al lavoro…"):"In attesa";
  $("#barra").style.width=a.in_corso&&r.n?(100*r.i/r.n)+"%":"0";
  $("#det").textContent=a.in_corso&&r.n?`${r.i} di ${r.n}`+(r.dettaglio?" · "+r.dettaglio:""):"";
  const box=$("#registro"),giu=box.scrollTop+box.clientHeight>=box.scrollHeight-30;
  for(const x of r.righe)box.insertAdjacentHTML("beforeend",`<p class="${x.tipo}"><span class="ora">${x.ora}</span><span>${esc(x.testo)}</span></p>`);
  righe=r.totale_righe;if(giu&&r.righe.length)box.scrollTop=box.scrollHeight;
  const chiave=JSON.stringify([a.tipo,a.in_corso,a.lavoro,!!a.risultato,a.errore]);
  if(chiave!==ultimoEsito){ultimoEsito=chiave;mostraEsito(a)}
  mostraLavori(s.lavori);
  mostraElenco(s);
}
let chiaveElenco="";
function mostraElenco(s){
  const k=JSON.stringify([s.elenco,s.esclusi,s.attivita.in_corso]);if(k===chiaveElenco)return;chiaveElenco=k;
  $("#elencoTit").textContent=`Elenco delle persone (${s.elenco.length})`+(s.esclusi.length?` · ${s.esclusi.length} escluse`:"");
  const occ=s.attivita.in_corso||!s.account;
  let h=`<table><tr><th>Nome</th><th>Foto utili</th><th></th></tr>`+s.elenco.map(p=>`<tr><td><b>${esc(p.nome)}</b><br><span class="nota">${p.tipo}</span></td>
    <td class="${p.foto<4?"debole":""}">${p.foto}${p.foto<4?" · debole":""}${p.primi_piani?`<br><span class="nota">${p.primi_piani} primi piani</span>`:""}</td>
    <td><div class="az"><input type="file" accept="image/*" multiple hidden data-pp="${esc(p.nome)}"><button type="button" ${occ?"disabled":""} onclick="this.previousElementSibling.click()">Primi piani…</button>
    ${p.primi_piani?`<button ${occ?"disabled":""} data-re="${esc(p.nome)}">Reimpara</button>`:""}
    <button ${occ?"disabled":""} data-ex="${esc(p.nome)}">Escludi</button></div></td></tr>`).join("")+"</table>";
  if(s.esclusi.length)h+=`<p class="nota" style="margin-top:12px">Escluse: `+s.esclusi.map(n=>`${esc(n)} <button ${occ?"disabled":""} data-in="${esc(n)}">Includi</button>`).join(" ")+"</p>";
  $("#elenco").innerHTML=h;
  $("#elenco").querySelectorAll("[data-ex]").forEach(b=>b.onclick=()=>{if(confirm(`Escludo ${b.dataset.ex}? Lo script non lo considererà più una persona (le cartelle su MEGA non vengono toccate).`))api("/api/escludi",{nome:b.dataset.ex,escluso:true}).catch(avvisa)});
  $("#elenco").querySelectorAll("[data-in]").forEach(b=>b.onclick=()=>api("/api/escludi",{nome:b.dataset.in,escluso:false}).catch(avvisa));
  $("#elenco").querySelectorAll("[data-re]").forEach(b=>b.onclick=()=>api("/api/impara",{solo:[b.dataset.re]}).catch(avvisa));
  $("#elenco").querySelectorAll("[data-pp]").forEach(inp=>inp.onchange=async()=>{
    const nome=inp.dataset.pp;let ok=0;
    for(const f of inp.files){const r=await fetch(`/api/primopiano?persona=${encodeURIComponent(nome)}&nome=${encodeURIComponent(f.name)}`,{method:"POST",body:f});
      if(r.ok)ok++;else alert((await r.json()).errore)}
    if(ok&&confirm(`${ok} primi piani aggiunti per ${nome}. Lo reimparo adesso?`))api("/api/impara",{solo:[nome]}).catch(avvisa)});
}
let REGOLE=[];
function regole(p){if(!p.regole||!p.regole.length)return"";REGOLE=p.regole;
  return `<div style="margin-top:12px"><b>Regole proposte</b><p class="nota" style="margin:4px 0 8px">Lo script ha provato molte combinazioni (somiglianza, grandezza del volto, nitidezza) per avvicinarsi al vostro criterio «almeno un po' protagonista». In alto: trova più foto; in basso: sbaglia meno. Scegline una: vale dalla prossima analisi.</p>
  <table><tr><th>Regola</th><th>Proposte</th><th>Precisione</th><th>Lavoro trovato</th><th></th></tr>`+
  p.regole.map((r,i)=>`<tr style="${r.attuale?"font-weight:700":""}"><td>${esc(r.descrizione)}${r.attuale?" <span class='nota'>(in uso)</span>":""}</td><td>${r.proposte}</td><td>${r.precisione}%</td><td>${r.copertura}%</td><td>${r.attuale?"":`<button data-regola="${i}">Usa questa</button>`}</td></tr>`).join("")+"</table></div>"}
document.addEventListener("click",e=>{const b=e.target.closest("[data-regola]");if(!b)return;const r=REGOLE[+b.dataset.regola];
  if(confirm("Uso questa regola dalla prossima analisi?\n\n"+r.descrizione))api("/api/regola",r).then(()=>{b.textContent="In uso ✓";b.disabled=true}).catch(avvisa)});
function taratura(p){if(!p.taratura)return"";
  return `<details style="margin-top:8px"><summary style="cursor:pointer;font-weight:600">Taratura: cosa succederebbe con soglie diverse</summary>
  <p class="nota" style="margin:6px 0">Solo la somiglianza, senza regola del protagonista. Soglia più alta = meno errori ma meno foto trovate.</p>
  <table><tr><th>Soglia</th><th>Proposte</th><th>Precisione</th><th>Lavoro trovato</th></tr>`+
  p.taratura.map(r=>`<tr style="${Math.abs(r.soglia-p.soglia_attuale)<0.001?"font-weight:700":""}"><td>${r.soglia.toFixed(2)}</td><td>${r.proposte}</td><td>${r.precisione}%</td><td>${r.copertura}%</td></tr>`).join("")+"</table></details>"}
function tilesProva(p){return `<div class="tiles"><div><b>${p.precisione}%</b>precisione (giuste sulle proposte)</div><div><b>${p.copertura}%</b>del lavoro a mano trovato da solo</div><div><b>${p.sbagliate}</b>assegnazioni sbagliate</div><div><b>${p.giuste}</b>giuste su ${p.a_mano} fatte a mano</div><div><b>${p.tra_i_dubbi}</b>altre trovate tra i dubbi</div><div><b>${p.mancate}</b>mancate del tutto</div></div>`+regole(p)+taratura(p)}
function mostraEsito(a){
  const e=$("#esito");
  if(a.in_corso||!a.tipo){e.innerHTML="";return}
  if(a.errore){e.innerHTML=`<div class="problema">Interrotto: ${esc(a.errore)}</div>`;return}
  if(a.tipo=="smista"&&a.lavoro)e.innerHTML=`<div class="riga"><a href="/l/${encodeURIComponent(a.lavoro)}"><button class="primo">Apri la revisione →</button></a></div>`;
  else if(a.tipo=="prova"&&a.risultato)e.innerHTML="<b>Risultato della prova</b>"+tilesProva(a.risultato)+`<div class="riga"><a href="/l/${encodeURIComponent(a.lavoro)}"><button class="primo">Vedi i volti: verdi giusti, rossi no →</button></a></div><p class="nota">Dettaglio per persona nel file prova.csv dentro la cartella lavori/${esc(a.lavoro)}.</p>`;
  else e.innerHTML="";
}
function mostraLavori(L){
  if(!L.length)return;
  $("#lavori").innerHTML=`<table><tr><th>Partita</th><th>Data</th><th>Foto</th><th></th></tr>`+L.map(l=>{
    let st;if(l.prova)st=`<a href="/l/${encodeURIComponent(l.id)}"><span class="etich prova">Prova · ${l.prova.precisione}% precisione · vedi i volti →</span></a>`;
    else if(l.copiato)st=`<span class="etich fatto">Copiata</span>`;
    else st=`<a href="/l/${encodeURIComponent(l.id)}"><span class="etich da">Da rivedere →</span></a>`;
    return `<tr><td>${esc(l.evento)}<br><span class="nota">${esc(l.competizione)}</span></td><td>${esc(l.creato)}</td><td>${l.foto}</td><td>${st}</td></tr>`}).join("")+"</table>";
}
async function apri(percorso){
  $("#sfoglia").hidden=false;$("#cartelle").innerHTML='<div class="vuota">Apro la cartella su MEGA…</div>';$("#sfogliaAz").innerHTML="";
  let r;try{r=await api("/api/sfoglia",{percorso})}catch(e){$("#cartelle").innerHTML=`<div class="vuota">${esc(e.message)}</div>`;return}
  const parti=r.percorso.split("/").filter(Boolean);
  $("#briciole").innerHTML=(r.su!==null?`<a data-p="${esc(r.su)}">↑ indietro</a> · `:"")+parti.map((p,i)=>`<span>${esc(p)}</span>`).join(" › ");
  $("#briciole").querySelectorAll("a").forEach(a=>a.onclick=()=>apri(a.dataset.p));
  const ord=[...r.cartelle].sort((a,b)=>(b=="Foto")-(a=="Foto")||a.localeCompare(b,"it",{numeric:true}));
  $("#cartelle").innerHTML=ord.length?ord.map(c=>`<div data-c="${esc(c)}" class="${c=="Foto"?"foto":""}">📁 ${esc(c)}</div>`).join(""):'<div class="vuota">Nessuna sottocartella.</div>';
  $("#cartelle").querySelectorAll("[data-c]").forEach(d=>d.onclick=()=>apri(r.percorso.replace(/\/$/,"")+"/"+d.dataset.c));
  if(r.foto||parti[parti.length-1]=="Foto"){
    $("#sfogliaAz").innerHTML=`<button class="primo" id="bUsa">Usa questa cartella</button> <span class="nota">${r.foto} foto qui`+(r.cartelle.length?` + sottocartelle dei fotografi`:"")+`</span>`;
    $("#bUsa").onclick=()=>{$("#percorso").value=r.percorso;$("#sfoglia").hidden=true;controlla()}}
  else if(r.cartelle.includes("Foto"))$("#sfogliaAz").innerHTML='<span class="nota">Apri la cartella <b>Foto</b> per selezionarla.</span>';
}
$("#bSfoglia").onclick=()=>apri("");
$("#bImpara").onclick=()=>api("/api/impara",{tutti:false}).catch(avvisa);
$("#bReimpara").onclick=()=>{if(confirm("Reimparo tutti i volti da zero? Ci vorrà un po'."))api("/api/impara",{tutti:true}).catch(avvisa)};
let C=null;
$("#bControlla").onclick=()=>controlla();
async function controlla(){const b=$("#bControlla");b.textContent="Controllo…";$("#dest").hidden=true;
  try{C=await api("/api/controlla",{percorso:$("#percorso").value,prova:true});
    $("#destOrig").textContent=C.sorgente;$("#comp").value=C.competizione;$("#evento").value=C.evento;$("#esistente").value=C.esistente;aggDest();$("#dest").hidden=false;
    if(!C.competizione)alert("Non riconosco competizione e partita dal percorso: scrivile tu nei due campi.");
    $("#dest").scrollIntoView({behavior:"smooth",block:"nearest"});
  }catch(e){avvisa(e)}finally{b.textContent="Controlla"}}
function aggDest(){$("#destPercorso").textContent="PLAYERS / <NOME> / "+($("#comp").value||"?").toUpperCase()+" / "+($("#evento").value||"?").toUpperCase()}
$("#comp").oninput=aggDest;$("#evento").oninput=aggDest;
$("#percorso").oninput=()=>{$("#dest").hidden=true};
$("#bSmista").onclick=()=>api("/api/smista",{sorgente:C.sorgente,competizione:$("#comp").value,evento:$("#evento").value}).catch(avvisa);
$("#bProva").onclick=()=>api("/api/prova",{sorgente:C.sorgente,competizione:$("#comp").value,evento:$("#evento").value,esistente:$("#esistente").value}).catch(avvisa);
$("#bEsci").onclick=async()=>{if(!confirm("Chiudo Smista Foto?"))return;await api("/api/esci");document.body.innerHTML='<main><section class="carta"><h2>Smista Foto è chiuso.</h2><p class="nota">Puoi chiudere questa finestra e quella del Terminale.</p></section></main>'};
aggiorna();setInterval(aggiorna,1000);
</script></body></html>"""
