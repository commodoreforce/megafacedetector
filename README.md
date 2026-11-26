# Smista Foto · Cesena FC

Versione **3.5** · 26 novembre 2026

Smista Foto guarda le foto caricate dai fotografi su MEGA, riconosce giocatori e staff e
copia ogni foto nella cartella personale di chi ne è protagonista:

```
2026-27/MATCH/SERIEBKT/G10_Sudtirol_Cesena_1_1/Foto       →  PLAYERS/BIANCHI/SERIE BKT/G10_SUDTIROL_CESENA/
2026-27/ALLENAMENTI/2026_11_Novembre/20261102              →  PLAYERS/BIANCHI/ALLENAMENTI/20261102_IMG_5169.jpg
```

Trova anche gli **sponsor** nelle foto (maglie, cartelloni fissi e luminosi) e mette le foto
migliori di ognuno nella sua cartella, quante ne hai chieste:

```
2026-27/MATCH/SERIEBKT/G10_Sudtirol_Cesena_1_1/Foto       →  SPONSOR/AMADORI/SERIE BKT/G10_SUDTIROL_CESENA/  (es. le 4 migliori)
```

Gira tutto sul computer: le foto non vengono mandate a nessun servizio esterno.
**Non copia niente senza la tua conferma**, e prima di copiare mostra sempre il riepilogo.

La guida completa è dentro l'app, alla voce **Aiuto**.

## Installazione (una volta sola)

| | Mac | Windows |
|---|---|---|
| 1 | Scarica la cartella (da GitHub: **Code › Download ZIP**, oppure `git clone`) | uguale |
| 2 | Doppio clic su **`Installa_Mac.command`**. Se il Mac lo blocca: clic destro › **Apri** › **Apri** | Doppio clic su **`Installa_Windows.bat`** |
| 3 | Segui le istruzioni in giallo | uguale |

L'installazione guidata controlla e installa quello che manca, in sei passi:
Python (3.10 o più recente), MEGAcmd (il programma ufficiale di MEGA), i componenti di
Smista Foto, l'icona **Smista Foto** sulla Scrivania e l'accesso a MEGA. Si può rilanciare
quando si vuole: rifà solo quello che manca. Il registro è nel file `installazione.log`.

Al primo avvio l'app completa la configurazione: scarica il modello di riconoscimento
(circa 260 MB) e impara i volti dalle cartelle `PLAYERS` e `PLAYERS/_STAFF` (10-20 minuti).

## Uso

Doppio clic su **Smista Foto** sulla Scrivania. Si apre una finestra nera, da **lasciare
aperta** (è il motore dell'app), e poi l'app.

1. **Smista foto** › scegli la cartella su MEGA › controlla la destinazione › **Avvia l'analisi**.
2. Puoi fare altro: quando ha finito compare un avviso.
3. **Revisione**: decidi i volti da verificare (tasti `1` `2` `3`, `0`), escludi con un clic
   quello che non va, poi **Controlla e copia** › riepilogo › **Copia su MEGA**.

Le revisioni non finite restano in **Revisioni** e si riprendono da dove le avevi lasciate.

### Sponsor

Ogni sponsor è una cartella in `SPONSOR` su MEGA, accanto a `PLAYERS`: Smista Foto la trova da
sola e aggiunge gli sponsor che contiene. Nella pagina **Sponsor**:

- **Foto a partita / ad allenamento**: quante foto proporre (di solito tra 2 e 10, ma è libero).
- **Modifica**: le scritte da cercare (es. `DOLOMIA, ACQUA DOLOMIA`) e le immagini del logo.
  «Cerca anche il disegno del logo» serve per loghi senza scritte o molto stilizzati.
- **Aggiungi sponsor**: per un'azienda nuova. Se la cartella su MEGA non c'è, viene creata alla prima copia.
- **Prova su una foto**: carichi una foto e vedi cosa legge e quali sponsor trova.
- **Metti in pausa**: lo sponsor non viene più cercato, senza perdere le impostazioni.

Nello smistamento resta spuntato «Cerca anche gli sponsor» (circa un secondo in più a foto). Nella
revisione, per ogni sponsor, ci sono le foto scelte (logo grande, nitido e leggibile, meglio con
un nostro giocatore protagonista, niente doppioni della stessa raffica, maglie e cartelloni
insieme) e le altre in cui c'è il logo: un clic per togliere o aggiungere.
La pagina **Cartelle** mostra tutte le cartelle caricate dai fotografi e quali sono già state smistate.

## Nuovo computer

I volti imparati, la regola scelta e le cartelle escluse stanno nelle cartelle `dati/` e
`primi_piani/`, solo su quel computer. Per non rifare l'apprendimento su un computer nuovo:

1. sul computer già configurato: **Giocatori e staff → Esporta i volti** (il file
   `SmistaFoto_volti_AAAAMMGG.zip` finisce nei Download);
2. sul computer nuovo, dopo l'installazione: **Importa i volti** (nella pagina Inizio durante la
   prima configurazione, oppure in Giocatori e staff) e scegli il file.

