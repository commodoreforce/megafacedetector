"""Sponsor nelle foto: legge le scritte (AMADORI, DOLOMIA...) e, se ci sono le immagini dei
loghi, cerca anche il disegno del logo. Poi sceglie le foto migliori per ogni sponsor.

Tutto avviene sul computer: questo modulo non usa MEGA.

Lettura delle scritte: modelli PP-OCRv3 di PaddleOCR (licenza Apache 2.0, file in modelli/),
eseguiti con OpenCV, che Smista Foto usa già: nessun programma in più da installare.
"""

import json
import math
import os
import re
import unicodedata

import cv2
import numpy as np

from .volti import _contenuto

MODELLO_RILEVA = "testo_rileva_ppocrv3.onnx"
MODELLO_LEGGI = "testo_leggi_ppocrv3.onnx"
ALFABETO = "testo_alfabeto_ppocrv3.txt"
NOME_VALIDO = re.compile(r"^[A-Z0-9][A-Z0-9 &'.\-]{0,39}$")


# ------------------------------------------------------------------ impostazioni sponsor

class ElencoSponsor:
    """Gli sponsor configurati su questo computer (dati/sponsor.json) e i loro loghi (loghi/<NOME>/)."""

    def __init__(self, cartella_dati, cartella_loghi):
        self.file = os.path.join(cartella_dati, "sponsor.json")
        self.cartella_loghi = cartella_loghi
        self.voci = {}
        if os.path.exists(self.file):
            with open(self.file, encoding="utf-8") as f:
                self.voci = json.load(f)

    def salva(self):
        os.makedirs(os.path.dirname(self.file), exist_ok=True)
        tmp = self.file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.voci, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.file)

    @staticmethod
    def nome_pulito(nome):
        n = " ".join(str(nome).upper().split())
        if not NOME_VALIDO.match(n):
            raise ValueError("Il nome può contenere lettere, numeri, spazi e i segni & ' . - (massimo 40 caratteri).")
        return n

    def imposta(self, nome, parole=None, foto_partita=None, foto_allenamento=None, attivo=None, disegno=None):
        nome = self.nome_pulito(nome)
        v = self.voci.setdefault(nome, {"parole": [normalizza(nome)], "foto_partita": 4, "foto_allenamento": 2,
                                        "attivo": True, "disegno": False})
        if parole is not None:
            pulite = []
            for p in parole:
                p = normalizza(p)
                if len(p) >= 3 and p not in pulite:
                    pulite.append(p)
            if not pulite and not self.loghi(nome):
                raise ValueError("Serve almeno una parola da cercare (di almeno 3 lettere) o un'immagine del logo.")
            v["parole"] = pulite
        for chiave, val in (("foto_partita", foto_partita), ("foto_allenamento", foto_allenamento)):
            if val is not None:
                val = int(val)
                if not 1 <= val <= 50:
                    raise ValueError("Il numero di foto deve essere tra 1 e 50.")
                v[chiave] = val
        if attivo is not None:
            v["attivo"] = bool(attivo)
        if disegno is not None:
            v["disegno"] = bool(disegno)
        return nome

    def loghi(self, nome):
        c = os.path.join(self.cartella_loghi, nome)
        if not os.path.isdir(c):
            return []
        return sorted(os.path.join(c, f) for f in os.listdir(c)
                      if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")) and not f.startswith("."))

    def attivi(self):
        return {n: v for n, v in sorted(self.voci.items()) if v.get("attivo", True)}


# ------------------------------------------------------------------ testo

def normalizza(testo):
    """'Amadori®' -> 'AMADORI'. Solo lettere e numeri, senza accenti."""
    t = unicodedata.normalize("NFKD", str(testo)).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]", "", t)


def _distanza(a, b):
    """Distanza di Levenshtein (poche lettere: basta la versione semplice)."""
    prima = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        ora = [i]
        for j, cb in enumerate(b, 1):
            ora.append(min(prima[j] + 1, ora[j - 1] + 1, prima[j - 1] + (ca != cb)))
        prima = ora
    return prima[-1]


