"""Registro delle attività: righe leggibili con l'ora, più lo stato di avanzamento.
Lo leggono sia la finestra del Terminale sia l'app nel browser."""

import threading
import time


class Registro:
    def __init__(self):
        self._lucchetto = threading.Lock()
        self.righe = []
        self.fase = ""
        self.i = 0
        self.n = 0
        self.dettaglio = ""
        self.inizio_fase = time.time()

    def _scrivi(self, testo, tipo):
        ora = time.strftime("%H:%M:%S")
        with self._lucchetto:
            self.righe.append({"ora": ora, "testo": testo, "tipo": tipo})
            del self.righe[:-2000]
        segno = {"avviso": "⚠ ", "errore": "✖ ", "ok": "✓ "}.get(tipo, "")
        print(f"[{ora}] {segno}{testo}", flush=True)

    def info(self, testo):
        self._scrivi(testo, "info")

    def ok(self, testo):
        self._scrivi(testo, "ok")

    def avviso(self, testo):
        self._scrivi(testo, "avviso")

    def errore(self, testo):
        self._scrivi(testo, "errore")

    def inizia_fase(self, fase, n=0):
        self.fase, self.i, self.n, self.dettaglio = fase, 0, n, ""
        self.inizio_fase = time.time()

    def passo(self, i, dettaglio=""):
        self.i, self.dettaglio = i, dettaglio
        if self.n and (i == self.n or i % max(1, self.n // 10) == 0):
            print(f"           … {self.fase}: {i}/{self.n}", flush=True)

    def stato(self, dalla=0):
        with self._lucchetto:
            return {"fase": self.fase, "i": self.i, "n": self.n, "dettaglio": self.dettaglio,
                    "secondi_fase": round(time.time() - self.inizio_fase, 1),
                    "righe": self.righe[dalla:], "totale_righe": len(self.righe)}
