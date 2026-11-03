/* Smista Foto: vista di revisione di un'analisi. */
"use strict";

V.revisione = {
  titolo: "Revisione",
  nav: "storico",
  async mostra(el, [id]) {
    this.el = el; this.id = id; this.D = null; this.annulla = [];
    el.innerHTML = `<p class="tenue">Carico la revisione…</p>`;
    try { this.D = await api("/api/lavoro/" + encodeURIComponent(id)); }
    catch (e) { el.innerHTML = `<h1>Revisione non trovata</h1><p class="tenue">${esc(e.message)}</p><a class="btn primo" href="#/storico">Vai alle revisioni</a>`; return; }
    const salvate = memo("rev:" + id) || {};
    this.scelte = {
      escluse: new Set(salvate.escluse || []),      // volti riconosciuti da NON copiare
      dubbi: salvate.dubbi || {},                   // id volto -> persona, "" = non copiare
      recuperate: new Set(salvate.recuperate || []),// comparse da copiare comunque
      nessuno: salvate.nessuno || {},               // id foto -> persona (foto senza volti)
    };
    this.solo_no = false; this.cerca = "";
    this.prepara(); this.disegna();
    this.tasti = e => this.tastiera(e);
    document.addEventListener("keydown", this.tasti);
    if (salvate.escluse || salvate.dubbi) avviso("Ho ripreso le scelte che avevi fatto su questa revisione.", "info");
  },
  esci() { if (this.tasti) document.removeEventListener("keydown", this.tasti); this.chiudiAnteprima?.(); },
  salva() {
    if (this.D.copiato || this.D.prova) return;
    const s = this.scelte;
    memo("rev:" + this.id, {escluse: [...s.escluse], dubbi: s.dubbi, recuperate: [...s.recuperate], nessuno: s.nessuno});
  },
  prepara() {
    const D = this.D;
    this.fotoPer = Object.fromEntries(D.foto.map(f => [f.id, f]));
    this.persone = Object.keys(D.persone).sort((a, b) => (D.persone[a] > D.persone[b]) - (D.persone[a] < D.persone[b]) || a.localeCompare(b));
    this.sicure = D.volti.filter(v => v.stato === "sicuro");
    this.dubbi = D.volti.filter(v => v.stato === "dubbio");
    this.comparse = D.volti.filter(v => v.stato === "comparsa");
    const conVolti = new Set(D.volti.map(v => v.foto));
    this.vuote = D.foto.filter(f => !conVolti.has(f.id));
    this.solaLettura = D.copiato || D.prova;
  },

  /* ------------------------------------------------------------ disegno */
  disegna() {
    const D = this.D, el = this.el;
    const titolo = D.unica ? `Allenamento ${D.evento}` : D.evento;
    el.innerHTML = `<div class="intesta"><h1>${esc(titolo)}</h1>
        <span class="dx">${D.prova ? `<span class="chip senza">Prova</span>` : D.copiato ? `<span class="chip verde">Copiata</span>` : `<span class="chip giallo">Da confermare</span>`}</span></div>
      <p class="tenue" style="margin-top:6px">${esc(D.competizione)}, ${D.foto.length} foto analizzate il ${esc(D.creato)}.
        Destinazione: <code>PLAYERS / persona / ${esc(D.competizione)}${D.unica ? "" : " / " + esc(D.evento)}</code></p>
      ${D.copiato ? `<div class="avviso verde"><b>Queste foto sono già state copiate.</b>Qui puoi solo guardare. Per rifarlo, smista di nuovo la cartella: le foto già presenti vengono saltate.</div>` : ""}
      ${D.prova ? this.bannerProva() : ""}
      <div class="barra-strumenti">
        <label class="sr" for="cercaR">Cerca una persona</label><input id="cercaR" class="testo" placeholder="Cerca una persona" value="${esc(this.cerca)}">
        ${D.prova ? `<button class="btn" id="bSoloNo" aria-pressed="${this.solo_no}">${this.solo_no ? "Mostra tutti" : "Solo quelli che non coincidono"}</button>` : ""}
        <button class="btn piatto" id="bTasti">Scorciatoie da tastiera</button>
        ${!this.solaLettura ? `<button class="btn piatto" id="bAnnulla" disabled>Annulla l'ultima scelta</button>` : ""}
      </div>
      <div id="secDubbi"></div><div id="secSicure"></div><div id="secComparse"></div><div id="secVuote"></div>
      ${this.solaLettura ? "" : `<div class="piede-revisione" id="piede"><div class="riep" id="riep"></div>
        <button class="btn primo grande" id="bCopia">Controlla e copia</button></div>`}`;
    this.disegnaDubbi(); this.disegnaSicure(); this.disegnaComparse(); this.disegnaVuote(); this.riepilogo();
    $("#cercaR", el).oninput = e => { this.cerca = e.target.value.toLowerCase(); this.disegnaSicure(); this.disegnaComparse(); };
    $("#bSoloNo", el)?.addEventListener("click", () => { this.solo_no = !this.solo_no; this.disegna(); });
    $("#bTasti", el).onclick = () => this.mostraTasti();
    $("#bAnnulla", el)?.addEventListener("click", () => this.annullaUltima());
    $("#bCopia", el)?.addEventListener("click", () => this.controllaECopia());
  },
  bannerProva() {
    const n = this.D.numeri || {};
    return `<div class="avviso info"><b>Prova: niente da copiare.</b>I bordi pieni sono le foto che coincidono con lo smistamento fatto a mano, quelli tratteggiati no.
      ${n.precisione != null ? `Precisione ${n.precisione}%, lavoro trovato ${n.copertura}%.` : ""} Le regole proposte sono in <a href="#/strumenti">Prove e regole</a>.</div>`;
  },
  esito(v) { return this.D.esiti ? this.D.esiti[v.id] : null; },
  nomeFile(fid) { return this.fotoPer[fid].relativo; },

  disegnaDubbi() {
    const box = $("#secDubbi", this.el);
    let L = this.dubbi;
    if (this.solo_no) L = L.filter(v => this.esito(v) === "no");
    if (!L.length) { box.innerHTML = ""; return; }
    const decisi = L.filter(v => v.id in this.scelte.dubbi).length;
    box.innerHTML = `<section class="sezione"><div class="intesta"><h2>Da verificare</h2><span class="chip giallo tab-num">${decisi} di ${L.length} decisi</span>${q("dubbio")}
        ${!this.solaLettura && decisi < L.length ? `<button class="btn piatto dx" id="bRestanti">${L.length - decisi === 1 ? "Non copiare il restante" : "Non copiare i " + (L.length - decisi) + " restanti"}</button>` : ""}</div>
      <p class="tenue">Smista Foto non è sicuro di chi sia. Scegli il nome giusto (tasti <kbd>1</kbd> <kbd>2</kbd> <kbd>3</kbd>) oppure «Non copiare» (<kbd>0</kbd>). Clicca la foto per vederla grande.</p>
      <div class="dubbi">${L.map(v => this.cartaDubbio(v)).join("")}</div></section>`;
    $$(".dubbio", box).forEach(c => {
      const v = this.D.volti[+c.dataset.v];
      c.onclick = e => {
        if (e.target.closest(".volto")) return this.apriAnteprima("dubbi", v.id);
        const b = e.target.closest("[data-p]"); if (!b || this.solaLettura) return;
        this.decidi(v.id, b.dataset.p);
      };
      $("select", c)?.addEventListener("change", e => this.decidi(v.id, e.target.value === "__nessuno" ? "" : e.target.value));
    });
    $("#bRestanti", box)?.addEventListener("click", async () => {
      const rest = L.filter(v => !(v.id in this.scelte.dubbi));
      if (!await conferma("Non copiare i restanti?", `${rest.length} volti da verificare verranno segnati come «non copiare». Puoi sempre cambiare idea con un clic.`, "Segna come non copiare")) return;
      const prima = {...this.scelte.dubbi};
      rest.forEach(v => this.scelte.dubbi[v.id] = "");
      this.registraAnnulla(() => { this.scelte.dubbi = prima; }, "Segnati come non copiare");
      this.dopoModifica(true);
    });
  },
  cartaDubbio(v) {
    const scelto = this.scelte.dubbi[v.id];
    const opzioni = [[v.persona, v.punteggio], ...v.alternative].slice(0, 3);
    const stato = scelto === undefined ? "" : scelto === "" ? "scartato" : "deciso";
    const es = this.esito(v);
    return `<article class="dubbio ${stato}" tabindex="0" data-v="${this.D.volti.indexOf(v)}" aria-label="Volto da verificare, ${esc(this.nomeFile(v.foto))}">
      <img class="volto" src="/l/${encodeURIComponent(this.id)}/m/${v.mini}" alt="Volto da verificare" loading="lazy">
      <div class="info"><span class="file" title="${esc(this.nomeFile(v.foto))}">${esc(this.nomeFile(v.foto))}${es ? (es === "ok" ? " · c'è anche a mano" : " · non c'è a mano") : ""}</span>
        ${v.solo_nome ? `<span class="piccolo" style="color:var(--giallo-t)">Volto non riconosciuto: il nome viene dal nome del file, controlla.</span>` : ""}
        ${opzioni.map(([n, s], i) => `<button type="button" class="scelta-nome" data-p="${esc(n)}" aria-pressed="${scelto === n}" ${this.solaLettura ? "disabled" : ""}><kbd>${i + 1}</kbd>${esc(n)}<span class="perc">${v.solo_nome ? "nome del file" : Math.round(s * 100) + "%"}</span></button>`).join("")}
        <button type="button" class="scelta-nome nessuno" data-p="" aria-pressed="${scelto === ""}" ${this.solaLettura ? "disabled" : ""}><kbd>0</kbd>Non copiare</button>
        ${this.solaLettura ? "" : `<label class="sr" for="sel${v.id}">Un'altra persona</label><select id="sel${v.id}" class="testo" style="border:1px solid var(--linea);border-radius:4px;padding:6px">
          <option value="">Un'altra persona…</option>${this.persone.map(p => `<option value="${esc(p)}" ${scelto === p && !opzioni.some(o => o[0] === p) ? "selected" : ""}>${esc(p)}${this.D.persone[p] === "staff" ? " (staff)" : ""}</option>`).join("")}</select>`}
      </div></article>`;
  },
  decidi(idVolto, persona) {
    const prima = this.scelte.dubbi[idVolto];
    this.scelte.dubbi[idVolto] = persona;
    this.registraAnnulla(() => { if (prima === undefined) delete this.scelte.dubbi[idVolto]; else this.scelte.dubbi[idVolto] = prima; });
    const att = document.activeElement?.closest?.(".dubbio");
    this.dopoModifica(true);
    // passa da solo al prossimo volto da decidere: si lavora tutto da tastiera
    if (att) {
      const carte = $$(".dubbio", this.el), i = carte.findIndex(c => +c.dataset.v === +att.dataset.v);
      const prossima = carte.slice(i + 1).find(c => !(this.D.volti[+c.dataset.v].id in this.scelte.dubbi)) || carte[i];
      prossima?.focus();
    }
  },

  disegnaSicure() {
    const box = $("#secSicure", this.el);
    let L = this.sicure.filter(v => v.persona.toLowerCase().includes(this.cerca));
    if (this.solo_no) L = L.filter(v => this.esito(v) === "no");
    const per = {};
    for (const v of L) (per[v.persona] ??= []).push(v);
    const nomi = this.persone.filter(p => per[p]);
    box.innerHTML = `<section class="sezione"><div class="intesta"><h2>Riconosciute</h2><span class="chip verde tab-num">${L.length} foto, ${nomi.length} persone</span>${q("riconosciute")}</div>
      <p class="tenue">Bordo verde: verrà copiata nella cartella della persona. Clicca (o <kbd>Spazio</kbd>) per escluderla, <kbd>V</kbd> per vederla grande.</p>
      ${nomi.length ? nomi.map(p => {
        const fuori = per[p].filter(v => this.scelte.escluse.has(v.id)).length;
        return `<section class="persona" data-p="${esc(p)}"><header><h3>${esc(p)}</h3><span class="tenue piccolo">${this.D.persone[p] === "staff" ? "staff" : "giocatore"}</span>
          <span class="tab-num">${per[p].length - fuori} di ${per[p].length} da copiare</span>
          ${this.solaLettura ? "" : `<span class="dx"><button class="btn piatto" data-tutte="${esc(p)}">${fuori === per[p].length ? "Includi tutte" : "Escludi tutte"}</button></span>`}</header>
          <div class="provino">${per[p].map(v => this.scatto(v, "sicure")).join("")}</div></section>`;
      }).join("") : `<p class="tenue">${this.cerca ? "Nessuna persona con questo nome." : "Nessun volto riconosciuto con sicurezza."}</p>`}</section>`;
    this.collegaScatti(box);
    $$("[data-tutte]", box).forEach(b => b.onclick = () => {
      const p = b.dataset.tutte, vv = per[p], tutteFuori = vv.every(v => this.scelte.escluse.has(v.id));
      const prima = new Set(this.scelte.escluse);
      vv.forEach(v => tutteFuori ? this.scelte.escluse.delete(v.id) : this.scelte.escluse.add(v.id));
      this.registraAnnulla(() => { this.scelte.escluse = prima; }, tutteFuori ? `Incluse tutte le foto di ${p}` : `Escluse tutte le foto di ${p}`);
      this.dopoModifica();
    });
  },
  scatto(v, gruppo) {
    const fuori = gruppo === "comparse" ? !this.scelte.recuperate.has(v.id) : this.scelte.escluse.has(v.id);
    const es = this.esito(v);
    const cl = ["scatto", gruppo === "comparse" ? "comparsa" : "", gruppo === "comparse" && !fuori ? "dentro" : "", gruppo !== "comparse" && fuori ? "fuori" : "", es ? "prova-" + es : ""].join(" ");
    const stato = fuori ? (gruppo === "comparse" ? "non verrà copiata" : "esclusa") : "verrà copiata";
    return `<button type="button" class="${cl}" data-id="${v.id}" data-g="${gruppo}" aria-pressed="${!fuori}" aria-label="${esc(v.persona)}, ${esc(this.nomeFile(v.foto))}, ${stato}" title="${esc(this.nomeFile(v.foto))}" ${this.solaLettura ? 'aria-disabled="true"' : ""}>
      <img src="/l/${encodeURIComponent(this.id)}/m/${v.mini}" alt="" loading="lazy"><span class="px">${v.larghezza ? v.larghezza + " px" : ""}</span><span class="zoom" data-zoom>${ICONA.zoom}</span></button>`;
  },
  collegaScatti(box) {
    $$(".scatto", box).forEach(b => b.onclick = e => {
      const id = +b.dataset.id, g = b.dataset.g;
      if (e.target.closest("[data-zoom]") || this.solaLettura) return this.apriAnteprima(g, id);
      this.commuta(g, id);
    });
  },
  commuta(gruppo, id) {
    const insieme = gruppo === "comparse" ? this.scelte.recuperate : this.scelte.escluse;
    const presente = insieme.has(id);
    presente ? insieme.delete(id) : insieme.add(id);
    this.registraAnnulla(() => { presente ? insieme.add(id) : insieme.delete(id); });
    const fuoco = document.activeElement?.dataset?.id;
    this.dopoModifica();
    if (fuoco) $(`.scatto[data-id="${fuoco}"]`, this.el)?.focus();
  },

  disegnaComparse() {
    const box = $("#secComparse", this.el);
    let L = this.comparse.filter(v => v.persona.toLowerCase().includes(this.cerca));
    if (this.solo_no) L = L.filter(v => this.esito(v) === "no");
    if (!L.length) { box.innerHTML = ""; return; }
    const aperto = this._compAperto ? "open" : "";
    const recup = L.filter(v => this.scelte.recuperate.has(v.id)).length;
    box.innerHTML = `<details class="cassetto" ${aperto}><summary>Comparse: riconosciute ma non protagoniste (${L.length}${recup ? `, ${recup} da copiare comunque` : ""}) ${q("comparsa")}</summary><div class="dentro-cassetto">
      <p class="tenue">Persone piccole, sullo sfondo o fuori fuoco: <b>non vengono copiate</b>. Clicca una foto per copiarla comunque.</p>
      <div class="provino" style="padding:0">${L.map(v => this.scatto(v, "comparse")).join("")}</div></div></details>`;
    $("details", box).ontoggle = e => this._compAperto = e.target.open;
    this.collegaScatti(box);
  },
  disegnaVuote() {
    const box = $("#secVuote", this.el), L = this.vuote;
    if (!L.length) { box.innerHTML = ""; return; }
    const aperto = this._vuoteAperto ? "open" : "";
    box.innerHTML = `<details class="cassetto" ${aperto}><summary>Foto senza nessuno riconosciuto (${L.length})</summary><div class="dentro-cassetto">
      <p class="tenue">Campi lunghi, giocatori di spalle, pubblico, avversari. Se in una c'è un nostro giocatore, sceglilo dall'elenco.</p>
      <div class="senza-volti">${aperto ? L.map(f => `<figure><img src="/l/${encodeURIComponent(this.id)}/m/${f.anteprima}" alt="" loading="lazy" data-f="${f.id}">
        <figcaption title="${esc(f.relativo)}">${esc(f.relativo)}</figcaption>
        ${this.solaLettura ? "" : `<select class="testo" data-f="${f.id}" aria-label="Persona in questa foto" style="border:1px solid var(--linea);border-radius:4px;padding:6px;width:100%"><option value="">Non copiare</option>${this.persone.map(p => `<option value="${esc(p)}" ${this.scelte.nessuno[f.id] === p ? "selected" : ""}>${esc(p)}</option>`).join("")}</select>`}</figure>`).join("") : ""}</div></div></details>`;
    $("details", box).ontoggle = e => { this._vuoteAperto = e.target.open; if (e.target.open && !$("figure", box)) this.disegnaVuote(); };
    $$("img[data-f]", box).forEach(i => i.onclick = () => this.apriAnteprima("vuote", +i.dataset.f));
    $$("select[data-f]", box).forEach(s => s.onchange = () => {
      const f = +s.dataset.f, prima = this.scelte.nessuno[f];
      if (s.value) this.scelte.nessuno[f] = s.value; else delete this.scelte.nessuno[f];
      this.registraAnnulla(() => { if (prima) this.scelte.nessuno[f] = prima; else delete this.scelte.nessuno[f]; });
      this.dopoModifica(false, false);
    });
  },

  /* ------------------------------------------------------------ decisioni, annulla, riepilogo */
  decisioni() {
    const out = [], s = this.scelte;
    for (const v of this.sicure) if (!s.escluse.has(v.id)) out.push({foto: v.foto, persona: v.persona, volto: v.solo_nome ? null : v.id});
    for (const v of this.comparse) if (s.recuperate.has(v.id)) out.push({foto: v.foto, persona: v.persona, volto: v.id});
    for (const v of this.dubbi) {
      const p = s.dubbi[v.id];
      if (p) out.push({foto: v.foto, persona: p, volto: !v.solo_nome && (p === v.persona || v.alternative.some(a => a[0] === p)) ? v.id : null});
    }
    for (const [f, p] of Object.entries(s.nessuno)) if (p) out.push({foto: +f, persona: p});
    const visti = new Set();
    return out.filter(d => { const k = d.foto + "|" + d.persona; if (visti.has(k)) return false; visti.add(k); return true; });
  },
  riepilogo() {
    const r = $("#riep", this.el); if (!r) return;
    const d = this.decisioni(), cartelle = new Set(d.map(x => x.persona)).size;
    const nonDecisi = this.dubbi.filter(v => !(v.id in this.scelte.dubbi)).length;
    r.innerHTML = `<b class="tab-num">${d.length} foto da copiare</b> in ${cartelle} cartelle` +
      (nonDecisi ? `<br><span style="color:var(--giallo)">${nonDecisi === 1 ? "1 volto ancora da verificare: se non lo decidi, non viene copiato." : nonDecisi + " volti ancora da verificare: se non li decidi, non vengono copiati."}</span>` : "<br>Tutti i volti da verificare sono decisi.");
    $("#bCopia", this.el).disabled = !d.length;
  },
  registraAnnulla(fn, messaggio) {
    this.annulla.push(fn);
    if (this.annulla.length > 100) this.annulla.shift();
    const b = $("#bAnnulla", this.el); if (b) b.disabled = false;
    if (messaggio) avviso(messaggio + ".", "info", {azione: () => this.annullaUltima(), etichetta: "Annulla"});
  },
  annullaUltima() {
    const fn = this.annulla.pop(); if (!fn) return;
    fn(); this.dopoModifica(true);
    const b = $("#bAnnulla", this.el); if (b) b.disabled = !this.annulla.length;
  },
  dopoModifica(dubbi = false, sicure = true) {
    this.salva();
    if (dubbi) { const f = document.activeElement?.closest?.(".dubbio")?.dataset.v; this.disegnaDubbi(); if (f) $(`.dubbio[data-v="${f}"]`, this.el)?.focus(); }
    if (sicure) { this.disegnaSicure(); this.disegnaComparse(); }
    this.riepilogo();
    const b = $("#bAnnulla", this.el); if (b) b.disabled = !this.annulla.length;
  },

  /* ------------------------------------------------------------ tastiera */
  tastiera(e) {
    if (modaleAperta || this.anteprimaAperta || vistaAttiva !== this || !this.D) return;
    if (e.target.matches("input, select, textarea")) return;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); return this.annullaUltima(); }
    if (e.key === "?") { e.preventDefault(); return this.mostraTasti(); }
    const carta = document.activeElement?.closest?.(".dubbio");
    const scatto = document.activeElement?.closest?.(".scatto");
    if (carta) {
      const v = this.D.volti[+carta.dataset.v], opz = [v.persona, ...v.alternative.map(a => a[0])].slice(0, 3);
      if (/^[1-3]$/.test(e.key) && opz[+e.key - 1] && !this.solaLettura) { e.preventDefault(); this.decidi(v.id, opz[+e.key - 1]); }
      else if ((e.key === "0" || e.key.toLowerCase() === "n") && !this.solaLettura) { e.preventDefault(); this.decidi(v.id, ""); }
      else if (["ArrowDown", "ArrowRight", "j"].includes(e.key)) { e.preventDefault(); (carta.nextElementSibling || carta).focus(); }
      else if (["ArrowUp", "ArrowLeft", "k"].includes(e.key)) { e.preventDefault(); (carta.previousElementSibling || carta).focus(); }
      else if (e.key.toLowerCase() === "v" || e.key === "Enter") { e.preventDefault(); this.apriAnteprima("dubbi", v.id); }
    } else if (scatto) {
      const tutti = $$(".scatto", this.el), i = tutti.indexOf(scatto);
      if (e.key === "ArrowRight") { e.preventDefault(); tutti[i + 1]?.focus(); }
      if (e.key === "ArrowLeft") { e.preventDefault(); tutti[i - 1]?.focus(); }
      if (e.key.toLowerCase() === "v") { e.preventDefault(); this.apriAnteprima(scatto.dataset.g, +scatto.dataset.id); }
    } else if (e.key.toLowerCase() === "j" || e.key === "ArrowDown") {
      const prima = $$(".dubbio", this.el).find(c => !(this.D.volti[+c.dataset.v].id in this.scelte.dubbi)) || $(".dubbio, .scatto", this.el);
      if (prima && e.key.toLowerCase() === "j") { e.preventDefault(); prima.focus(); }
    }
  },
  mostraTasti() {
    modale({titolo: "Scorciatoie da tastiera", corpo: `<table><tbody>
      <tr><td><kbd>J</kbd> o <kbd>↓</kbd></td><td>Vai al prossimo volto da verificare</td></tr>
      <tr><td><kbd>1</kbd> <kbd>2</kbd> <kbd>3</kbd></td><td>Scegli il nome proposto e passa al successivo</td></tr>
      <tr><td><kbd>0</kbd> o <kbd>N</kbd></td><td>Non copiare questa foto</td></tr>
      <tr><td><kbd>Tab</kbd>, <kbd>←</kbd> <kbd>→</kbd></td><td>Muoviti tra le miniature</td></tr>
      <tr><td><kbd>Spazio</kbd></td><td>Escludi o includi la miniatura</td></tr>
      <tr><td><kbd>V</kbd></td><td>Vedi la foto intera, con il volto evidenziato</td></tr>
      <tr><td><kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>Z</kbd></td><td>Annulla l'ultima scelta</td></tr>
      <tr><td><kbd>Esc</kbd></td><td>Chiudi la finestra o l'anteprima</td></tr></tbody></table>
      <p class="tenue" style="margin-top:12px">Le scelte si salvano da sole: puoi chiudere e riprendere più tardi.</p>`});
  },

  /* ------------------------------------------------------------ anteprima grande */
  elencoAnteprima(gruppo) {
    if (gruppo === "vuote") return this.vuote.map(f => ({foto: f.id}));
    const L = gruppo === "dubbi" ? this.dubbi : gruppo === "comparse" ? this.comparse : this.sicure.filter(v => v.persona.toLowerCase().includes(this.cerca));
    return L.map(v => ({foto: v.foto, v}));
  },
  apriAnteprima(gruppo, id) {
    const elenco = this.elencoAnteprima(gruppo);
    let i = elenco.findIndex(x => gruppo === "vuote" ? x.foto === id : x.v.id === id);
    if (i < 0) i = 0;
    const box = document.createElement("div");
    box.className = "anteprima"; box.setAttribute("role", "dialog"); box.setAttribute("aria-modal", "true"); box.setAttribute("aria-label", "Anteprima della foto");
    document.body.append(box);
    this.anteprimaAperta = true;
    const prima = document.activeElement;
    const mostra = () => {
      const x = elenco[i], f = this.fotoPer[x.foto], v = x.v;
      let stato = "", comandi = "", colore = "";
      if (v && gruppo === "sicure") { const fuori = this.scelte.escluse.has(v.id); colore = fuori ? "rosso" : "verde"; stato = fuori ? "Esclusa: non verrà copiata" : "Verrà copiata"; comandi = this.solaLettura ? "" : `<button class="btn primo" data-a="commuta">${fuori ? "Includi" : "Escludi"} <kbd>X</kbd></button>`; }
      if (v && gruppo === "comparse") { const den = this.scelte.recuperate.has(v.id); colore = den ? "verde" : ""; stato = den ? "Comparsa: verrà copiata comunque" : "Comparsa: non verrà copiata"; comandi = this.solaLettura ? "" : `<button class="btn primo" data-a="commuta">${den ? "Non copiare" : "Copia comunque"} <kbd>X</kbd></button>`; }
      if (v && gruppo === "dubbi") {
        const sc = this.scelte.dubbi[v.id]; colore = sc ? "verde" : "";
        stato = sc === undefined ? "Da verificare" : sc === "" ? "Non verrà copiata" : "Verrà copiata a " + sc;
        comandi = this.solaLettura ? "" : [v.persona, ...v.alternative.map(a => a[0])].slice(0, 3).map((n, k) => `<button class="btn ${sc === n ? "primo" : ""}" data-scegli="${esc(n)}"><kbd>${k + 1}</kbd> ${esc(n)}</button>`).join("") + `<button class="btn ${sc === "" ? "primo" : ""}" data-scegli=""><kbd>0</kbd> Non copiare</button>`;
      }
      const b = v?.box;
      box.innerHTML = `<button class="chiudi" aria-label="Chiudi l'anteprima">✕</button>
        <div class="foto"><div class="cornice"><img src="/l/${encodeURIComponent(this.id)}/m/${f.anteprima}" alt="${esc(f.relativo)}">
          ${b ? `<div class="box ${colore}" style="left:${b[0] * 100}%;top:${b[1] * 100}%;width:${b[2] * 100}%;height:${b[3] * 100}%"></div>` : ""}</div>
          ${i > 0 ? `<button class="nav-foto prec" aria-label="Foto precedente">‹</button>` : ""}${i < elenco.length - 1 ? `<button class="nav-foto succ" aria-label="Foto successiva">›</button>` : ""}</div>
        <footer><span><b>${esc(v ? v.persona : "Nessuno riconosciuto")}</b> <span style="color:#bbb">${esc(f.relativo)} · ${i + 1} di ${elenco.length}</span><br><span style="color:#ddd">${esc(stato)}</span></span>
          <span style="margin-left:auto;display:flex;gap:8px;flex-wrap:wrap">${comandi}</span></footer>`;
      $(".chiudi", box).onclick = chiudi;
      $(".prec", box)?.addEventListener("click", () => { i--; mostra(); });
      $(".succ", box)?.addEventListener("click", () => { i++; mostra(); });
      $("[data-a=commuta]", box)?.addEventListener("click", () => { this.commuta(gruppo, v.id); mostra(); });
      $$("[data-scegli]", box).forEach(bt => bt.onclick = () => { this.decidi(v.id, bt.dataset.scegli); mostra(); });
      $(".chiudi", box).focus();
    };
    const tasti = e => {
      e.stopPropagation();
      if (e.key === "Escape") return chiudi();
      if (e.key === "ArrowRight" && i < elenco.length - 1) { i++; mostra(); }
      if (e.key === "ArrowLeft" && i > 0) { i--; mostra(); }
      const v = elenco[i].v; if (!v || this.solaLettura) return;
      if (e.key.toLowerCase() === "x" && gruppo !== "dubbi" && gruppo !== "vuote") { this.commuta(gruppo, v.id); mostra(); }
      if (gruppo === "dubbi") {
        const opz = [v.persona, ...v.alternative.map(a => a[0])].slice(0, 3);
        if (/^[1-3]$/.test(e.key) && opz[+e.key - 1]) { this.decidi(v.id, opz[+e.key - 1]); if (i < elenco.length - 1) i++; mostra(); }
        if (e.key === "0" || e.key.toLowerCase() === "n") { this.decidi(v.id, ""); if (i < elenco.length - 1) i++; mostra(); }
      }
    };
    const chiudi = () => { document.removeEventListener("keydown", tasti, true); box.remove(); this.anteprimaAperta = false; this.chiudiAnteprima = null; prima?.focus?.(); };
    this.chiudiAnteprima = chiudi;
    document.addEventListener("keydown", tasti, true);
    box.addEventListener("mousedown", e => { if (e.target === box || e.target.classList.contains("foto")) chiudi(); });
    mostra();
  },

  /* ------------------------------------------------------------ controllo e copia */
  attendi(tipo, aggiorna) {
    return new Promise(risolvi => {
      const t = setInterval(() => {
        const a = S?.attivita; if (!a) return;
        if (a.in_corso) { aggiorna?.(S.registro); return; }
        if (a.tipo === tipo) { clearInterval(t); risolvi(a); }
      }, 400);
    });
  },
  async controllaECopia() {
    const d = this.decisioni();
    if (!d.length) return avviso("Non c'è nessuna foto da copiare: includi almeno una foto.", "avviso");
    if (S?.attivita.in_corso) return avviso("C'è un'altra attività in corso: aspetta che finisca.", "avviso");
    const nonDecisi = this.dubbi.filter(v => !(v.id in this.scelte.dubbi)).length;
    const corpo = document.createElement("div");
    corpo.innerHTML = `<p>Prima di copiare controllo, senza scrivere niente su MEGA, cosa succederà a ogni foto.</p>
      <div class="progresso" style="margin:14px 0"><i></i></div><p class="tenue tab-num" id="simDet">Controllo…</p>`;
    const promessa = modale({titolo: "Controllo prima di copiare", corpo, larga: true, chiudibile: false,
      azioni: [{testo: "Annulla", valore: false, id: "mAnnulla", disabilitato: true}, {testo: "Copia su MEGA", tipo: "primo", valore: true, id: "mCopia", disabilitato: true}]});
    try { await api(`/l/${encodeURIComponent(this.id)}/simula`, {decisioni: d}); }
    catch (e) { modaleAperta?.chiudi(false); return errore(e); }
    const a = await this.attendi("simulazione", r => { $(".progresso i", corpo).style.width = r.n ? (100 * r.i / r.n) + "%" : "10%"; $("#simDet", corpo).textContent = r.n ? `${r.i} di ${r.n}` : "Controllo…"; });
    const bAnn = $("#mAnnulla"), bCop = $("#mCopia");
    if (bAnn) bAnn.disabled = false;
    if (a.errore || !a.risultato) { corpo.innerHTML = `<div class="avviso rosso"><b>Il controllo non è riuscito.</b>${esc(a.errore || "")}</div>`; return; }
    const x = a.risultato;
    corpo.innerHTML = `<div class="riassunto">
        <div class="verde"><span class="numero">${x.copierebbe}</span><small>foto da copiare</small></div>
        <div><span class="numero">${x.salterebbe}</span><small>già presenti: saltate</small></div>
        <div><span class="numero">${x.cartelle_nuove}</span><small>cartelle nuove da creare</small></div>
        <div class="${x.bloccata ? "rosso" : ""}"><span class="numero">${x.bloccata}</span><small>bloccate dalle regole di sicurezza</small></div></div>
      ${x.bloccata ? `<div class="avviso rosso"><b>${x.bloccata} copie sono bloccate dalle regole di sicurezza.</b>Non copio niente finché ci sono copie bloccate. Il dettaglio è qui sotto: <a href="#/aiuto/sicurezza">cosa può e non può fare Smista Foto</a>.</div>` : ""}
      ${nonDecisi ? `<div class="avviso giallo"><b>${nonDecisi === 1 ? "1 volto da verificare non è deciso." : nonDecisi + " volti da verificare non sono decisi."}</b>${nonDecisi === 1 ? "Quella foto non verrà copiata." : "Quelle foto non verranno copiate."} Puoi annullare e decidere.</div>` : ""}
      <table><thead><tr><th>Persona</th><th>Cartella su MEGA</th><th>Da copiare</th><th>Già presenti</th></tr></thead><tbody>
      ${x.persone.map(p => `<tr><td><b>${esc(p.persona)}</b></td><td><span class="percorso">${esc(p.cartella)}</span>${p.nuova ? ` <span class="chip senza">nuova</span>` : ""}</td><td class="tab-num">${p.copierebbe}</td><td class="tab-num">${p.salterebbe}</td></tr>`).join("")}</tbody></table>
      <details class="cassetto"><summary>Foto per foto (${x.dettaglio.length})</summary><div class="dentro-cassetto"><table><tbody>${x.dettaglio.map(r => `<tr><td>${esc(r[0])}</td><td><span class="percorso">${esc(r[1])}</span></td><td>${esc(r[3])}</td></tr>`).join("")}</tbody></table></div></details>
      <p class="tenue piccolo" style="margin-top:12px">La copia avviene dentro MEGA: non sovrascrive niente, non cancella e non sposta niente.</p>`;
    if (bCop) { bCop.disabled = !!x.bloccata || !x.copierebbe; bCop.textContent = x.copierebbe ? `Copia ${x.copierebbe} foto su MEGA` : "Niente da copiare"; bCop.focus(); }
    if (!await promessa) return;
    this.esegui(d);
  },
  async esegui(d) {
    const corpo = document.createElement("div");
    corpo.innerHTML = `<p>Sto copiando le foto nelle cartelle su MEGA. <b>Non chiudere Smista Foto</b> finché non ho finito.</p>
      <div class="progresso" style="margin:14px 0"><i></i></div><p class="tenue tab-num" id="copDet">Inizio…</p>`;
    const fine = modale({titolo: "Copia in corso", corpo, chiudibile: false, azioni: [{testo: "Chiudi", valore: true, id: "mFine", disabilitato: true}]});
    try { await api(`/l/${encodeURIComponent(this.id)}/conferma`, {decisioni: d}); }
    catch (e) { modaleAperta?.chiudi(); return errore(e); }
    const a = await this.attendi("copia", r => {
      $(".progresso i", corpo).style.width = r.n ? (100 * r.i / r.n) + "%" : "5%";
      const eta = r.n && r.i > 2 ? " · circa " + durata(r.secondi_fase / r.i * (r.n - r.i)) + " alla fine" : "";
      $("#copDet", corpo).textContent = (r.n ? `${r.i} di ${r.n}` : "") + eta + (r.dettaglio ? " · " + r.dettaglio : "");
    });
    const x = a.risultato || {};
    $("#mFine").disabled = false;
    $("h2", modaleAperta.velo).textContent = a.errore ? "Copia interrotta" : "Copia finita";
    corpo.innerHTML = a.errore ? `<div class="avviso rosso"><b>Che cosa è successo</b>${esc(a.errore)}</div><p>Le foto copiate prima dell'interruzione restano. Puoi rifare la copia: quelle già presenti vengono saltate.</p>`
      : `<div class="riassunto"><div class="verde"><span class="numero">${x.copiate}</span><small>foto copiate</small></div><div><span class="numero">${x.gia_presenti}</span><small>già presenti, saltate</small></div><div class="${x.errori?.length ? "rosso" : ""}"><span class="numero">${x.errori?.length || 0}</span><small>errori</small></div><div><span class="numero">${new Set(d.map(z => z.persona)).size}</span><small>persone</small></div></div>
        ${x.errori?.length ? `<div class="avviso rosso"><b>Alcune copie non sono riuscite</b>${x.errori.slice(0, 8).map(esc).join("<br>")}</div>` : `<div class="avviso verde"><b>Tutto a posto.</b>I giocatori trovano le foto nelle loro cartelle condivise.</div>`}`;
    $("#mFine").focus();
    await fine;
    if (!a.errore) { memo("rev:" + this.id, null); location.hash = "#/"; avviso(`Copiate ${x.copiate} foto.`, "ok"); }
  },
};
