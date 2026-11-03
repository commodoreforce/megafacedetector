/* Smista Foto: interfaccia. Nessuna libreria esterna. */
"use strict";

/* ================================================================ utilità */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = t => String(t ?? "").replace(/[&<>"']/g, c => "&#" + c.charCodeAt(0) + ";");
const V = {};            // viste registrate: V.nome = {titolo, mostra(el, parametri), aggiorna(S)}
let S = null;            // ultimo stato dal server
let vistaAttiva = null;

async function api(url, dati) {
  const opz = dati === undefined ? {} : {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(dati)};
  let r;
  try { r = await fetch(url, opz); } catch (e) { throw new Error("Smista Foto non risponde: è stato chiuso? Riaprilo con l'icona sulla Scrivania."); }
  let j = {};
  try { j = await r.json(); } catch (e) { /* risposta vuota */ }
  if (!r.ok) throw new Error(j.errore || "Operazione non riuscita.");
  return j;
}
function memo(chiave, valore) {
  try {
    if (valore === undefined) return JSON.parse(localStorage.getItem("sf:" + chiave) || "null");
    if (valore === null) localStorage.removeItem("sf:" + chiave); else localStorage.setItem("sf:" + chiave, JSON.stringify(valore));
  } catch (e) { return null; }
}
function durata(s) {
  if (!isFinite(s) || s < 0) return "";
  s = Math.round(s);
  if (s < 60) return s + " s";
  const m = Math.round(s / 60);
  return m < 60 ? m + " min" : Math.floor(m / 60) + " h " + (m % 60) + " min";
}
const ICONA = {
  cartella: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
  foto: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="11" r="2"/><path d="M21 16l-5-5-8 8"/></svg>',
  zoom: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/></svg>',
  copia: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></svg>',
};

/* ================================================================ notifiche, modali, aiuti */
function avviso(testo, tipo = "info", {azione, etichetta, durataMs} = {}) {
  const t = document.createElement("div");
  t.className = "toast " + tipo;
  t.setAttribute("role", tipo === "errore" ? "alert" : "status");
  t.innerHTML = `<span>${esc(testo)}</span>`;
  if (azione) {
    const b = document.createElement("button");
    b.textContent = etichetta;
    b.onclick = () => { azione(); t.remove(); };
    t.append(b);
  }
  const x = document.createElement("button");
  x.textContent = "Chiudi"; x.setAttribute("aria-label", "Chiudi l'avviso");
  x.onclick = () => t.remove();
  t.append(x);
  $("#toasts").append(t);
  setTimeout(() => t.remove(), durataMs ?? (tipo === "errore" ? 14000 : azione ? 12000 : 6000));
}
function errore(e) { avviso(e.message || String(e), "errore"); }

let modaleAperta = null;
function modale({titolo, corpo, azioni = [{testo: "Chiudi", valore: null}], chiudibile = true, larga = false}) {
  return new Promise(risolvi => {
    const velo = document.createElement("div");
    velo.className = "velo";
    velo.innerHTML = `<div class="modale" role="dialog" aria-modal="true" aria-labelledby="mTit" ${larga ? 'style="width:min(980px,100%)"' : ""}>
      <header><h2 id="mTit">${esc(titolo)}</h2></header><div class="corpo"></div><footer></footer></div>`;
    const box = $(".corpo", velo);
    if (typeof corpo === "string") box.innerHTML = corpo; else if (corpo) box.append(corpo);
    const prima = document.activeElement;
    const chiudi = v => { velo.remove(); modaleAperta = null; document.removeEventListener("keydown", tasti, true); prima?.focus?.(); risolvi(v); };
    const piede = $("footer", velo);
    azioni.forEach(a => {
      const b = document.createElement("button");
      b.className = "btn " + (a.tipo || ""); b.textContent = a.testo;
      if (a.id) b.id = a.id;
      if (a.disabilitato) b.disabled = true;
      b.onclick = () => chiudi(a.valore);
      piede.append(b);
    });
    function tasti(e) {
      if (e.key === "Escape" && chiudibile) { e.stopPropagation(); chiudi(null); }
      if (e.key === "Tab") { // il fuoco resta dentro la finestra
        const f = $$("button:not([disabled]), input, select, a[href], [tabindex='0']", velo);
        if (!f.length) return;
        if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
        else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
      }
    }
    document.addEventListener("keydown", tasti, true);
    velo.addEventListener("mousedown", e => { if (e.target === velo && chiudibile) chiudi(null); });
    document.body.append(velo);
    modaleAperta = {velo, chiudi};
    (piede.querySelector(".primo:not([disabled])") || piede.querySelector("button"))?.focus();
  });
}
function conferma(titolo, testo, ok = "Conferma", tipo = "primo") {
  return modale({titolo, corpo: `<p>${testo}</p>`, azioni: [{testo: "Annulla", valore: false}, {testo: ok, tipo, valore: true}]});
}

/* bottone «?»: spiegazione breve sul posto, con collegamento alla guida */
document.addEventListener("click", e => {
  const q = e.target.closest("[data-q]");
  $$(".fumetto").forEach(f => f.remove());
  if (!q) return;
  e.preventDefault();
  const voce = (window.GLOSSARIO || {})[q.dataset.q];
  if (!voce) return;
  const f = document.createElement("div");
  f.className = "fumetto"; f.setAttribute("role", "tooltip");
  f.innerHTML = `<b>${esc(voce.titolo)}</b>${voce.testo}${voce.link ? `<p style="margin:8px 0 0"><a href="#/aiuto/${voce.link}">Leggi nella guida</a></p>` : ""}`;
  document.body.append(f);
  const r = q.getBoundingClientRect();
  f.style.top = (window.scrollY + r.bottom + 8) + "px";
  f.style.left = Math.max(12, Math.min(window.scrollX + r.left - 20, window.scrollX + innerWidth - f.offsetWidth - 12)) + "px";
});
document.addEventListener("keydown", e => { if (e.key === "Escape") $$(".fumetto").forEach(f => f.remove()); });
const q = chiave => `<button type="button" class="q" data-q="${chiave}" aria-label="Che cos'è?">?</button>`;

/* ================================================================ tema */
function applicaTema(t) {
  if (t === "chiaro" || t === "scuro") document.documentElement.dataset.tema = t; else delete document.documentElement.dataset.tema;
  $("#bTema").textContent = "Tema: " + ({chiaro: "chiaro", scuro: "scuro"}[t] || "automatico");
}
$("#bTema").onclick = () => {
  const ordine = ["auto", "chiaro", "scuro"], ora = memo("tema") || "auto";
  const t = ordine[(ordine.indexOf(ora) + 1) % 3];
  memo("tema", t); applicaTema(t);
};
applicaTema(memo("tema") || "auto");

/* ================================================================ stato dal server, barra attività, registro */
let righeLette = 0, eraInCorso = false, ultimaAttivita = null;
async function aggiornaStato() {
  let s;
  try { s = await api("/api/stato?dalla=" + righeLette); }
  catch (e) {
    $("#faseAtt").textContent = "Smista Foto è chiuso. Per riaprirlo usa l'icona sulla Scrivania.";
    $("#semaforo").className = "semaforo rosso";
    return;
  }
  S = s;
  aggiornaCornice(s);
  aggiornaRegistro(s.registro);
  gestisciFineAttivita(s.attivita);
  vistaAttiva?.aggiorna?.(s);
}
function aggiornaCornice(s) {
  $("#versione").textContent = `Versione ${s.versione} · ${s.modello}`;
  $("#semaforo").className = "semaforo " + s.semaforo;
  $("#megaTitolo").textContent = {verde: "MEGA collegato", giallo: "Controllo MEGA", rosso: "MEGA non collegato"}[s.semaforo];
  $("#megaSub").textContent = s.account || (s.semaforo === "rosso" ? "ricontrollo ogni 15 secondi" : "");
  const daRivedere = s.lavori.filter(l => !l.copiato && !l.prova).length;
  $("#contaRevisioni").textContent = daRivedere; $("#contaRevisioni").classList.toggle("nascosto", !daRivedere);
  const deb = s.persone.deboli.length;
  $("#contaDeboli").textContent = deb; $("#contaDeboli").classList.toggle("nascosto", !deb);
  const a = s.attivita, r = s.registro;
  $("#progAtt").classList.toggle("nascosto", !a.in_corso);
  if (a.in_corso) {
    $("#faseAtt").textContent = r.fase || "Al lavoro";
    const p = $("#progAtt"), ind = !r.n;
    p.classList.toggle("indet", ind);
    $("i", p).style.width = ind ? "" : (100 * r.i / r.n) + "%";
    let eta = "";
    if (r.n && r.i > 2) eta = "circa " + durata(r.secondi_fase / r.i * (r.n - r.i)) + " alla fine";
    $("#etaAtt").textContent = (r.n ? `${r.i} di ${r.n}` : "") + (eta ? "  ·  " + eta : "");
  } else {
    $("#faseAtt").textContent = s.pronto ? "Nessuna attività in corso" : "Configurazione da completare: vedi la pagina Inizio";
    $("#etaAtt").textContent = "";
  }
  document.title = (a.in_corso && r.n ? Math.round(100 * r.i / r.n) + "% · " : "") + "Smista Foto";
}
function aggiornaRegistro(r) {
  if (!r.righe.length) return;
  const box = $("#righe"), giu = box.scrollTop + box.clientHeight >= box.scrollHeight - 30;
  for (const x of r.righe) box.insertAdjacentHTML("beforeend", `<p class="${x.tipo}"><span class="ora">${x.ora}</span><span>${esc(x.testo)}</span></p>`);
  righeLette = r.totale_righe;
  if (giu) box.scrollTop = box.scrollHeight;
}
$("#bRegistro").onclick = () => {
  const reg = $("#registro"), aperto = reg.classList.toggle("nascosto") === false;
  $("#bRegistro").setAttribute("aria-expanded", aperto);
  if (aperto) $("#righe").scrollTop = $("#righe").scrollHeight;
};
$("#bChiudiRegistro").onclick = () => { $("#registro").classList.add("nascosto"); $("#bRegistro").setAttribute("aria-expanded", false); };

function notifica(titolo, testo) {
  if (!document.hidden || !("Notification" in window) || Notification.permission !== "granted") return;
  try { new Notification(titolo, {body: testo}); } catch (e) { /* non disponibile */ }
}
function gestisciFineAttivita(a) {
  if (a.in_corso) { eraInCorso = true; ultimaAttivita = a.tipo; return; }
  if (!eraInCorso) return;
  eraInCorso = false;
  if (a.errore) { avviso("Interrotto: " + a.errore, "errore"); notifica("Smista Foto: interrotto", a.errore); return; }
  const tipo = a.tipo || ultimaAttivita;
  if (tipo === "smista" && a.lavoro) {
    avviso("Analisi finita: le foto sono pronte da rivedere.", "ok", {azione: () => location.hash = "#/revisione/" + a.lavoro, etichetta: "Apri la revisione"});
    notifica("Analisi finita", "Le foto sono pronte da rivedere in Smista Foto.");
  } else if (tipo === "impara") {
    avviso("Volti imparati.", "ok"); notifica("Smista Foto", "Ho finito di imparare i volti.");
  } else if (tipo === "prova" && a.risultato) {
    avviso(`Prova finita: ${a.risultato.precisione}% di precisione, ${a.risultato.copertura}% del lavoro trovato.`, "ok", {azione: () => location.hash = "#/strumenti", etichetta: "Vedi i risultati"});
    notifica("Prova finita", `${a.risultato.precisione}% di precisione`);
  } else if (tipo === "calibra") {
    avviso("Regole calcolate.", "ok");
  }
}
function chiediNotifiche() {
  if ("Notification" in window && Notification.permission === "default") { try { Notification.requestPermission(); } catch (e) { /* ignorato */ } }
}

$("#statoMega").onclick = () => location.hash = "#/aiuto/mega";
$("#bEsci").onclick = async () => {
  if (S?.attivita.in_corso && !await conferma("Chiudere Smista Foto?", "C'è un'attività in corso: chiudendo si interrompe.", "Chiudi comunque", "pericolo")) return;
  else if (!S?.attivita.in_corso && !await conferma("Chiudere Smista Foto?", "Potrai riaprirlo con l'icona sulla Scrivania.", "Chiudi")) return;
  await api("/api/esci", {}).catch(() => {});
  document.body.innerHTML = '<main class="vista" style="text-align:center;padding-top:12vh"><img src="/web/scudetto.png" alt="Cesena FC" style="height:160px;background:#000;padding:18px 22px;border-radius:12px"><h1 style="margin-top:24px">Smista Foto è chiuso.</h1><p style="margin:10px auto">Puoi chiudere questa finestra e quella del Terminale.</p></main>';
};
window.addEventListener("beforeunload", e => {
  if (S?.attivita.in_corso && S.attivita.tipo === "copia") { e.preventDefault(); e.returnValue = ""; }
});

/* ================================================================ navigazione */
function percorsoHash() { return (location.hash.replace(/^#\/?/, "") || "").split("/").map(decodeURIComponent); }
function naviga() {
  $$(".fumetto").forEach(f => f.remove());
  modaleAperta?.chiudi(null);
  const [nome, ...par] = percorsoHash();
  const v = V[nome || "home"] || V.home;
  vistaAttiva?.esci?.();
  vistaAttiva = v;
  const radice = v.nav || nome || "home";
  $$("#nav a").forEach(a => a.dataset.vista === radice ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
  $("#titoloVista").textContent = v.titolo;
  const el = $("#vista");
  el.innerHTML = "";
  v.mostra(el, par);
  if (S) v.aggiorna?.(S);
  el.focus({preventScroll: true});
  window.scrollTo(0, 0);
}
window.addEventListener("hashchange", naviga);

/* ================================================================ componenti riutilizzabili */
const PASSI_PREP = {
  megacmd: {titolo: "Installa MEGAcmd", testo: `È il programma ufficiale di MEGA che Smista Foto usa per leggere e copiare le foto. Scaricalo da <a href="https://mega.io/cmd" target="_blank" rel="noopener">mega.io/cmd</a>, installalo come un normale programma e poi premi «Ricontrolla».`},
  accesso: {titolo: "Entra in MEGA con l'account del club", testo: `Apri <b>MEGAcmd</b> (dalle Applicazioni sul Mac, dal menu Start su Windows). Nella finestra che si apre scrivi il comando qui sotto con l'email del club, premi Invio e inserisci la password: mentre la scrivi non compare nulla, è normale. Il semaforo in alto diventa verde da solo.`},
  modello: {titolo: "Prepara il riconoscimento dei volti", testo: "Al primo avvio Smista Foto scarica il modello di riconoscimento (circa 260 MB, una volta sola). Parte da solo appena MEGA è collegato."},
  volti: {titolo: "Impara i volti di giocatori e staff", testo: "Smista Foto guarda le cartelle in PLAYERS e PLAYERS/_STAFF e impara chi è il proprietario di ogni cartella. Su MEGA legge soltanto. Ci vogliono 10-20 minuti; intanto puoi usare il computer per altro."},
};
function vistaPreparazione(s) {
  const prima = s.preparazione.findIndex(p => !p.fatto);
  return `<ol class="passi">` + s.preparazione.map((p, i) => {
    const t = PASSI_PREP[p.id];
    const classe = p.fatto ? "fatto" : p.errore ? "errore" : p.in_corso ? "in-corso" : i === prima ? "attivo" : "futuro";
    let az = "";
    if (p.id === "megacmd") az = `<div class="riga-btn"><a class="btn primo" href="https://mega.io/cmd" target="_blank" rel="noopener">Scarica MEGAcmd</a><button class="btn" data-az="ricontrolla">Ricontrolla</button></div>`;
    if (p.id === "accesso") az = `<div class="riga-btn"><code id="cmdLogin">login social@cesenafc.com</code><button class="btn" data-az="copia-login">${ICONA.copia} Copia il comando</button><button class="btn" data-az="ricontrolla">Ricontrolla</button></div>`;
    if (p.id === "modello" && p.errore) az = `<div class="avviso rosso"><b>Non riesco a preparare il modello.</b>${esc(s.problema || "")}</div><div class="riga-btn"><button class="btn primo" data-az="ricontrolla">Riprova</button><a class="btn" href="#/aiuto/problemi">Soluzioni ai problemi</a></div>`;
    if (p.id === "modello" && p.in_corso) az = `<p class="tenue">Download in corso: l'avanzamento è nella barra in basso.</p>`;
    if (p.id === "volti") az = p.in_corso ? `<p class="tenue">Sto imparando: l'avanzamento è nella barra in basso.</p>` : `<div class="riga-btn"><button class="btn primo" data-az="impara" ${s.preparazione.slice(0, 3).every(x => x.fatto) ? "" : "disabled"}>Impara i volti</button></div>`;
    return `<li class="${classe}"><h3>${t.titolo}</h3><div class="corpo"><p>${t.testo}</p>${az}</div></li>`;
  }).join("") + `</ol>`;
}
function collegaAzioniPrep(el) {
  el.onclick = async e => {
    const b = e.target.closest("[data-az]"); if (!b) return;
    try {
      if (b.dataset.az === "ricontrolla") { await api("/api/collega", {}); avviso("Ricontrollo in corso.", "info"); }
      if (b.dataset.az === "impara") { chiediNotifiche(); await api("/api/impara", {tutti: false}); avviso("Inizio a imparare i volti: ti avviso quando ho finito.", "info"); }
      if (b.dataset.az === "copia-login") { await navigator.clipboard.writeText($("#cmdLogin").textContent); avviso("Comando copiato: incollalo nella finestra di MEGAcmd e correggi l'email se serve.", "ok"); }
    } catch (err) { errore(err); }
  };
}

/* esploratore delle cartelle su MEGA: solo lettura */
function esploratore(contenitore, {alla_scelta, inizio = ""}) {
  let corrente = null, filtro = "";
  contenitore.innerHTML = `<div class="esploratore">
    <div class="briciole" aria-label="Percorso"></div>
    <div class="filtro-cartelle"><label class="sr" for="filtroC">Filtra le cartelle</label><input id="filtroC" class="testo" placeholder="Filtra, es. G10 o 1102" autocomplete="off"></div>
    <div class="cartelle" role="list"></div>
    <div class="scelta nascosto"></div></div>`;
  const brici = $(".briciole", contenitore), lista = $(".cartelle", contenitore), scelta = $(".scelta", contenitore), inp = $("#filtroC", contenitore);
  inp.oninput = () => { filtro = inp.value.toLowerCase(); disegna(); };
  inp.onkeydown = e => { if (e.key === "Enter") { const b = $("button[data-c]", lista); b?.click(); } if (e.key === "ArrowDown") { e.preventDefault(); $("button", lista)?.focus(); } };
  lista.onkeydown = e => {
    const bs = $$("button", lista), i = bs.indexOf(document.activeElement);
    if (e.key === "ArrowDown" && i < bs.length - 1) { e.preventDefault(); bs[i + 1].focus(); }
    if (e.key === "ArrowUp") { e.preventDefault(); i > 0 ? bs[i - 1].focus() : inp.focus(); }
    if (e.key === "Backspace" && corrente?.su) { e.preventDefault(); apri(corrente.su); }
  };
  async function apri(p) {
    lista.innerHTML = `<div class="vuoto">Apro la cartella su MEGA…</div>`; scelta.classList.add("nascosto");
    try { corrente = await api("/api/sfoglia", {percorso: p}); }
    catch (e) { lista.innerHTML = `<div class="vuoto">${esc(e.message)}</div>`; return; }
    filtro = ""; inp.value = ""; disegna(); inp.focus();
  }
  function disegna() {
    const r = corrente; if (!r) return;
    const parti = r.percorso.split("/").filter(Boolean);
    brici.innerHTML = parti.map((p, i) => i === parti.length - 1 ? `<span class="qui">${esc(p)}</span>`
      : `<button type="button" data-p="/${esc(parti.slice(0, i + 1).join("/"))}">${esc(p)}</button><span class="sep">›</span>`).join("");
    $$("button", brici).forEach(b => b.onclick = () => apri(b.dataset.p));
    const ord = [...r.cartelle].sort((a, b) => (b === "Foto") - (a === "Foto") || b.localeCompare(a, "it", {numeric: true}));
    const vis = ord.filter(c => c.toLowerCase().includes(filtro));
    lista.innerHTML = (r.su ? `<button type="button" data-su="1">${ICONA.cartella}<span>Cartella superiore</span></button>` : "") +
      (vis.length ? vis.map(c => `<button type="button" role="listitem" data-c="${esc(c)}" class="${c === "Foto" ? "consigliata" : ""}">${ICONA.cartella}<span>${esc(c)}</span></button>`).join("")
        : `<div class="vuoto">${filtro ? "Nessuna cartella con questo nome." : r.foto ? "Nessuna sottocartella: le foto sono qui." : "Cartella vuota."}</div>`);
    $$("button", lista).forEach(b => b.onclick = () => b.dataset.su ? apri(r.su) : apri(r.percorso.replace(/\/$/, "") + "/" + b.dataset.c));
    if (r.selezionabile) {
      scelta.classList.remove("nascosto");
      scelta.innerHTML = `<span><b>${r.foto ? r.foto + " foto qui" : "Cartella delle foto"}</b>${r.cartelle.length ? ` e ${r.cartelle.length} sottocartelle (dei fotografi): le leggo tutte` : ""}.</span>
        <button type="button" class="btn primo">Usa questa cartella</button>`;
      $("button", scelta).onclick = () => alla_scelta(r.percorso);
    } else {
      scelta.classList.add("nascosto");
      if (parti.length <= 1) lista.insertAdjacentHTML("afterbegin", `<div class="vuoto">Partite: apri <b>MATCH</b>, poi la competizione, la partita e la cartella <b>Foto</b>. Allenamenti: apri <b>ALLENAMENTI</b>, poi il mese e il giorno.</div>`);
      else if (r.cartelle.includes("Foto")) lista.insertAdjacentHTML("afterbegin", `<div class="vuoto">Apri la cartella <b>Foto</b> per sceglierla.</div>`);
    }
  }
  apri(inizio);
  return {apri};
}

/* ================================================================ vista: Inizio */
V.home = {
  titolo: "Inizio",
  mostra(el) { this.el = el; this.chiave = ""; el.innerHTML = `<p class="tenue">Carico…</p>`; },
  aggiorna(s) {
    const pend = s.lavori.filter(l => !l.copiato && !l.prova);
    const chiave = JSON.stringify([s.pronto, s.preparazione, s.persone, pend.map(l => l.id), s.regola, s.attivita.in_corso && s.attivita.tipo]);
    if (chiave === this.chiave) return; this.chiave = chiave;
    const el = this.el;
    if (!s.pronto) {
      el.innerHTML = `<h1>Prima configurazione</h1><p class="tenue" style="margin-top:8px">Quattro passaggi, da fare una volta sola su questo computer. Ogni passo si spunta da solo quando è fatto.</p>
        <div class="blocco" style="margin-top:20px" id="prep">${vistaPreparazione(s)}</div>
        <p class="tenue piccolo" style="margin-top:14px">Qualcosa non va? <a href="#/aiuto/problemi">Soluzioni ai problemi più comuni</a>.</p>`;
      collegaAzioniPrep($("#prep", el));
      return;
    }
    const deb = s.persone.deboli;
    el.innerHTML = `<div class="benvenuto">
      <section class="lancio"><img class="scudo" src="/web/scudetto.png" alt="" aria-hidden="true">
        <h1>Nuove foto da smistare?</h1>
        <p style="margin-top:12px">Scegli la cartella di una partita o di un allenamento su MEGA. Smista Foto riconosce giocatori e staff e ti propone dove copiare ogni foto. Non copia niente finché non confermi.</p>
        <div class="riga-btn"><a class="btn primo grande" href="#/smista">Smista una cartella</a></div>
      </section>
      <section class="cifre" aria-label="Situazione">
        <div><span class="numero">${s.persone.giocatori}</span><small>giocatori riconoscibili</small></div>
        <div><span class="numero">${s.persone.staff}</span><small>persone dello staff</small></div>
        <div><span class="numero">${pend.length}</span><small>revisioni da completare</small>${pend.length ? `<a href="#/storico">Vedi</a>` : ""}</div>
        <div><span class="numero" style="color:${deb.length ? "var(--giallo-t)" : "inherit"}">${deb.length}</span><small>da riconoscere meglio ${q("debole")}</small>${deb.length ? `<a href="#/volti">Aggiungi primi piani</a>` : ""}</div>
      </section></div>
      ${pend.length ? `<section class="sezione"><div class="intesta"><h2>Da rivedere</h2><span class="tenue">analisi finite, foto non ancora copiate</span></div>
        <div class="blocco" style="padding:6px 18px"><table><tbody>${pend.map(l => `<tr class="cliccabile" data-id="${esc(l.id)}">
          <td><b>${esc(l.unica ? "Allenamento " + l.evento : l.evento)}</b><br><span class="tenue piccolo">${esc(l.competizione)}</span></td>
          <td class="tab-num">${esc(l.creato)}</td><td class="tab-num">${l.foto} foto</td>
          <td>${l.da_decidere ? `<span class="chip giallo">${l.da_decidere} da verificare</span>` : `<span class="chip verde">pronta da copiare</span>`}</td>
          <td><div class="az"><a class="btn primo" href="#/revisione/${encodeURIComponent(l.id)}">Riprendi la revisione</a></div></td></tr>`).join("")}</tbody></table></div></section>` : ""}
      <section class="sezione"><div class="intesta"><h2>Come funziona</h2></div>
        <ol class="passi" style="margin-top:8px">
          <li class="attivo"><h3>Scegli la cartella</h3><div class="corpo"><p class="tenue">Quella dove hanno caricato i fotografi: <code>MATCH › … › Foto</code> oppure <code>ALLENAMENTI › mese › giorno</code>.</p></div></li>
          <li class="attivo"><h3>Lascia lavorare Smista Foto</h3><div class="corpo"><p class="tenue">Scarica e analizza una foto alla volta, solo sul computer. Puoi fare altro: ti avvisa quando ha finito.</p></div></li>
          <li class="attivo"><h3>Rivedi e copia</h3><div class="corpo"><p class="tenue">Controlli le proposte, decidi i casi dubbi, vedi il riepilogo di cosa verrà copiato e confermi.</p></div></li>
        </ol>
        <p class="tenue piccolo">Regola in uso per decidere chi è protagonista ${q("protagonista")}: ${esc(s.regola)}.</p></section>`;
    $$("tr.cliccabile", el).forEach(tr => tr.onclick = e => { if (!e.target.closest("a")) location.hash = "#/revisione/" + tr.dataset.id; });
  },
};

/* ================================================================ vista: Smista (procedura a passi) */
V.smista = {
  titolo: "Smista foto",
  mostra(el) {
    this.el = el; this.passo = 1; this.scelta = null; this.attesa = false;
    if (S && !S.pronto) {
      el.innerHTML = `<h1>Smista foto</h1><div class="avviso giallo"><b>Prima completa la configurazione.</b>Mancano alcuni passaggi, per esempio il collegamento a MEGA o l'apprendimento dei volti.</div><a class="btn primo" href="#/">Vai alla configurazione</a>`;
      return;
    }
    if (S?.attivita.in_corso && S.attivita.tipo === "smista") { this.passo = 3; }
    this.disegna();
  },
  testataPassi() {
    const nomi = ["Cartella", "Destinazione", "Analisi", "Revisione"];
    return `<ol class="stepper" aria-label="Avanzamento">${nomi.map((n, i) => {
      const k = i + 1, cl = k < this.passo ? "fatto" : k === this.passo ? "attivo" : "";
      return `<li class="${cl}" ${k === this.passo ? 'aria-current="step"' : ""}><b>${k < this.passo ? "✓" : k}</b><span>${n}</span></li>`;
    }).join("")}</ol>`;
  },
  disegna() {
    const el = this.el;
    if (this.passo === 1) {
      el.innerHTML = `${this.testataPassi()}<h1>Quale cartella vuoi smistare?</h1>
        <p class="tenue" style="margin-top:8px">Scegli la cartella dove hanno caricato i fotografi. Su MEGA, in questa fase, Smista Foto legge soltanto.</p>
        <div id="esp" style="margin-top:18px"></div>
        <details class="cassetto"><summary>Ho il percorso copiato da MEGA</summary><div class="dentro-cassetto">
          <div class="campo"><label for="incolla">Percorso della cartella</label><input id="incolla" placeholder="Cloud drive > 2026-27 > MATCH > SERIEBKT > G10_Sudtirol_Cesena_1_1 > Foto">
          <span class="aiuto-campo">Va bene anche copiato dalla barra di MEGA, con le frecce.</span></div>
          <div class="riga-btn"><button class="btn" id="bIncolla">Usa questo percorso</button></div></div></details>`;
      esploratore($("#esp", el), {alla_scelta: p => this.controlla(p)});
      $("#bIncolla", el).onclick = () => { const v = $("#incolla", el).value.trim(); if (!v) return avviso("Incolla prima il percorso.", "avviso"); this.controlla(v); };
    }
    if (this.passo === 2) this.disegnaDestinazione();
    if (this.passo === 3) this.disegnaAnalisi();
  },
  async controlla(percorso) {
    try { this.scelta = await api("/api/controlla", {percorso, prova: false}); }
    catch (e) { return errore(e); }
    this.passo = 2; this.disegna();
  },
  disegnaDestinazione() {
    const c = this.scelta, el = this.el;
    const gia = (S?.lavori || []).filter(l => l.sorgente === c.sorgente && !l.prova);
    el.innerHTML = `${this.testataPassi()}<h1>${c.unica ? "Allenamento" : "Partita"}: controlla la destinazione</h1>
      ${gia.length ? `<div class="avviso giallo"><b>Questa cartella è già stata analizzata il ${esc(gia[0].creato)}.</b>${gia[0].copiato ? "Le foto sono già state copiate: rifarlo non crea doppioni (le foto già presenti vengono saltate)." : "Quella revisione non è ancora finita: puoi riprenderla invece di rifare l'analisi."}
        ${gia[0].copiato ? "" : `<div class="riga-btn"><a class="btn primo" href="#/revisione/${encodeURIComponent(gia[0].id)}">Riprendi quella revisione</a></div>`}</div>` : ""}
      <div class="blocco" style="margin-top:18px"><dl class="tratta">
        <dt>Da</dt><dd><span class="percorso">${esc(c.sorgente)}</span></dd>
        <dt>A</dt><dd><span class="percorso" id="dest"></span><div class="tenue piccolo" style="margin-top:6px">Una cartella per ogni persona riconosciuta. ${c.unica ? `Negli allenamenti tutte le foto stanno nella stessa cartella, quindi metto la data davanti al nome del file ${q("data")}.` : "La cartella della partita viene creata se non c'è."}</div></dd>
      </dl>
      <div class="griglia-campi" style="margin-top:18px">
        <div class="campo"><label for="fComp">${c.unica ? "Cartella" : "Competizione"}</label><input id="fComp" value="${esc(c.competizione)}" ${c.unica ? "readonly" : ""} autocomplete="off">
          <span class="aiuto-campo">${c.unica ? "Cartella unica per tutti gli allenamenti." : "Come la cartella nelle cartelle dei giocatori, es. SERIE BKT."}</span><span class="errore-campo" id="eComp"></span></div>
        <div class="campo"><label for="fEv">${c.unica ? "Data dell'allenamento" : "Nome della partita"}</label><input id="fEv" value="${esc(c.evento)}" autocomplete="off" ${c.unica ? 'inputmode="numeric" placeholder="es. 20261102"' : 'placeholder="es. G10_SUDTIROL_CESENA"'}>
          <span class="aiuto-campo">${c.unica ? "Anno, mese, giorno attaccati: 20261102." : "Maiuscolo, senza risultato. Viene ricavato dal nome della cartella."}</span><span class="errore-campo" id="eEv"></span></div>
      </div></div>
      <div class="riga-btn" style="margin-top:20px"><button class="btn" id="bIndietro">Cambia cartella</button><button class="btn primo grande" id="bAvvia">Avvia l'analisi</button></div>
      <p class="tenue piccolo" style="margin-top:10px">L'analisi non copia nulla: alla fine rivedi tutto e confermi tu.</p>`;
    const fC = $("#fComp", el), fE = $("#fEv", el);
    const valida = () => {
      const comp = fC.value.trim().toUpperCase(), ev = fE.value.trim().toUpperCase();
      let ok = true;
      $("#eComp", el).textContent = comp ? "" : "Serve il nome della competizione.";
      fC.setAttribute("aria-invalid", !comp); ok = ok && !!comp;
      let msg = "";
      if (!ev) msg = c.unica ? "Serve la data dell'allenamento." : "Serve il nome della partita.";
      else if (c.unica && !/^20\d{6}$/.test(ev)) msg = "Scrivi la data come 20261102 (anno, mese, giorno).";
      else if (!c.unica && /[\/\\*?]/.test(ev)) msg = "Il nome non può contenere / \\ * ?";
      $("#eEv", el).textContent = msg; fE.setAttribute("aria-invalid", !!msg); ok = ok && !msg;
      $("#dest", el).textContent = c.unica ? `PLAYERS / <persona> / ${comp || "?"}   (es. ${ev || "DATA"}_IMG_1234.jpg)` : `PLAYERS / <persona> / ${comp || "?"} / ${ev || "?"}`;
      $("#bAvvia", el).disabled = !ok;
      return ok;
    };
    fC.oninput = fE.oninput = valida; valida();
    if (!c.competizione) avviso("Non riconosco competizione e partita dal percorso: scrivile nei due campi.", "avviso");
    $("#bIndietro", el).onclick = () => { this.passo = 1; this.disegna(); };
    $("#bAvvia", el).onclick = async () => {
      if (!valida()) return;
      try {
        chiediNotifiche();
        await api("/api/smista", {sorgente: c.sorgente, competizione: fC.value, evento: fE.value});
        this.passo = 3; this.disegna();
      } catch (e) { errore(e); }
    };
  },
  disegnaAnalisi() {
    this.el.innerHTML = `${this.testataPassi()}<h1>Analisi in corso</h1>
      <p class="tenue" style="margin-top:8px">Scarico e analizzo una foto alla volta. Le foto restano sul computer solo il tempo dell'analisi. Puoi chiudere questa pagina o usare il computer per altro: ti avviso quando ho finito.</p>
      <div class="blocco" style="margin-top:18px"><h3 id="anFase">Preparo</h3><div class="progresso" id="anProg" style="margin:14px 0 8px"><i></i></div>
        <div class="tenue tab-num" id="anDet"></div></div>`;
  },
  aggiorna(s) {
    if (this.passo !== 3 || !this.el) return;
    const a = s.attivita, r = s.registro;
    if (a.in_corso && a.tipo === "smista") {
      $("#anFase", this.el).textContent = r.fase || "Al lavoro";
      $("#anProg i", this.el).style.width = r.n ? (100 * r.i / r.n) + "%" : "5%";
      const eta = r.n && r.i > 2 ? " · circa " + durata(r.secondi_fase / r.i * (r.n - r.i)) + " alla fine" : "";
      $("#anDet", this.el).textContent = (r.n ? `${r.i} di ${r.n}` : "") + eta + (r.dettaglio ? " · " + r.dettaglio : "");
    } else if (!a.in_corso && a.tipo === "smista") {
      if (a.errore) { this.el.innerHTML = `${this.testataPassi()}<h1>Analisi interrotta</h1><div class="avviso rosso"><b>Che cosa è successo</b>${esc(a.errore)}</div><div class="riga-btn"><button class="btn primo" id="bRiprova">Torna alla scelta della cartella</button><a class="btn" href="#/aiuto/problemi">Soluzioni ai problemi</a></div>`; $("#bRiprova", this.el).onclick = () => { this.passo = 1; this.disegna(); }; this.passo = 0; }
      else if (a.lavoro) { this.passo = 4; location.hash = "#/revisione/" + a.lavoro; }
    }
  },
};

/* ================================================================ vista: Revisioni (storico) */
V.storico = {
  titolo: "Revisioni",
  mostra(el) { this.el = el; this.chiave = ""; this.filtro = memo("filtroStorico") || "tutte"; },
  aggiorna(s) {
    const k = JSON.stringify([s.lavori.map(l => [l.id, l.copiato, !!l.prova, l.da_decidere]), this.filtro]); if (k === this.chiave) return; this.chiave = k;
    const filtri = {tutte: "Tutte", aperte: "Da completare", copiate: "Copiate", prove: "Prove"};
    const L = s.lavori.filter(l => this.filtro === "tutte" || (this.filtro === "aperte" && !l.copiato && !l.prova) || (this.filtro === "copiate" && l.copiato) || (this.filtro === "prove" && l.prova));
    this.el.innerHTML = `<div class="intesta"><h1>Revisioni</h1><a class="btn primo dx" href="#/smista">Smista una cartella</a></div>
      <div class="riga-btn" role="group" aria-label="Filtro">${Object.entries(filtri).map(([k, v]) => `<button class="btn ${this.filtro === k ? "primo" : ""}" data-f="${k}" aria-pressed="${this.filtro === k}">${v}</button>`).join("")}</div>
      ${L.length ? `<div class="blocco" style="margin-top:16px;padding:6px 18px"><table><thead><tr><th>Cartella</th><th>Analizzata</th><th>Foto</th><th>Stato</th><th></th></tr></thead><tbody>${L.map(l => {
        const st = l.prova ? `<span class="chip senza">Prova: ${l.prova.precisione}% di precisione</span>` : l.copiato ? `<span class="chip verde">Copiata</span>` : l.da_decidere ? `<span class="chip giallo">${l.da_decidere} da verificare</span>` : `<span class="chip giallo">Da confermare</span>`;
        return `<tr class="cliccabile" data-id="${esc(l.id)}"><td><b>${esc(l.unica ? "Allenamento " + l.evento : l.evento)}</b><br><span class="tenue piccolo">${esc(l.competizione)}</span></td><td class="tab-num">${esc(l.creato)}</td><td class="tab-num">${l.foto}</td><td>${st}</td><td><div class="az"><a class="btn ${!l.copiato && !l.prova ? "primo" : ""}" href="#/revisione/${encodeURIComponent(l.id)}">${!l.copiato && !l.prova ? "Riprendi" : "Apri"}</a></div></td></tr>`;
      }).join("")}</tbody></table></div>` : `<div class="blocco" style="margin-top:16px"><h3>Niente da mostrare</h3><p class="tenue">Le analisi compaiono qui dopo che hai smistato una cartella.</p><a class="btn primo" href="#/smista">Smista una cartella</a></div>`}`;
    $$("[data-f]", this.el).forEach(b => b.onclick = () => { this.filtro = b.dataset.f; memo("filtroStorico", this.filtro); this.aggiorna(S); });
    $$("tr.cliccabile", this.el).forEach(tr => tr.onclick = e => { if (!e.target.closest("a")) location.hash = "#/revisione/" + tr.dataset.id; });
  },
};

/* ================================================================ vista: Giocatori e staff */
V.volti = {
  titolo: "Giocatori e staff",
  mostra(el) { this.el = el; this.chiave = ""; this.filtro = "tutti"; this.cerca = ""; },
  aggiorna(s) {
    const occ = s.attivita.in_corso || !s.pronto && !s.preparazione.slice(0, 3).every(p => p.fatto);
    const k = JSON.stringify([s.elenco, s.esclusi, occ, this.filtro]); if (k === this.chiave) return; this.chiave = k;
    const el = this.el;
    el.innerHTML = `<div class="intesta"><h1>Giocatori e staff</h1><div class="dx riga-btn" style="margin-top:0">
        <button class="btn primo" id="bImpara" ${occ ? "disabled" : ""}>Impara i volti nuovi</button>
        <button class="btn" id="bReimpara" ${occ ? "disabled" : ""}>Reimpara tutti</button></div></div>
      <p class="tenue" style="margin-top:8px">Le persone sono le cartelle in <code>PLAYERS</code> e <code>PLAYERS/_STAFF</code>. Quando arriva qualcuno di nuovo, crea la sua cartella su MEGA come sempre, mettici qualche foto e premi «Impara i volti nuovi».</p>
      ${s.persone.deboli.length ? `<div class="avviso giallo"><b>${s.persone.deboli.length} persone sono difficili da riconoscere</b>Hanno poche foto utili nella loro cartella. Aggiungi 3-5 primi piani in cui si vede bene il volto: trascinali sulla riga della persona o usa «Aggiungi primi piani». Restano solo su questo computer.</div>` : ""}
      <div class="barra-strumenti" style="top:57px"><label class="sr" for="cercaP">Cerca</label><input id="cercaP" class="testo" placeholder="Cerca un nome" value="${esc(this.cerca)}">
        ${["tutti", "deboli", "giocatore", "staff"].map(f => `<button class="btn ${this.filtro === f ? "primo" : ""}" data-f="${f}" aria-pressed="${this.filtro === f}">${{tutti: "Tutti", deboli: "Da migliorare", giocatore: "Giocatori", staff: "Staff"}[f]}</button>`).join("")}</div>
      <div class="blocco" style="padding:6px 18px;margin-top:12px"><table><thead><tr><th>Nome</th><th>Foto utili ${q("debole")}</th><th>Primi piani</th><th></th></tr></thead><tbody id="righeP"></tbody></table></div>
      ${s.esclusi.length ? `<section class="sezione"><h3>Cartelle escluse</h3><p class="tenue">Non sono persone (es. 00VARIE): Smista Foto le ignora. Su MEGA non cambia nulla.</p><div class="riga-btn">${s.esclusi.map(n => `<span class="chip senza">${esc(n)}</span><button class="btn piatto" data-in="${esc(n)}" ${occ ? "disabled" : ""}>Includi di nuovo</button>`).join("")}</div></section>` : ""}`;
    const disegnaRighe = () => {
      const c = this.cerca.toLowerCase();
      const R = s.elenco.filter(p => (this.filtro === "tutti" || (this.filtro === "deboli" && p.foto < 4) || p.tipo === this.filtro) && p.nome.toLowerCase().includes(c));
      $("#righeP", el).innerHTML = R.length ? R.map(p => `<tr data-n="${esc(p.nome)}">
        <td><b>${esc(p.nome)}</b><br><span class="tenue piccolo">${p.tipo === "staff" ? "staff" : "giocatore"}</span></td>
        <td>${p.foto < 4 ? `<span class="chip giallo">${p.foto} · da migliorare</span>` : `<span class="chip verde">${p.foto}</span>`}</td>
        <td class="tab-num">${p.primi_piani || "—"}</td>
        <td><div class="az"><input type="file" accept="image/jpeg,image/png,image/webp" multiple hidden data-pp="${esc(p.nome)}">
          <button class="btn" data-sfoglia ${occ ? "disabled" : ""}>Aggiungi primi piani</button>
          ${p.primi_piani ? `<button class="btn" data-re="${esc(p.nome)}" ${occ ? "disabled" : ""}>Reimpara</button>` : ""}
          <button class="btn piatto" data-ex="${esc(p.nome)}" ${occ ? "disabled" : ""}>Non è una persona</button></div></td></tr>`).join("")
        : `<tr><td colspan="4" class="tenue">Nessuna persona con questi criteri.</td></tr>`;
    };
    disegnaRighe();
    $("#cercaP", el).oninput = e => { this.cerca = e.target.value; disegnaRighe(); };
    $$("[data-f]", el).forEach(b => b.onclick = () => { this.filtro = b.dataset.f; this.chiave = ""; this.aggiorna(S); });
    $("#bImpara", el).onclick = () => api("/api/impara", {tutti: false}).then(() => { chiediNotifiche(); avviso("Imparo i volti nuovi: l'avanzamento è in basso.", "info"); }).catch(errore);
    $("#bReimpara", el).onclick = async () => { if (await conferma("Reimparare tutti i volti?", "Rifà l'apprendimento di tutte le persone da zero: 10-20 minuti. Serve solo se il riconoscimento è peggiorato.", "Reimpara tutti")) api("/api/impara", {tutti: true}).catch(errore); };
    const carica = async (nome, files) => {
      let ok = 0;
      for (const f of files) {
        if (!/\.(jpe?g|png|webp)$/i.test(f.name)) { avviso(`${f.name}: servono foto JPG, PNG o WEBP.`, "avviso"); continue; }
        const r = await fetch(`/api/primopiano?persona=${encodeURIComponent(nome)}&nome=${encodeURIComponent(f.name)}`, {method: "POST", body: f});
        if (r.ok) ok++; else errore(new Error((await r.json()).errore));
      }
      if (ok && await conferma(`${ok} primi piani aggiunti per ${nome}`, "Li uso subito per migliorare il riconoscimento? Ci vuole meno di un minuto.", "Sì, reimpara " + nome)) api("/api/impara", {solo: [nome]}).catch(errore);
    };
    el.onclick = async e => {
      const b = e.target.closest("button"); if (!b || b.disabled) return;
      if (b.hasAttribute("data-sfoglia")) b.previousElementSibling.click();
      if (b.dataset.re) api("/api/impara", {solo: [b.dataset.re]}).catch(errore);
      if (b.dataset.ex && await conferma(`${b.dataset.ex} non è una persona?`, "Smista Foto la ignorerà (succede con cartelle come 00VARIE). Su MEGA non cambia nulla e puoi includerla di nuovo quando vuoi.", "Escludi")) api("/api/escludi", {nome: b.dataset.ex, escluso: true}).catch(errore);
      if (b.dataset.in) api("/api/escludi", {nome: b.dataset.in, escluso: false}).then(() => avviso("Inclusa di nuovo: premi «Impara i volti nuovi» per impararla.", "info")).catch(errore);
    };
    el.onchange = e => { const i = e.target.closest("[data-pp]"); if (i?.files.length) carica(i.dataset.pp, [...i.files]); };
    el.ondragover = e => { const tr = e.target.closest("tr[data-n]"); if (tr && !occ) { e.preventDefault(); tr.style.outline = "3px dashed var(--prato)"; } };
    el.ondragleave = e => { const tr = e.target.closest("tr[data-n]"); if (tr) tr.style.outline = ""; };
    el.ondrop = e => { const tr = e.target.closest("tr[data-n]"); if (!tr) return; e.preventDefault(); tr.style.outline = ""; carica(tr.dataset.n, [...e.dataTransfer.files]); };
  },
};

/* ================================================================ vista: Prove e regole (per chi configura) */
V.strumenti = {
  titolo: "Prove e regole",
  mostra(el) { this.el = el; this.chiave = ""; this.scelta = null; this.risultato = null; },
  aggiorna(s) {
    const a = s.attivita;
    if (!a.in_corso && (a.tipo === "prova" || a.tipo === "calibra") && a.risultato) this.risultato = {tipo: a.tipo, ...a.risultato};
    const prove = s.lavori.filter(l => l.prova);
    const nProve = new Set(prove.map(l => l.sorgente)).size;
    const k = JSON.stringify([prove.map(l => l.id), this.scelta, !!this.risultato, a.in_corso, s.regola, s.pronto]); if (k === this.chiave) return; this.chiave = k;
    const el = this.el;
    el.innerHTML = `<h1>Prove e regole</h1>
      <p class="tenue" style="margin-top:8px">Strumenti per chi configura Smista Foto. Una prova analizza foto <b>già smistate a mano</b> e confronta il risultato con il vostro lavoro, senza copiare nulla. Da più prove si sceglie la regola che decide chi è protagonista ${q("protagonista")}.</p>
      <div class="avviso info"><b>Regola in uso</b>${esc(s.regola)}</div>
      <section class="sezione"><h2>Nuova prova</h2>
        <div class="blocco">${this.scelta ? `<dl class="tratta"><dt>Cartella</dt><dd><span class="percorso">${esc(this.scelta.sorgente)}</span></dd></dl>
          ${this.scelta.unica ? `<p class="tenue" style="margin-top:10px">Confronto con le foto di questo allenamento già presenti nelle cartelle ALLENAMENTI.</p>` : `<div class="campo" style="margin-top:12px;max-width:440px"><label for="fEs">Cartella della partita nelle cartelle dei giocatori</label><input id="fEs" value="${esc(this.scelta.esistente)}"><span class="aiuto-campo">Trovata da sola quando possibile, es. G10_SUDTIROL_CESENA.</span></div>`}
          <div class="riga-btn"><button class="btn" id="bCambia">Cambia cartella</button><button class="btn primo" id="bProva" ${a.in_corso ? "disabled" : ""}>Fai la prova</button></div>`
        : `<div id="espP"></div>`}</div></section>
      <section class="sezione"><div class="intesta"><h2>Risultati</h2>
        ${nProve >= 2 ? `<button class="btn primo dx" id="bCalibra" ${a.in_corso ? "disabled" : ""}>Calcola la regola su tutte le prove (${nProve} cartelle)</button>` : ""}</div>
        ${nProve < 2 ? `<p class="tenue">Con prove su almeno due cartelle diverse potrai calcolare una regola che va bene per tutte.</p>` : ""}
        <div id="ris"></div>
        ${prove.length ? `<div class="blocco" style="padding:6px 18px;margin-top:14px"><table><thead><tr><th>Prova</th><th>Data</th><th>Precisione ${q("precisione")}</th><th>Lavoro trovato</th><th></th></tr></thead><tbody>${prove.map(l => `<tr><td><b>${esc(l.evento)}</b><br><span class="tenue piccolo">${esc(l.competizione)}</span></td><td class="tab-num">${esc(l.creato)}</td><td class="tab-num">${l.prova.precisione}%</td><td class="tab-num">${l.prova.copertura}%</td><td><div class="az"><a class="btn" href="#/revisione/${encodeURIComponent(l.id)}">Vedi i volti</a></div></td></tr>`).join("")}</tbody></table></div>` : ""}
      </section>`;
    if (!this.scelta) esploratore($("#espP", el), {alla_scelta: async p => { try { this.scelta = await api("/api/controlla", {percorso: p, prova: true}); this.chiave = ""; this.aggiorna(S); } catch (e) { errore(e); } }});
    else {
      $("#bCambia", el).onclick = () => { this.scelta = null; this.chiave = ""; this.aggiorna(S); };
      $("#bProva", el).onclick = async () => {
        const c = this.scelta, es = c.unica ? c.competizione : $("#fEs", el).value.trim();
        if (!es) return avviso("Scrivi la cartella della partita già smistata a mano.", "avviso");
        try { chiediNotifiche(); await api("/api/prova", {sorgente: c.sorgente, competizione: c.competizione, evento: c.evento || "PROVA", esistente: es}); avviso("Prova avviata: l'avanzamento è in basso.", "info"); } catch (e) { errore(e); }
      };
    }
    $("#bCalibra", el)?.addEventListener("click", () => api("/api/calibra", {}).catch(errore));
    if (this.risultato) $("#ris", el).append(tabellaRegole(this.risultato));
  },
};
function tabellaRegole(r) {
  const box = document.createElement("div");
  const numeri = r.tipo === "prova" ? `<div class="riassunto"><div class="verde"><span class="numero">${r.precisione}%</span><small>precisione</small></div><div><span class="numero">${r.copertura}%</span><small>del lavoro a mano trovato da solo</small></div><div class="rosso"><span class="numero">${r.sbagliate}</span><small>proposte non coincidenti</small></div><div><span class="numero">${r.mancate}</span><small>mancate del tutto</small></div></div>` : `<p>Regole calcolate su: ${r.partite.map(esc).join(", ")}.</p>`;
  box.className = "blocco";
  box.innerHTML = `<h3>${r.tipo === "prova" ? "Ultima prova" : "Regole su più cartelle"}</h3>${numeri}
    ${(r.regole || []).length ? `<h3 style="margin-top:16px">Regole proposte</h3><p class="tenue">Dall'alto in basso: trovano meno foto ma sbagliano meno. «Usa questa» vale dalla prossima analisi.</p>
    <table><thead><tr><th>Regola</th><th>Proposte</th><th>Precisione</th><th>Lavoro trovato</th><th></th></tr></thead><tbody>${r.regole.map((x, i) => `<tr><td>${x.attuale ? "<b>In uso</b><br>" : ""}${esc(x.descrizione)}${(x.per_partita || []).length ? `<br><span class="tenue piccolo">${x.per_partita.map(p => `${esc(p.partita)}: ${p.precisione}% / ${p.copertura}%`).join("; ")}</span>` : ""}</td><td class="tab-num">${x.proposte}</td><td class="tab-num">${x.precisione}%</td><td class="tab-num">${x.copertura}%</td><td>${x.attuale ? "" : `<button class="btn" data-r="${i}">Usa questa</button>`}</td></tr>`).join("")}</tbody></table>` : ""}`;
  $$("[data-r]", box).forEach(b => b.onclick = async () => {
    const x = r.regole[+b.dataset.r];
    if (!await conferma("Usare questa regola?", `${esc(x.descrizione)}.<br><br>Vale dalla prossima analisi, su questo computer.`, "Usa questa regola")) return;
    try { await api("/api/regola", x); avviso("Regola salvata.", "ok"); b.textContent = "In uso"; b.disabled = true; } catch (e) { errore(e); }
  });
  return box;
}

/* ================================================================ avvio */
window.addEventListener("load", () => {
  naviga();
  aggiornaStato();
  setInterval(aggiornaStato, 1000);
});
