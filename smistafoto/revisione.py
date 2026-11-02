"""Pagina di revisione di un'analisi: mostra cosa verrà copiato e dove,
e fa partire la copia solo dopo la conferma."""

import json

from . import VERSIONE


def pagina_revisione(lavoro_id, lavoro):
    dati = {k: lavoro[k] for k in ("competizione", "evento", "persone", "foto", "volti", "copiato")}
    dati["versione"] = VERSIONE
    dati["id"] = lavoro_id
    dati["prova"] = bool(lavoro.get("prova_su"))
    js = json.dumps(dati, ensure_ascii=False).replace("</", "<\\/")
    return PAGINA.replace("/*DATI*/null", js)


PAGINA = r"""<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Revisione · Smista Foto</title>
<style>
:root{--fondo:#f4f4f0;--carta:#fff;--testo:#16161c;--tenue:#6b6b75;--bordo:#dcdcd4;
--ok:#1e7a3c;--okf:#e3f3e7;--dubbio:#9a5b00;--dubbiof:#fff2dc;--no:#a3a3ad}
@media (prefers-color-scheme:dark){:root{--fondo:#111114;--carta:#1b1b20;--testo:#f4f4f0;
--tenue:#9a9aa6;--bordo:#2e2e36;--ok:#5fd07f;--okf:#16301f;--dubbio:#ffb347;--dubbiof:#33270f;--no:#55555f}}
*{box-sizing:border-box}
body{margin:0;background:var(--fondo);color:var(--testo);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
header{background:#0a0a0c;color:#f4f4f0;padding:14px 24px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
header a{color:#c8c8d0;text-decoration:none;font-size:14px}
header h1{margin:0;font-size:20px;letter-spacing:.02em}
header .sub{color:#a0a0aa;font-size:13.5px}
main{padding:8px 24px 130px;max-width:1300px;margin:0 auto}
h2{font-size:17px;margin:26px 0 4px;display:flex;align-items:baseline;gap:10px}
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
.anteprima{position:fixed;right:16px;bottom:110px;max-width:min(520px,60vw);border:3px solid #0a0a0c;border-radius:8px;display:none;z-index:5;background:#000}
.nessuno{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}
.nessuno .carta{flex-direction:column}
.nessuno img{width:100%;border-radius:6px}
details summary{cursor:pointer;font-weight:600;margin:26px 0 8px}
footer{position:fixed;left:0;right:0;bottom:0;background:#0a0a0c;color:#f4f4f0;padding:14px 24px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
footer .riep{flex:1;min-width:200px}
footer button{background:#f4f4f0;border:0;color:#0a0a0c;font-weight:700;padding:12px 20px;font-size:16px}
footer button:disabled{opacity:.5;cursor:default}
footer button.sec{background:transparent;color:#f4f4f0;border:1px solid #6b6b75}
#simBox{background:var(--carta);border:2px solid var(--testo);border-radius:12px;padding:16px;margin:20px 0}
#simBox h2{margin-top:0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:10px 0}
.tiles div{background:var(--fondo);border-radius:8px;padding:10px;font-size:13px;color:var(--tenue)}
.tiles b{display:block;font-size:24px;color:var(--testo)}
.tiles .rosso b{color:#d93025}
table{width:100%;border-collapse:collapse;font-size:13.5px}
td,th{padding:6px;border-bottom:1px solid var(--bordo);text-align:left;vertical-align:top}
th{color:var(--tenue);font-weight:600;font-size:12px}
.mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;word-break:break-all}
.barra{height:8px;background:#444;border-radius:4px;overflow:hidden;margin-top:6px}
.barra i{display:block;height:100%;background:#f4f4f0;width:0;transition:width .4s}
@media (max-width:600px){main,header{padding-left:16px;padding-right:16px}}
</style></head><body>
<header><a href="/">← Smista Foto</a><h1 id="titolo"></h1><span class="sub" id="sottotitolo"></span></header>
<main>
<section id="simBox" hidden></section>
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
<button id="simula" class="sec">Simula (non copia nulla)</button>
<button id="copia">Copia nelle cartelle</button></footer>
<script>
const D=/*DATI*/null;
const B="/l/"+encodeURIComponent(D.id);
const $=s=>document.querySelector(s);
const esc=t=>String(t).replace(/[&<>"']/g,c=>"&#"+c.charCodeAt(0)+";");
const persone=Object.keys(D.persone).sort((a,b)=>(D.persone[a]>D.persone[b])-(D.persone[a]<D.persone[b])||a.localeCompare(b));
const fotoPer=Object.fromEntries(D.foto.map(f=>[f.id,f]));
const escluse=new Set(), sceltaDubbio={}, sceltaNessuno={};
$("#titolo").textContent=D.evento;
$("#sottotitolo").textContent=D.competizione+" · "+D.foto.length+" foto analizzate · versione "+D.versione;
const ante=$("#anteprima");
function hover(el,fid){el.onmouseenter=()=>{ante.src=B+"/m/"+fotoPer[fid].anteprima;ante.style.display="block"};el.onmouseleave=()=>ante.style.display="none"}
function selectPersone(valore,onChange){
  const s=document.createElement("select");
  s.innerHTML='<option value="">— non copiare —</option>'+persone.map(p=>`<option value="${esc(p)}">${esc(p)}${D.persone[p]=="staff"?" (staff)":""}</option>`).join("");
  s.value=valore||"";s.onchange=()=>onChange(s.value);return s}
const dubbi=D.volti.filter(v=>v.stato=="dubbio");
$("#nDubbi").textContent=dubbi.length;
if(!dubbi.length)$("#secDubbi").hidden=true;
for(const v of dubbi){
  const c=document.createElement("div");c.className="carta";
  c.innerHTML=`<img class="volto" src="${B}/m/${v.mini}" alt=""><div class="info"><div class="foto">${esc(fotoPer[v.foto].relativo)}</div></div>`;
  hover(c.querySelector("img"),v.foto);
  const info=c.querySelector(".info");
  const sel=selectPersone("",val=>{sceltaDubbio[v.id]=val;c.classList.toggle("scelto",!!val);aggiorna()});
  for(const [n,s] of [[v.persona,v.punteggio],...v.alternative]){
    const b=document.createElement("button");b.className="prop";b.textContent="È "+n+"?";
    b.title="somiglianza "+Math.round(s*100)+"%";
    b.onclick=()=>{sel.value=n;sel.onchange()};info.append(b)}
  info.append(sel);$("#dubbi").append(c)}
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
    const m=document.createElement("div");m.className="mini";m.innerHTML=`<img src="${B}/m/${v.mini}" alt="" loading="lazy">`;
    hover(m,v.foto);
    m.onclick=()=>{escluse.has(v.id)?escluse.delete(v.id):escluse.add(v.id);m.classList.toggle("off");contaAgg();aggiorna()};
    g.append(m)}
  contaAgg();$("#sicure").append(box)}
const conVolti=new Set(D.volti.map(v=>v.foto));
const vuote=D.foto.filter(f=>!conVolti.has(f.id));
$("#nNessuno").textContent="Foto senza nessuno riconosciuto ("+vuote.length+")";
if(!vuote.length)$("#secNessuno").hidden=true;
$("#secNessuno").ontoggle=()=>{if(!$("#nessuno").children.length)for(const f of vuote){
  const c=document.createElement("div");c.className="carta";
  c.innerHTML=`<img src="${B}/m/${f.anteprima}" alt="" loading="lazy"><div class="foto">${esc(f.relativo)}</div>`;
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
const btn=$("#copia"), bSim=$("#simula");
async function attendi(onFine){
  const t=setInterval(async()=>{const s=await(await fetch("/api/stato?dalla=999999")).json();const a=s.attivita,g=s.registro;
    if(g.n)$("#barra i").style.width=(100*g.i/g.n)+"%";
    if(a.in_corso){$("#riepilogo").textContent=`${g.fase}: ${g.i} di ${g.n||"?"}`+(g.dettaglio?" · "+g.dettaglio:"");return}
    clearInterval(t);onFine(a)},1000)}
function mostraSimulazione(x){
  const b=$("#simBox");b.hidden=false;
  b.innerHTML=`<h2>Simulazione della copia <small>su MEGA non è stato scritto nulla</small></h2>
  <div class="tiles"><div><b>${x.copierebbe}</b>foto verrebbero copiate</div><div><b>${x.salterebbe}</b>già presenti: verrebbero saltate</div>
  <div><b>${x.cartelle_nuove}</b>cartelle nuove da creare</div><div class="${x.bloccata?"rosso":""}"><b>${x.bloccata}</b>bloccate dalle regole di sicurezza</div></div>
  <table><tr><th>Persona</th><th>Cartella su MEGA</th><th>Da copiare</th><th>Già presenti</th></tr>`+
  x.persone.map(p=>`<tr><td><b>${esc(p.persona)}</b></td><td class="mono">${esc(p.cartella)}${p.nuova?' <i>(nuova)</i>':""}</td><td>${p.copierebbe}</td><td>${p.salterebbe}</td></tr>`).join("")+`</table>
  <details style="margin-top:10px"><summary>Dettaglio foto per foto (${x.dettaglio.length})</summary><table><tr><th>Persona</th><th>Foto</th><th>Destinazione</th><th>Cosa succederebbe</th></tr>`+
  x.dettaglio.map(r=>`<tr><td>${esc(r[0])}</td><td class="mono">${esc(r[1])}</td><td class="mono">${esc(r[2])}</td><td>${esc(r[3])}</td></tr>`).join("")+`</table></details>
  <p class="nota" style="margin-top:10px">Lo stesso elenco è salvato nel file simulazione.csv dentro la cartella lavori/${esc(D.id)}. Se va bene, premi «Copia nelle cartelle» in basso. Se cambi qualche scelta, puoi rifare la simulazione.</p>`;
  b.scrollIntoView({behavior:"smooth"})}
bSim.onclick=async()=>{
  const d=decisioni();if(!d.length)return alert("Non c'è niente da simulare.");
  const r=await fetch(B+"/simula",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({decisioni:d})});
  if(!r.ok){alert((await r.json()).errore);return}
  bSim.disabled=btn.disabled=true;bSim.textContent="Simulazione…";$("#barra").hidden=false;
  attendi(a=>{bSim.disabled=btn.disabled=false;bSim.textContent="Simula di nuovo";$("#barra").hidden=true;aggiorna();
    if(a.errore)alert("Simulazione interrotta: "+a.errore);else mostraSimulazione(a.risultato)})};
if(D.prova){bSim.disabled=true;btn.disabled=true;$("#riepilogo").textContent="Questa è una prova: non si può copiare. Per copiare, avvia lo smistamento normale.";}
else if(D.copiato){bSim.disabled=true;btn.disabled=true;$("#riepilogo").textContent="Questa partita è già stata copiata."}
btn.onclick=async()=>{
  const d=decisioni();if(!d.length)return alert("Non c'è niente da copiare.");
  const nondecisi=dubbi.length-dubbi.filter(v=>sceltaDubbio[v.id]).length;
  if(!confirm(`Copio ${d.length} foto nelle cartelle di ${D.evento}.`+(nondecisi?`\n${nondecisi} volti dubbi restano non copiati.`:"")+"\nLe foto già presenti vengono saltate, niente viene sovrascritto.\nProcedo?"))return;
  const r=await fetch(B+"/conferma",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({decisioni:d})});
  if(!r.ok){alert((await r.json()).errore);return}
  btn.disabled=bSim.disabled=true;btn.textContent="Copia in corso…";$("#barra").hidden=false;
  attendi(a=>{
      if(a.errore){$("#riepilogo").textContent="Interrotto: "+a.errore;btn.textContent="Errore";return}
      const x=a.risultato||{};$("#barra i").style.width="100%";
      $("#riepilogo").textContent=`Finito: ${x.copiate} copiate · ${x.gia_presenti} già presenti (saltate) · ${(x.errori||[]).length} errori`;
      if((x.errori||[]).length)alert("Alcune copie non sono riuscite:\n"+x.errori.slice(0,10).join("\n"));
      btn.textContent="Torna a Smista Foto";btn.disabled=false;btn.onclick=()=>location.href="/"})};
</script></body></html>"""
