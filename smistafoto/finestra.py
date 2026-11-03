"""Apre l'interfaccia in una finestra del browser. Lancia SOLO il browser del
computer: non ha niente a che fare con MEGA (controllato da tests/test_sicurezza.py)."""

import os
import shutil
import subprocess
import sys
import webbrowser


def apri_finestra(url):
    """Apre l'app in una finestra dedicata (modalità app di Chrome o Edge), se presenti;
    altrimenti nel browser predefinito."""
    candidati = []
    if sys.platform == "darwin":
        for nome in ("Google Chrome", "Microsoft Edge", "Brave Browser"):
            if os.path.exists(f"/Applications/{nome}.app"):
                candidati.append(["open", "-na", nome, "--args", f"--app={url}", "--new-window"])
    elif os.name == "nt":
        for base in (os.environ.get("PROGRAMFILES", ""), os.environ.get("PROGRAMFILES(X86)", ""),
                     os.environ.get("LOCALAPPDATA", "")):
            for rel in (r"Google\Chrome\Application\chrome.exe", r"Microsoft\Edge\Application\msedge.exe"):
                exe = os.path.join(base, rel)
                if base and os.path.exists(exe):
                    candidati.append([exe, f"--app={url}"])
    else:
        for exe in ("google-chrome", "chromium", "chromium-browser"):
            if shutil.which(exe):
                candidati.append([exe, f"--app={url}"])
    for cmd in candidati:
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except OSError:
            continue
    webbrowser.open(url)
