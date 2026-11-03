#!/bin/bash
# Smista Foto · installazione guidata per Mac
# Doppio clic per avviarla. Si può rilanciare quante volte si vuole: rifà solo quello che manca.

cd "$(dirname "$0")" || exit 1
QUI="$(pwd)"
LOG="$QUI/installazione.log"
exec > >(tee -a "$LOG") 2>&1

G=$'\033[1m'; V=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; N=$'\033[0m'
passo() { echo; echo "${G}[$1/6] $2${N}"; }
ok()    { echo "   ${V}✓${N} $1"; }
info()  { echo "   $1"; }
male()  { echo "   ${R}✗ $1${N}"; }
attendi() { echo; read -r -p "   ${Y}$1 Poi premi Invio.${N} " _; }
fine_errore() {
  echo; male "$1"
  echo "   Il dettaglio è nel file installazione.log, in questa cartella."
  echo; read -r -p "Premi Invio per chiudere." _; exit 1
}

clear
echo "${G}SMISTA FOTO · Cesena FC${N}"
echo "Installazione guidata. Ci vogliono pochi minuti e si fa una volta sola."
echo "Ti dico io cosa fare quando serve: segui le istruzioni in giallo."
echo "($(date '+%d/%m/%Y %H:%M'))"

# ------------------------------------------------------------------ 1
passo 1 "Controllo il Mac"
info "macOS $(sw_vers -productVersion 2>/dev/null), processore $(uname -m)"
# i file scaricati da internet sono «in quarantena»: la tolgo da questa cartella
xattr -dr com.apple.quarantine "$QUI" 2>/dev/null && ok "Cartella sbloccata per l'uso"
chmod +x "$QUI"/*.command 2>/dev/null

# ------------------------------------------------------------------ 2
passo 2 "Cerco Python (serve a far girare Smista Foto)"
trova_python() {
  for c in python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3 /usr/local/bin/python3 /opt/homebrew/bin/python3; do
    if command -v "$c" >/dev/null 2>&1; then
      if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        echo "$c"; return 0
      fi
    fi
  done
  return 1
}
PY="$(trova_python)"
TENTATIVI=0
while [ -z "$PY" ]; do
  TENTATIVI=$((TENTATIVI + 1))
  [ $TENTATIVI -gt 3 ] && fine_errore "Non trovo ancora Python 3.10 o più recente."
  male "Python non c'è, oppure è troppo vecchio (serve 3.10 o più recente)."
  info "Ti apro la pagina di download: scarica il pacchetto per macOS e installalo"
  info "come un normale programma (Continua, Accetto, Installa)."
  open "https://www.python.org/downloads/macos/"
  attendi "Installa Python."
  PY="$(trova_python)"
done
ok "Python trovato: $("$PY" --version 2>&1)"

# ------------------------------------------------------------------ 3
passo 3 "Cerco MEGAcmd (serve a leggere e copiare le foto su MEGA)"
MEGACMD_DIR="/Applications/MEGAcmd.app/Contents/MacOS"
TENTATIVI=0
while [ ! -x "$MEGACMD_DIR/mega-whoami" ]; do
  TENTATIVI=$((TENTATIVI + 1))
  [ $TENTATIVI -gt 3 ] && fine_errore "Non trovo ancora MEGAcmd nelle Applicazioni."
  male "MEGAcmd non è installato."
  info "Ti apro la pagina di MEGA: scarica «MEGAcmd» per macOS, apri il file"
  info "e trascina MEGAcmd nella cartella Applicazioni."
  open "https://mega.io/cmd"
  attendi "Installa MEGAcmd."
done
ok "MEGAcmd trovato"

# ------------------------------------------------------------------ 4
passo 4 "Preparo Smista Foto (scarico i componenti, 1-3 minuti)"
if [ ! -x .venv/bin/python ]; then
  "$PY" -m venv .venv || fine_errore "Non riesco a creare l'ambiente di Python."
fi
.venv/bin/python -m pip install --upgrade pip -q || fine_errore "Non riesco ad aggiornare pip. Controlla la connessione a internet."
.venv/bin/python -m pip install -r requirements.txt -q --progress-bar on || fine_errore "Non riesco a scaricare i componenti. Controlla la connessione a internet."
.venv/bin/python -c "import cv2, numpy, PIL; print('   componenti:', 'OpenCV', cv2.__version__)" || fine_errore "I componenti non funzionano."
ok "Smista Foto è pronto"

# ------------------------------------------------------------------ 5
passo 5 "Metto l'icona «Smista Foto» sulla Scrivania"
APP="$HOME/Desktop/Smista Foto.app"
rm -rf "$APP"
if osacompile -o "$APP" -e "do shell script \"open -a Terminal \" & quoted form of \"$QUI/Avvia_Mac.command\"" 2>/dev/null; then
  ok "Icona creata: d'ora in poi apri Smista Foto con un doppio clic sulla Scrivania"
else
  ln -sf "$QUI/Avvia_Mac.command" "$HOME/Desktop/Smista Foto.command" && ok "Collegamento creato sulla Scrivania"
fi

# ------------------------------------------------------------------ 6
passo 6 "Controllo l'accesso a MEGA"
CHI="$(PATH="$MEGACMD_DIR:$PATH" "$MEGACMD_DIR/mega-whoami" 2>&1)"
if echo "$CHI" | grep -q "@"; then
  ok "Collegato a MEGA come $(echo "$CHI" | grep -o '[^ ]*@[^ ]*' | head -1)"
else
  info "Non sei ancora entrato in MEGA con l'account del club. Lo puoi fare anche dopo,"
  info "l'app ti guida. Per farlo adesso:"
  info "  1. si apre MEGAcmd (una finestra nera)"
  info "  2. scrivi:  ${G}login social@cesenafc.com${N}  e premi Invio"
  info "  3. scrivi la password e premi Invio (mentre la scrivi non compare nulla)"
  read -r -p "   Apro MEGAcmd adesso? [S/n] " R1
  if [ "${R1:-s}" != "n" ] && [ "${R1:-s}" != "N" ]; then open -a MEGAcmd 2>/dev/null || open "/Applications/MEGAcmd.app"; fi
fi

echo
echo "${V}${G}Installazione completata.${N}"
echo "Per usare Smista Foto: doppio clic su «Smista Foto» sulla Scrivania."
echo "Si apre una finestra nera (lasciala aperta) e poi l'app."
echo
read -r -p "Avvio Smista Foto adesso? [S/n] " R2
if [ "${R2:-s}" != "n" ] && [ "${R2:-s}" != "N" ]; then
  exec "$QUI/Avvia_Mac.command"
fi
