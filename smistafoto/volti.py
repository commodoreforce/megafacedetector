"""Riconoscimento dei volti con i modelli di OpenCV (YuNet per trovarli,
SFace per riconoscerli). Tutto gira sul computer: nessun servizio esterno."""

import json
import os

import cv2
import numpy as np
from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = None
try:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
except AttributeError:
    pass

MODELLO_TROVA = "face_detection_yunet_2023mar.onnx"
MODELLO_RICONOSCI = "face_recognition_sface_2021dec.onnx"


class Volti:
    def __init__(self, cartella_modelli, cfg):
        self.cfg = cfg
        self.trova = cv2.FaceDetectorYN.create(
            os.path.join(cartella_modelli, MODELLO_TROVA), "", (320, 320), 0.8, 0.3, 5000)
        self.riconosci = cv2.FaceRecognizerSF.create(
            os.path.join(cartella_modelli, MODELLO_RICONOSCI), "")

    def carica(self, percorso):
        """Apre la foto girata nel verso giusto, ridotta quanto basta."""
        lato = self.cfg["lato_lungo_analisi"]
        im = Image.open(percorso)
        w, h = im.size
        k = max(w, h) / (lato * 1.5)
        if k >= 2 and im.format == "JPEG":
            im.draft("RGB", (int(w / k), int(h / k)))
        im = ImageOps.exif_transpose(im).convert("RGB")
        return np.asarray(im)[:, :, ::-1].copy()

    def analizza(self, percorso, minimo=None):
        """Restituisce (volti, immagine). Ogni volto: riquadro, affidabilità, impronta."""
        minimo = minimo or self.cfg["volto_minimo_px"]
        try:
            grande = self.carica(percorso)
        except Exception:
            return [], None
        h, w = grande.shape[:2]
        s = min(1.0, self.cfg["lato_lungo_analisi"] / max(h, w))
        piccola = cv2.resize(grande, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else grande
        self.trova.setInputSize((piccola.shape[1], piccola.shape[0]))
        _, trovati = self.trova.detect(piccola)
        risultato = []
        for f in trovati if trovati is not None else []:
            f = f.copy()
            f[:14] /= s
            x, y, fw, fh = (float(v) for v in f[:4])
            if fw < minimo:
                continue
            allineato = self.riconosci.alignCrop(grande, f)
            e = self.riconosci.feature(allineato).flatten().astype(np.float32)
            e /= np.linalg.norm(e) + 1e-9
            risultato.append({"riquadro": [x, y, fw, fh], "affidabilita": float(f[14]), "impronta": e})
        risultato.sort(key=lambda v: -v["riquadro"][2])
        return risultato, grande


class Riferimenti:
    """Le impronte dei volti di giocatori e staff, salvate in dati/."""

    def __init__(self, cartella_dati):
        self.cartella = cartella_dati
        os.makedirs(cartella_dati, exist_ok=True)
        self.file_json = os.path.join(cartella_dati, "riferimenti.json")
        self.file_npz = os.path.join(cartella_dati, "riferimenti.npz")
        self.info = {}      # nome -> {tipo, cartella, imparate, confermate, fonti}
        self.impronte = {}  # nome -> matrice N x 128
        if os.path.exists(self.file_json):
            with open(self.file_json, encoding="utf-8") as f:
                self.info = json.load(f)
            dati = np.load(self.file_npz)
            for nome, i in self.info.items():
                self.impronte[nome] = dati[i["chiave"]]

    def salva(self):
        matrici = {}
        for n, (nome, i) in enumerate(sorted(self.info.items())):
            i["chiave"] = f"p{n}"
            matrici[i["chiave"]] = self.impronte.get(nome, np.zeros((0, 128), np.float32))
        np.savez_compressed(self.file_npz, **matrici)
        with open(self.file_json, "w", encoding="utf-8") as f:
            json.dump(self.info, f, ensure_ascii=False, indent=1)

    def imposta(self, nome, tipo, cartella, impronte, fonti):
        """fonti: per ogni impronta, il percorso della foto da cui viene."""
        self.info[nome] = {"tipo": tipo, "cartella": cartella, "imparate": len(impronte),
                           "confermate": 0, "fonti": list(fonti)}
        self.impronte[nome] = np.asarray(impronte, np.float32).reshape(-1, 128)

    def senza(self, testo):
        """Copia dei riferimenti senza le impronte imparate da foto il cui percorso
        contiene 'testo'. Serve alla prova: lo script non deve conoscere già
        le foto su cui viene giudicato."""
        copia = Riferimenti.__new__(Riferimenti)
        copia.info, copia.impronte, tolte = self.info, {}, 0
        for nome, m in self.impronte.items():
            fonti = self.info[nome].get("fonti", [])
            tieni = [i for i in range(len(m))
                     if not (i < len(fonti) and testo.upper() in fonti[i].upper())]
            tolte += len(m) - len(tieni)
            copia.impronte[nome] = m[tieni]
        return copia, tolte

    def aggiungi_conferma(self, nome, impronta, fonte, massimo=200):
        """Ogni volto confermato in revisione migliora il riferimento."""
        if nome not in self.impronte:
            return
        m = np.vstack([self.impronte[nome], impronta[None, :]])
        fonti = self.info[nome].setdefault("fonti", []) + [fonte]
        if len(m) > massimo:  # tiene le impronte imparate e le conferme più recenti
            base = self.info[nome]["imparate"]
            m = np.vstack([m[:base], m[-(massimo - base):]])
            fonti = fonti[:base] + fonti[-(massimo - base):]
        self.impronte[nome] = m
        self.info[nome]["fonti"] = fonti
        self.info[nome]["confermate"] = self.info[nome].get("confermate", 0) + 1

    def classifica(self, impronta):
        """Lista (punteggio, nome) dal più probabile. Punteggio = media dei 3 più simili."""
        voti = []
        for nome, m in self.impronte.items():
            if len(m) == 0:
                continue
            sim = m @ impronta
            k = min(3, len(sim))
            voti.append((float(np.sort(sim)[-k:].mean()), nome))
        voti.sort(reverse=True)
        return voti


def volto_ricorrente(volti_per_foto, soglia=0.40):
    """Dalle foto della cartella di una persona trova il volto che ricorre
    (il proprietario della cartella) e scarta compagni, avversari, tifosi.
    volti_per_foto: lista di liste di impronte.
    Restituisce una lista di (indice della foto, impronta scelta)."""
    tutti = [(i, e) for i, lista in enumerate(volti_per_foto) for e in lista]
    if not tutti:
        return []
    if len({i for i, _ in tutti}) == 1:  # una sola foto: il volto più grande
        i = tutti[0][0]
        return [(i, volti_per_foto[i][0])]
    foto = np.array([i for i, _ in tutti])
    E = np.stack([e for _, e in tutti])
    S = E @ E.T
    sostegno = []
    for a in range(len(tutti)):
        altre = {int(foto[b]) for b in np.where(S[a] > 0.45)[0] if foto[b] != foto[a]}
        sostegno.append(len(altre))
    centro = E[int(np.argmax(sostegno))]
    for _ in range(2):  # due passaggi per stabilizzare il centro
        scelti = []
        for i, lista in enumerate(volti_per_foto):
            if not lista:
                continue
            sims = [float(e @ centro) for e in lista]
            j = int(np.argmax(sims))
            if sims[j] > soglia:
                scelti.append((i, lista[j]))
        if not scelti:
            return []
        centro = np.mean([e for _, e in scelti], axis=0)
        centro /= np.linalg.norm(centro) + 1e-9
    return scelti
