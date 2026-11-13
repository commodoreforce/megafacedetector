"""Smista Foto come app nel browser: un piccolo server sul computer, raggiungibile
solo da questo computer (127.0.0.1). L'interfaccia è in smistafoto/web/."""

import json
import mimetypes
import os
import posixpath
import shutil
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import DATA_VERSIONE, VERSIONE
from .archivio import esporta, importa
from .flussi import (e_unica, panoramica, analizza_cartella, calibra_insieme, carica_lavoro, confronta, deboli, elenca_lavori,
                     esegui_copia, impara, ricava_evento, simula_copia, trova_cartella_esistente)
from .finestra import apri_finestra as _apri_finestra
from .mega import collegamento, normalizza
from .registro import Registro
from .revisione import dati_revisione
from .volti import Riferimenti, Volti, nome_modello, scarica_auraface

PORTA = 8765


def cartella_in_cloud(percorso):
    """OneDrive, iCloud, Dropbox, Google Drive: la cartella si sincronizza con un cloud esterno al club."""
    p = os.path.abspath(percorso).replace("\\", "/").lower()
    for segno, nome in (("onedrive", "OneDrive"), ("/library/mobile documents/", "iCloud Drive"),
                        ("/library/cloudstorage/", "una cartella sincronizzata nel cloud"),
                        ("dropbox", "Dropbox"), ("google drive", "Google Drive"), ("googledrive", "Google Drive")):
        if segno in p:
            return nome
    return None