L'importazione sostituisce i volti del computer, dopo averne salvato una copia in `backup_volti/`.
Accetta solo file creati con «Esporta i volti» e scrive solo in `dati/` e `primi_piani/`; non usa
MEGA. Il file contiene le impronte dei volti: spostalo con una chiavetta o una cartella interna,
mai su GitHub, per email o in chat, e cancellalo dopo l'uso.

## Aggiornamento

Dentro l'app, in basso a sinistra, c'è il pulsante **Aggiorna**: diventa giallo quando su
GitHub c'è una versione nuova (il controllo è automatico all'avvio e ogni 6 ore). Mostra le novità
e, con **Aggiorna ora**:

1. scarica i file nuovi (con git se la cartella è una copia git, altrimenti con lo zip di GitHub);
2. chiude l'app e aggiorna i componenti Python (`requirements.txt`) ad app chiusa, perché su
   Windows i componenti in uso non si possono sostituire;
3. riapre l'app, e la pagina si ricarica da sola.

Se lo scaricamento dei componenti non riesce, o se la nuova versione non parte, torna da solo
alla versione di prima. Le scelte fatte nell'app (`dati/`), le analisi (`lavori/`), i primi piani,
i loghi e l'ambiente Python (`.venv/`) non vengono toccati. Su MEGA non cambia nulla.

Il pulsante funziona quando l'app è aperta con l'icona sulla Scrivania (o con `Avvia_*`). Se l'app
non si apre, restano **`Aggiorna_Mac.command`** e **`Aggiorna_Windows.bat`** nella cartella di
Smista Foto. MEGAcmd si aggiorna a parte, dal sito di MEGA.

## Sicurezza dell'archivio

MEGA è l'archivio storico del club, senza altre copie. Smista Foto ha regole rigide scritte
nel programma (`smistafoto/mega.py`), controllate prima di ogni comando:

- **Usa solo comandi di lettura e di creazione**: `whoami`, `ls`, `find`, `get`, `preview`,
  `mkdir`, `cp`. Qualsiasi altro comando di MEGAcmd viene rifiutato prima di partire.
- **Non cancella, non sposta e non rinomina nulla su MEGA.** Non esiste nessuna funzione che lo faccia.
- **Non sovrascrive mai**: prima di ogni copia verifica che il file non esista già; nel dubbio non copia.
- **Scrive solo in `PLAYERS/<NOME>/<COMPETIZIONE>/<EVENTO>/`** oppure direttamente in
  `PLAYERS/<NOME>/ALLENAMENTI/` (le «cartelle uniche» di `config.json`, senza sottocartelle), e
  con le stesse regole in `SPONSOR/<NOME>/<COMPETIZIONE>/<EVENTO>/` o `SPONSOR/<NOME>/ALLENAMENTI/`.
  La cartella SPONSOR deve essere specifica e separata da PLAYERS. Le cartelle dei fotografi
  vengono solo lette e non possono stare dentro PLAYERS o SPONSOR.
- Percorsi con `..` o caratteri jolly (`*`, `?`) sono rifiutati.
- L'interfaccia risponde solo da questo computer (`127.0.0.1`).

`python3 tests/test_sicurezza.py` prova tutte queste regole senza toccare MEGA e deve finire con
**TUTTO OK**.

Resta fuori dal controllo dello script solo la finestra di MEGAcmd: da lì si hanno tutti i
permessi dell'account. Nella finestra di MEGAcmd non va scritto nessun comando oltre a `login`.

## Il modello di riconoscimento

