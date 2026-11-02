"""Riconoscimento dei volti. YuNet (OpenCV) trova i volti; per riconoscerli si usa
AuraFace (ResNet100 tipo ArcFace, licenza Apache 2.0, uso commerciale consentito)
oppure SFace (OpenCV), più leggero ma meno preciso. Tutto gira sul computer."""

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
MODELLO_SFACE = "face_recognition_sface_2021dec.onnx"
# solo la rete di riconoscimento di AuraFace: gli altri file di quel repository
# (rilevamento, punti del viso, età) non hanno una licenza chiara e non si usano
FILE_AURAFACE = "auraface_v1_glintr100.onnx"
URL_AURAFACE = "https://huggingface.co/fal/AuraFace-v1/resolve/main/glintr100.onnx"
DIMENSIONE_MINIMA_AURAFACE = 200 * 1024 * 1024

# posizione standard di occhi, naso e bocca in un volto 112x112 (convenzione ArcFace)
MODELLO_ARCFACE = np.array([[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366],
                            [41.5493, 92.3655], [70.7299, 92.2041]], np.float32)

SOGLIE_PREDEFINITE = {
    "sface": {"soglia_sicura": 0.50, "soglia_dubbia": 0.36, "margine": 0.06, "ricorrente": 0.40},
    "auraface": {"soglia_sicura": 0.40, "soglia_dubbia": 0.25, "margine": 0.08, "ricorrente": 0.30},
}


def nome_modello(cfg):
    return cfg.get("modello", "sface").lower()


def soglie(cfg):
    """Le soglie del modello in uso: config.json → "soglie" → <modello>, altrimenti predefinite."""
    m = nome_modello(cfg)
    s = dict(SOGLIE_PREDEFINITE.get(m, SOGLIE_PREDEFINITE["sface"]))
    if m == "sface":  # compatibilità con le versioni precedenti di config.json
        s.update({k: cfg[k] for k in ("soglia_sicura", "soglia_dubbia", "margine") if k in cfg})
    s.update(cfg.get("soglie", {}).get(m, {}))
    return s