class App:
    def __init__(self, qui):
        self.qui = qui
        self.dati = os.path.join(qui, "dati")
        self.lavori = os.path.join(qui, "lavori")
        self.file_locali = os.path.join(self.dati, "impostazioni_locali.json")
        self.cfg = self._leggi_config()
        self.reg = Registro()
        self.cloud = cartella_in_cloud(qui)
        if self.cloud:
            self.reg.avviso(f"Smista Foto è dentro {self.cloud}: i volti imparati (dati personali) vengono copiati "
                            "nel cloud. Sposta la cartella fuori, ad esempio in C:\\SmistaFoto o nella tua cartella Utente.")
        self.conn = self.volti = None
        self.modello = nome_modello(self.cfg)
        self.rif = Riferimenti(self.dati, self.modello, 512 if self.modello == "auraface" else 128)
        self.account = None
        self.problema = "Controllo del collegamento in corso…"
        self.stato_mega = "controllo"   # controllo | assente | scollegato | ok
        self.stato_modello = "attesa"   # attesa | download | pronto | errore
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
                self.stato_mega = "assente"
                self.problema = str(e)
                if not silenzioso:
                    self.reg.errore(self.problema)
                return
            chi = self.conn.chi_sono()
            if not chi:
                self.stato_mega = "scollegato"
                self.problema = ("MEGAcmd risponde ma non risulta collegato a un account. Nella finestra di "
                                 "MEGAcmd scrivi login seguito dall'email del club e la password. "
                                 "Il semaforo diventa verde da solo entro qualche secondo.")
                if not silenzioso:
                    self.reg.errore(self.problema)
                    self.reg.info("Risposta di MEGAcmd: " + getattr(self.conn, "risposta_whoami", "?"))
                return
            self.account = chi
            self.stato_mega = "ok"
            self.reg.ok(f"Collegato a MEGA come {chi}.")
            if self.volti is None:
                try:
                    if self.modello == "auraface":
                        self.stato_modello = "download"
                        scarica_auraface(os.path.join(self.qui, "modelli"), self.reg)
                    self.reg.info("Carico il modello di riconoscimento dei volti…")
                    self.volti = Volti(os.path.join(self.qui, "modelli"), self.cfg)
                    self.reg.ok(f"Modello di riconoscimento: {self.volti.nome}.")
                    self.stato_modello = "pronto"
                except Exception as e:
                    self.stato_modello = "errore"
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
        if (sorgente + "/").upper().startswith(self.cfg["cartella_giocatori"].rstrip("/").upper() + "/"):
            raise RuntimeError("Questa è una cartella dei giocatori: scegli la cartella dove caricano i fotografi.")
        comp, evento = ricava_evento(self.cfg, sorgente)
        unica = bool(comp) and e_unica(self.cfg, comp)
        if unica:
            esistente = comp
        else:
            esistente = trova_cartella_esistente(self.conn, self.rif, comp, evento) if prova and comp else ""
        return {"sorgente": sorgente, "competizione": comp, "evento": evento, "esistente": esistente,
                "unica": unica}

    def smista(self, sorgente, comp, evento, prova_su=None):
        self._serve_collegamento()
        comp, evento = comp.strip().upper(), evento.strip().upper()
        unica = e_unica(self.cfg, comp)
        if not comp or not evento:
            raise RuntimeError("Indica la data dell'allenamento." if unica else "Indica competizione e nome della partita.")
        import re
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9_\-]*", evento) and unica:
            raise RuntimeError("La data va scritta solo con numeri, es. 20261102.")

        def lavoro():
            rif = self.rif
            if prova_su and unica:
                self.reg.info(f"PROVA (non copia nulla): confronto con le foto già presenti in <NOME>/{comp}.")
                rif, tolte = self.rif.senza(f"/{comp}/")
                self.reg.info(f"Per una prova onesta ignoro {tolte} volti imparati dalle cartelle {comp}.")
            elif prova_su:
                self.reg.info(f"PROVA (non copia nulla): confronto con lo smistamento a mano in "
                              f"<NOME>/{comp}/{prova_su}.")
                rif, tolte = self.rif.senza(f"/{comp}/{prova_su}/")
                self.reg.info(f"Per una prova onesta ignoro {tolte} volti imparati proprio da questa partita.")
            elif unica:
                self.reg.info(f"Le foto andranno in <NOME>/{comp}, con «{evento}_» davanti al nome, "
                              "ma solo dopo la tua revisione.")
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

    def calibra(self):
        self._serve_collegamento()

        def lavoro():
            self.attivita["risultato"] = calibra_insieme(self.cfg, self.conn, self.lavori, self.reg)
        self.avvia("calibra", lavoro)

    def _leggi_config(self):
        """config.json (del repository) + dati/impostazioni_locali.json (solo su questo
        computer, scritto dall'app: git non lo tocca, quindi gli aggiornamenti non si bloccano)."""
        with open(os.path.join(self.qui, "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        if os.path.exists(self.file_locali):
            with open(self.file_locali, encoding="utf-8") as f:
                locali = json.load(f)
            for k, v in locali.items():
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    for k2, v2 in v.items():
                        if isinstance(v2, dict) and isinstance(cfg[k].get(k2), dict):
                            cfg[k][k2] = {**cfg[k][k2], **v2}
                        else:
                            cfg[k][k2] = v2
                else:
                    cfg[k] = v
        return cfg

    def controlla_cartelle(self):
        self._serve_collegamento()

        def lavoro():
            self.attivita["risultato"] = panoramica(self.cfg, self.conn, self.rif, self.lavori, self.dati, self.reg)
        self.avvia("cartelle", lavoro)

    def ultima_panoramica(self):
        p = os.path.join(self.dati, "panoramica.json")
        if not os.path.exists(p):
            return None
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)

    def applica_regola(self, r):
        if self.attivita["in_corso"]:
            raise RuntimeError("C'è un'attività in corso: aspetta che finisca.")
        valori = {k: float(r[k]) for k in ("soglia", "relativa_min", "frazione_min", "nitidezza_min")}
        if not (0.1 <= valori["soglia"] <= 0.9 and 0 <= valori["relativa_min"] <= 1
                and 0 <= valori["frazione_min"] <= 0.5 and 0 <= valori["nitidezza_min"] <= 100000):
            raise RuntimeError("Valori della regola non validi.")
        locali = {}
        if os.path.exists(self.file_locali):
            with open(self.file_locali, encoding="utf-8") as f:
                locali = json.load(f)
        locali.setdefault("soglie", {}).setdefault(self.modello, {})["soglia_sicura"] = valori["soglia"]
        locali["protagonista"] = {k: valori[k] for k in ("relativa_min", "frazione_min", "nitidezza_min")}
        os.makedirs(self.dati, exist_ok=True)
        with open(self.file_locali, "w", encoding="utf-8") as f:
            json.dump(locali, f, ensure_ascii=False, indent=2)
        cfg = self.cfg = self._leggi_config()
        if self.volti:
            self.volti.cfg = cfg
        from .flussi import descrivi_regola
        self.reg.ok("Nuova regola salvata: " + descrivi_regola(cfg["protagonista"], valori["soglia"])
                    + ". Vale dalla prossima analisi.")

    def sfoglia(self, percorso):
        self._serve_collegamento()
        giocatori = self.cfg["cartella_giocatori"].rstrip("/")
        stagione = posixpath.dirname(giocatori) or "/"
        p = normalizza(percorso) if percorso else stagione
        if not (p + "/").startswith(stagione.rstrip("/") + "/") or p == stagione.rstrip("/") + "/":
            p = stagione  # si sfoglia solo dentro la stagione
        cartelle, foto = self.conn.elenca_cartelle(p)
        if p.rstrip("/") == stagione.rstrip("/"):
            cartelle = [c for c in cartelle if c.upper() != posixpath.basename(giocatori).upper()]
        comp, evento = ricava_evento(self.cfg, p)
        scegli = foto > 0 or p.rstrip("/").split("/")[-1].upper() == "FOTO" or \
            (bool(comp) and e_unica(self.cfg, comp) and bool(evento))
        return {"percorso": p, "su": posixpath.dirname(p) if p.rstrip("/") != stagione.rstrip("/") else None,
                "cartelle": cartelle, "foto": foto, "selezionabile": scegli}

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
        n_persone = len(self.rif.info)
        preparazione = [
            {"id": "megacmd", "fatto": self.stato_mega in ("scollegato", "ok"),
             "in_corso": self.stato_mega == "controllo"},
            {"id": "accesso", "fatto": self.stato_mega == "ok", "in_corso": self.stato_mega == "controllo"},
            {"id": "modello", "fatto": self.stato_modello == "pronto",
             "in_corso": self.stato_modello == "download", "errore": self.stato_modello == "errore"},
            {"id": "volti", "fatto": n_persone > 0,
             "in_corso": self.attivita["in_corso"] and self.attivita["tipo"] == "impara"},
        ]
        g = sum(1 for i in self.rif.info.values() if i.get("tipo") == "giocatore")
        a = dict(self.attivita)
        if a.get("inizio"):
            a["secondi"] = int(time.time() - a["inizio"])
        return {"versione": VERSIONE, "data_versione": DATA_VERSIONE, "cartella_cloud": self.cloud,
                "modello": self.volti.nome if self.volti else self.modello,
                "account": self.account, "problema": self.problema, "semaforo": semaforo,
                "stato_mega": self.stato_mega, "stato_modello": self.stato_modello,
                "preparazione": preparazione, "pronto": all(p["fatto"] for p in preparazione),
                "regola": self._descrizione_regola(),
                "persone": {"giocatori": g, "staff": len(self.rif.info) - g, "deboli": deboli(self.rif)},
                "elenco": self._lista_persone(), "esclusi": sorted(self.esclusi),
                "attivita": a, "registro": self.reg.stato(dalla),
                "lavori": self._lavori()}

    def _descrizione_regola(self):
        from .flussi import descrivi_regola
        from .volti import protagonista, soglie
        return descrivi_regola(protagonista(self.cfg), soglie(self.cfg)["soglia_sicura"])

    def dati_lavoro(self, lavoro_id):
        d = self._cartella_lavoro(lavoro_id)
        lavoro, _ = carica_lavoro(d)
        prova = None
        if os.path.exists(os.path.join(d, "prova.json")):
            with open(os.path.join(d, "prova.json"), encoding="utf-8") as fh:
                prova = json.load(fh)
        return dati_revisione(lavoro_id, lavoro, prova)

    # ------------------------------------------------------------ volti su un altro computer

    def esporta_volti(self):
        """Crea lo zip con dati/ e primi_piani/. Solo sul computer: MEGA non c'entra."""
        if not self.rif.info:
            raise RuntimeError("Su questo computer non ci sono ancora volti imparati da esportare.")
        tmp = os.path.join(self.qui, ".esportazione_tmp.zip")
        r = esporta(self.qui, tmp, VERSIONE, len(self.rif.info), self.modello)
        self.reg.ok(f"Volti esportati: {r['persone']} persone, {r['primi_piani']} primi piani.")
        return tmp, time.strftime("SmistaFoto_volti_%Y%m%d.zip")

    def importa_volti(self, percorso_zip):
        with self._lucchetto:  # niente analisi o apprendimenti mentre sostituisco i volti
            if self.attivita["in_corso"]:
                raise RuntimeError("C'è un'attività in corso: aspetta che finisca e riprova.")
            r = importa(self.qui, percorso_zip, os.path.join(self.qui, "backup_volti"), VERSIONE)
            self.cfg = self._leggi_config()
            self.rif = Riferimenti(self.dati, self.modello, 512 if self.modello == "auraface" else 128)
            self.esclusi = []
            if os.path.exists(self.file_esclusi):
                with open(self.file_esclusi, encoding="utf-8") as f:
                    self.esclusi = json.load(f)
        m = r["manifesto"]
        n = len(self.rif.info)
        if n:
            self.reg.ok(f"Volti importati: {n} persone (esportati il {m.get('creato_il', '?')}).")
        elif m.get("modello") and m.get("modello") != self.modello:
            raise RuntimeError(f"L'archivio contiene volti imparati con un altro modello ({m.get('modello')}): "
                               "su questo computer vanno imparati di nuovo.")
        if r["backup"]:
            self.reg.info(f"I volti che c'erano prima sono salvati in {r['backup']}.")
        return {"persone": n, "creato_il": m.get("creato_il"), "backup": r["backup"]}

    def _lavori(self):
        ora = time.time()
        if ora - self._cache_lavori[0] > 5 or self.attivita["in_corso"] != self._cache_lavori[2]:
            self._cache_lavori = (ora, elenca_lavori(self.lavori)[:15], self.attivita["in_corso"])
        return self._cache_lavori[1]


def avvia_app(qui, apri=True):
    app = App(qui)
    url = f"http://127.0.0.1:{PORTA}/"
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORTA), _gestore(app))
    except OSError:
        print(f"Smista Foto è già aperto: apro la finestra {url}")
        if apri:
            _apri_finestra(url)
        return
    print(f"\n  SMISTA FOTO  Cesena FC  versione {VERSIONE}\n")
    print(f"  L'app si apre in una finestra: {url}")
    print("  Tieni aperta questa finestra del Terminale finché usi Smista Foto:")
    print("  chiudendola si chiude anche l'app. Qui sotto scorre il registro.\n")
    app.collega()
    if apri:
        threading.Timer(0.8, lambda: _apri_finestra(url)).start()
    app.server = server
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
    print("Smista Foto chiuso.")


WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


def _gestore(app):
    class Gestore(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _invia(self, corpo, tipo="application/json; charset=utf-8", codice=200, extra=None):
            if isinstance(corpo, (dict, list)):
                corpo = json.dumps(corpo, ensure_ascii=False)
            if isinstance(corpo, str):
                corpo = corpo.encode("utf-8")
            self.send_response(codice)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(corpo)

        def _file_web(self, nome):
            nome = os.path.basename(nome)
            percorso = os.path.join(WEB, nome)
            if not os.path.isfile(percorso):
                return self._invia(b"", "text/plain", 404)
            tipo = mimetypes.guess_type(nome)[0] or "application/octet-stream"
            if tipo.startswith("text/") or tipo in ("application/javascript", "image/svg+xml"):
                tipo += "; charset=utf-8"
            with open(percorso, "rb") as fh:
                self._invia(fh.read(), tipo)

        def _corpo(self):
            n = int(self.headers.get("Content-Length", 0) or 0)
            return json.loads(self.rfile.read(n) or b"{}")

        def _ricevi_file(self):
            """Salva il file caricato in una cartella temporanea, a pezzi (può essere grande)."""
            n = int(self.headers.get("Content-Length", 0) or 0)
            if n <= 0 or n > 4 * 1024 ** 3:
                raise RuntimeError("File vuoto o troppo grande.")
            dest = os.path.join(app.qui, ".importazione_upload.zip")
            with open(dest, "wb") as out:
                resto = n
                while resto:
                    pezzo = self.rfile.read(min(resto, 1024 * 1024))
                    if not pezzo:
                        raise RuntimeError("Caricamento interrotto: riprova.")
                    out.write(pezzo)
                    resto -= len(pezzo)
            return dest

        def _invia_file(self, percorso, nome):
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Length", str(os.path.getsize(percorso)))
                self.send_header("Content-Disposition", f'attachment; filename="{nome}"')
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                with open(percorso, "rb") as fh:
                    shutil.copyfileobj(fh, self.wfile, 1024 * 1024)
            finally:
                os.remove(percorso)

        def _stessa_origine(self):
            # le richieste che cambiano qualcosa devono arrivare dall'app stessa
            origine = self.headers.get("Origin")
            return origine in (None, f"http://127.0.0.1:{PORTA}", f"http://localhost:{PORTA}")

        def do_GET(self):
            u = urlparse(self.path)
            parti = [p for p in u.path.split("/") if p]
            try:
                if not parti:
                    self._file_web("index.html")
                elif parti[0] == "web" and len(parti) == 2:
                    self._file_web(parti[1])
                elif parti == ["api", "stato"]:
                    dalla = int(parse_qs(u.query).get("dalla", ["0"])[0])
                    self._invia(app.stato(dalla))
                elif parti == ["api", "cartelle"]:
                    self._invia(app.ultima_panoramica() or {})
                elif parti[:2] == ["api", "lavoro"] and len(parti) == 3:
                    self._invia(app.dati_lavoro(parti[2]))
                elif parti[0] == "l" and len(parti) == 2:  # vecchi collegamenti alla revisione
                    self._invia(b"", "text/plain", 302, {"Location": f"/#/revisione/{parti[1]}"})
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
            if not self._stessa_origine():
                return self._invia({"errore": "Richiesta non consentita."}, codice=403)
            parti = [p for p in urlparse(self.path).path.split("/") if p]
            try:
                if parti == ["api", "primopiano"]:
                    q = parse_qs(urlparse(self.path).query)
                    n = int(self.headers.get("Content-Length", 0) or 0)
                    app.salva_primo_piano(q["persona"][0], q["nome"][0], self.rfile.read(n))
                    return self._invia({"ok": True})
                if parti == ["api", "importa-volti"]:
                    caricato = os.path.join(app.qui, ".importazione_upload.zip")
                    try:
                        return self._invia(app.importa_volti(self._ricevi_file()))
                    finally:
                        if os.path.exists(caricato):
                            os.remove(caricato)
                if parti == ["api", "esporta-volti"]:
                    self._corpo()
                    return self._invia_file(*app.esporta_volti())
                c = self._corpo()
                r = {"ok": True}
                if parti == ["api", "collega"]:
                    app.collega()
                elif parti == ["api", "impara"]:
                    app.impara(bool(c.get("tutti")), c.get("solo"))
                elif parti == ["api", "cartelle"]:
                    app.controlla_cartelle()
                elif parti == ["api", "calibra"]:
                    app.calibra()
                elif parti == ["api", "regola"]:
                    app.applica_regola(c)
                elif parti == ["api", "sfoglia"]:
                    r = app.sfoglia(c.get("percorso", ""))
                elif parti == ["api", "escludi"]:
                    app.escludi(c["nome"], bool(c["escluso"]))
                elif parti == ["api", "controlla"]:
                    r = app.controlla(c.get("percorso", ""), bool(c.get("prova")))
                elif parti == ["api", "smista"]:
                    app.smista(c["sorgente"], c["competizione"], c["evento"])
                elif parti == ["api", "prova"]:
                    if not str(c.get("esistente", "")).strip():
                        raise RuntimeError("Indica la cartella della partita già smistata a mano.")
                    app.smista(c["sorgente"], c["competizione"], c["evento"], prova_su=c["esistente"].strip())
                elif len(parti) == 3 and parti[0] == "l" and parti[2] == "simula":
                    app.simula(parti[1], c["decisioni"])
                elif len(parti) == 3 and parti[0] == "l" and parti[2] == "conferma":
                    app.copia(parti[1], c["decisioni"])
                elif parti == ["api", "esci"]:
                    threading.Thread(target=app.server.shutdown, daemon=True).start()
                else:
                    return self._invia({"errore": "sconosciuto"}, codice=404)
                self._invia(r)
            except Exception as e:
                self._invia({"errore": str(e)}, codice=400)
    return Gestore
