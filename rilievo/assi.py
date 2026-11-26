"""Pianta per APE dagli assi dei muri (pratica C003).

Quando la planimetria catastale ha muri inclinati, rientranze e locali non rettangolari, il rilievo per locali
rettangolari non basta e la vettorializzazione automatica dei pixel viene ondulata e piena di moncherini.
Qui si parte dagli **assi** letti a mano sul catastale raddrizzato (rette, quindi muri dritti per costruzione):

- `contorno`: anello degli assi dei muri esterni (spessore `esterni`, di norma 30 cm);
- `tramezzi`: segmenti d'asse dei muri interni (spessore `interni`, di norma 10 cm), con gli estremi sugli assi
  dei muri in cui si innestano;
- `porte_interne` (vani liberi), `finestre`, `ingresso` (con anta e arco), `balconi` (solo il bordo libero).

Tutte le coordinate sono in metri, y verso l'alto. Il risultato e' la pianta "solo disegno" per Blumatica e
simili: un layer bianco, linee normali, niente scritte ne' quote, AutoCAD 2000, in metri (lezioni C001-C003).
"""
from __future__ import annotations

import math
import shutil
import tempfile
from pathlib import Path

import ezdxf
import numpy as np
import yaml
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import unary_union

MITRA = {"join_style": "mitre", "mitre_limit": 10.0}


def carica(percorso: str | Path) -> dict:
    return yaml.safe_load(Path(percorso).read_text(encoding="utf-8"))


def _segmenti(d: dict) -> list[tuple[np.ndarray, np.ndarray, float]]:
    se, si = d["spessori"]["esterni"], d["spessori"]["interni"]
    c = [np.array(p, float) for p in d["contorno"]]
    segs = [(c[i], c[(i + 1) % len(c)], se) for i in range(len(c))]
    segs += [(np.array(a, float), np.array(b, float), si) for a, b in d.get("tramezzi", [])]
    return segs


def _dist(p, a, b) -> float:
    return LineString([tuple(a), tuple(b)]).distance(Point(tuple(p)))


def _muro_di(p, segs, escludi=None):
    """Il muro il cui asse passa piu' vicino al punto p."""
    cand = [s for s in segs if s is not escludi]
    return min(cand, key=lambda s: _dist(p, s[0], s[1]))


def _rettangolo(a, b, mezzo: float) -> Polygon:
    return LineString([tuple(a), tuple(b)]).buffer(mezzo, cap_style="flat")