def somiglianza_parola(parola, testo):
    """1.0 se la parola compare nel testo letto, meno se ci sono lettere lette male, 0 se no.
    Le parole corte devono comparire esatte: troppe scritte casuali le somigliano."""
    if not parola or not testo:
        return 0.0
    if parola in testo:
        return 1.0
    n = len(parola)
    tolleranza = 0 if n <= 4 else 1 if n <= 7 else 2
    if not tolleranza:
        return 0.0
    # logo coperto in parte (un braccio, un avversario): si legge solo l'inizio o la fine.
    # Vale se resta almeno il 70% della parola e almeno 5 lettere; conta meno di un logo intero.
    minimo = max(5, math.ceil(0.7 * n))
    for k in range(n - 1, minimo - 1, -1):
        if parola[:k] in testo or parola[-k:] in testo:
            return 0.55 + 0.3 * k / n
    migliore = None
    for lung in (n - 1, n, n + 1):
        for i in range(0, max(1, len(testo) - lung + 1)):
            d = _distanza(parola, testo[i:i + lung])
            migliore = d if migliore is None else min(migliore, d)
    if migliore is None or migliore > tolleranza:
        return 0.0
    return 1.0 - 0.15 * migliore


class _Rete:
    """Esegue un modello ONNX con onnxruntime se c'è (più veloce), altrimenti con OpenCV 5.
    OpenCV 4 non riesce a caricare il modello di lettura: in quel caso serve «Aggiorna»."""

    def __init__(self, percorso):
        dati = _contenuto(percorso)
        self.ort = None
        try:
            import onnxruntime
            self.ort = onnxruntime.InferenceSession(dati, providers=["CPUExecutionProvider"])
            self.ingresso = self.ort.get_inputs()[0].name
            return
        except Exception:
            self.ort = None
        try:
            self.rete = cv2.dnn.readNetFromONNX(np.frombuffer(dati, np.uint8))
        except cv2.error:
            raise RuntimeError(f"Questa versione di OpenCV ({cv2.__version__}) non riesce a leggere le scritte degli "
                               "sponsor: chiudi Smista Foto, fai doppio clic su «Aggiorna» e riaprilo.")

    def __call__(self, x):
        if self.ort is not None:
            return self.ort.run(None, {self.ingresso: x})[0]
        self.rete.setInput(x)
        return self.rete.forward()


