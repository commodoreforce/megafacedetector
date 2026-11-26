/* Smista Foto: pagina Sponsor (elenco, impostazioni, loghi, prova su una foto). */
"use strict";

const logoUrl = (nome, file) => `/logo/${encodeURIComponent(nome)}/${encodeURIComponent(file)}`;

V.sponsor = {
  titolo: "Sponsor",
  async mostra(el) {
    this.el = el; this.D = null;
    el.innerHTML = `<p class="tenue">Carico gli sponsor…</p>`;
    await this.carica();
  },
  async carica() {
    try { this.D = await api("/api/sponsor"); } catch (e) { this.el.innerHTML = `<div class="avviso rosso"><b>Non riesco a leggere gli sponsor</b>${esc(e.message)}</div>`; return; }
    this.disegna();
  },
  aggiorna(s) {
    // quando MEGA si collega la cartella SPONSOR viene trovata: ricarico una volta
    if (this.D && !this.D.radice && s.sponsor?.radice) { this.carica(); }
  },
  disegna() {
    const D = this.D, el = this.el;
    const attivi = D.elenco.filter(x => x.attivo).length;
    el.innerHTML = `<div class="intesta"><h1>Sponsor</h1><div class="dx riga-btn" style="margin-top:0">
        <button class="btn" id="bProvaS" ${attivi ? "" : "disabled"}>Prova su una foto</button>
        <button class="btn primo" id="bNuovoS">Aggiungi sponsor</button></div></div>
      <p class="tenue" style="margin-top:8px;max-width:72ch">Durante lo smistamento Smista Foto legge le scritte nelle foto (maglie, cartelloni fissi e luminosi) e, se gliel'hai dato, cerca anche il disegno del logo. Per ogni sponsor sceglie le foto migliori, che controlli nella revisione prima della copia in
        <code>${esc(D.radice || "SPONSOR")} / sponsor / competizione / partita</code>.</p>
      ${!D.radice ? `<div class="avviso giallo" style="margin-top:14px"><b>${D.collegato ? "Non trovo la cartella SPONSOR su MEGA" : "MEGA non è ancora collegato"}</b>${D.collegato ? "Smista Foto la cerca nella cartella della stagione (accanto a PLAYERS). Finché non c'è, gli sponsor non vengono smistati." : "Quando il semaforo diventa verde, Smista Foto trova la cartella SPONSOR e gli sponsor che contiene."}</div>` : ""}
      <div class="blocco" style="padding:6px 18px;margin-top:16px"><table class="tabella-sponsor"><thead><tr>
        <th>Sponsor</th><th>Cosa cerca ${q("sponsor_parole")}</th><th>Foto a partita ${q("sponsor_quante")}</th><th>Foto ad allenamento</th><th></th></tr></thead>
        <tbody>${D.elenco.length ? D.elenco.map(s => this.riga(s)).join("") : `<tr><td colspan="5" class="tenue">Nessuno sponsor. Crea le cartelle in SPONSOR su MEGA oppure premi «Aggiungi sponsor».</td></tr>`}</tbody></table></div>
      ${D.non_validi.length ? `<p class="tenue piccolo" style="margin-top:10px">Cartelle in SPONSOR con nomi che Smista Foto non usa (minuscole o caratteri speciali): ${D.non_validi.map(esc).join(", ")}. Rinominale in maiuscolo su MEGA se sono sponsor.</p>` : ""}
      <p class="tenue piccolo" style="margin-top:12px">Le impostazioni e i loghi restano su questo computer e passano su un altro con «Esporta i volti». Togliere uno sponsor da qui non cancella nulla su MEGA.</p>`;
    $("#bNuovoS", el).onclick = () => this.modifica(null);
    $("#bProvaS", el).onclick = () => this.prova();
    $$("input[data-quante]", el).forEach(i => i.onchange = () => this.salvaNumero(i));
    el.onclick = e => {
      const b = e.target.closest("button[data-az]"); if (!b) return;
      const s = D.elenco.find(x => x.nome === b.dataset.n);
      if (b.dataset.az === "modifica") this.modifica(s);
      if (b.dataset.az === "pausa") api("/api/sponsor-salva", {nome: s.nome, attivo: !s.attivo}).then(() => { avviso(s.attivo ? `${s.nome} in pausa: non viene cercato.` : `${s.nome} di nuovo attivo.`, "info"); this.carica(); }).catch(errore);
    };
  },
  riga(s) {
    const logo = s.loghi[0];
    return `<tr class="${s.attivo ? "" : "in-pausa"}">
      <td><div class="sp-nome">${logo ? `<img class="logo-mini" src="${logoUrl(s.nome, logo)}" alt="">` : `<span class="logo-mini vuoto" aria-hidden="true">${esc(s.nome.slice(0, 1))}</span>`}
        <div><b>${esc(s.nome)}</b><br><span class="tenue piccolo">${!s.attivo ? "In pausa" : s.su_mega ? "Cartella su MEGA" : this.D.radice ? "Cartella creata alla prima copia" : ""}</span></div></div></td>
      <td>${s.parole.map(p => `<span class="chip senza">${esc(p)}</span>`).join(" ")}${s.disegno && s.loghi.length ? ` <span class="chip senza">+ disegno del logo</span>` : ""}${!s.parole.length && !(s.disegno && s.loghi.length) ? `<span class="chip giallo">niente da cercare</span>` : ""}</td>
      <td><input class="testo numero" type="number" min="1" max="50" value="${s.foto_partita}" data-quante="foto_partita" data-n="${esc(s.nome)}" aria-label="Foto a partita per ${esc(s.nome)}"></td>
      <td><input class="testo numero" type="number" min="1" max="50" value="${s.foto_allenamento}" data-quante="foto_allenamento" data-n="${esc(s.nome)}" aria-label="Foto ad allenamento per ${esc(s.nome)}"></td>
      <td><div class="az"><button class="btn" data-az="modifica" data-n="${esc(s.nome)}">Modifica</button>
        <button class="btn piatto" data-az="pausa" data-n="${esc(s.nome)}">${s.attivo ? "Metti in pausa" : "Riattiva"}</button></div></td></tr>`;
  },
  async salvaNumero(i) {
    const v = Math.round(+i.value);
    if (!(v >= 1 && v <= 50)) { avviso("Scrivi un numero tra 1 e 50.", "avviso"); i.value = this.D.elenco.find(x => x.nome === i.dataset.n)[i.dataset.quante]; return; }
    try {
      await api("/api/sponsor-salva", {nome: i.dataset.n, [i.dataset.quante]: v});
      this.D.elenco.find(x => x.nome === i.dataset.n)[i.dataset.quante] = v;
      avviso(`${i.dataset.n}: ${v} foto ${i.dataset.quante === "foto_partita" ? "a partita" : "ad allenamento"}${v < 2 || v > 10 ? " (fuori dal solito 2-10, va bene se è quello che vuoi)" : ""}.`, "ok");
    } catch (e) { errore(e); }
  },

  /* ------------------------------------------------------------ aggiungi / modifica */
  async modifica(s) {
    const nuovo = !s;
    s = s || {nome: "", parole: [], foto_partita: 4, foto_allenamento: 2, attivo: true, disegno: false, loghi: []};
    const corpo = document.createElement("div");
    corpo.innerHTML = `
      <div class="campo"><label for="sNome">Nome</label><input id="sNome" value="${esc(s.nome)}" ${nuovo ? "" : "readonly"} autocomplete="off" placeholder="es. AMADORI" style="text-transform:uppercase">
        <span class="aiuto-campo">${nuovo ? "Come la cartella in SPONSOR su MEGA. Se non c'è, viene creata alla prima copia." : "Il nome corrisponde alla cartella su MEGA e non si cambia da qui."}</span><span class="errore-campo" id="eNome"></span></div>
      <div class="campo"><label for="sParole">Scritte da cercare</label><input id="sParole" value="${esc(s.parole.join(", "))}" autocomplete="off" placeholder="es. AMADORI">
        <span class="aiuto-campo">Le parole del logo, separate da virgole. Aggiungi le varianti che compaiono davvero (es. DOLOMIA, ACQUA DOLOMIA). Almeno 3 lettere: le parole corte devono comparire identiche.</span></div>
      <div class="griglia-campi" style="grid-template-columns:1fr 1fr">
        <div class="campo"><label for="sPart">Foto a partita</label><input id="sPart" type="number" min="1" max="50" value="${s.foto_partita}"><span class="aiuto-campo">Di solito tra 2 e 10.</span></div>
        <div class="campo"><label for="sAll">Foto ad allenamento</label><input id="sAll" type="number" min="1" max="50" value="${s.foto_allenamento}"><span class="aiuto-campo">Di solito tra 2 e 10.</span></div></div>
      <div class="campo"><span class="etichetta">Immagini del logo</span>
        <div class="loghi-elenco" id="sLoghi"></div>
        <input type="file" id="sFile" accept="image/png,image/jpeg,image/webp" multiple hidden>
        <div class="riga-btn" style="margin-top:8px"><button type="button" class="btn" id="sAggiungiLogo">Aggiungi immagine del logo</button></div>
        <span class="aiuto-campo">PNG con sfondo trasparente o bianco, anche più versioni (positivo, negativo, orizzontale). Si vedono in elenco e servono per cercare il disegno.</span></div>
      <label class="spunta"><input type="checkbox" id="sDisegno" ${s.disegno ? "checked" : ""}> Cerca anche il disegno del logo
        <span class="aiuto-campo">Utile per loghi senza scritte o con lettere molto stilizzate. Rende l'analisi un po' più lenta (circa mezzo secondo a foto).</span></label>
      ${nuovo ? "" : `<details class="cassetto" style="margin-top:16px"><summary>Togli lo sponsor</summary><div class="dentro-cassetto">
        <p class="tenue">Toglie ${esc(s.nome)} da Smista Foto su questo computer, con i suoi loghi. La cartella su MEGA e le foto già copiate restano. Se la cartella c'è ancora su MEGA, al prossimo collegamento ricompare con le impostazioni di partenza: per non cercarlo più usa «Metti in pausa».</p>
        <div class="riga-btn"><button type="button" class="btn pericolo" id="sElimina">Togli ${esc(s.nome)}</button></div></div></details>`}`;
    let loghi = [...s.loghi], nomeAttuale = s.nome;
    const disegnaLoghi = () => {
      $("#sLoghi", corpo).innerHTML = loghi.length ? loghi.map(f => `<figure><img src="${logoUrl(nomeAttuale, f)}?${Date.now()}" alt="Logo ${esc(nomeAttuale)}"><button type="button" class="btn piatto" data-togli="${esc(f)}" aria-label="Togli ${esc(f)}">Togli</button></figure>`).join("")
        : `<p class="tenue piccolo" style="margin:0">Nessuna immagine: basta la scritta per gli sponsor con il nome nel logo.</p>`;
      $("#sDisegno", corpo).disabled = !loghi.length;
      if (!loghi.length) $("#sDisegno", corpo).checked = false;
    };
    const salva = async (silenzioso) => {
      const nome = $("#sNome", corpo).value.trim().toUpperCase();
      if (!nome) { $("#eNome", corpo).textContent = "Serve il nome."; $("#sNome", corpo).focus(); return false; }
      const dati = {nome, nuovo: nuovo && !nomeAttuale, parole: $("#sParole", corpo).value || nome,
        foto_partita: +$("#sPart", corpo).value, foto_allenamento: +$("#sAll", corpo).value, disegno: $("#sDisegno", corpo).checked};
      try { const r = await api("/api/sponsor-salva", dati); nomeAttuale = r.nome; $("#sNome", corpo).readOnly = true; if (!silenzioso) avviso(`${r.nome} salvato.`, "ok"); return true; }
      catch (e) { $("#eNome", corpo).textContent = e.message; return false; }
    };
    disegnaLoghi();
    $("#sAggiungiLogo", corpo).onclick = async () => { if (!nomeAttuale && !await salva(true)) return; $("#sFile", corpo).click(); };
    $("#sFile", corpo).onchange = async e => {
      for (const f of e.target.files) {
        const r = await fetch(`/api/sponsor-logo?nome=${encodeURIComponent(nomeAttuale)}&file=${encodeURIComponent(f.name)}`, {method: "POST", body: f});
        const j = await r.json().catch(() => ({}));
        if (r.ok) loghi.push(j.file); else errore(new Error(j.errore || "Logo non caricato."));
      }
      e.target.value = ""; disegnaLoghi();
      if (loghi.length && !$("#sParole", corpo).value.trim()) $("#sDisegno", corpo).checked = true;
    };
    $("#sLoghi", corpo).onclick = async e => {
      const b = e.target.closest("[data-togli]"); if (!b) return;
      try { await api("/api/sponsor-togli-logo", {nome: nomeAttuale, file: b.dataset.togli}); loghi = loghi.filter(x => x !== b.dataset.togli); disegnaLoghi(); } catch (er) { errore(er); }
    };
    $("#sElimina", corpo)?.addEventListener("click", () => modaleAperta?.chiudi("togli"));
    const esito = await modale({titolo: nuovo ? "Nuovo sponsor" : s.nome, corpo,
      azioni: [{testo: "Annulla", valore: false}, {testo: "Salva", tipo: "primo", valore: true}]});
    if (esito === "togli") {
      if (!await conferma(`Togliere ${s.nome}?`, "Su MEGA non cambia nulla: la cartella e le foto già copiate restano.", "Togli", "pericolo")) return this.modifica(s);
      try { await api("/api/sponsor-elimina", {nome: s.nome}); avviso(`${s.nome} tolto da Smista Foto.`, "info"); } catch (er) { errore(er); }
      return this.carica();
    }
    if (esito) { if (await salva(false)) this.carica(); else this.modifica({...s, nome: nomeAttuale || $("#sNome", corpo).value}); }
    else if (nomeAttuale) this.carica();
  },

  /* ------------------------------------------------------------ prova su una foto */
  prova() {
    const i = Object.assign(document.createElement("input"), {type: "file", accept: "image/jpeg,image/png,image/webp"});
    i.onchange = async () => {
      const f = i.files[0]; if (!f) return;
      avviso("Cerco gli sponsor nella foto…", "info");
      let r;
      try {
        const risp = await fetch("/api/sponsor-prova", {method: "POST", body: f});
        r = await risp.json(); if (!risp.ok) throw new Error(r.errore);
      } catch (e) { return errore(e); }
      const url = URL.createObjectURL(f), nomi = Object.keys(r.trovati);
      const riquadri = [
        ...r.letture.map(l => `<rect x="${l.box[0]}" y="${l.box[1]}" width="${l.box[2]}" height="${l.box[3]}" class="r-letto"><title>${esc(l.testo)}</title></rect>`),
        ...nomi.map(n => `<polygon points="${r.trovati[n].quad.map(p => p.join(",")).join(" ")}" class="r-sponsor"/>`)].join("");
      await modale({titolo: nomi.length ? `Trovati: ${nomi.join(", ")}` : "Nessuno sponsor trovato", larga: true, corpo: `
        <div class="foto-prova"><img src="${url}" alt="Foto di prova"><svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">${riquadri}</svg></div>
        ${nomi.length ? `<table style="margin-top:14px"><thead><tr><th>Sponsor</th><th>Dove</th><th>Scritta letta</th><th>Punteggio ${q("sponsor_punteggio")}</th></tr></thead><tbody>
          ${nomi.map(n => { const t = r.trovati[n]; return `<tr><td><b>${esc(n)}</b></td><td>${t.tipo === "maglia" ? "Su una persona" : "Cartellone o sfondo"}</td><td>${esc(t.testo)}</td><td class="tab-num">${Math.round(t.punteggio * 100)}</td></tr>`; }).join("")}</tbody></table>` : ""}
        <p class="tenue piccolo" style="margin-top:12px">In verde gli sponsor trovati, in grigio tutte le scritte lette (passa sopra per leggerle): ${r.letture.length ? r.letture.map(l => esc(l.testo)).join(" · ") : "nessuna"}. Tempo: ${r.secondi} s.
        ${nomi.length ? "" : "Se lo sponsor si vede ma non è stato trovato, controlla in «Modifica» che le scritte da cercare siano quelle del logo, oppure aggiungi l'immagine del logo e attiva «Cerca anche il disegno»."}</p>`});
      URL.revokeObjectURL(url);
    };
    i.click();
  },
};
