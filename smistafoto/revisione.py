"""Pagina di revisione: si apre nel browser, mostra cosa verrà copiato e dove,
e copia solo dopo la conferma."""

import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import VERSIONE
from .flussi import carica_lavoro, esegui_copia


def apri(conn, rif, lavoro_dir):
    lavoro, _ = carica_lavoro(lavoro_dir)
    mini_dir = os.path.join(lavoro_dir, "miniature")
    stato = {}

    dati = {k: lavoro[k] for k in ("competizione", "evento", "persone", "foto", "volti", "copiato")}
    dati["versione"] = VERSIONE
    pagina = PAGINA.replace("/*DATI*/null", json.dumps(dati, ensure_ascii=False)).encode("utf-8")

    class Gestore(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _rispondi(self, corpo, tipo="application/json", codice=200):
            self.send_response(codice)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def do_GET(self):
            if self.path == "/":
                self._rispondi(pagina, "text/html; charset=utf-8")
            elif self.path.startswith("/m/"):
                f = os.path.join(mini_dir, os.path.basename(self.path[3:]))
                if os.path.exists(f):
                    with open(f, "rb") as fh:
                        self._rispondi(fh.read(), "image/jpeg")
                else:
                    self._rispondi(b"", codice=404)
            elif self.path == "/stato":
                self._rispondi(json.dumps(stato).encode())
            else:
                self._rispondi(b"", codice=404)

        def do_POST(self):
            if self.path == "/conferma" and not stato:
                n = int(self.headers.get("Content-Length", 0))
                decisioni = json.loads(self.rfile.read(n))
                stato["avviato"] = True

                def lavora():
                    try:
                        esegui_copia(conn, rif, lavoro_dir, decisioni, stato)
                    except Exception as e:
                        stato["errori"] = stato.get("errori", []) + [str(e)]
                        stato["finito"] = True
                    print(f"\nCopia finita: {stato.get('copiate', 0)} copiate, "
                          f"{stato.get('gia_presenti', 0)} già presenti, "
                          f"{len(stato.get('errori', []))} errori.")
                threading.Thread(target=lavora, daemon=True).start()
                self._rispondi(b'{"ok":true}')
            elif self.path == "/chiudi":
                self._rispondi(b'{"ok":true}')
                threading.Thread(target=server.shutdown, daemon=True).start()
            else:
                self._rispondi(b'{"ok":false}', codice=409)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Gestore)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"\nPagina di revisione: {url}")
    print("Se non si apre da sola, copia l'indirizzo nel browser. Per chiudere: pulsante nella pagina o Ctrl+C.")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
    return stato