class Lettore:
    """Trova e legge le scritte in una foto."""

    def __init__(self, cartella_modelli):
        self.rileva = _Rete(os.path.join(cartella_modelli, MODELLO_RILEVA))
        self.leggi_rete = _Rete(os.path.join(cartella_modelli, MODELLO_LEGGI))
        with open(os.path.join(cartella_modelli, ALFABETO), encoding="utf-8") as f:
            caratteri = f.read().split("\n")
        # come PaddleOCR: 0 = "vuoto" (CTC), poi l'alfabeto, poi lo spazio
        self.caratteri = ["", *caratteri, " "]

    def _riquadri(self, img, lato):
        h, w = img.shape[:2]
        s = min(1.0, lato / max(h, w))
        nh, nw = max(32, int(round(h * s / 32)) * 32), max(32, int(round(w * s / 32)) * 32)
        piccola = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
        x = (piccola.astype(np.float32) / 255.0 - (0.485, 0.456, 0.406)) / (0.229, 0.224, 0.225)
        mappa = self.rileva(np.ascontiguousarray(x.transpose(2, 0, 1)[None], np.float32))[0, 0]
        binaria = cv2.dilate((mappa > 0.3).astype(np.uint8), np.ones((2, 2), np.uint8))
        contorni, _ = cv2.findContours(binaria, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        sx, sy = w / nw, h / nh
        riquadri = []
        for c in contorni[:1000]:
            (cx, cy), (rw, rh), ang = cv2.minAreaRect(c)
            if min(rw, rh) < 3:
                continue
            x0, y0, bw, bh = cv2.boundingRect(c)
            maschera = np.zeros((bh, bw), np.uint8)
            cv2.fillPoly(maschera, [c.reshape(-1, 2) - (x0, y0)], 1)
            punteggio = float(cv2.mean(mappa[y0:y0 + bh, x0:x0 + bw], maschera)[0])
            if punteggio < 0.5:
                continue
            # "unclip": il modello disegna le scritte un po' più strette del vero
            d = rw * rh * 1.6 / (2 * (rw + rh))
            rw, rh = rw + 2 * d, rh + 2 * d
            if min(rw, rh) < 5:
                continue
            pts = cv2.boxPoints(((cx, cy), (rw, rh), ang)) * (sx, sy)
            riquadri.append((float(rw * rh * sx * sy), pts.astype(np.float32)))
        riquadri.sort(key=lambda r: -r[0])
        return [p for _, p in riquadri[:80]]  # le 80 scritte più grandi bastano

    @staticmethod
    def _ritaglio(img, pts):
        # ordina i 4 angoli: alto-sinistra, alto-destra, basso-destra, basso-sinistra
        s, d = pts.sum(1), np.diff(pts, axis=1).ravel()
        quad = np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], np.float32)
        larg = int(max(np.linalg.norm(quad[0] - quad[1]), np.linalg.norm(quad[3] - quad[2])))
        alt = int(max(np.linalg.norm(quad[0] - quad[3]), np.linalg.norm(quad[1] - quad[2])))
        if larg < 4 or alt < 4:
            return None, quad
        M = cv2.getPerspectiveTransform(quad, np.float32([[0, 0], [larg, 0], [larg, alt], [0, alt]]))
        r = cv2.warpPerspective(img, M, (larg, alt), borderMode=cv2.BORDER_REPLICATE, flags=cv2.INTER_CUBIC)
        if alt >= 1.5 * larg:
            r = np.rot90(r)
        return r, quad

    def _leggi(self, ritaglio):
        h, w = ritaglio.shape[:2]
        nw = int(min(1600, max(16, math.ceil(48 * w / h))))
        x = cv2.resize(ritaglio, (nw, 48)).astype(np.float32) / 255.0
        x = (x - 0.5) / 0.5
        p = self.leggi_rete(np.ascontiguousarray(x.transpose(2, 0, 1)[None], np.float32))[0]
        indici, prob = p.argmax(1), p.max(1)
        testo, conf, prec = [], [], -1
        for i, pr in zip(indici, prob):
            if i != prec and i != 0 and i < len(self.caratteri):
                testo.append(self.caratteri[i])
                conf.append(pr)
            prec = i
        return "".join(testo), float(np.mean(conf)) if conf else 0.0

    def leggi(self, img, lato=2048):
        """[{testo, normale, affidabilita, quad (4 angoli in pixel), riquadro (x, y, l, a)}]"""
        risultati = []
        for pts in self._riquadri(img, lato):
            ritaglio, quad = self._ritaglio(img, pts)
            if ritaglio is None:
                continue
            testo, conf = self._leggi(ritaglio)
            normale = normalizza(testo)
            if len(normale) < 3 or conf < 0.5:
                continue
            x, y, w, h = cv2.boundingRect(quad.astype(np.int32))
            risultati.append({"testo": testo, "normale": normale, "affidabilita": round(conf, 3),
                              "quad": quad.round(1).tolist(), "riquadro": [x, y, w, h]})
        return risultati


# ------------------------------------------------------------------ disegno del logo

