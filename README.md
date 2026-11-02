# Smista Foto · Cesena FC

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

## 2. Primo avvio: imparare i volti

Doppio clic su `Avvia_Windows.bat` (o `Avvia_Mac.command`) e scegli **1) Impara i volti**.

Lo script guarda le cartelle in `PLAYERS` e `PLAYERS/_STAFF`, prende circa 30 foto
per persona (soprattutto dal MEDIADAY) e impara chi è il proprietario di ogni cartella.
Scarica solo le anteprime, quindi è leggero. Ci vuole un po' la prima volta;
può andare in sottofondo.

Alla fine segnala:
- **riferimenti deboli**: persone con poche foto utili (succede con lo staff).
  Metti 3-5 primi piani nella cartella `primi_piani/COGNOME/` (es. `primi_piani/D'URBANO/`)
  e rilancia **1**.
- **persone che si assomigliano troppo**: di solito vuol dire che una cartella
  contiene soprattutto foto di un altro. Vanno controllate.

Quando arriva un giocatore nuovo: crea la sua cartella su MEGA come sempre,
mettici qualche foto e rilancia **1**. Impara solo i nuovi.

## 3. Uso dopo ogni partita

1. Avvia e scegli **2) Smista una cartella di foto**.
2. Incolla il percorso della cartella `Foto` della partita. Va bene anche copiato
   dalla barra di MEGA: `Cloud drive > 2026-27 > MATCH > SERIEBKT > G10_Sudtirol_Cesena_1_1 > Foto`.
   Le sottocartelle dei fotografi vengono lette tutte.
3. Conferma il nome della cartella di destinazione (es. `SERIE BKT / G10_SUDTIROL_CESENA`).
4. Lo script scarica e analizza le foto. Intanto puoi fare altro.
5. Si apre la **pagina di revisione** nel browser:
   - **Da verificare**: volti incerti. Clicca "È CIOFI?" se è giusto, oppure scegli
     dall'elenco. Quelli lasciati su "non copiare" non vengono copiati.
   - **Riconosciute**: raggruppate per persona. Clicca una miniatura per escluderla.
     Passando sopra con il mouse vedi la foto intera.
   - **Foto senza nessuno riconosciuto**: se vuoi le assegni a mano.
6. Premi **Copia nelle cartelle**. La copia avviene dentro MEGA (non ricarica le foto).

Se chiudi la pagina prima di copiare, l'analisi non si perde: **3) Riapri la revisione**.

**Nomi dei file:** se la foto è nella sottocartella di un fotografo, il nome diventa
`Rossi_DSC_0412.jpg`, così due fotografi con lo stesso nome file non si sovrascrivono.
Le foto già presenti nella cartella del giocatore vengono saltate, quindi rilanciare
è sicuro.

Ogni volto confermato in revisione migliora il riconoscimento per la volta dopo.

## 4. Prova pilota (per Gianluca)

**4) Prova su una partita già smistata a mano** analizza una partita e confronta il
risultato con le cartelle fatte a mano, **senza copiare nulla**. Dice quante foto
avrebbe messo giuste, quante sbagliate e quante mancate, e salva il dettaglio in
`lavori/<partita>/prova.csv`.

Per una prova onesta, prima di imparare i volti scrivi il nome della partita di prova
in `config.json` → `"escludi_da_imparare": ["G10_SUDTIROL_CESENA"]`, così lo script
non impara proprio dalle foto su cui viene giudicato. Poi rilancia **5) Reimpara tutti**.

## 5. Impostazioni (`config.json`)

| Voce | A cosa serve |
|---|---|
| `cartella_giocatori`, `cartella_staff` | dove sono le cartelle personali (cambiare a ogni stagione) |
| `competizioni` | come si traducono i nomi: `SERIEBKT` → `SERIE BKT`, ecc. |
| `nome_partita` | maiuscolo e senza risultato (`G10_SUDTIROL_CESENA`) |
| `prefisso_fotografo` | aggiunge il nome della sottocartella del fotografo al file |
| `soglia_sicura` | più alta = meno errori ma più foto da verificare |
| `soglia_dubbia` | sotto questa soglia un volto viene ignorato (avversari, pubblico) |
| `modalita` | sempre `megacmd` (`cartella_locale` serve solo per i test) |

## 6. Privacy

- Le impronte dei volti (numeri, non foto) sono salvate solo in `dati/`, e solo per
  giocatori e staff.
- I volti non riconosciuti (avversari, tifosi) vengono scartati subito, senza salvare nulla.
- Le foto scaricate per l'analisi vengono cancellate dopo la copia.

## 7. Problemi frequenti

- **"Non trovo MEGAcmd"**: installalo da https://mega.io/cmd.
- **"MEGAcmd non è collegato"**: apri MEGAcmd e fai `login`.
- **La pagina non si apre**: copia nel browser l'indirizzo `http://127.0.0.1:...` scritto nella finestra.
- **Lento**: è normale alla prima analisi di una partita grande; il computer può essere usato per altro.
