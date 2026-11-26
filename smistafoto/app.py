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
from urllib.parse import parse_qs, unquote, urlparse

from . import DATA_VERSIONE, VERSIONE
from .aggiornamento import CODICE_RIAVVIO, metodo as metodo_aggiornamento, novita, scarica_versione
from .archivio import esporta, importa
from .flussi import (e_unica, panoramica, analizza_cartella, calibra_insieme, carica_lavoro, confronta, deboli, elenca_lavori,
                     esegui_copia, impara, ricava_evento, simula_copia, trova_cartella_esistente)
from .finestra import apri_finestra as _apri_finestra
from .mega import collegamento, normalizza
from .registro import Registro
from .sponsor import ElencoSponsor, Lettore, Loghi, sponsor_nella_foto
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
        self.loghi = os.path.join(qui, "loghi")
        self.sponsor = ElencoSponsor(self.dati, self.loghi)
        self.radice_sponsor = None      # es. /2026-27/SPONSOR, trovata su MEGA al collegamento
        self.sponsor_su_mega = []       # le cartelle sponsor che esistono su MEGA
        self.lettore = None
        # aggiornamenti: esito dell'ultimo (lo passa il programma di avvio) e novità su GitHub
        esito = os.environ.get("SMISTA_ESITO_AGGIORNAMENTO", "")
        self.esito_aggiornamento = esito or None
        if esito.startswith("ok|"):
            self.reg.ok(f"Smista Foto è stato aggiornato alla versione {VERSIONE}.")
        elif esito.startswith("annullato|"):
            self.reg.avviso("Aggiornamento annullato: " + esito.split("|", 2)[2] + f" Resta la versione {VERSIONE}.")
        self.info_aggiornamento = None
        self._ultimo_controllo_agg = 0

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
            self._trova_sponsor(silenzioso)
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

    # ------------------------------------------------------------ sponsor

    def _trova_sponsor(self, silenzioso=False):
        """Cerca la cartella degli sponsor nella stagione (es. /2026-27/SPONSOR) e i nomi
        delle cartelle sponsor che contiene. Solo lettura. Gli sponsor nuovi trovati su MEGA
        vengono aggiunti con le impostazioni di partenza (parola = nome, 4 foto a partita, 2 ad allenamento)."""
        radice = (self.cfg.get("cartella_sponsor") or "").strip()
        try:
            if not radice:
                stagione = posixpath.dirname(self.cfg["cartella_giocatori"].rstrip("/"))
                nomi = [n for n in self.conn.elenca_nomi(stagione) if n.upper().startswith("SPONSOR")]
                radice = posixpath.join(stagione, sorted(nomi, key=len)[0]) if nomi else ""
            if not radice:
                self.radice_sponsor, self.sponsor_su_mega = None, []
                if self.sponsor.voci and not silenzioso:
                    self.reg.avviso("Non trovo la cartella SPONSOR nella stagione su MEGA: gli sponsor non vengono smistati.")
                return
            self.conn.imposta_radice_sponsor(radice)
            cartelle, _ = self.conn.elenca_cartelle(radice)
        except Exception as e:
            self.radice_sponsor, self.sponsor_su_mega = None, []
            self.reg.avviso(f"Cartella degli sponsor non utilizzabile: {e}")
            return
        self.radice_sponsor = radice
        self.sponsor_su_mega = sorted(cartelle)
        nuovi = []
        for nome in cartelle:
            try:
                pulito = ElencoSponsor.nome_pulito(nome)
            except ValueError:
                continue
            if pulito == nome and nome not in self.sponsor.voci:
                self.sponsor.imposta(nome)
                nuovi.append(nome)
        if nuovi:
            self.sponsor.salva()
            self.reg.ok(f"Trovati su MEGA {len(nuovi)} sponsor nuovi: {', '.join(nuovi)}. "
                        "Nella pagina Sponsor puoi aggiungere i loghi e scegliere quante foto prendere.")
        elif not silenzioso and self.sponsor.attivi():
            self.reg.info(f"Sponsor: {len(self.sponsor.attivi())} attivi, cartella {radice}.")

    # ------------------------------------------------------------ aggiornamento del programma

    def controlla_aggiornamento(self, forza=False):
        """Chiede a GitHub qual è l'ultima versione (al massimo ogni 6 ore, se non forzato)."""
        if not forza and time.time() - self._ultimo_controllo_agg < 6 * 3600 and self.info_aggiornamento:
            return self.info_aggiornamento
        self._ultimo_controllo_agg = time.time()
        try:
            info = novita(VERSIONE)
            info["metodo"] = metodo_aggiornamento(self.qui)
            info["errore"] = None
            if info["disponibile"] and (not self.info_aggiornamento or not self.info_aggiornamento.get("disponibile")):
                self.reg.info(f"È disponibile la versione {info['nuova']} di Smista Foto: in basso a sinistra c'è «Aggiorna».")
        except Exception as e:
            info = {"attuale": VERSIONE, "disponibile": False, "errore": f"Non riesco a controllare gli aggiornamenti ({e})."}
        self.info_aggiornamento = info
        return info

    def aggiorna_programma(self):
        if not os.environ.get("SMISTA_CONTROLLORE"):
            raise RuntimeError("Per aggiornare dall'app chiudi Smista Foto e riaprilo dall'icona sulla Scrivania, poi riprova.")
        if self.attivita["in_corso"]:
            raise RuntimeError("C'è un'attività in corso: aggiorna quando ha finito.")

        def lavoro():
            self.reg.inizia_fase("Aggiorno Smista Foto")
            self.attivita["risultato"] = {"versione": scarica_versione(self.qui, VERSIONE, self.reg)}
            # il programma di avvio aggiorna i componenti ad app chiusa e la riapre
            global CODICE_USCITA
            CODICE_USCITA = CODICE_RIAVVIO
            threading.Timer(2.5, self.server.shutdown).start()
        self.avvia("aggiornamento", lavoro)

    def _prepara_lettore(self):
        if self.lettore is None:
            self.lettore = Lettore(os.path.join(self.qui, "modelli"))
        return self.lettore

    def dati_sponsor(self):
        elenco = []
        for nome, v in sorted(self.sponsor.voci.items()):
            elenco.append({"nome": nome, **v, "su_mega": nome in self.sponsor_su_mega,
                           "loghi": [os.path.basename(f) for f in self.sponsor.loghi(nome)]})
        solo_mega = [n for n in self.sponsor_su_mega if n not in self.sponsor.voci]
        return {"radice": self.radice_sponsor, "elenco": elenco, "non_validi": solo_mega,
                "collegato": bool(self.account)}

    def salva_sponsor(self, c):
        if self.attivita["in_corso"] and self.attivita["tipo"] in ("smista", "prova"):
            raise RuntimeError("C'è un'analisi in corso: modifica gli sponsor quando finisce.")
        nome = ElencoSponsor.nome_pulito(c.get("nome", ""))
        if c.get("nuovo") and nome in self.sponsor.voci:
            raise RuntimeError(f"{nome} c'è già: modificalo dall'elenco.")
        parole = c.get("parole")
        if isinstance(parole, str):
            parole = [p for p in parole.replace(";", ",").split(",")]
        self.sponsor.imposta(nome, parole=parole, foto_partita=c.get("foto_partita"),
                             foto_allenamento=c.get("foto_allenamento"), attivo=c.get("attivo"),
                             disegno=c.get("disegno"))
        self.sponsor.salva()
        self.reg.ok(f"Sponsor {nome} salvato." + ("" if nome in self.sponsor_su_mega or not self.radice_sponsor else
                    f" Su MEGA la cartella {nome} non c'è ancora: verrà creata alla prima copia."))
        return {"nome": nome}

    def elimina_sponsor(self, nome):
        if nome not in self.sponsor.voci:
            raise RuntimeError("Sponsor sconosciuto.")
        del self.sponsor.voci[nome]
        self.sponsor.salva()
        cartella = os.path.join(self.loghi, nome)
        if os.path.isdir(cartella):
            shutil.rmtree(cartella)
        self.reg.info(f"Sponsor {nome} tolto da Smista Foto (su questo computer). Su MEGA non cambia nulla.")
        if nome in self.sponsor_su_mega:
            self.reg.info(f"La cartella {nome} esiste ancora su MEGA: al prossimo collegamento verrà ritrovata.")

    def salva_logo(self, nome, nome_file, dati):
        if nome not in self.sponsor.voci:
            raise RuntimeError("Sponsor sconosciuto.")
        if not dati or len(dati) > 20 * 1024 * 1024:
            raise RuntimeError("File vuoto o troppo grande (massimo 20 MB).")
        from io import BytesIO
        from PIL import Image
        try:
            img = Image.open(BytesIO(dati))
            img.load()
        except Exception:
            raise RuntimeError(f"{nome_file}: non è un'immagine (servono PNG, JPG o WEBP; per i loghi vettoriali esporta un PNG).")
        if max(img.size) < 80:
            raise RuntimeError(f"{nome_file}: immagine troppo piccola, serve almeno 80 pixel.")
        img.thumbnail((1600, 1600))
        cartella = os.path.join(self.loghi, nome)
        os.makedirs(cartella, exist_ok=True)
        base = "".join(ch for ch in os.path.splitext(os.path.basename(nome_file.replace("\\", "/")))[0]
                       if ch.isalnum() or ch in "-_")[:40] or "logo"
        destinazione = os.path.join(cartella, base + ".png")
        i = 2
        while os.path.exists(destinazione):
            destinazione = os.path.join(cartella, f"{base}_{i}.png")
            i += 1
        img.convert("RGBA").save(destinazione)
        self.reg.info(f"{nome}: aggiunto il logo {os.path.basename(destinazione)}.")
        return os.path.basename(destinazione)

    def togli_logo(self, nome, file):
        f = os.path.join(self.loghi, nome, os.path.basename(file))
        if nome in self.sponsor.voci and os.path.isfile(f):
            os.remove(f)

    def file_logo(self, nome, file):
        f = os.path.join(self.loghi, os.path.basename(nome), os.path.basename(file))
        return f if os.path.isfile(f) else None

    def prova_sponsor(self, dati):
        """Cerca gli sponsor in una foto caricata dal computer: per capire cosa vede il programma."""
        from io import BytesIO
        from PIL import Image, ImageOps
        import numpy as np
        if not dati or len(dati) > 60 * 1024 * 1024:
            raise RuntimeError("File vuoto o troppo grande.")
        try:
            img = np.array(ImageOps.exif_transpose(Image.open(BytesIO(dati))).convert("RGB"))[:, :, ::-1].copy()
        except Exception:
            raise RuntimeError("Non riesco ad aprire la foto.")
        attivi = self.sponsor.attivi()
        if not attivi:
            raise RuntimeError("Non ci sono sponsor attivi da cercare.")
        t = time.time()
        letture = self._prepara_lettore().leggi(img, self.cfg.get("lato_lungo_sponsor", 2048))
        loghi = Loghi(self.sponsor)
        disegni = loghi.cerca(img) if loghi else {}
        volti = []
        if self.volti is not None:
            h, w = img.shape[:2]
            s = min(1.0, self.cfg["lato_lungo_analisi"] / max(h, w))
            import cv2
            piccola = cv2.resize(img, (int(w * s), int(h * s))) if s < 1 else img
            self.volti.trova.setInputSize((piccola.shape[1], piccola.shape[0]))
            _, tv = self.volti.trova.detect(piccola)
            volti = [{"riquadro": [float(v) / s for v in f[:4]]} for f in (tv if tv is not None else [])]
        trovati = sponsor_nella_foto(img, letture, disegni, attivi, volti, set())
        H, W = img.shape[:2]
        return {"trovati": trovati, "secondi": round(time.time() - t, 1),
                "letture": [{"testo": l["testo"], "affidabilita": l["affidabilita"],
                             "box": [round(l["riquadro"][0] / W, 4), round(l["riquadro"][1] / H, 4),
                                     round(l["riquadro"][2] / W, 4), round(l["riquadro"][3] / H, 4)]} for l in letture]}

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

    def smista(self, sorgente, comp, evento, prova_su=None, cerca_sponsor=True):
        self._serve_collegamento()
        sponsor = None
        if cerca_sponsor and not prova_su and self.sponsor.attivi():
            if not self.radice_sponsor:
                self.reg.avviso("Gli sponsor non vengono cercati: su MEGA non trovo la cartella SPONSOR nella stagione.")
            else:
                try:
                    sponsor = {"attivi": self.sponsor.attivi(), "lettore": self._prepara_lettore(),
                               "loghi": Loghi(self.sponsor) or None, "radice": self.radice_sponsor}
                except Exception as e:  # gli sponsor non devono impedire lo smistamento dei volti
                    self.reg.avviso(f"Gli sponsor non vengono cercati: {e}")
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
                                  self.lavori, self.reg, prova_su=prova_su, sponsor=sponsor)
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
                "sponsor": {"attivi": len(self.sponsor.attivi()), "radice": self.radice_sponsor},
                "aggiornamento": dict(self.info_aggiornamento or {}, esito=self.esito_aggiornamento,
                                      dall_app=bool(os.environ.get("SMISTA_CONTROLLORE"))),
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
        dati = dati_revisione(lavoro_id, lavoro, prova)
        dati["loghi"] = {n: (self.sponsor.loghi(n) and os.path.basename(self.sponsor.loghi(n)[0])) or None
                         for n in lavoro.get("sponsor", {})}
        return dati

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
    # controllo degli aggiornamenti: poco dopo l'avvio e poi ogni 6 ore (solo lettura da GitHub)
    def controlla_spesso():
        while True:
            app.controlla_aggiornamento()
            time.sleep(6 * 3600 + 60)
    primo_controllo = threading.Timer(8, lambda: threading.Thread(target=controlla_spesso, daemon=True).start())
    primo_controllo.daemon = True
    primo_controllo.start()
    if apri:
        threading.Timer(0.8, lambda: _apri_finestra(url)).start()
    app.server = server
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
    print("Smista Foto chiuso.")


