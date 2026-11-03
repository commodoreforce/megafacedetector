# Smista Foto · Cesena FC

Versione **2.2** · 3 novembre 2026 (il numero compare in alto nel menu e nella pagina di revisione).

Riconosce giocatori e staff nelle foto caricate su MEGA e le copia nelle loro cartelle:

```
2026-27/MATCH/SERIEBKT/G10_Sudtirol_Cesena_1_1/Foto   (dove caricano i fotografi)
        ↓
2026-27/PLAYERS/CIOFI/SERIE BKT/G10_SUDTIROL_CESENA/
2026-27/PLAYERS/_STAFF/DIAMANTI/SERIE BKT/G10_SUDTIROL_CESENA/
```

Tutto gira sul computer: le foto non vengono mandate a nessun servizio esterno.
**Non copia mai niente senza la vostra conferma** nella pagina di revisione.

## Sicurezza del cloud

MEGA è l'archivio storico del club, senza altre copie. Per questo lo script ha regole
rigide scritte nel codice (`smistafoto/mega.py`), controllate prima di ogni comando:

- **Usa solo comandi di lettura e di creazione**: `whoami`, `ls`, `find`, `get`, `preview`,
  `mkdir`, `cp`. Qualsiasi altro comando di MEGAcmd (cancellare, spostare, caricare,
  sincronizzare, condividere...) viene rifiutato prima di partire.
- **Non cancella, non sposta e non rinomina nulla su MEGA.** Non esiste nessuna
  funzione che lo faccia.
- **Non sovrascrive mai**: prima di ogni copia verifica che il file non esista già.
  Se esiste, o se la verifica non riesce, la copia non si fa.
- **Scrive solo dentro `PLAYERS/<NOME>/<COMPETIZIONE>/<EVENTO>/`.** Le cartelle `MATCH`
  vengono solo lette.
- Percorsi con `..` o caratteri jolly (`*`, `?`) sono rifiutati.

Il file `tests/test_sicurezza.py` prova tutte queste regole senza toccare MEGA:
`python3 tests/test_sicurezza.py` deve finire con **TUTTO OK**.

Una cosa resta fuori dal controllo dello script: chi usa MEGAcmd a mano, nella sua
finestra, ha tutti i permessi dell'account. Nella finestra di MEGAcmd non va scritto
nessun comando oltre a `login`.

---

## 1. Installazione (una volta sola)

**Servono due programmi:**

1. **Python** da https://www.python.org/downloads/
   Su Windows, durante l'installazione spunta **"Add python.exe to PATH"**.
2. **MEGAcmd** da https://mega.io/cmd (lo strumento di MEGA da riga di comando).

**Poi colleghi MEGAcmd all'account del club:** apri MEGAcmd, scrivi
`login email@delclub.it` e inserisci la password quando la chiede. Resta collegato
anche dopo aver riavviato il computer.

**Infine installi lo script:**
- **Windows:** doppio clic su `Installa_Windows.bat`
- **Mac:** doppio clic su `Installa_Mac.command`.
  La prima volta il Mac può bloccarlo: clic destro sul file → **Apri** → **Apri**.

## 2. Come si usa

Doppio clic su `Avvia_Mac.command` (o `Avvia_Windows.bat`). Si apre una finestra del
Terminale **da lasciare aperta** e, dopo un attimo, l'app nel browser
(indirizzo `http://127.0.0.1:8765`, raggiungibile solo da questo computer).

In alto c'è il numero di versione e il **semaforo di MEGA**: verde = collegato,
giallo = controllo in corso, rosso = non collegato (in quel caso l'app ricontrolla da
sola ogni 15 secondi, e nel registro mostra la risposta di MEGAcmd).
A destra, **«Cosa sta facendo»** mostra la fase, una barra di avanzamento e il registro
di ogni passo. Lo stesso registro compare anche nel Terminale.

### Prima volta: imparare i volti

Premi **«Impara i volti nuovi»**. Lo script legge le cartelle in `PLAYERS` e
`PLAYERS/_STAFF`, prende circa 30 foto per persona (soprattutto dal MEDIADAY) e impara
chi è il proprietario di ogni cartella. Su MEGA legge soltanto; scarica solo anteprime
leggere e le cancella subito.

Alla fine può segnalare:
- **riconoscimento debole**: persone con poche foto utili (succede con lo staff).
  Apri **«Elenco delle persone»**, premi **«Primi piani…»** accanto al nome, scegli
  3-5 foto in cui si vede bene il volto e confermi di reimpararlo.
- **cartelle che non sono persone** (es. `00VARIE`): nell'elenco premi **«Escludi»**.
  Su MEGA non cambia nulla, lo script semplicemente la ignora.
- **persone che si assomigliano troppo**: di solito una cartella contiene soprattutto
  foto di un altro. Va controllata.

Quando arriva qualcuno di nuovo, crea la sua cartella su MEGA come sempre e premi di
nuovo «Impara i volti nuovi»: impara solo i nuovi.

### Dopo ogni partita

1. In **«Smista una partita»** premi **«Sfoglia le cartelle su MEGA…»**, entra nella
   competizione e nella partita, apri la cartella **Foto** e premi **«Usa questa cartella»**.
   (Si può anche incollare il percorso a mano.)
2. Controlla la destinazione proposta (es. `PLAYERS / <NOME> / SERIE BKT / G10_SUDTIROL_CESENA`)
   e premi **«Avvia lo smistamento»**. Lo script scarica e analizza una foto alla volta.