def scarica_auraface(cartella_modelli, reg):
    """Scarica la rete di AuraFace (circa 260 MB) da Hugging Face, una volta sola."""
    import ssl
    import urllib.request
    dest = os.path.join(cartella_modelli, FILE_AURAFACE)
    if os.path.exists(dest) and os.path.getsize(dest) >= DIMENSIONE_MINIMA_AURAFACE:
        return dest
    try:
        import certifi
        contesto = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        contesto = ssl.create_default_context()
    reg.info("Scarico il modello di riconoscimento AuraFace (circa 260 MB, solo la prima volta)…")
    parziale = dest + ".parziale"
    with urllib.request.urlopen(URL_AURAFACE, context=contesto, timeout=60) as r, open(parziale, "wb") as f:
        totale = int(r.headers.get("Content-Length") or 0)
        reg.inizia_fase("Scarico il modello AuraFace (MB)", totale // (1024 * 1024))
        letti = 0
        while True:
            blocco = r.read(1024 * 1024)
            if not blocco:
                break
            f.write(blocco)
            letti += len(blocco)
            reg.passo(letti // (1024 * 1024))
    if os.path.getsize(parziale) < DIMENSIONE_MINIMA_AURAFACE:
        os.remove(parziale)
        raise RuntimeError("Il download di AuraFace non è completo. Riprova.")
    os.replace(parziale, dest)
    reg.ok("Modello AuraFace scaricato.")
    return dest


class _SFace:
    nome, dimensione = "SFace", 128

    def __init__(self, cartella_modelli):
        self.rete = cv2.FaceRecognizerSF.create(os.path.join(cartella_modelli, MODELLO_SFACE), "")

    def impronta(self, immagine, volto):
        return self.rete.feature(self.rete.alignCrop(immagine, volto)).flatten()


class _AuraFace:
    nome, dimensione = "AuraFace", 512

    def __init__(self, percorso):
        self.ort = None
        try:  # onnxruntime è più veloce; se manca (es. Python troppo nuovo) si usa OpenCV
            import onnxruntime
            self.ort = onnxruntime.InferenceSession(percorso, providers=["CPUExecutionProvider"])
            self.ingresso = self.ort.get_inputs()[0].name
        except Exception:
            self.rete = cv2.dnn.readNetFromONNX(percorso)

    def _rete(self, blob):
        if self.ort is not None:
            return self.ort.run(None, {self.ingresso: blob})[0]
        self.rete.setInput(blob)
        return self.rete.forward()

    def impronta(self, immagine, volto):
        punti = np.asarray(volto[4:14], np.float32).reshape(5, 2)
        M, _ = cv2.estimateAffinePartial2D(punti, MODELLO_ARCFACE, method=cv2.LMEDS)
        if M is None:
            M, _ = cv2.estimateAffinePartial2D(punti, MODELLO_ARCFACE)
        ritaglio = cv2.warpAffine(immagine, M, (112, 112), borderValue=0)
        # il volto e la sua immagine allo specchio: la media è più stabile con i profili
        blob = cv2.dnn.blobFromImages([ritaglio, cv2.flip(ritaglio, 1)], 1.0 / 127.5, (112, 112),
                                      (127.5, 127.5, 127.5), swapRB=True)
        uscita = self._rete(blob).reshape(2, -1)
        return uscita[0] / (np.linalg.norm(uscita[0]) + 1e-9) + uscita[1] / (np.linalg.norm(uscita[1]) + 1e-9)


class Volti:
    def __init__(self, cartella_modelli, cfg):
        self.cfg = cfg
        self.trova = cv2.FaceDetectorYN.create(
            os.path.join(cartella_modelli, MODELLO_TROVA), "", (320, 320), 0.8, 0.3, 5000)
        if nome_modello(cfg) == "auraface":
            percorso = os.path.join(cartella_modelli, FILE_AURAFACE)
            if not os.path.exists(percorso):
                raise RuntimeError("Il modello AuraFace non è ancora stato scaricato.")
            self.riconosci = _AuraFace(percorso)
        else:
            self.riconosci = _SFace(cartella_modelli)
        self.dimensione = self.riconosci.dimensione
        self.nome = self.riconosci.nome
        # prova a vuoto: se il modello non gira su questo computer, meglio saperlo subito
        finto = np.full((200, 200, 3), 128, np.uint8)
        punti = np.array([0, 0, 200, 200, 70, 90, 130, 90, 100, 120, 75, 150, 125, 150, 1], np.float32)
        e = np.asarray(self.riconosci.impronta(finto, punti), np.float32).flatten()
        if e.shape[0] != self.dimensione or not np.all(np.isfinite(e)):
            raise RuntimeError(f"il modello {self.nome} non funziona su questo computer")

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
            e = np.asarray(self.riconosci.impronta(grande, f), np.float32).flatten()
            e /= np.linalg.norm(e) + 1e-9
            risultato.append({"riquadro": [x, y, fw, fh], "affidabilita": float(f[14]), "impronta": e})
        risultato.sort(key=lambda v: -v["riquadro"][2])
        return risultato, grande


class Riferimenti:
    """Le impronte dei volti di giocatori e staff, salvate in dati/."""

    def __init__(self, cartella_dati, modello="sface", dimensione=128):
        self.cartella = cartella_dati
        self.dimensione = dimensione
        os.makedirs(cartella_dati, exist_ok=True)
        # un file per modello: le impronte di modelli diversi non sono confrontabili
        suffisso = "" if modello == "sface" else "_" + modello
        self.file_json = os.path.join(cartella_dati, f"riferimenti{suffisso}.json")
        self.file_npz = os.path.join(cartella_dati, f"riferimenti{suffisso}.npz")
        self.info = {}      # nome -> {tipo, cartella, imparate, confermate, fonti}
        self.impronte = {}  # nome -> matrice N x 128
        if os.path.exists(self.file_json):
            with open(self.file_json, encoding="utf-8") as f:
                self.info = json.load(f)
            dati = np.load(self.file_npz)
            for nome, i in list(self.info.items()):
                if "/" in nome or nome.endswith(":"):  # righe di intestazione lette per errore (v1.5)
                    del self.info[nome]
                    continue
                self.impronte[nome] = dati[i["chiave"]]

    def rimuovi(self, nome):
        self.info.pop(nome, None)
        self.impronte.pop(nome, None)

    def salva(self):
        matrici = {}
        for n, (nome, i) in enumerate(sorted(self.info.items())):
            i["chiave"] = f"p{n}"
            matrici[i["chiave"]] = self.impronte.get(nome, np.zeros((0, self.dimensione), np.float32))
        np.savez_compressed(self.file_npz, **matrici)
        with open(self.file_json, "w", encoding="utf-8") as f:
            json.dump(self.info, f, ensure_ascii=False, indent=1)

    def imposta(self, nome, tipo, cartella, impronte, fonti):
        """fonti: per ogni impronta, il percorso della foto da cui viene."""
        self.info[nome] = {"tipo": tipo, "cartella": cartella, "imparate": len(impronte),
                           "confermate": 0, "fonti": list(fonti)}
        self.impronte[nome] = np.asarray(impronte, np.float32).reshape(len(impronte), self.dimensione)

    def senza(self, testo):
        """Copia dei riferimenti senza le impronte imparate da foto il cui percorso
        contiene 'testo'. Serve alla prova: lo script non deve conoscere già
        le foto su cui viene giudicato."""
        copia = Riferimenti.__new__(Riferimenti)
        copia.info, copia.impronte, tolte = self.info, {}, 0
        copia.dimensione = self.dimensione
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
    sostegno_minimo = soglia + 0.05
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
        altre = {int(foto[b]) for b in np.where(S[a] > sostegno_minimo)[0] if foto[b] != foto[a]}
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
