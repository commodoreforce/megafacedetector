# Smista Foto · Cesena FC

Versione **3.2** · 12 novembre 2026

Smista Foto guarda le foto caricate dai fotografi su MEGA, riconosce giocatori e staff e
copia ogni foto nella cartella personale di chi ne è protagonista:

```
2026-27/MATCH/SERIEBKT/G10_Sudtirol_Cesena_1_1/Foto       →  PLAYERS/BIANCHI/SERIE BKT/G10_SUDTIROL_CESENA/
2026-27/ALLENAMENTI/2026_11_Novembre/20261102              →  PLAYERS/BIANCHI/ALLENAMENTI/20261102_IMG_5169.jpg
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
La pagina **Cartelle** mostra tutte le cartelle caricate dai fotografi e quali sono già state smistate.

## Nuovo computer

I volti imparati, la regola scelta e le cartelle escluse stanno nella cartella `dati/`, solo
su quel computer. Su un computer nuovo: installa, poi **copia la cartella `dati/`** (e
`primi_piani/`, se ci sono) da un computer già configurato, prima del primo avvio. Così non serve
rifare l'apprendimento. Contengono le impronte dei volti: passale con una chiavetta o una cartella
interna, mai su GitHub o in chat.

## Aggiornamento

Doppio clic su **`Aggiorna_Mac.command`** o **`Aggiorna_Windows.bat`**. Le scelte fatte
nell'app (`dati/`), le analisi (`lavori/`) e i primi piani (`primi_piani/`) restano.

## Sicurezza dell'archivio

MEGA è l'archivio storico del club, senza altre copie. Smista Foto ha regole rigide scritte
nel programma (`smistafoto/mega.py`), controllate prima di ogni comando:

- **Usa solo comandi di lettura e di creazione**: `whoami`, `ls`, `find`, `get`, `preview`,
  `mkdir`, `cp`. Qualsiasi altro comando di MEGAcmd viene rifiutato prima di partire.
- **Non cancella, non sposta e non rinomina nulla su MEGA.** Non esiste nessuna funzione che lo faccia.
- **Non sovrascrive mai**: prima di ogni copia verifica che il file non esista già; nel dubbio non copia.
- **Scrive solo in `PLAYERS/<NOME>/<COMPETIZIONE>/<EVENTO>/`** oppure direttamente in
  `PLAYERS/<NOME>/ALLENAMENTI/` (le «cartelle uniche» di `config.json`, senza sottocartelle).
  Le cartelle dei fotografi vengono solo lette.
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

## Privacy

- Le «impronte» dei volti sono numeri, non foto, e restano solo in `dati/`, solo per giocatori e staff.
- I volti non riconosciuti (avversari, tifosi) vengono scartati subito.
- Le foto scaricate per l'analisi vengono cancellate subito dopo; restano solo miniature in `lavori/`.
- `dati/`, `lavori/` e `primi_piani/` sono esclusi dal repository.

## Struttura

```
smista.py                 avvio
smistafoto/mega.py        accesso a MEGA con le regole di sicurezza
smistafoto/volti.py       riconoscimento dei volti
smistafoto/flussi.py      imparare, analizzare, simulare, copiare, provare
smistafoto/app.py         server locale dell'interfaccia
smistafoto/web/           interfaccia (HTML, CSS, JavaScript, guida)
tests/test_sicurezza.py   verifica delle regole di sicurezza
installazione/            icona dell'app (scudetto del Cesena FC) per Mac e Windows
```

## Versioni

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