def geometria(d: dict) -> dict:
    """Massa muraria (con i vani gia' tagliati) e simboli: finestre, ingresso, balconi."""
    se, si = d["spessori"]["esterni"], d["spessori"]["interni"]
    anello = Polygon(d["contorno"])
    if not anello.is_valid or anello.area <= 0:
        raise ValueError("contorno degli assi non valido (si incrocia?)")
    fuori = anello.buffer(se / 2, **MITRA)
    pezzi = [fuori.difference(anello.buffer(-se / 2, **MITRA))]
    segs = _segmenti(d)
    for s in segs[len(d["contorno"]):]:
        a, b, sp = s
        u = (b - a) / np.linalg.norm(b - a)
        # ogni estremo entra nel muro in cui si innesta di meta' del suo spessore: spigoli puliti, niente sporgenze
        ext = []
        for p in (a, b):
            altri = [t[2] for t in segs if t is not s and _dist(p, t[0], t[1]) < 1e-3]
            ext.append(max(altri) / 2 if altri else 0.0)
        pezzi.append(_rettangolo(a - u * ext[0], b + u * ext[1], sp / 2))
    massa = unary_union(pezzi).intersection(fuori)
    tagli, finestre, ingresso = [], [], None

    def facce(muro):
        """Posizioni (lungo l'asse del muro) delle facce dei muri che vi s'innestano o lo incrociano."""
        a, b, _ = muro
        L = float(np.linalg.norm(b - a))
        u = (b - a) / L
        asse = LineString([tuple(a), tuple(b)])
        out = []
        for t in segs:
            if t is muro:
                continue
            v = (t[1] - t[0]) / np.linalg.norm(t[1] - t[0])
            seno = abs(float(u[0] * v[1] - u[1] * v[0]))
            if seno < 0.2 or LineString([tuple(t[0]), tuple(t[1])]).distance(asse) > t[2]:
                continue
            # punto in cui l'asse dell'altro muro taglia questo asse (rette)
            A = np.array([u, -v]).T
            s = float(np.linalg.solve(A, t[0] - a)[0])
            mezzo = t[2] / 2 / seno
            out.append((s - mezzo, s + mezzo))  # facce del muro che s'innesta: prima e dopo
        return out

    def vano(p, q, muro, tol=0.12):
        """Vano da p a q sull'asse del muro; un estremo a meno di `tol` dalla faccia di un muro che s'innesta
        arriva alla faccia: niente pezzetti di muro di pochi centimetri (pratica C003). 12 cm dalla C005: le
        crocette del catastale sono approssimate e un pezzetto da 8-12 cm si vede come un dentino."""
        a, b, _ = muro
        u = (b - a) / np.linalg.norm(b - a)
        s0, s1 = sorted(float(np.dot(np.asarray(x, float) - a, u)) for x in (p, q))
        for f0, f1 in facce(muro):
            # il vano arriva alla faccia del muro dalla sua parte, mai alla faccia opposta (non lo attraversa)
            if abs(s0 - f1) < tol:
                s0 = f1
            if abs(s1 - f0) < tol:
                s1 = f0
        return a + u * s0, a + u * s1, u

    for p in d.get("porte_interne", []):
        muro = _muro_di(p["centro"], segs)
        w = p.get("larghezza", 0.80)
        c = np.asarray(p["centro"], float)
        u0 = (muro[1] - muro[0]) / np.linalg.norm(muro[1] - muro[0])
        a, b, _ = vano(c - u0 * w / 2, c + u0 * w / 2, muro)
        tagli.append(_rettangolo(a, b, muro[2] / 2 + 0.01))
    for f in d.get("finestre", []):
        muro = _muro_di((np.add(f["da"], f["a"])) / 2, segs)
        a, b, _ = vano(f["da"], f["a"], muro)
        tagli.append(_rettangolo(a, b, muro[2] / 2 + 0.01))
        finestre.append((a, b, muro[2]))
    if d.get("ingresso"):
        g = d["ingresso"]
        muro = _muro_di((np.add(g["da"], g["a"])) / 2, segs)
        a, b, u = vano(g["da"], g["a"], muro)
        if float(np.dot(np.subtract(g["a"], g["da"]), u)) < 0:
            a, b, u = b, a, -u  # cerniera dalla parte di `da`
        tagli.append(_rettangolo(a, b, muro[2] / 2 + 0.01))
        n = np.array([-u[1], u[0]])
        m = (a + b) / 2
        if not anello.contains(Point(tuple(m + n * 0.3))):
            n = -n  # verso l'interno
        ingresso = (a, b, n, muro[2])
    if tagli:
        massa = massa.difference(unary_union(tagli))
    bordi = []
    for pl in d.get("balconi", []):
        libero = LineString(pl).difference(fuori.buffer(0.005, **MITRA))
        bordi += [g for g in getattr(libero, "geoms", [libero]) if g.length > 0.05]
    return {"massa": massa, "anello": anello, "fuori": fuori, "finestre": finestre, "ingresso": ingresso,
            "balconi": bordi}


def _pulisci(pts, chiusa: bool, tol: float = 0.0005) -> list:
    from .esporta import _pulisci_vertici
    return _pulisci_vertici(pts, chiusa, tol=tol)


