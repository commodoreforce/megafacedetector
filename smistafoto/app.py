"""Smista Foto come app nel browser: un piccolo server sul computer
(raggiungibile solo da questo computer) con pulsanti, avanzamento e registro."""

import json
import os
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import DATA_VERSIONE, VERSIONE
from .flussi import (analizza_cartella, carica_lavoro, confronta, deboli, elenca_lavori,
                     esegui_copia, impara, ricava_evento, trova_cartella_esistente)
from .mega import collegamento, normalizza
from .registro import Registro
from .revisione import pagina_revisione
from .volti import Riferimenti, Volti

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
        self.rif = Riferimenti(self.dati)
        self.account = None
        self.problema = "Controllo del collegamento in corso…"
        self.attivita = {"tipo": None, "in_corso": False, "lavoro": None, "risultato": None, "errore": None}
        self._lucchetto = threading.Lock()
        self._cache_lavori = (0, [], None)
        self._ultimo_controllo = 0

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
            if self.volti is None:
                self.reg.info("Carico i modelli di riconoscimento dei volti…")
                self.volti = Volti(os.path.join(self.qui, "modelli"), self.cfg)
            self.account = chi
            self.reg.ok(f"Collegato a MEGA come {chi}.")
            n = len(self.rif.info)
            if n:
                self.reg.info(f"Conosco già {n} persone.")
            else:
                self.reg.info("Non conosco ancora nessun volto: premi «Impara i volti».")
        self.avvia("collegamento", lavoro)

    def impara(self, tutti):
        self._serve_collegamento()
        self.avvia("impara", lambda: impara(self.cfg, self.conn, self.volti, self.rif,
                                            self.dati, self.reg, tutti=tutti))

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
                "account": self.account, "problema": self.problema, "semaforo": semaforo,
                "persone": {"giocatori": g, "staff": len(self.rif.info) - g, "deboli": deboli(self.rif)},
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
                    self._invia(pagina_revisione(parti[1], lavoro), "text/html; charset=utf-8")
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
                c = self._corpo()
                if parti == ["api", "collega"]:
                    app.collega()
                    r = {"ok": True}
                elif parti == ["api", "impara"]:
                    app.impara(bool(c.get("tutti")))
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
  <div id="problema"></div>
 </section>
 <section class="carta">
  <h2>2 · Smista una partita</h2>
  <p class="nota">Incolla il percorso della cartella delle foto su MEGA. Va bene anche copiato dalla barra di MEGA (Cloud drive › 2026-27 › MATCH › …).</p>
  <input id="percorso" placeholder="2026-27/MATCH/SERIEBKT/G10_Sudtirol_Cesena_1_1/Foto">
  <div class="riga"><button class="primo" id="bControlla">Controlla</button></div>
  <div id="dest" hidden class="dest">
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
  S=s;$("#ver").textContent="versione "+s.versione;
  $("#semaforo").className="semaforo "+s.semaforo;
  $("#conto").textContent={verde:"MEGA collegato",giallo:"Controllo MEGA…",rosso:"MEGA non collegato"}[s.semaforo];
  $("#contoSub").textContent=s.account||(s.semaforo=="rosso"?"ricontrollo da solo ogni 15 secondi":"");
  $("#problema").innerHTML=s.problema&&!s.account?`<div class="problema">${esc(s.problema)}<br><button id="bRiprova">Riprova</button></div>`:"";
  if($("#bRiprova"))$("#bRiprova").onclick=()=>api("/api/collega").catch(avvisa);
  $("#nG").textContent=s.persone.giocatori;$("#nS").textContent=s.persone.staff;
  $("#deboli").innerHTML=s.persone.deboli.length?`<div class="avviso">Riconoscimento debole per: <b>${s.persone.deboli.map(esc).join(", ")}</b>. Metti 3-5 primi piani di ciascuno nella cartella <b>primi_piani/COGNOME</b> dello script e premi «Impara i volti nuovi».</div>`:"";
  const a=s.attivita, occ=a.in_corso||!s.account;
  for(const b of ["#bImpara","#bReimpara","#bControlla","#bSmista","#bProva"])$(b).disabled=occ;
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
}
function tilesProva(p){return `<div class="tiles"><div><b>${p.precisione}%</b>precisione (giuste sulle proposte)</div><div><b>${p.copertura}%</b>del lavoro a mano trovato da solo</div><div><b>${p.sbagliate}</b>assegnazioni sbagliate</div><div><b>${p.giuste}</b>giuste su ${p.a_mano} fatte a mano</div><div><b>${p.tra_i_dubbi}</b>altre trovate tra i dubbi</div><div><b>${p.mancate}</b>mancate del tutto</div></div>`}
function mostraEsito(a){
  const e=$("#esito");
  if(a.in_corso||!a.tipo){e.innerHTML="";return}
  if(a.errore){e.innerHTML=`<div class="problema">Interrotto: ${esc(a.errore)}</div>`;return}
  if(a.tipo=="smista"&&a.lavoro)e.innerHTML=`<div class="riga"><a href="/l/${encodeURIComponent(a.lavoro)}"><button class="primo">Apri la revisione →</button></a></div>`;
  else if(a.tipo=="prova"&&a.risultato)e.innerHTML="<b>Risultato della prova</b>"+tilesProva(a.risultato)+`<p class="nota">Dettaglio per persona nel file prova.csv dentro la cartella lavori/${esc(a.lavoro)}.</p>`;
  else e.innerHTML="";
}
function mostraLavori(L){
  if(!L.length)return;
  $("#lavori").innerHTML=`<table><tr><th>Partita</th><th>Data</th><th>Foto</th><th></th></tr>`+L.map(l=>{
    let st;if(l.prova)st=`<span class="etich prova">Prova · ${l.prova.precisione}% precisione</span>`;
    else if(l.copiato)st=`<span class="etich fatto">Copiata</span>`;
    else st=`<a href="/l/${encodeURIComponent(l.id)}"><span class="etich da">Da rivedere →</span></a>`;
    return `<tr><td>${esc(l.evento)}<br><span class="nota">${esc(l.competizione)}</span></td><td>${esc(l.creato)}</td><td>${l.foto}</td><td>${st}</td></tr>`}).join("")+"</table>";
}
$("#bImpara").onclick=()=>api("/api/impara",{tutti:false}).catch(avvisa);
$("#bReimpara").onclick=()=>{if(confirm("Reimparo tutti i volti da zero? Ci vorrà un po'."))api("/api/impara",{tutti:true}).catch(avvisa)};
let C=null;
$("#bControlla").onclick=async()=>{const b=$("#bControlla");b.textContent="Controllo…";
  try{C=await api("/api/controlla",{percorso:$("#percorso").value,prova:true});
    $("#comp").value=C.competizione;$("#evento").value=C.evento;$("#esistente").value=C.esistente;aggDest();$("#dest").hidden=false;
    if(!C.competizione)alert("Non riconosco competizione e partita dal percorso: scrivile tu nei due campi.");
  }catch(e){avvisa(e)}finally{b.textContent="Controlla"}};
function aggDest(){$("#destPercorso").textContent="PLAYERS / <NOME> / "+($("#comp").value||"?").toUpperCase()+" / "+($("#evento").value||"?").toUpperCase()}
$("#comp").oninput=aggDest;$("#evento").oninput=aggDest;
$("#percorso").oninput=()=>{$("#dest").hidden=true};
$("#bSmista").onclick=()=>api("/api/smista",{sorgente:C.sorgente,competizione:$("#comp").value,evento:$("#evento").value}).catch(avvisa);
$("#bProva").onclick=()=>api("/api/prova",{sorgente:C.sorgente,competizione:$("#comp").value,evento:$("#evento").value,esistente:$("#esistente").value}).catch(avvisa);
$("#bEsci").onclick=async()=>{if(!confirm("Chiudo Smista Foto?"))return;await api("/api/esci");document.body.innerHTML='<main><section class="carta"><h2>Smista Foto è chiuso.</h2><p class="nota">Puoi chiudere questa finestra e quella del Terminale.</p></section></main>'};
aggiorna();setInterval(aggiorna,1000);
</script></body></html>"""
