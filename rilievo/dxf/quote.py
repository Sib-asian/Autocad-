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


def _scatole_testo(dim) -> list:
    """Rettangoli dei testi di una quota gia' disegnata."""
    import ezdxf.bbox
    from shapely.geometry import box
    out = []
    for v in dim.virtual_entities():
        if v.dxftype() in ("TEXT", "MTEXT"):
            bb = ezdxf.bbox.extents([v], fast=False)
            if bb.has_data:
                out.append(box(bb.extmin.x, bb.extmin.y, bb.extmax.x, bb.extmax.y))
    return out


def _testi_quote(msp) -> list:
    """Testi delle quote gia' presenti nel disegno (calcolati una volta, poi aggiornati quota per quota)."""
    if not hasattr(msp, "_testi_quote_cache"):
        msp._testi_quote_cache = [b for d in msp.query("DIMENSION") for b in _scatole_testo(d)]
    return msp._testi_quote_cache


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
    stile = msp.doc.dimstyles.get(dimstyle)
    k = float(stile.dxf.get("dimscale", 1.0)) or 1.0  # metri di disegno per mm di carta
    h_txt = float(stile.dxf.get("dimtxt", 2.2))
    spostati: list[tuple[float, float, int]] = []  # (centro lungo d in mm, larghezza, livello)
    occupati = _testi_quote(msp)

    def scatola(centro, w):  # ingombro del testo (allineato alla catena) attorno al centro
        from shapely.geometry import Polygon
        a, b = d * k * w / 2, n * k * h_txt / 2
        c = np.array(centro, float)
        return Polygon([tuple(c - a - b), tuple(c + a - b), tuple(c + a + b), tuple(c - a + b)])

    def libero(centro, w):
        sc = scatola(centro, w).buffer(-k * 0.2)
        return not any(sc.intersects(q) for q in occupati)

    def quota(xa, xb, va, vb, off, corto_fuori=True, estremo=0):
        from .stile import larghezza_testo
        p1 = o + d * xa + n * base_off
        p2 = o + d * xb + n * base_off
        base = o + d * xa + n * (base_off + off)
        testo = fmt(vb - va)
        dim = msp.add_linear_dim(base=tuple(base), p1=tuple(p1), p2=tuple(p2), angle=ang, dimstyle=dimstyle,
                                 text=testo, dxfattribs={"layer": layer})
        w = larghezza_testo(testo, h_txt)
        sgn = 1.0 if off >= 0 else -1.0
        posto = None
        if corto_fuori and (xb - xa) / k < w + 1.0:
            # il testo non entra fra i due trattini. Primo o ultimo tratto: oltre l'estremita' della catena;
            # altrimenti (o se li' e' occupato) appena fuori dalla linea, a livelli crescenti: sempre in un posto
            # libero da altri testi di quota
            candidati = []
            if estremo:
                x = (xa - k * (w / 2 + 1.0)) if estremo < 0 else (xb + k * (w / 2 + 1.0))
                candidati.append(o + d * x + n * (base_off + off + sgn * k * (h_txt / 2 + 1.1)))
            c = (xa + xb) / 2 / k
            # un solo livello, appena fuori dalla linea (fra 1,1 e 3,6 mm): oltre c'e' la fascia dei testi della
            # catena successiva, 8 mm piu' in la'
            if not any(abs(c - c2) < (w + w2) / 2 + 1.0 for c2, w2, _ in spostati):
                candidati.append((1, o + d * (xa + xb) / 2 + n * (base_off + off + sgn * k * (h_txt / 2 + 1.1))))
            for cand in candidati:
                livello, pos = cand if isinstance(cand, tuple) else (0, cand)
                if libero(pos, w):
                    posto = pos
                    if livello:
                        spostati.append((c, w, livello))
                    break
        if posto is not None:
            dim.set_location(tuple(posto), leader=False)
        try:
            dim.render()
        except (TypeError, ValueError):  # ezdxf non sa tagliare la linea attorno al testo spostato:
            msp.delete_entity(dim.dimension)  # meglio la quota nella posizione normale che nessuna quota
            dim = msp.add_linear_dim(base=tuple(base), p1=tuple(p1), p2=tuple(p2), angle=ang, dimstyle=dimstyle,
                                     text=testo, dxfattribs={"layer": layer})
            dim.render()
        occupati.extend(_scatole_testo(dim.dimension))
        return dim.dimension

    tratti = list(zip(zip(pts, vals), zip(pts[1:], vals[1:])))
    for i, ((xa, va), (xb, vb)) in enumerate(tratti):
        estremo = 0 if len(tratti) < 2 else (-1 if i == 0 else (1 if i == len(tratti) - 1 else 0))
        ent.append(quota(xa, xb, va, vb, offset, estremo=estremo))
        parz.append(vb - va)
    tot = vals[-1] - vals[0] if vals else Decimal(0)
    if totale and len(pts) > 2:
        ent.append(quota(pts[0], pts[-1], vals[0], vals[-1], offset_totale or offset * 2))
    return Catena(parz, tot, ent)


def quota_allineata(msp, p1, p2, offset: float, dimstyle: str, layer: str = "QUOTE"):
    """Singola quota allineata p1-p2 spostata di `offset` a sinistra di p1->p2."""
    return catena(msp, [p1, p2], np.subtract(p2, p1), offset, dimstyle, layer).entita