def disegna_dxf(d: dict, dxf: str | Path) -> dict:
    """DXF R2000 in metri, un solo layer bianco PIANTA, origine nello spigolo esterno in basso a sinistra."""
    g = geometria(d)
    massa = g["massa"]
    x0, y0 = g["fuori"].bounds[:2]
    T = lambda p: (round(float(p[0]) - x0, 4), round(float(p[1]) - y0, 4))  # noqa: E731
    doc = ezdxf.new("R2000", setup=False)
    doc.header["$INSUNITS"] = 6  # metri
    doc.header["$MEASUREMENT"] = 1
    doc.layers.add("PIANTA", color=7)
    msp = doc.modelspace()
    att = {"layer": "PIANTA"}
    poligoni = massa.geoms if isinstance(massa, MultiPolygon) else [massa]
    for pg in poligoni:
        for r in [pg.exterior, *pg.interiors]:
            msp.add_lwpolyline(_pulisci([T(p) for p in r.coords[:-1]], True), close=True, dxfattribs=att)
    for a, b, sp in g["finestre"]:  # le due facce del muro e la doppia linea del vetro
        u = (b - a) / np.linalg.norm(b - a)
        n = np.array([-u[1], u[0]])
        for k in (-sp / 2, sp / 2, -0.01, 0.01):
            msp.add_line(T(a + n * k), T(b + n * k), dxfattribs=att)
    if g["ingresso"] is not None:  # anta aperta a 90 gradi verso l'interno e arco di apertura
        a, b, n, sp = g["ingresso"]
        w = float(np.linalg.norm(b - a))
        cern = a + n * sp / 2
        punta = cern + n * w
        msp.add_line(T(cern), T(punta), dxfattribs=att)
        ang_b = math.degrees(math.atan2(*(b - a)[::-1]))
        ang_p = math.degrees(math.atan2(n[1], n[0]))
        s, e = (ang_b, ang_p) if (ang_p - ang_b) % 360 < 180 else (ang_p, ang_b)
        msp.add_arc(T(cern), w, s, e, dxfattribs=att)
    for ln in g["balconi"]:
        msp.add_lwpolyline(_pulisci([T(p) for p in ln.coords], False), dxfattribs=att)
    doc.saveas(dxf)
    return g


def pianta_ape_da_assi(d: dict, cartella: str | Path, nome: str, versione: str = "ACAD2000") -> dict:
    from .esporta import dxf_a_dwg, oda_disponibile
    cartella = Path(cartella)
    cartella.mkdir(parents=True, exist_ok=True)
    dxf = cartella / f"{nome}_APE_m_{versione}.dxf"
    g = disegna_dxf(d, dxf)
    out = {"dxf": dxf, "geometria": g}
    if oda_disponibile():
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / dxf.name
            shutil.copy(dxf, src)
            out["dwg"] = dxf_a_dwg(src, cartella / f"{nome}_APE_m_{versione}.dwg", versione)
    return out


def locali(d: dict) -> list[Polygon]:
    """Superfici calpestabili: l'interno del contorno meno i muri (i vani delle porte uniscono i locali,
    quindi si calcolano sulla massa senza tagli)."""
    d2 = {k: v for k, v in d.items() if k not in ("porte_interne", "finestre", "ingresso")}
    g = geometria(d2)
    vuoti = g["fuori"].difference(g["massa"])
    return [p for p in getattr(vuoti, "geoms", [vuoti]) if p.area > 0.5 and g["anello"].contains(p.centroid)]


def pezzetti(dxf: str | Path, minimo: float = 0.09) -> list[tuple]:
    """Lati dei contorni dei muri piu' corti di `minimo` (in metri): moncherini, scalini, residui di taglio.
    I lati da 10 cm delle testate dei tramezzi sono ammessi (minimo 9 cm)."""
    doc = ezdxf.readfile(str(dxf))
    out = []
    for e in doc.modelspace().query("LWPOLYLINE"):
        p = [tuple(q[:2]) for q in e.get_points()]
        if e.closed:
            p.append(p[0])
        out += [(a, b) for a, b in zip(p, p[1:]) if math.dist(a, b) < minimo]
    return out


def linee_scansione(immagine: str | Path, lunghezza: int = 20, soglia: int = 150) -> dict:
    """Linee orizzontali e verticali di una scansione raddrizzata (apertura morfologica): per ognuna la posizione
    media in pixel, l'inizio, la fine e lo spessore. Serve a leggere gli assi dei muri (lezione C004)."""
    import cv2
    img = cv2.imread(str(immagine), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(immagine)
    b = (img < soglia).astype(np.uint8)
    out = {}
    for nome, k in (("orizzontali", (lunghezza, 1)), ("verticali", (1, lunghezza))):
        o = cv2.morphologyEx(b, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, k))
        n, lab, st, _ = cv2.connectedComponentsWithStats(o)
        righe = []
        for i in range(1, n):
            x, y, w, h, _a = (int(v) for v in st[i])
            ys, xs = np.nonzero(lab == i)
            if nome == "orizzontali":
                righe.append((round(float(ys.mean()), 1), x, x + w, h))
            else:
                righe.append((round(float(xs.mean()), 1), y, y + h, w))
        out[nome] = sorted(righe)
    return out
