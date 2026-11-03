# Smista Foto - installazione guidata per Windows (la avvia Installa_Windows.bat)
# Si può rilanciare quante volte si vuole: rifà solo quello che manca.
$ErrorActionPreference = "Continue"
$Qui = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Qui
Start-Transcript -Path (Join-Path $Qui "installazione.log") -Append | Out-Null
$Host.UI.RawUI.WindowTitle = "Smista Foto - installazione"

function Passo($n, $t) { Write-Host ""; Write-Host "[$n/6] $t" -ForegroundColor White -BackgroundColor DarkGray }
function Ok($t)    { Write-Host "   OK  $t" -ForegroundColor Green }
function Info($t)  { Write-Host "   $t" }
function Male($t)  { Write-Host "   X   $t" -ForegroundColor Red }
function Attendi($t) { Write-Host ""; Read-Host "   $t Poi premi Invio" | Out-Null }
function FineErrore($t) {
  Write-Host ""; Male $t
  Write-Host "   Il dettaglio è nel file installazione.log, in questa cartella."
  Read-Host "Premi Invio per chiudere" | Out-Null; Stop-Transcript | Out-Null; exit 1
}

Clear-Host
Write-Host "SMISTA FOTO - Cesena FC" -ForegroundColor White
Write-Host "Installazione guidata. Ci vogliono pochi minuti e si fa una volta sola."
Write-Host "Ti dico io cosa fare quando serve: segui le istruzioni in giallo." -ForegroundColor Yellow

# ------------------------------------------------------------------ 1
Passo 1 "Controllo il computer"
Info ("Windows " + [Environment]::OSVersion.Version + ", " + $env:PROCESSOR_ARCHITECTURE)
Get-ChildItem -Path $Qui -Recurse -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue
Ok "Cartella sbloccata per l'uso"
$winget = [bool](Get-Command winget -ErrorAction SilentlyContinue)

