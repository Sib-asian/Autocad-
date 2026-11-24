"""Quote con arrotondamento HALF-UP al centimetro sugli estremi.

Arrotondando gli estremi (e non le differenze) la somma dei parziali
mostrati coincide sempre con il totale mostrato.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import numpy as np

CM = Decimal("0.01")


def arrotonda(x: float) -> Decimal:
    return Decimal(repr(round(float(x), 9))).quantize(CM, rounding=ROUND_HALF_UP)


def fmt(d: Decimal | float) -> str:
    if not isinstance(d, Decimal):
        d = arrotonda(d)
    s = f"{d:.2f}".replace(".", ",")
    return "0,00" if s == "-0,00" else s


def fmt_quota(z: float) -> str:
    d = arrotonda(z)
    if d == 0:
        return "±0,00"  # quota di riferimento
    return ("+" if d > 0 else "") + fmt(d)


@dataclass
class Catena:
    parziali: list[Decimal]
    totale: Decimal
    entita: list


def catena(msp, punti, direzione, offset: float, dimstyle: str, layer: str = "QUOTE",
           totale: bool = False, offset_totale: float | None = None, min_parziale: float = 0.005) -> Catena:
    """Catena di quote allineate lungo `direzione`, spostata di `offset` a sinistra di essa.

    I punti vengono proiettati sulla direzione e ordinati; ogni estremo e'
    arrotondato al cm, i parziali sono differenze di estremi arrotondati.
    """
    d = np.array(direzione, float)
    d /= np.linalg.norm(d)
    n = np.array([-d[1], d[0]])
    ang0 = float(np.degrees(np.arctan2(d[1], d[0])))
    if not (-90 + 1e-6 < ang0 <= 90 + 1e-6):  # testo capovolto: inverte la direzione, stesso lato
        d = -d
        n = -n
        offset = -offset
        if offset_totale is not None:
            offset_totale = -offset_totale
    P = [np.array(p, float) for p in punti]
    o = P[0]
    s = sorted({float(np.dot(p - o, d)) for p in P})
    # base: proiezione del punto piu' lontano verso il lato quotato
    proj = [float(np.dot(p - o, n)) for p in P]
    base_off = max(proj) if offset >= 0 else min(proj)
    sr = [arrotonda(x) for x in s]
    # elimina estremi coincidenti dopo l'arrotondamento
    pts, vals = [], []
    for x, xr in zip(s, sr):
        if vals and xr - vals[-1] < Decimal(str(min_parziale)):
            continue
        pts.append(x)
        vals.append(xr)
    if pts and pts[-1] != s[-1]:  # l'estremo finale resta sempre (al posto dell'ultimo troppo vicino)
        pts[-1], vals[-1] = s[-1], sr[-1]
    ang = float(np.degrees(np.arctan2(d[1], d[0])))
    ent, parz = [], []

    def quota(xa, xb, va, vb, off):
        p1 = o + d * xa + n * base_off
        p2 = o + d * xb + n * base_off
        base = o + d * xa + n * (base_off + off)
        dim = msp.add_linear_dim(base=tuple(base), p1=tuple(p1), p2=tuple(p2), angle=ang, dimstyle=dimstyle,
                                 text=fmt(vb - va), dxfattribs={"layer": layer})
        dim.render()
        return dim.dimension

    for (xa, va), (xb, vb) in zip(zip(pts, vals), zip(pts[1:], vals[1:])):
        ent.append(quota(xa, xb, va, vb, offset))
        parz.append(vb - va)
    tot = vals[-1] - vals[0] if vals else Decimal(0)
    if totale and len(pts) > 2:
        ent.append(quota(pts[0], pts[-1], vals[0], vals[-1], offset_totale or offset * 2))
    return Catena(parz, tot, ent)


def quota_allineata(msp, p1, p2, offset: float, dimstyle: str, layer: str = "QUOTE"):
    """Singola quota allineata p1-p2 spostata di `offset` a sinistra di p1->p2."""
    return catena(msp, [p1, p2], np.subtract(p2, p1), offset, dimstyle, layer).entita