class Loghi:
    """Confronto con le immagini dei loghi (punti caratteristici SIFT + omografia).
    Serve soprattutto per cartelloni e loghi non fatti di sole lettere."""

    def __init__(self, elenco):
        self.sift = cv2.SIFT_create(nfeatures=4000)
        self.modelli = {}
        for nome, v in elenco.attivi().items():
            if not v.get("disegno"):
                continue
            for percorso in elenco.loghi(nome):
                img = cv2.imdecode(np.fromfile(percorso, np.uint8), cv2.IMREAD_UNCHANGED)
                if img is None:
                    continue
                if img.ndim == 3 and img.shape[2] == 4:  # trasparenza: sfondo bianco
                    a = img[:, :, 3:4].astype(np.float32) / 255
                    img = (img[:, :, :3] * a + 255 * (1 - a)).astype(np.uint8)
                grigio = img if img.ndim == 2 else cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
                s = min(1.0, 600 / max(grigio.shape))
                grigio = cv2.resize(grigio, None, fx=s, fy=s) if s < 1 else grigio
                kp, des = self.sift.detectAndCompute(grigio, None)
                if des is not None and len(kp) >= 15:
                    self.modelli.setdefault(nome, []).append((kp, des, grigio.shape[:2]))
        self.matcher = cv2.FlannBasedMatcher({"algorithm": 1, "trees": 5}, {"checks": 50})

    def __bool__(self):
        return bool(self.modelli)

    def cerca(self, img):
        """{nome: {affidabilita, quad, riquadro}} dei loghi trovati."""
        h, w = img.shape[:2]
        s = min(1.0, 1600 / max(h, w))
        grigio = cv2.cvtColor(cv2.resize(img, None, fx=s, fy=s) if s < 1 else img, cv2.COLOR_BGR2GRAY)
        kp, des = self.sift.detectAndCompute(grigio, None)
        trovati = {}
        if des is None or len(kp) < 15:
            return trovati
        for nome, modelli in self.modelli.items():
            for kp_l, des_l, (lh, lw) in modelli:
                coppie = self.matcher.knnMatch(des_l, des, k=2)
                buone = [m for m, n in (c for c in coppie if len(c) == 2) if m.distance < 0.75 * n.distance]
                if len(buone) < 12:
                    continue
                a = np.float32([kp_l[m.queryIdx].pt for m in buone])
                b = np.float32([kp[m.trainIdx].pt for m in buone])
                H, dentro = cv2.findHomography(a, b, cv2.RANSAC, 5.0)
                if H is None or int(dentro.sum()) < 12:
                    continue
                quad = cv2.perspectiveTransform(np.float32([[0, 0], [lw, 0], [lw, lh], [0, lh]])[None], H)[0]
                area = cv2.contourArea(quad)
                if not cv2.isContourConvex(quad.astype(np.int32)) or area < 0.0003 * grigio.size:
                    continue
                quad = quad / s
                conf = min(1.0, int(dentro.sum()) / 40)
                if conf > trovati.get(nome, {}).get("affidabilita", 0):
                    x, y, bw, bh = cv2.boundingRect(quad.astype(np.int32))
                    trovati[nome] = {"affidabilita": round(conf, 3), "quad": quad.round(1).tolist(),
                                     "riquadro": [x, y, bw, bh]}
        return trovati


# ------------------------------------------------------------------ in una foto