- I volti si **trovano** con YuNet (OpenCV, Apache 2.0), incluso nel pacchetto.
- I volti si **riconoscono** con **AuraFace v1** (ResNet100 di tipo ArcFace, Apache 2.0,
  pensato per l'uso commerciale): https://huggingface.co/fal/AuraFace-v1. Si usa solo il file
  di riconoscimento (`glintr100.onnx`); gli altri file di quel repository non hanno una licenza
  indicata e non si usano. Si scarica da solo al primo avvio in `modelli/`.
- Le **scritte degli sponsor** si leggono con i modelli PP-OCRv3 di PaddleOCR (Apache 2.0,
  inclusi in `modelli/testo_*`), eseguiti con OpenCV: nessun programma in più da installare.
  Il disegno del logo si cerca con SIFT (OpenCV).
- Una foto va a una persona solo se lì è **almeno un po' protagonista** (volto tra i più grandi
  della foto, non minuscolo, abbastanza a fuoco). La regola predefinita è stata scelta con le
  prove sulle partite; si può ritarare da **Prove e regole**.

## Impostazioni

Non modificare `config.json` a mano: le scelte fatte dall'app vanno in
`dati/impostazioni_locali.json`, solo su quel computer, e hanno la precedenza.

| Voce di `config.json` | A cosa serve |
|---|---|
| `cartella_giocatori`, `cartella_staff` | dove sono le cartelle personali (da cambiare a ogni stagione) |
| `cartella_partite`, `cartella_allenamenti` | dove caricano i fotografi |
| `cartelle_uniche` | cartelle senza sottocartella per evento, es. `["ALLENAMENTI"]` |
| `competizioni` | come si traducono i nomi: `SERIEBKT` › `SERIE BKT`, ecc. |
| `nome_partita` | maiuscolo e senza risultato (`G10_SUDTIROL_CESENA`) |
| `prefisso_fotografo` | aggiunge il nome della sottocartella del fotografo al file |
| `modello` | `auraface` (predefinito) oppure `sface` (più leggero, meno preciso) |
| `soglie`, `protagonista` | la regola predefinita; di solito si cambia da «Prove e regole» |
| `cartella_sponsor` | facoltativa: di solito si trova da sola (`SPONSOR` nella cartella della stagione) |
| `lato_lungo_sponsor` | a che dimensione si leggono le scritte (predefinito 2048 px) |

## Privacy

- Le «impronte» dei volti sono numeri, non foto, e restano solo in `dati/`, solo per giocatori e staff.
- I volti non riconosciuti (avversari, tifosi) vengono scartati subito.
- Le foto scaricate per l'analisi vengono cancellate subito dopo; restano solo miniature in `lavori/`.
- `dati/`, `lavori/`, `primi_piani/` e `loghi/` sono esclusi dal repository.

## Struttura

```
smista.py                 avvio: apre l'app e, dopo un aggiornamento, aggiorna i componenti e la riapre
smistafoto/aggiornamento.py  aggiornamento del programma da GitHub
smistafoto/mega.py        accesso a MEGA con le regole di sicurezza
smistafoto/volti.py       riconoscimento dei volti
smistafoto/sponsor.py     sponsor: lettura delle scritte, disegno del logo, scelta delle foto migliori
smistafoto/flussi.py      imparare, analizzare, simulare, copiare, provare
smistafoto/app.py         server locale dell'interfaccia
smistafoto/web/           interfaccia (HTML, CSS, JavaScript, guida)
tests/test_sicurezza.py   verifica delle regole di sicurezza
installazione/            icona dell'app (scudetto del Cesena FC) per Mac e Windows
```

## Versioni