CODICE_USCITA = 0  # 75 = riavviare dopo l'aggiornamento (lo legge smista.py)

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
                elif parti == ["api", "aggiornamento"]:
                    self._invia(app.controlla_aggiornamento(forza=True))
                elif parti == ["api", "sponsor"]:
                    self._invia(app.dati_sponsor())
                elif parti[0] == "logo" and len(parti) == 3:
                    f = app.file_logo(unquote(parti[1]), unquote(parti[2]))
                    if not f:
                        return self._invia(b"", "text/plain", 404)
                    with open(f, "rb") as fh:
                        self._invia(fh.read(), "image/png")
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
                if parti == ["api", "sponsor-logo"]:
                    q = parse_qs(urlparse(self.path).query)
                    n = int(self.headers.get("Content-Length", 0) or 0)
                    return self._invia({"file": app.salva_logo(q["nome"][0], q["file"][0], self.rfile.read(n))})
                if parti == ["api", "sponsor-prova"]:
                    n = int(self.headers.get("Content-Length", 0) or 0)
                    if n > 60 * 1024 * 1024:
                        raise RuntimeError("Foto troppo grande.")
                    return self._invia(app.prova_sponsor(self.rfile.read(n)))
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
                    app.smista(c["sorgente"], c["competizione"], c["evento"], cerca_sponsor=c.get("sponsor", True))
                elif parti == ["api", "aggiorna"]:
                    app.aggiorna_programma()
                elif parti == ["api", "sponsor-salva"]:
                    r = app.salva_sponsor(c)
                elif parti == ["api", "sponsor-elimina"]:
                    app.elimina_sponsor(c["nome"])
                elif parti == ["api", "sponsor-togli-logo"]:
                    app.togli_logo(c["nome"], c["file"])
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
