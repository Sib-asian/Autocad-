"""Geometria in pianta ricavata dal modello: muri, locali, aperture, perimetro."""
from __future__ import annotations

import math

import numpy as np
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from .modello import Apertura, Edificio, Falda, Muro

TOL_GIUNTO = 0.02


def direzione(m: Muro) -> np.ndarray:
    (x0, y0), (x1, y1) = m.asse
    d = np.array([x1 - x0, y1 - y0], float)
    return d / np.linalg.norm(d)


def normale_sx(m: Muro) -> np.ndarray:
    d = direzione(m)
    return np.array([-d[1], d[0]])


def _estensioni(ed: Edificio, m: Muro) -> tuple[float, float]:
    """Di quanto allungare l'asse alle due estremita' per chiudere i giunti con altri muri."""
    ext = []
    for p in m.asse:
        pt = Point(p)
        e = 0.0
        for altro in ed.muri:
            if altro.id == m.id:
                continue
            if LineString(altro.asse).distance(pt) < TOL_GIUNTO:
                e = max(e, altro.spessore.valore / 2)
        ext.append(e)
    return ext[0], ext[1]


def asse_esteso(ed: Edificio, m: Muro) -> tuple[np.ndarray, np.ndarray]:
    d = direzione(m)
    e0, e1 = _estensioni(ed, m)
    p0 = np.array(m.asse[0], float) - d * e0
    p1 = np.array(m.asse[1], float) + d * e1
    return p0, p1


def poligono_muro(ed: Edificio, m: Muro) -> Polygon:
    p0, p1 = asse_esteso(ed, m)
    return LineString([tuple(p0), tuple(p1)]).buffer(m.spessore.valore / 2, cap_style="flat", join_style="mitre")


def apertura_mondo(ed: Edificio, ap: Apertura) -> tuple[tuple[float, float], tuple[float, float]]:
    """Estremi dell'apertura sull'asse del muro, in coordinate di pianta."""
    m = ed.muro(ap.muro)
    d = direzione(m)
    o = np.array(m.asse[0], float)
    a = o + d * (m.zero.valore + ap.da.valore)
    b = o + d * (m.zero.valore + ap.a.valore)
    return (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))


def rettangolo_apertura(ed: Edificio, ap: Apertura, margine: float = 0.001) -> Polygon:
    m = ed.muro(ap.muro)
    a, b = apertura_mondo(ed, ap)
    return LineString([a, b]).buffer(m.spessore.valore / 2 + margine, cap_style="flat")


def poligoni_muri(ed: Edificio, con_aperture: bool = True) -> dict[str, Polygon]:
    out = {}
    for m in ed.muri:
        p = poligono_muro(ed, m)
        if con_aperture:
            for ap in ed.aperture_di(m.id):
                p = p.difference(rettangolo_apertura(ed, ap))
        out[m.id] = p
    return out


def ingombro_muri(ed: Edificio) -> Polygon | MultiPolygon:
    return unary_union(list(poligoni_muri(ed, con_aperture=False).values())).simplify(1e-9, preserve_topology=True)


def celle(ed: Edificio) -> list[Polygon]:
    """Spazi chiusi delimitati dai muri (escluso l'esterno)."""
    u = ingombro_muri(ed)
    minx, miny, maxx, maxy = u.bounds
    vuoto = box(minx - 1, miny - 1, maxx + 1, maxy + 1).difference(u)
    parti = list(vuoto.geoms) if isinstance(vuoto, MultiPolygon) else [vuoto]
    esterno = Point(minx - 0.5, miny - 0.5)
    return [p for p in parti if not p.contains(esterno)]


def poligono_locale(ed: Edificio, loc) -> Polygon:
    pt = Point(loc.punto)
    for c in celle(ed):
        if c.contains(pt):
            return c
    raise ValueError(f"Il punto del locale {loc.nome} non cade in uno spazio chiuso dai muri")


def perimetro_esterno(ed: Edificio):
    """Lati del perimetro esterno: (p0, p1, normale uscente)."""
    u = ingombro_muri(ed)
    poligoni = list(u.geoms) if isinstance(u, MultiPolygon) else [u]
    lati = []
    for pol in poligoni:
        pol = orient(pol, 1.0)
        c = list(pol.exterior.coords)
        for p0, p1 in zip(c, c[1:]):
            dx, dy = p1[0] - p0[0], p1[1] - p0[1]
            L = math.hypot(dx, dy)
            if L < 1e-6:
                continue
            lati.append((p0, p1, (dy / L, -dx / L)))
    return _unisci_collineari(lati)


def _unisci_collineari(lati):
    if not lati:
        return lati
    out = [lati[0]]
    for p0, p1, n in lati[1:]:
        q0, q1, m = out[-1]
        if abs(n[0] - m[0]) < 1e-9 and abs(n[1] - m[1]) < 1e-9 and math.dist(q1, p0) < 1e-9:
            out[-1] = (q0, p1, m)
        else:
            out.append((p0, p1, n))
    if len(out) > 1:
        p0, p1, n = out[0]
        q0, q1, m = out[-1]
        if abs(n[0] - m[0]) < 1e-9 and abs(n[1] - m[1]) < 1e-9 and math.dist(q1, p0) < 1e-9:
            out[0] = (q0, p1, n)
            out.pop()
    return out


# ---------------------------------------------------------------- coperture

def piano_falda(f: Falda) -> tuple[float, float, float]:
    """Coefficienti (a, b, c) del piano z = a x + b y + c dell'estradosso."""
    A = np.array([[x, y, 1.0] for x, y in f.poligono])
    z = np.array([q.valore for q in f.quote])
    coef, *_ = np.linalg.lstsq(A, z, rcond=None)
    return float(coef[0]), float(coef[1]), float(coef[2])


def z_falda(f: Falda, x: float, y: float) -> float:
    a, b, c = piano_falda(f)
    return a * x + b * y + c


def quota_intradosso(ed: Edificio, x: float, y: float) -> float | None:
    """Quota dell'intradosso della copertura sopra il punto (max tra le falde che lo coprono)."""
    pt = Point(x, y)
    zs = [z_falda(f, x, y) - f.spessore.valore for f in ed.falde if Polygon(f.poligono).buffer(1e-3).covers(pt)]  # 1 mm: i vertici delle falde sono arrotondati
    return max(zs) if zs else None


def profilo_apertura(ap: Apertura, n_arco: int = 16) -> list[tuple[float, float]]:
    """Contorno dell'apertura in coordinate locali (s da 0 a larghezza, z assoluta), antiorario."""
    w = ap.larghezza
    z0 = ap.davanzale.valore
    z1 = z0 + ap.altezza.valore
    if ap.forma == "rettangolare":
        return [(0, z0), (w, z0), (w, z1), (0, z1)]
    if ap.forma == "arco":
        f = w / 2
    else:
        f = ap.freccia.valore if ap.freccia else w / 6
    f = min(f, w / 2, z1 - z0)
    # arco di circonferenza per i punti (0, z1-f), (w/2, z1), (w, z1-f)
    r = (f * f + (w / 2) ** 2) / (2 * f)
    cx, cz = w / 2, z1 - r
    a0 = math.atan2((z1 - f) - cz, w - cx)
    a1 = math.pi - a0
    arco = [(cx + r * math.cos(t), cz + r * math.sin(t)) for t in np.linspace(a0, a1, n_arco + 1)]
    return [(0, z0), (w, z0)] + arco