def _nitidezza(img, riquadro):
    x, y, w, h = riquadro
    r = img[max(0, y):y + h, max(0, x):x + w]
    if r.size == 0 or min(r.shape[:2]) < 4:
        return 0.0
    r = cv2.resize(r, (max(8, int(64 * r.shape[1] / r.shape[0])), 64), interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(cv2.cvtColor(r, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())


def _su_una_persona(riquadro, volti):
    """Il logo sta sul corpo di una persona (sotto al volto, larghezza delle spalle)?
    Restituisce l'indice del volto o None."""
    x, y, w, h = riquadro
    cx, cy = x + w / 2, y + h / 2
    for i, v in enumerate(volti):
        vx, vy, vw, vh = v["riquadro"]
        if abs(cx - (vx + vw / 2)) < 2.2 * vw and vy + vh * 0.8 < cy < vy + vh * 7:
            return i
    return None


def impronta_visiva(img):
    """Una miniatura 32x24 in grigi, normalizzata: due scatti di una raffica ne hanno di quasi
    uguali (correlazione vicina a 1), due foto diverse no, anche se entrambe hanno molto prato."""
    g = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (32, 24), interpolation=cv2.INTER_AREA).astype(np.float32)
    g = g.flatten() - g.mean()
    n = float(np.linalg.norm(g))
    return g / n if n > 1e-6 else g


def sponsor_nella_foto(img, letture, loghi_trovati, elenco_attivi, volti, protagonisti):
    """Per ogni sponsor trovato nella foto: {nome: {punteggio, tipo, riquadro, testo, ...}}.
    volti: tutti i volti trovati (anche sconosciuti); protagonisti: indici dei volti di nostri
    giocatori protagonisti."""
    H, W = img.shape[:2]
    trovati = {}
    for nome, cfg in elenco_attivi.items():
        candidati = []
        for parola in cfg.get("parole", []):
            for l in letture:
                sim = somiglianza_parola(parola, l["normale"])
                if sim:
                    candidati.append((sim * l["affidabilita"], l["riquadro"], l["quad"], l["testo"]))
        if nome in loghi_trovati:
            g = loghi_trovati[nome]
            candidati.append((g["affidabilita"], g["riquadro"], g["quad"], "(logo)"))
        if not candidati:
            continue
        conf, riquadro, quad, testo = max(candidati, key=lambda c: c[0] * (1 + c[1][3] / H))
        x, y, w, h = riquadro
        grandezza = min(1.0, max(h, w / 5) / (0.035 * H))   # una scritta alta 3,5% della foto è "grande"
        nitidezza = _nitidezza(img, riquadro)
        persona = _su_una_persona(riquadro, volti)
        tipo = "maglia" if persona is not None else "cartellone"
        punteggio = 0.45 * grandezza + 0.25 * min(1.0, nitidezza / 150) + 0.30 * conf
        if protagonisti:
            punteggio += 0.15
        if persona is not None and persona in protagonisti:
            punteggio += 0.10
        trovati[nome] = {"punteggio": round(punteggio, 3), "affidabilita": round(conf, 3), "tipo": tipo,
                         "testo": testo, "nitidezza": round(nitidezza, 1),
                         "box": [round(x / W, 4), round(y / H, 4), round(w / W, 4), round(h / H, 4)],
                         "quad": [[round(px / W, 4), round(py / H, 4)] for px, py in quad]}
    return trovati


# ------------------------------------------------------------------ le migliori

def numero_scatto(relativo):
    """('FOTOGRAFO1', 5169) da 'FOTOGRAFO1/IMG_5169.jpg': serve a riconoscere le raffiche."""
    cartella, _, nome = relativo.replace("\\", "/").rpartition("/")
    numeri = re.findall(r"\d+", os.path.splitext(nome)[0])
    if not numeri:
        return None
    return cartella, int(max(reversed(numeri), key=len))  # il numero più lungo è il contatore della macchina


def scegli_migliori(candidate, quante, impronte, persone_in_foto, scatti=None):
    """candidate: [{foto, punteggio, tipo}] (già per uno sponsor). Sceglie le `quante` migliori
    evitando doppioni (raffiche quasi uguali), variando giocatori e, se possibile,
    mettendo insieme maglie e cartelloni. Restituisce gli id delle foto scelte, in ordine."""
    scatti = scatti or {}

    def _simili(a, b):
        """Stessa foto o quasi (raffica): miniature molto simili, oppure scatti vicini dello
        stesso fotografo (numeri di file a meno di 4) con miniature abbastanza simili."""
        somiglianza = float(np.dot(impronte[a], impronte[b]))
        if somiglianza > 0.92:
            return True
        sa, sb = scatti.get(a), scatti.get(b)
        return bool(sa and sb and sa[0] == sb[0] and abs(sa[1] - sb[1]) <= 3 and somiglianza > 0.75)

    ordinate = sorted(candidate, key=lambda c: -c["punteggio"])
    scelte, giocatori_usati = [], {}
    for c in ordinate:
        if len(scelte) >= quante:
            break
        if any(_simili(c["foto"], s["foto"]) for s in scelte):
            continue
        # lo stesso giocatore già scelto due volte: passa avanti se c'è altro di valido
        ripetuti = [p for p in persone_in_foto.get(c["foto"], []) if giocatori_usati.get(p, 0) >= 2]
        if ripetuti and any(o["punteggio"] >= c["punteggio"] - 0.15 and o not in scelte
                            and not set(persone_in_foto.get(o["foto"], [])) & set(ripetuti)
                            for o in ordinate[len(scelte) + 1:]):
            continue
        scelte.append(c)
        for p in persone_in_foto.get(c["foto"], []):
            giocatori_usati[p] = giocatori_usati.get(p, 0) + 1
    if len(scelte) < quante:  # se la varietà ha lasciato posti vuoti, li riempie
        for c in ordinate:
            if len(scelte) >= quante:
                break
            if c not in scelte and not any(_simili(c["foto"], s["foto"]) for s in scelte):
                scelte.append(c)
    # maglie e cartelloni: se ne manca un tipo ma ci sono buone foto di quel tipo, ne mette una
    if quante >= 2 and scelte:
        for tipo in ("maglia", "cartellone"):
            if any(s["tipo"] == tipo for s in scelte):
                continue
            altra = next((c for c in ordinate if c["tipo"] == tipo and c not in scelte
                          and c["punteggio"] >= 0.6 * scelte[0]["punteggio"]
                          and not any(_simili(c["foto"], s["foto"]) for s in scelte)), None)
            if altra:
                if len(scelte) >= quante:
                    tolta = min((s for s in scelte if sum(x["tipo"] == s["tipo"] for x in scelte) > 1),
                                key=lambda s: s["punteggio"], default=None)
                    if tolta is None:
                        continue
                    scelte.remove(tolta)
                scelte.append(altra)
    scelte.sort(key=lambda c: -c["punteggio"])
    return [c["foto"] for c in scelte]