PAGINA = r"""<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smistamento foto</title>
<style>
:root{--fondo:#f4f4f0;--carta:#fff;--testo:#16161c;--tenue:#6b6b75;--bordo:#dcdcd4;
--ok:#1e7a3c;--okf:#e3f3e7;--dubbio:#b26a00;--dubbiof:#fff2dc;--no:#a3a3ad}
@media (prefers-color-scheme:dark){:root{--fondo:#111114;--carta:#1b1b20;--testo:#f4f4f0;
--tenue:#9a9aa6;--bordo:#2e2e36;--ok:#5fd07f;--okf:#16301f;--dubbio:#ffb347;--dubbiof:#33270f;--no:#55555f}}
*{box-sizing:border-box}
body{margin:0;background:var(--fondo);color:var(--testo);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
header{padding:20px 24px 8px;border-bottom:4px solid var(--testo)}
h1{margin:0;font-size:22px;letter-spacing:.02em}
.sub{color:var(--tenue);margin-top:4px}
main{padding:8px 24px 120px;max-width:1300px;margin:0 auto}
h2{font-size:17px;margin:28px 0 4px;display:flex;align-items:baseline;gap:10px}
h2 small{font-weight:400;color:var(--tenue);font-size:14px}
.nota{color:var(--tenue);margin:0 0 12px}
.dubbi{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.carta{background:var(--carta);border:2px solid var(--bordo);border-radius:10px;padding:10px;display:flex;gap:10px}
.carta.scelto{border-color:var(--ok);background:var(--okf)}
.carta img.volto{width:110px;height:110px;object-fit:cover;border-radius:6px;flex:none}
.carta .info{flex:1;min-width:0;display:flex;flex-direction:column;gap:6px}
.carta .foto{font-size:12px;color:var(--tenue);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
button,select{font:inherit;border-radius:6px;border:1px solid var(--bordo);background:var(--carta);color:var(--testo);padding:5px 9px;cursor:pointer}
button.prop{border-color:var(--dubbio);background:var(--dubbiof);font-weight:600;text-align:left}
select{width:100%}
.persona{background:var(--carta);border:1px solid var(--bordo);border-radius:10px;padding:10px 12px;margin-bottom:10px}
.persona .testa{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.persona .testa b{font-size:16px}
.tipo{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--tenue);margin-left:6px}
.griglia{display:flex;flex-wrap:wrap;gap:6px}
.mini{position:relative;width:84px;height:84px;border-radius:6px;overflow:hidden;cursor:pointer;border:3px solid var(--ok)}
.mini img{width:100%;height:100%;object-fit:cover;display:block}
.mini.off{border-color:var(--no);opacity:.35}
.mini.off::after{content:"✕";position:absolute;inset:0;display:grid;place-items:center;font-size:30px;color:#fff;text-shadow:0 0 4px #000}
.anteprima{position:fixed;right:16px;bottom:96px;max-width:min(520px,60vw);border:3px solid var(--testo);border-radius:8px;display:none;z-index:5;background:#000}
.nessuno{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}
.nessuno .carta{flex-direction:column}
.nessuno img{width:100%;border-radius:6px}
details summary{cursor:pointer;font-weight:600;margin:28px 0 8px}
footer{position:fixed;left:0;right:0;bottom:0;background:var(--testo);color:var(--fondo);padding:14px 24px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
footer .riep{flex:1;min-width:200px}
footer button{background:#ff7a1a;border:0;color:#0a0a0c;font-weight:700;padding:12px 20px;font-size:16px}
footer button:disabled{opacity:.5;cursor:default}
.barra{height:8px;background:#444;border-radius:4px;overflow:hidden;margin-top:6px}
.barra i{display:block;height:100%;background:#ff7a1a;width:0}
@media (max-width:600px){main,header{padding-left:16px;padding-right:16px}}
</style></head><body>
<header><h1 id="titolo"></h1><div class="sub" id="sottotitolo"></div></header>
<main>
<section id="secDubbi"><h2>Da verificare <small id="nDubbi"></small></h2>
<p class="nota">Lo script non è sicuro. Clicca il nome se è giusto, oppure scegli la persona dall'elenco. Quelle lasciate su “non copiare” non vengono copiate.</p>
<div class="dubbi" id="dubbi"></div></section>
<section><h2>Riconosciute <small id="nSicure"></small></h2>
<p class="nota">Clicca una miniatura per escluderla. Passa sopra con il mouse per vedere la foto intera.</p>
<div id="sicure"></div></section>
<details id="secNessuno"><summary id="nNessuno"></summary>
<p class="nota">Foto in cui lo script non ha riconosciuto nessuno (campi lunghi, spalle, pubblico). Se vuoi, assegnale a mano.</p>
<div class="nessuno" id="nessuno"></div></details>
</main>
<img class="anteprima" id="anteprima" alt="">
<footer><div class="riep"><div id="riepilogo"></div><div class="barra" id="barra" hidden><i></i></div></div>
<button id="copia">Copia nelle cartelle</button></footer>
<script>
const D=/*DATI*/null;
const $=s=>document.querySelector(s);
const esc=t=>String(t).replace(/[&<>"']/g,c=>"&#"+c.charCodeAt(0)+";");
const persone=Object.keys(D.persone).sort((a,b)=>(D.persone[a]>D.persone[b])-(D.persone[a]<D.persone[b])||a.localeCompare(b));
const fotoPer=Object.fromEntries(D.foto.map(f=>[f.id,f]));
const escluse=new Set(), sceltaDubbio={}, sceltaNessuno={};
$("#titolo").textContent=D.evento;
$("#sottotitolo").textContent=D.competizione+" · "+D.foto.length+" foto analizzate · Smista Foto versione "+D.versione;
const ante=$("#anteprima");
function hover(el,fid){el.onmouseenter=()=>{ante.src="/m/"+fotoPer[fid].anteprima;ante.style.display="block"};el.onmouseleave=()=>ante.style.display="none"}
function selectPersone(valore,onChange){
  const s=document.createElement("select");
  s.innerHTML='<option value="">— non copiare —</option>'+persone.map(p=>`<option value="${esc(p)}">${esc(p)}${D.persone[p]=="staff"?" (staff)":""}</option>`).join("");
  s.value=valore||"";s.onchange=()=>onChange(s.value);return s}
// dubbi
const dubbi=D.volti.filter(v=>v.stato=="dubbio");
$("#nDubbi").textContent=dubbi.length;
if(!dubbi.length)$("#secDubbi").hidden=true;
for(const v of dubbi){
  const c=document.createElement("div");c.className="carta";
  c.innerHTML=`<img class="volto" src="/m/${v.mini}" alt=""><div class="info"><div class="foto">${esc(fotoPer[v.foto].relativo)}</div></div>`;
  hover(c.querySelector("img"),v.foto);
  const info=c.querySelector(".info");
  const sel=selectPersone("",val=>{sceltaDubbio[v.id]=val;c.classList.toggle("scelto",!!val);aggiorna()});
  for(const [n,s] of [[v.persona,v.punteggio],...v.alternative]){
    const b=document.createElement("button");b.className="prop";b.textContent="È "+n+"?";
    b.title="somiglianza "+Math.round(s*100)+"%";
    b.onclick=()=>{sel.value=n;sel.onchange()};info.append(b)}
  info.append(sel);$("#dubbi").append(c)}
// sicure, raggruppate per persona
const sicure=D.volti.filter(v=>v.stato=="sicuro");
const perPersona={};for(const v of sicure)(perPersona[v.persona]??=[]).push(v);
$("#nSicure").textContent=sicure.length+" volti, "+Object.keys(perPersona).length+" persone";
for(const p of persone.filter(p=>perPersona[p])){
  const box=document.createElement("div");box.className="persona";
  box.innerHTML=`<div class="testa"><span><b>${esc(p)}</b><span class="tipo">${D.persone[p]}</span> <span class="conta"></span></span><button>Escludi tutte</button></div><div class="griglia"></div>`;
  const conta=box.querySelector(".conta"),g=box.querySelector(".griglia");
  const contaAgg=()=>{conta.textContent=perPersona[p].filter(v=>!escluse.has(v.id)).length+" foto"};
  box.querySelector("button").onclick=e=>{const tutte=perPersona[p].every(v=>escluse.has(v.id));
    for(const v of perPersona[p]){tutte?escluse.delete(v.id):escluse.add(v.id)}
    g.querySelectorAll(".mini").forEach(m=>m.classList.toggle("off",!tutte));
    e.target.textContent=tutte?"Escludi tutte":"Includi tutte";contaAgg();aggiorna()};
  for(const v of perPersona[p]){
    const m=document.createElement("div");m.className="mini";m.innerHTML=`<img src="/m/${v.mini}" alt="" loading="lazy">`;
    hover(m,v.foto);
    m.onclick=()=>{escluse.has(v.id)?escluse.delete(v.id):escluse.add(v.id);m.classList.toggle("off");contaAgg();aggiorna()};
    g.append(m)}
  contaAgg();$("#sicure").append(box)}
// foto senza nessuno
const conVolti=new Set(D.volti.map(v=>v.foto));
const vuote=D.foto.filter(f=>!conVolti.has(f.id));
$("#nNessuno").textContent="Foto senza nessuno riconosciuto ("+vuote.length+")";
if(!vuote.length)$("#secNessuno").hidden=true;
$("#secNessuno").ontoggle=()=>{if(!$("#nessuno").children.length)for(const f of vuote){
  const c=document.createElement("div");c.className="carta";
  c.innerHTML=`<img src="/m/${f.anteprima}" alt="" loading="lazy"><div class="foto">${esc(f.relativo)}</div>`;
  c.append(selectPersone("",val=>{sceltaNessuno[f.id]=val;c.classList.toggle("scelto",!!val);aggiorna()}));
  $("#nessuno").append(c)}};
function decisioni(){
  const out=[];
  for(const v of sicure)if(!escluse.has(v.id))out.push({foto:v.foto,persona:v.persona,volto:v.id});
  for(const v of dubbi)if(sceltaDubbio[v.id])out.push({foto:v.foto,persona:sceltaDubbio[v.id],volto:sceltaDubbio[v.id]==v.persona||v.alternative.some(a=>a[0]==sceltaDubbio[v.id])?v.id:null});
  for(const [f,p] of Object.entries(sceltaNessuno))if(p)out.push({foto:+f,persona:p});
  const visti=new Set();return out.filter(d=>{const k=d.foto+"|"+d.persona;if(visti.has(k))return false;visti.add(k);return true})}
function aggiorna(){const d=decisioni();const decisi=dubbi.filter(v=>sceltaDubbio[v.id]).length;
  $("#riepilogo").textContent=`${d.length} copie da fare · dubbi decisi: ${decisi}/${dubbi.length}`}
aggiorna();
if(D.copiato){$("#copia").disabled=true;$("#riepilogo").textContent="Questa partita è già stata copiata."}
$("#copia").onclick=async()=>{
  const d=decisioni();if(!d.length)return alert("Non c'è niente da copiare.");
  const nondecisi=dubbi.length-dubbi.filter(v=>sceltaDubbio[v.id]).length;
  if(!confirm(`Copio ${d.length} foto nelle cartelle di ${D.evento}.`+(nondecisi?`\n${nondecisi} volti dubbi restano non copiati.`:"")+"\nProcedo?"))return;
  const b=$("#copia");b.disabled=true;b.textContent="Copia in corso…";$("#barra").hidden=false;
  await fetch("/conferma",{method:"POST",body:JSON.stringify(d)});
  const t=setInterval(async()=>{const s=await(await fetch("/stato")).json();
    if(s.totale)$("#barra i").style.width=(100*s.fatte/s.totale)+"%";
    $("#riepilogo").textContent=`Copiate ${s.copiate||0} · già presenti ${s.gia_presenti||0} · errori ${(s.errori||[]).length} · ${s.fatte||0}/${s.totale||"?"}`;
    if(s.finito){clearInterval(t);b.textContent="Fatto · chiudi";b.disabled=false;
      if((s.errori||[]).length)alert("Alcune copie non sono riuscite:\n"+s.errori.slice(0,10).join("\n"));
      b.onclick=async()=>{await fetch("/chiudi",{method:"POST"});document.body.innerHTML='<main><h2>Finito. Puoi chiudere questa finestra.</h2></main>'}}},1000)};
</script></body></html>"""