# ------------------------------------------------------------------ 2
Passo 2 "Cerco Python (serve a far girare Smista Foto)"
function TrovaPython {
  $candidati = @()
  if (Get-Command py -ErrorAction SilentlyContinue) { $candidati += ,@("py", "-3") }
  $candidati += ,@("python")
  $candidati += ,@((Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"))
  $candidati += ,@((Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"))
  foreach ($c in $candidati) {
    $exe = $c[0]; $arg = @($c | Select-Object -Skip 1)
    if ($exe -eq "python") {
      $p = Get-Command python -ErrorAction SilentlyContinue
      if (-not $p -or $p.Source -like "*WindowsApps*") { continue }  # collegamento al Microsoft Store, non è Python
    } elseif ($exe -ne "py" -and -not (Test-Path $exe)) { continue }
    & $exe @arg -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) { return ,@($c) }
  }
  return $null
}
$PY = TrovaPython
$tentativi = 0
while (-not $PY) {
  $tentativi++
  if ($tentativi -gt 3) { FineErrore "Non trovo ancora Python 3.10 o più recente." }
  Male "Python non c'è, oppure è troppo vecchio (serve 3.10 o più recente)."
  if ($winget) {
    Info "Lo installo io con winget (Python 3.12). Può comparire una richiesta di conferma: accetta."
    winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")
  } else {
    Info "Ti apro la pagina di download: scarica «Windows installer (64-bit)»."
    Info "Durante l'installazione spunta «Add python.exe to PATH», poi «Install Now»." 
    Start-Process "https://www.python.org/downloads/windows/"
    Attendi "Installa Python."
  }
  $PY = TrovaPython
}
$PYexe = $PY[0]; $PYarg = @($PY | Select-Object -Skip 1)
Ok ("Python trovato: " + (& $PYexe @PYarg --version 2>&1))

# ------------------------------------------------------------------ 3
Passo 3 "Cerco MEGAcmd (serve a leggere e copiare le foto su MEGA)"
function TrovaMega {
  foreach ($d in @((Join-Path $env:LOCALAPPDATA "MEGAcmd"), "C:\Program Files\MEGAcmd", "C:\Program Files (x86)\MEGAcmd")) {
    if (Test-Path (Join-Path $d "mega-whoami.bat")) { return $d }
  }
  return $null
}
$MEGA = TrovaMega
$tentativi = 0
while (-not $MEGA) {
  $tentativi++
  if ($tentativi -gt 3) { FineErrore "Non trovo ancora MEGAcmd." }
  Male "MEGAcmd non è installato."
  Info "Ti apro la pagina di MEGA: scarica «MEGAcmd» per Windows e installalo."
  Start-Process "https://mega.io/cmd"
  Attendi "Installa MEGAcmd."
  $MEGA = TrovaMega
}
Ok "MEGAcmd trovato in $MEGA"

# ------------------------------------------------------------------ 4
Passo 4 "Preparo Smista Foto (scarico i componenti, 1-3 minuti)"
$venvPy = Join-Path $Qui ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
  & $PYexe @PYarg -m venv .venv
  if (-not (Test-Path $venvPy)) { FineErrore "Non riesco a creare l'ambiente di Python." }
}
& $venvPy -m pip install --upgrade pip -q
if ($LASTEXITCODE -ne 0) { FineErrore "Non riesco ad aggiornare pip. Controlla la connessione a internet." }
& $venvPy -m pip install -r requirements.txt -q
if ($LASTEXITCODE -ne 0) { FineErrore "Non riesco a scaricare i componenti. Controlla la connessione a internet." }
& $venvPy -c "import cv2, numpy, PIL; print('   componenti: OpenCV', cv2.__version__)"
if ($LASTEXITCODE -ne 0) { FineErrore "I componenti non funzionano." }
Ok "Smista Foto è pronto"

# ------------------------------------------------------------------ 5
Passo 5 "Metto l'icona «Smista Foto» sulla Scrivania"
try {
  $desk = [Environment]::GetFolderPath("Desktop")
  $sh = New-Object -ComObject WScript.Shell
  $lnk = $sh.CreateShortcut((Join-Path $desk "Smista Foto.lnk"))
  $lnk.TargetPath = Join-Path $Qui "Avvia_Windows.bat"
  $lnk.WorkingDirectory = $Qui
  $lnk.IconLocation = "$env:SystemRoot\System32\imageres.dll,108"
  $lnk.Description = "Smista Foto - Cesena FC"
  $lnk.Save()
  Ok "Icona creata: d'ora in poi apri Smista Foto con un doppio clic sulla Scrivania"
} catch { Male "Non sono riuscito a creare l'icona: usa Avvia_Windows.bat in questa cartella." }

# ------------------------------------------------------------------ 6
Passo 6 "Controllo l'accesso a MEGA"
$env:Path = "$MEGA;" + $env:Path
$chi = (& (Join-Path $MEGA "mega-whoami.bat") 2>&1) -join " "
if ($chi -match "[\w.+-]+@[\w-]+\.[\w.-]+") {
  Ok ("Collegato a MEGA come " + $Matches[0])
} else {
  Info "Non sei ancora entrato in MEGA con l'account del club. Lo puoi fare anche dopo:"
  Info "l'app ti guida. Per farlo adesso:"
  Info "  1. si apre MEGAcmd (una finestra nera)"
  Write-Host "  2. scrivi:  login social@cesenafc.com  e premi Invio" -ForegroundColor Yellow
  Info "  3. scrivi la password e premi Invio (mentre la scrivi non compare nulla)"
  $r = Read-Host "   Apro MEGAcmd adesso? [S/n]"
  if ($r -ne "n" -and $r -ne "N") {
    $shell = Join-Path $MEGA "MEGAcmdShell.exe"
    if (Test-Path $shell) { Start-Process $shell } else { Start-Process (Join-Path $MEGA "MEGAcmdServer.exe") }
  }
}

Write-Host ""
Write-Host "Installazione completata." -ForegroundColor Green
Write-Host "Per usare Smista Foto: doppio clic su «Smista Foto» sulla Scrivania."
Write-Host "Si apre una finestra nera (lasciala aperta) e poi l'app."
Stop-Transcript | Out-Null
$r = Read-Host "Avvio Smista Foto adesso? [S/n]"
if ($r -ne "n" -and $r -ne "N") { Start-Process (Join-Path $Qui "Avvia_Windows.bat") -WorkingDirectory $Qui }