- **3.5** (26 novembre 2026): pulsante «Aggiorna» dentro l'app (in basso a sinistra): controlla da solo se c'è una versione nuova, mostra le novità, scarica la versione da GitHub (con git o con lo zip), aggiorna i componenti ad app chiusa e la riapre; se qualcosa non va torna alla versione di prima. Gli script di avvio e di aggiornamento ora si possono sostituire anche mentre sono aperti.
- **3.4** (26 novembre 2026): sponsor. Pagina «Sponsor» (scritte da cercare, loghi, foto a partita e ad allenamento, pausa, prova su una foto); nello smistamento Smista Foto legge le scritte e propone le foto migliori per ogni sponsor, che vanno in SPONSOR/<NOME>/<COMPETIZIONE>/<EVENTO> o SPONSOR/<NOME>/ALLENAMENTI dopo la revisione, con la stessa simulazione e le stesse regole di sicurezza; i loghi passano su un altro computer con «Esporta i volti». Richiede OpenCV 5: «Aggiorna» lo installa da solo.
- **3.3.1** (13 novembre 2026): i modelli si caricano anche se il percorso della cartella contiene lettere accentate (es. «OneDrive - Università di …» su Windows); avviso, nell'app e nell'installazione, se Smista Foto è dentro OneDrive, iCloud, Dropbox o Google Drive.
- **3.3** (12 novembre 2026): «Esporta i volti» e «Importa i volti» per portare volti, primi piani e regole su un altro computer senza rifare l'apprendimento; copia di sicurezza automatica prima di importare; il test di sicurezza verifica che un archivio manomesso venga rifiutato.
- **3.2.1** (12 novembre 2026): «Aggiorna» funziona anche quando la cronologia del repository viene ripulita.
- **3.2** (12 novembre 2026): pagina «Cartelle» con lo stato di ogni partita e allenamento (copiata, già nelle cartelle dei giocatori, da confermare, da smistare) e «Smista» diretto; l'email di MEGA non è più scritta nel programma (si inserisce nell'app e resta sul computer); nomi inventati negli esempi; il test di sicurezza controlla che nel repository non finiscano email.
- **3.1** (3 novembre 2026): marchio con lo scudetto del Cesena FC nell'app, nell'icona della scheda e nell'icona sulla Scrivania (Mac e Windows; per averla rilanciare l'installazione).
- **3.0** (3 novembre 2026): interfaccia ridisegnata con procedura guidata (cartella, destinazione, analisi, revisione), prima configurazione nell'app, revisione da tastiera con anteprima grande e volto evidenziato, annulla, scelte salvate da sole, copia sempre preceduta dal riepilogo, guida integrata con spiegazioni «?», tema chiaro/scuro; installazione e aggiornamento guidati per Mac e Windows con icona sulla Scrivania; regola del protagonista predefinita; corretto il conteggio «già presenti» dopo la copia.
- **2.3.1** (3 novembre 2026): la regola scelta con «Usa questa» si salva in `dati/impostazioni_locali.json` e non più in `config.json`, così `git pull` non si blocca.
- **2.3** (3 novembre 2026): smistamento degli allenamenti nella cartella unica PLAYERS/<NOME>/ALLENAMENTI, con la data davanti al nome dei file; «Sfoglia» parte dalla stagione.
- **2.2** (3 novembre 2026): «Calcola la regola su tutte le prove»: la regola del protagonista si sceglie su più partite insieme, con i numeri di ciascuna.
- **2.1** (3 novembre 2026): regola del «protagonista» (grandezza e nitidezza del volto): le comparse non vengono smistate; la prova propone le regole migliori e si applicano con un clic.
- **2.0** (2 novembre 2026): nuovo modello di riconoscimento AuraFace (molto più preciso con profili, cappellini e foto difficili); taratura delle soglie nella prova. Dopo l'aggiornamento: rilanciare l'installazione e reimparare i volti.
- **1.11** (2 novembre 2026): il nome nel file è solo un suggerimento tra i volti da verificare, mai un'assegnazione sicura (i fotografi a volte sbagliano).
- **1.10** (2 novembre 2026): se il fotografo ha scritto il cognome nel nome del file, la foto va a quella persona; corretto il filtro «solo le rosse».
- **1.9.1** (2 novembre 2026): corretta la pagina di revisione che restava vuota quando c'erano volti da verificare.
- **1.9** (2 novembre 2026): la revisione di una prova segna in verde i volti che coincidono con lo smistamento a mano e in rosso gli altri, con la larghezza di ogni volto.
- **1.8** (2 novembre 2026): «Simula» nella revisione: mostra cosa farebbe la copia, senza scrivere su MEGA.
- **1.7** (2 novembre 2026): pulsante «Sfoglia» per scegliere la cartella della partita su MEGA senza scriverla.
- **1.6** (2 novembre 2026): elenco delle persone nell'app, con «Escludi» per le cartelle che non sono persone e caricamento dei primi piani dal browser; corrette le righe di intestazione di MEGAcmd lette come nomi.
- **1.5** (2 novembre 2026): corretto il collegamento a MEGAcmd sul Mac ("mega-exec: command not found").
- **1.4** (2 novembre 2026): semaforo del collegamento a MEGA, ricontrollo automatico, riconoscimento più robusto dell'account collegato.
- **1.3** (2 novembre 2026): l'app si usa dal browser, con pulsanti, barra di avanzamento e registro leggibile; le foto si scaricano e si analizzano una alla volta.
- **1.2** (2 novembre 2026): la prova pilota esclude da sola la partita di prova; numero di versione nel menu.
- **1.1** (2 novembre 2026): regole di sicurezza rigide per MEGA.
- **1.0** (2 novembre 2026): prima versione.