3. Alla fine premi **«Apri la revisione»**:
   - **Da verificare**: volti incerti. Clicca "È CIOFI?" se è giusto, oppure scegli
     dall'elenco. Quelli lasciati su "non copiare" non vengono copiati.
   - **Riconosciute**: raggruppate per persona. Clicca una miniatura per escluderla.
     Passando sopra con il mouse vedi la foto intera.
   - **Foto senza nessuno riconosciuto**: se vuoi le assegni a mano.
4. Se vuoi essere sicuro, premi prima **«Simula (non copia nulla)»**: lo script fa tutti
   i controlli della copia vera ma su MEGA legge soltanto, e mostra per ogni persona
   la cartella di destinazione, quante foto verrebbero copiate, quante saltate perché
   già presenti, quali cartelle verrebbero create e se qualcosa verrebbe bloccato dalle
   regole di sicurezza. Il dettaglio foto per foto è anche in `lavori/<partita>/simulazione.csv`.
5. Premi **«Copia nelle cartelle»**. La copia avviene dentro MEGA.

Le analisi restano in **«Analisi recenti»**: si può riaprire la revisione in un secondo momento.

**Nomi dei file:** se la foto è nella sottocartella di un fotografo, il nome diventa
`Rossi_DSC_0412.jpg`, così due fotografi con lo stesso nome file non si sovrascrivono.
Le foto già presenti nella cartella del giocatore vengono saltate.

**Protagonisti e comparse:** si smistano solo le foto in cui la persona è almeno un po'
protagonista. Per ogni volto lo script misura quanto è grande (rispetto alla foto e al
volto più grande) e quanto è a fuoco. Chi è riconosciuto ma è una comparsa finisce nella
sezione chiusa **«Comparse»** della revisione e non viene copiato, a meno di cliccarlo.
La regola si sceglie dalla prova pilota (tabella **«Regole proposte»**, pulsante **«Usa questa»**).
Con prove su almeno due partite, in «Analisi recenti» compare **«Calcola la regola su tutte le
prove»**: la regola viene scelta perché funzioni su tutte, e per ognuna si vedono i numeri.

**Nomi nel file:** se il fotografo ha scritto un cognome nel nome del file
(es. `775A5531.Mangraviti.jpg`) e il volto non è stato riconosciuto, la foto compare tra
quelle **da verificare** con quel nome come suggerimento. Il nome nel file non basta mai
da solo per copiare, perché a volte è sbagliato.

Ogni volto confermato in revisione migliora il riconoscimento per la volta dopo.

### Prova pilota

Dopo «Controlla», apri **«Prova su una partita già smistata a mano»** e premi
**«Fai la prova»**. Lo script analizza la partita e confronta il risultato con le cartelle
fatte a mano, **senza copiare nulla**: mostra precisione, assegnazioni sbagliate e
mancate. Trova da solo la cartella della partita e ignora i volti imparati proprio da
quella partita, così la prova è onesta. Il dettaglio per persona è in
`lavori/<partita>/prova.csv`.

## Il modello di riconoscimento

- **I volti si trovano** con YuNet (OpenCV, licenza Apache 2.0), incluso nel pacchetto.
- **I volti si riconoscono** con **AuraFace v1** (rete ResNet100 di tipo ArcFace, licenza
  Apache 2.0, pensata per l'uso commerciale): https://huggingface.co/fal/AuraFace-v1.
  Si usa solo il file di riconoscimento (`glintr100.onnx`); gli altri file di quel
  repository non si usano perché la loro licenza non è indicata.
- Il modello (circa 260 MB) **si scarica da solo al primo avvio** e resta nella cartella
  `modelli/`. Tutto gira sul computer: le foto non vengono mandate a nessun servizio.
- Con `"modello": "sface"` in `config.json` si torna al modello precedente, più leggero
  ma molto meno preciso. Le impronte dei due modelli sono salvate in file separati.

## 3. Impostazioni (`config.json`)

| Voce | A cosa serve |
|---|---|
| `cartella_partite` | da dove parte «Sfoglia» (es. `/2026-27/MATCH`) |
| `cartella_giocatori`, `cartella_staff` | dove sono le cartelle personali (cambiare a ogni stagione) |
| `competizioni` | come si traducono i nomi: `SERIEBKT` → `SERIE BKT`, ecc. |
| `nome_partita` | maiuscolo e senza risultato (`G10_SUDTIROL_CESENA`) |
| `prefisso_fotografo` | aggiunge il nome della sottocartella del fotografo al file |
| `protagonista` | `relativa_min`, `frazione_min`, `nitidezza_min`: quando un volto conta come protagonista. Di solito si imposta dalla prova con «Usa questa» |
| `modello` | `auraface` (predefinito) oppure `sface` |
| `soglie` | per modello, es. `"soglie": {"auraface": {"soglia_sicura": 0.45}}`. `soglia_sicura`: più alta = meno errori ma più foto da verificare; `soglia_dubbia`: sotto, un volto viene ignorato; `margine`: distacco minimo dal secondo candidato. La tabella «Taratura» della prova dice quale soglia conviene |
| `modalita` | sempre `megacmd` (`cartella_locale` serve solo per i test) |

## 4. Privacy

- Le impronte dei volti (numeri, non foto) sono salvate solo in `dati/`, e solo per
  giocatori e staff.
- I volti non riconosciuti (avversari, tifosi) vengono scartati subito, senza salvare nulla.
- Le foto scaricate per l'analisi vengono cancellate dopo la copia.

## 5. Problemi frequenti

- **"Non trovo MEGAcmd"**: installalo da https://mega.io/cmd.
- **"MEGAcmd non è collegato"**: apri MEGAcmd e fai `login`.
- **La pagina non si apre**: apri nel browser `http://127.0.0.1:8765`.
- **Lento**: è normale alla prima analisi di una partita grande; il computer può essere usato per altro.

## Versioni

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
