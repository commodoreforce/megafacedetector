/* Smista Foto: guida integrata e spiegazioni brevi dei bottoni «?». */
"use strict";

window.GLOSSARIO = {
  sponsor_parole: {titolo: "Cosa cerca", link: "sponsor", testo: "<p>Smista Foto legge le scritte nelle foto e le confronta con queste parole. Tollera una lettera letta male nelle parole lunghe e un logo coperto in parte (almeno il 70% della parola). Con l'immagine del logo e «Cerca anche il disegno» trova anche loghi senza scritte.</p>"},
  sponsor_quante: {titolo: "Quante foto", link: "sponsor", testo: "<p>Quante foto Smista Foto propone per ogni partita o allenamento. Sceglie le migliori: logo grande, nitido e leggibile, meglio se con un nostro giocatore protagonista, senza doppioni della stessa raffica e mescolando maglie e cartelloni. Di solito tra 2 e 10, ma puoi mettere il numero che vuoi.</p>"},
  sponsor_punteggio: {titolo: "Punteggio", link: "sponsor", testo: "<p>Da 0 a circa 125: quanto il logo è grande, nitido e letto con sicurezza, più un bonus se c'è un nostro giocatore protagonista e se il logo è sulla sua maglia. Serve a mettere in fila le foto, non è un voto assoluto.</p>"},
  sponsor_scelte: {titolo: "Foto per gli sponsor", link: "sponsor", testo: "<p>Per ogni sponsor Smista Foto propone le foto migliori, quante ne hai chieste nella pagina Sponsor. Puoi toglierne o aggiungerne con un clic: «Altre foto» contiene tutte quelle in cui ha trovato il logo. Vengono copiate insieme a quelle dei giocatori, con la stessa simulazione.</p>"},
  protagonista: {titolo: "Protagonista", link: "glossario", testo: "<p>Smista Foto copia una foto nella cartella di una persona solo se lì è almeno un po' protagonista: il suo volto è tra i più grandi della foto, non è minuscolo ed è abbastanza a fuoco. Chi è sullo sfondo è una «comparsa» e non viene copiato.</p>"},
  comparsa: {titolo: "Comparse", link: "glossario", testo: "<p>Persone riconosciute ma piccole, sullo sfondo o fuori fuoco. Non vengono copiate, come fate a mano. Se una ti serve, cliccala: verrà copiata comunque.</p>"},
  dubbio: {titolo: "Da verificare", link: "revisione", testo: "<p>Volti che Smista Foto non riesce ad attribuire con sicurezza: di profilo, coperti, mossi, o simili a due persone. Scegli tu il nome giusto. Quelli che non decidi non vengono copiati.</p>"},
  riconosciute: {titolo: "Riconosciute", link: "revisione", testo: "<p>Foto in cui Smista Foto è sicuro di chi sia il protagonista. Verranno copiate nella cartella di quella persona, a meno che tu non le escluda con un clic.</p>"},
  debole: {titolo: "Riconoscimento debole", link: "volti", testo: "<p>Una persona con meno di 4 foto utili nella sua cartella è difficile da riconoscere. Succede soprattutto con lo staff. Aggiungi 3-5 primi piani dalla pagina «Giocatori e staff».</p>"},
  data: {titolo: "La data davanti al nome", link: "allenamenti", testo: "<p>Negli allenamenti tutte le foto di una persona stanno in un'unica cartella, e nomi come IMG_5169.jpg si ripetono tra giorni diversi. Per non confonderle, la foto diventa 20261102_IMG_5169.jpg.</p>"},
  stati: {titolo: "Stato delle cartelle", link: "cartelle", testo: "<p><b>Copiata con Smista Foto</b>: copiata da questo computer, con data e numeri. <b>Già nelle cartelle dei giocatori</b>: la partita c'è già nelle cartelle di alcuni giocatori, quindi è stata fatta a mano o da un altro computer. <b>Analizzata, da confermare</b>: manca la revisione. <b>Da smistare</b>: nessuna traccia.</p>"},
  precisione: {titolo: "Precisione", link: "prove", testo: "<p>Su 100 foto proposte, quante coincidono con lo smistamento fatto a mano. Lo smistamento a mano su un criterio sfumato come «un po' protagonista» non è perfetto, quindi la precisione reale è di solito un po' più alta.</p>"},
};

