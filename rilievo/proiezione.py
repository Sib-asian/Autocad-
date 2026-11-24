"""Proiezione ortogonale delle facce con rimozione delle parti nascoste.

Coordinate di vista: x = verso destra dell'osservatore, y = quota z.
La profondita' cresce allontanandosi dall'osservatore.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid

from .modello3d import Faccia

SU = np.array([0.0, 0.0, 1.0])


@dataclass
class Pezzo:
    poligono2d: object  # Polygon o MultiPolygon visibile
    profondita: float
    faccia: Faccia
    tagliato: bool = False


def assi_vista(direzione) -> tuple[np.ndarray, np.ndarray]:
    v = np.array(direzione, float)
    v[2] = 0.0
    v /= np.linalg.norm(v)
    r = np.array([v[1], -v[0], 0.0])
    return v, r


def a_vista(pts: np.ndarray, r: np.ndarray) -> np.ndarray:
    return np.column_stack([pts @ r, pts[:, 2]])


def _ritaglia(pts: np.ndarray, d: np.ndarray, d0: float) -> np.ndarray:
    """Sutherland-Hodgman: tiene la parte con dot(p, d) >= d0."""
    out = []
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        da, db = a @ d - d0, b @ d - d0
        if da >= 0:
            out.append(a)
        if (da >= 0) != (db >= 0):
            t = da / (da - db)
            out.append(a + (b - a) * t)
    return np.array(out) if len(out) >= 3 else np.zeros((0, 3))


def _poligono(f: Faccia, r, taglio) -> Polygon | None:
    shell = f.pts
    fori = f.fori
    if taglio is not None:
        d, d0 = taglio
        shell = _ritaglia(shell, d, d0)
        fori = [h for h in (_ritaglia(h, d, d0) for h in fori) if len(h)]
        if not len(shell):
            return None
    s2 = a_vista(shell, r)
    try:
        pol = Polygon(s2)
        if not pol.is_valid:
            pol = make_valid(pol)
        for h in fori:
            pol = pol.difference(make_valid(Polygon(a_vista(h, r))))
    except Exception:
        return None
    if pol.is_empty or pol.area < 1e-8:
        return None
    return pol


def _profondita_in(f: Faccia, v, r, x, z) -> float | None:
    """Profondita' del piano della faccia sulla retta di vista che passa per (x, z)."""
    n = f.normale
    den = float(n @ v)
    if abs(den) < 1e-9:
        return None
    q = x * r + z * SU
    return float(n @ (f.pts[0] - q) / den)


def proietta(facce: list[Faccia], direzione, piano_taglio=None, tipi=None) -> list[Pezzo]:
    """Proietta le facce viste dall'osservatore che guarda lungo `direzione`.

    piano_taglio: (punto, direzione) -> si tiene solo cio' che sta oltre il piano
    verticale passante per il punto (sezioni).
    """
    v, r = assi_vista(direzione)
    taglio = None
    if piano_taglio is not None:
        p, _ = piano_taglio
        p3 = np.array([p[0], p[1], 0.0])
        taglio = (v, float(p3 @ v))
    cand = []
    for f in facce:
        if tipi and f.tipo not in tipi:
            continue
        if float(f.normale @ v) > -1e-6:  # rivolta altrove o di taglio
            continue
        pol = _poligono(f, r, taglio)
        if pol is None:
            continue
        cand.append((f, pol, float((f.pts @ v).mean())))
    cand.sort(key=lambda t: t[2])
    pezzi = []
    for i, (fa, pa, da) in enumerate(cand):
        vis = pa
        coprenti = []
        for j, (fb, pb, db) in enumerate(cand):
            if i == j or not vis.intersects(pb):
                continue
            inter = vis.intersection(pb)
            if inter.is_empty or inter.area < 1e-9:
                continue
            c = inter.representative_point()
            za = _profondita_in(fa, v, r, c.x, c.y)
            zb = _profondita_in(fb, v, r, c.x, c.y)
            if za is None or zb is None:
                continue
            if zb < za - 1e-6 or (abs(zb - za) <= 1e-6 and fb.tipo == "infisso" and fa.tipo != "infisso"):
                coprenti.append(pb)
        if coprenti:
            vis = vis.difference(unary_union(coprenti))
        if vis.is_empty or vis.area < 1e-8:
            continue
        pezzi.append(Pezzo(vis, da, fa))
    return pezzi