V.aiuto = {
  titolo: "Aiuto",
  mostra(el, [sezione]) {
    const voci = [
      ["inizio", "Come funziona"], ["configurazione", "Prima configurazione"], ["mega", "Collegamento a MEGA"],
      ["partite", "Smistare una partita"], ["allenamenti", "Smistare un allenamento"], ["revisione", "La revisione"],
      ["cartelle", "Stato delle cartelle"], ["volti", "Giocatori e staff"], ["sponsor", "Sponsor"], ["sicurezza", "Sicurezza dell'archivio"], ["aggiornare", "Aggiornare Smista Foto"], ["prove", "Prove e regole"],
      ["problemi", "Problemi frequenti"], ["glossario", "Parole usate nell'app"],
    ];
    el.innerHTML = `<div class="aiuto"><nav aria-label="Indice della guida">${voci.map(([id, t]) => `<a href="#/aiuto/${id}">${t}</a>`).join("")}</nav><article>
<section id="a-inizio"><h1>Guida a Smista Foto</h1>
<p style="margin-top:12px">Smista Foto guarda le foto caricate dai fotografi su MEGA, riconosce giocatori e staff e copia ogni foto nella cartella personale di chi ne è protagonista. Tu controlli e confermi: senza la tua conferma non viene copiato niente.</p>
<ol><li><b>Scegli la cartella</b> della partita o dell'allenamento, da «Smista foto».</li>
<li><b>Aspetta l'analisi.</b> Scarica e analizza una foto alla volta, solo sul computer. Puoi fare altro: quando finisce compare un avviso.</li>
<li><b>Rivedi le proposte</b>, decidi i volti da verificare, guarda il riepilogo e conferma la copia.</li></ol>
<p>Tieni sempre aperta la finestra nera del Terminale che si apre insieme all'app: è il motore di Smista Foto. Se la chiudi, l'app si ferma.</p></section>

<section id="a-configurazione"><h2>Prima configurazione</h2>
<p>Si fa una volta sola per computer. La pagina «Inizio» la guida passo per passo e spunta da sola ogni passo fatto.</p>
<ol><li><b>Installazione.</b> Doppio clic su <code>Installa_Mac.command</code> (Mac) o <code>Installa_Windows.bat</code> (Windows). Controlla Python e MEGAcmd, installa quello che serve e crea l'icona <b>Smista Foto</b> sulla Scrivania.</li>
<li><b>Accesso a MEGA</b> con l'account del club, dentro MEGAcmd (vedi sotto).</li>
<li><b>Modello di riconoscimento:</b> si scarica da solo al primo avvio, circa 260 MB.</li>
<li><b>Impara i volti:</b> un pulsante, 10-20 minuti.</li></ol></section>

<section id="a-mega"><h2>Collegamento a MEGA</h2>
<p>Il semaforo in alto a destra dice se Smista Foto può usare MEGA: <b>verde</b> collegato, <b>giallo</b> controllo in corso, <b>rosso</b> non collegato. Quando è rosso ricontrolla da solo ogni 15 secondi.</p>
<h3>Per collegarsi</h3>
<ol><li>Apri <b>MEGAcmd</b>: dalle Applicazioni sul Mac, dal menu Start su Windows.</li>
<li>Scrivi <code>login</code> seguito dall'email dell'account MEGA del club (es. <code>login nome@dominio.it</code>) e premi Invio. Nella pagina Inizio puoi scrivere l'email e copiare il comando già pronto.</li>
<li>Scrivi la password e premi Invio. Mentre la scrivi non compare nulla: è normale.</li>
<li>Il semaforo diventa verde entro qualche secondo. L'accesso resta valido anche dopo aver riavviato il computer.</li></ol>
<div class="avviso giallo"><b>Nella finestra di MEGAcmd non scrivere altri comandi.</b>Da lì si hanno tutti i permessi sull'archivio del club. Smista Foto invece ha regole di sicurezza proprie, vedi «Sicurezza dell'archivio».</div></section>

<section id="a-partite"><h2>Smistare una partita</h2>
<ol><li>Apri «Smista foto» e scegli <code>MATCH</code>, la competizione (es. <code>SERIEBKT</code>), la partita e la cartella <b>Foto</b>. Le sottocartelle dei fotografi vengono lette tutte.</li>
<li>Controlla la destinazione: <code>PLAYERS / persona / SERIE BKT / G10_SUDTIROL_CESENA</code>. Il nome della partita viene ricavato da solo, in maiuscolo e senza risultato.</li>
<li>Avvia l'analisi e poi fai la revisione.</li></ol>
<p>Se la foto era nella sottocartella di un fotografo, il nome diventa <code>Rossi_DSC_0412.jpg</code>: così due fotografi con lo stesso nome di file non si sovrascrivono.</p></section>

<section id="a-allenamenti"><h2>Smistare un allenamento</h2>
<ol><li>Apri «Smista foto» e scegli <code>ALLENAMENTI</code>, il mese (es. <code>2026_11_Novembre</code>) e il giorno (es. <code>20261102</code>).</li>
<li>La destinazione è la cartella unica <code>PLAYERS / persona / ALLENAMENTI</code>, senza sottocartella per data.</li>
<li>Il nome di ogni foto inizia con la data: <code>20261102_IMG_5169.jpg</code>.</li></ol>
<p>Se una foto di quel giorno era già stata copiata a mano con il nome originale, Smista Foto la riconosce (stesso nome e stessa dimensione) e la salta. Una foto con lo stesso nome ma di un altro giorno non viene mai toccata.</p></section>

<section id="a-revisione"><h2>La revisione</h2>
<p>È la pagina dove decidi. Ha quattro parti:</p>
<dl><dt>Da verificare (bordo giallo)</dt><dd>Smista Foto non è sicuro. Scegli il nome tra quelli proposti, un'altra persona dall'elenco, oppure «Non copiare». Quelli che lasci in sospeso non vengono copiati.</dd>
<dt>Riconosciute (bordo verde)</dt><dd>Verranno copiate. Clicca una miniatura per escluderla: diventa rossa con una croce. «Escludi tutte» agisce su una persona intera e si può annullare.</dd>
<dt>Comparse</dt><dd>Riconosciute ma non protagoniste: non vengono copiate. Cliccale per copiarle comunque.</dd>
<dt>Foto senza nessuno riconosciuto</dt><dd>Campi lunghi, spalle, avversari, pubblico. Se ti serve, scegli la persona dall'elenco.</dd></dl>
<h3>Copiare</h3>
<p>«Controlla e copia» mostra sempre prima il riepilogo: quante foto verranno copiate, quante sono già presenti, quali cartelle verranno create, con il dettaglio foto per foto. Su MEGA non succede niente finché non premi «Copia su MEGA».</p>
<h3>Scorciatoie da tastiera</h3>
<table><tbody><tr><td><kbd>J</kbd></td><td>vai al prossimo volto da verificare</td></tr><tr><td><kbd>1</kbd> <kbd>2</kbd> <kbd>3</kbd></td><td>scegli il nome proposto</td></tr><tr><td><kbd>0</kbd></td><td>non copiare</td></tr><tr><td><kbd>Spazio</kbd></td><td>escludi o includi la miniatura</td></tr><tr><td><kbd>V</kbd></td><td>vedi la foto intera con il volto evidenziato</td></tr><tr><td><kbd>Ctrl</kbd>/<kbd>⌘</kbd>+<kbd>Z</kbd></td><td>annulla</td></tr></tbody></table>
<p>Le scelte si salvano da sole sul computer: puoi chiudere e riprendere la revisione più tardi da «Revisioni».</p></section>

<section id="a-cartelle"><h2>Stato delle cartelle</h2>
<p>La pagina «Cartelle» elenca tutte le cartelle caricate dai fotografi nella stagione, partite e allenamenti, con il loro stato:</p>
<dl><dt>Copiata con Smista Foto</dt><dd>Copiata da questo computer: vedi quando, quante foto, per quante persone e da quale computer.</dd>
<dt>Già nelle cartelle dei giocatori</dt><dd>La partita esiste già nelle cartelle di alcuni giocatori: è stata smistata a mano o da un altro computer. Per gli allenamenti si riconoscono le foto copiate con Smista Foto, che hanno la data davanti al nome.</dd>
<dt>Analizzata, da confermare</dt><dd>L'analisi è finita ma le foto non sono ancora state copiate: riprendi la revisione.</dd>
<dt>Da smistare</dt><dd>Nessuna traccia: premi «Smista» e la procedura parte con quella cartella già scelta.</dd></dl>
<p>«Controlla su MEGA» legge, senza modificare nulla, le cartelle dei fotografi e quelle di una dozzina di giocatori (non tutti, per fare in fretta: circa un minuto). Le copie fatte da questo computer compaiono subito. Ogni computer conserva la sua storia delle copie: quelle fatte da un altro computer risultano «già nelle cartelle dei giocatori».</p></section>

<section id="a-volti"><h2>Giocatori e staff</h2>
<p>Le persone sono le cartelle in <code>PLAYERS</code> e <code>PLAYERS/_STAFF</code>. Smista Foto impara il volto del proprietario di ogni cartella guardando circa 30 sue foto, soprattutto del Media Day.</p>
<ul><li><b>Arriva un giocatore nuovo:</b> crea la sua cartella su MEGA come sempre, mettici qualche foto e premi «Impara i volti nuovi».</li>
<li><b>Riconoscimento debole:</b> aggiungi 3-5 primi piani trascinandoli sulla riga della persona, poi conferma di reimpararla. I primi piani restano solo su questo computer.</li>
<li><b>Una cartella non è una persona</b> (es. 00VARIE): premi «Non è una persona». Su MEGA non cambia nulla.</li>
<li><b>Computer nuovo:</b> non serve imparare di nuovo. Sul computer già pronto premi «Esporta i volti» (in fondo a questa pagina): nei Download trovi un file <code>SmistaFoto_volti_….zip</code> con volti, primi piani, regola scelta e cartelle escluse. Sul computer nuovo premi «Importa i volti» (anche dalla pagina Inizio, durante la prima configurazione) e scegli il file. I volti che c'erano prima vengono salvati nella cartella <code>backup_volti</code>.</li></ul>
<div class="avviso giallo"><b>Il file esportato contiene le impronte dei volti delle persone</b>Spostalo con una chiavetta o una cartella interna del club, non mandarlo per email o chat e non caricarlo su GitHub. Dopo l'importazione cancellalo dai Download. Esportare e importare non usa MEGA.</div></section>

<section id="a-sponsor"><h2>Sponsor</h2>
<p>Ogni sponsor è una cartella in <code>SPONSOR</code> su MEGA, accanto a <code>PLAYERS</code>. Smista Foto trova da solo le cartelle che ci sono e le aggiunge alla pagina <b>Sponsor</b>, cercando la scritta uguale al nome.</p>
<ul><li><b>Nuovo sponsor:</b> crea la cartella su MEGA (in maiuscolo) oppure premi «Aggiungi sponsor». Scrivi le parole del logo e, se vuoi, carica l'immagine del logo. Se la cartella su MEGA non c'è, viene creata alla prima copia.</li>
<li><b>Quante foto:</b> si cambiano direttamente nell'elenco, separate per partite e allenamenti.</li>
<li><b>Prova su una foto:</b> carica una foto dal computer e guarda cosa legge Smista Foto. In verde gli sponsor trovati, in grigio tutte le scritte lette. È il modo più rapido per capire se le parole da cercare sono giuste.</li>
<li><b>Durante lo smistamento</b> lascia spuntato «Cerca anche gli sponsor». Nella revisione, sotto i volti da verificare, trovi un riquadro per sponsor con le foto scelte e le altre in cui c'è il logo.</li>
<li><b>Dove finiscono:</b> <code>SPONSOR / sponsor / competizione / partita</code>, oppure <code>SPONSOR / sponsor / ALLENAMENTI</code> con la data davanti al nome del file.</li>
<li><b>Mettere in pausa</b> uno sponsor (per esempio a fine contratto) lo esclude dalle ricerche senza perdere le impostazioni. Su MEGA non cambia nulla.</li></ul>
<p>Le scritte molto piccole, piegate o coperte sono le più difficili: per queste conviene controllare «Altre foto» nella revisione. Impostazioni e loghi restano su questo computer e passano su un altro con «Esporta i volti».</p></section>

<section id="a-aggiornare"><h2>Aggiornare Smista Foto</h2>
<p>In basso a sinistra c'è il pulsante <b>Controlla aggiornamenti</b>. Quando esce una versione nuova diventa giallo («Aggiorna alla …») e nella pagina Inizio compare un avviso. Smista Foto controlla da solo all'avvio e ogni 6 ore.</p>
<ol><li>Premi il pulsante: vedi le novità.</li>
<li>Premi <b>Aggiorna ora</b>. Smista Foto scarica la nuova versione, si chiude, aggiorna i suoi componenti e si riapre da solo: di solito 1-3 minuti. Non chiudere la finestra nera.</li>
<li>La pagina si ricarica e compare «Smista Foto è aggiornato».</li></ol>
<p>Volti imparati, revisioni, sponsor, loghi e impostazioni restano. Su MEGA non cambia nulla. Se l'aggiornamento non va a buon fine (per esempio manca la connessione), Smista Foto torna da solo alla versione di prima e te lo dice.</p>
<p class="tenue">Se l'app non si apre proprio, nella cartella di Smista Foto ci sono anche <code>Aggiorna_Windows.bat</code> e <code>Aggiorna_Mac.command</code>. MEGAcmd si aggiorna a parte, dal sito di MEGA.</p></section>

<section id="a-sicurezza"><h2>Sicurezza dell'archivio</h2>
<p>MEGA è l'archivio storico del club, senza altre copie. Per questo Smista Foto ha regole rigide scritte nel programma e controllate prima di ogni comando:</p>
<ul><li>Usa solo comandi per leggere, scaricare sul computer, creare cartelle e copiare. Qualsiasi altro comando viene rifiutato prima di partire.</li>
<li><b>Non cancella, non sposta e non rinomina nulla su MEGA.</b> Queste funzioni non esistono nel programma.</li>
<li><b>Non sovrascrive mai:</b> prima di ogni copia controlla che il file non ci sia già. Nel dubbio, non copia.</li>
<li>Scrive solo in <code>PLAYERS / persona / competizione / partita</code> oppure in <code>PLAYERS / persona / ALLENAMENTI</code>, e per gli sponsor in <code>SPONSOR / sponsor / competizione / partita</code> o <code>SPONSOR / sponsor / ALLENAMENTI</code>. Le cartelle dei fotografi vengono solo lette.</li>
<li>Le foto scaricate per l'analisi restano sul computer solo il tempo necessario.</li>
<li>Le «impronte» dei volti sono numeri, non foto, e restano solo su questo computer. I volti di avversari e tifosi vengono scartati subito.</li></ul></section>

<section id="a-prove"><h2>Prove e regole</h2>
<p>Per chi configura Smista Foto. Una <b>prova</b> analizza una cartella già smistata a mano e confronta il risultato con il vostro lavoro, senza copiare nulla. Ne escono la precisione (quante proposte coincidono) e il lavoro trovato (quanta parte dello smistamento a mano avrebbe fatto da solo).</p>
<p>Con almeno due prove su cartelle diverse, «Calcola la regola su tutte le prove» propone le regole del protagonista che funzionano bene su tutte. «Usa questa» la salva su questo computer e vale dalla prossima analisi.</p></section>

<section id="a-problemi"><h2>Problemi frequenti</h2>
<table class="problemi"><tbody>
<tr><td>Il semaforo resta rosso</td><td>Apri MEGAcmd e controlla di aver fatto <code>login</code>. Se MEGAcmd non è installato, scaricalo da mega.io/cmd. Apri il «Registro» in basso: c'è la risposta esatta di MEGAcmd.</td></tr>
<tr><td>«Smista Foto non risponde» o pagina bianca</td><td>La finestra del Terminale è stata chiusa. Riapri Smista Foto con l'icona sulla Scrivania.</td></tr>
<tr><td>L'app non si apre in una finestra</td><td>Apri il browser e vai su <code>http://127.0.0.1:8765</code>.</td></tr>
<tr><td>Errore sul modello di riconoscimento</td><td>Di solito è il download interrotto. Controlla la connessione e premi «Riprova» nella pagina Inizio.</td></tr>
<tr><td>La cartella di Smista Foto è in OneDrive, iCloud o Dropbox</td><td>Spostala fuori: i volti imparati sono dati personali e non devono finire in un cloud esterno al club, e la sincronizzazione può bloccare i file mentre l'app li usa. Chiudi Smista Foto, sposta tutta la cartella (su Windows ad esempio in <code>C:\\SmistaFoto</code>, sul Mac nella cartella Utente) e rilancia l'installazione per ricreare l'icona sulla Scrivania. Volti e analisi restano, perché si spostano con la cartella.</td></tr>
<tr><td>Una persona viene confusa con un'altra</td><td>In «Giocatori e staff» aggiungi primi piani di entrambe. Se una cartella contiene soprattutto foto di un altro giocatore, va sistemata su MEGA e reimparata.</td></tr>
<tr><td>Il Mac dice che il file non si può aprire</td><td>Clic destro sul file, poi «Apri» e di nuovo «Apri». Serve solo la prima volta.</td></tr>
<tr><td>«Aggiornamento annullato»</td><td>Di solito è la connessione: riprova più tardi con il pulsante in basso a sinistra. Smista Foto è rimasto alla versione di prima e funziona come prima. Se succede ancora, la finestra nera mostra il motivo.</td></tr>
<tr><td>Una copia è stata «bloccata»</td><td>Le regole di sicurezza hanno impedito di scrivere fuori dalle cartelle consentite. Non succede nulla su MEGA. Mandate il riepilogo a chi segue Smista Foto.</td></tr>
</tbody></table></section>

<section id="a-glossario"><h2>Parole usate nell'app</h2><dl>
<dt>Protagonista</dt><dd>${GLOSSARIO.protagonista.testo.replace(/<\/?p>/g, "")}</dd>
<dt>Comparsa</dt><dd>${GLOSSARIO.comparsa.testo.replace(/<\/?p>/g, "")}</dd>
<dt>Da verificare</dt><dd>${GLOSSARIO.dubbio.testo.replace(/<\/?p>/g, "")}</dd>
<dt>Somiglianza</dt><dd>Quanto un volto assomiglia a quelli che Smista Foto ha imparato per una persona, da 0 a 100%. Sopra una certa soglia l'attribuzione è sicura.</dd>
<dt>Cartella unica</dt><dd>Una cartella senza sottocartelle per evento, come ALLENAMENTI. Le foto hanno la data davanti al nome.</dd>
<dt>Analisi</dt><dd>Il lavoro che Smista Foto fa su una cartella prima della revisione. Resta salvata sul computer, e la revisione si può riprendere quando vuoi.</dd>
</dl></section>
</article></div>`;
    if (sezione) setTimeout(() => document.getElementById("a-" + sezione)?.scrollIntoView(), 30);
  },
};
