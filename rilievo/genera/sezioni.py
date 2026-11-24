"""Generatore delle sezioni verticali."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from ..dxf.quote import catena, fmt
from ..dxf.stile import aggiungi_dimstyle, mm
from ..geometria import (poligono_locale, poligono_muro, quota_intradosso, rettangolo_apertura, z_falda)
from ..modello import Edificio, LineaSezione
from ..modello3d import facce
from ..proiezione import Pezzo, assi_vista, proietta
from .pianta import Ingombro, _poligoni, retino
from .prospetti import _linee, disegna_pezzi

PASSO = 0.05
PROFONDITA_TERRENO = 0.5


@dataclass
class Tagliato:
    poligono: Polygon
    tipo: str  # muro, falda, terreno, pavimento
    rif: str
    materiale: str = ""


@dataclass
class GeometriaSezione:
    tagliati: list[Tagliato]
    visti: list[Pezzo]
    direzione: np.ndarray
    r: np.ndarray
    locali: list[tuple]  # (locale, x0, x1, xm, pianta_xy_medio)


def direzione_sezione(sez: LineaSezione) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    p0, p1 = np.array(sez.p0, float), np.array(sez.p1, float)
    u = (p1 - p0) / np.linalg.norm(p1 - p0)
    nl = np.array([-u[1], u[0]])
    v2 = nl if sez.verso == "sx" else -nl
    return p0, u, np.array([v2[0], v2[1], 0.0])


def geometria_sezione(ed: Edificio, sez: LineaSezione) -> GeometriaSezione:
    p0, u, v = direzione_sezione(sez)
    _, r = assi_vista(v)
    linea = LineString([tuple(p0 - u * 1000), tuple(p0 + u * 1000)])

    def X(xy):  # coordinata orizzontale di vista
        return float(np.array([xy[0], xy[1], 0.0]) @ r)

    def XY(x):  # punto in pianta sulla linea di taglio, data la x di vista
        pr0 = X(p0)
        s = (x - pr0) / float(np.array([u[0], u[1], 0]) @ r)
        return p0 + u * s

    tag: list[Tagliato] = []
    zt = ed.quota_terreno.valore
    # --- muri
    for m in ed.muri:
        inter = poligono_muro(ed, m).intersection(linea)
        for seg in _linee(inter):
            xa, xb = sorted(X(c) for c in seg.coords)
            if xb - xa < 1e-6:
                continue
            xs = np.unique(np.concatenate([np.arange(xa, xb, PASSO), [xb]]))
            top = []
            for x in xs:
                if m.altezza is not None:
                    top.append(m.altezza.valore)
                else:
                    q = quota_intradosso(ed, *XY(x))
                    top.append(q if q is not None else 3.0)
            pol = Polygon([(xa, zt), (xb, zt)] + [(x, z) for x, z in zip(xs[::-1], top[::-1])])
            for ap in ed.aperture_di(m.id):
                if rettangolo_apertura(ed, ap).intersects(linea):
                    z0 = ap.davanzale.valore
                    pol = pol.difference(box(xa - 0.01, z0, xb + 0.01, z0 + ap.altezza.valore))
            for pp in _poligoni(pol):
                tag.append(Tagliato(pp, "muro", m.id, m.materiale))
    # --- falde
    for f in ed.falde:
        inter = Polygon(f.poligono).intersection(linea)
        for seg in _linee(inter):
            (ax, ay), (bx, by) = seg.coords[0], seg.coords[-1]
            xa, xb = X((ax, ay)), X((bx, by))
            za, zb = z_falda(f, ax, ay), z_falda(f, bx, by)
            sp = f.spessore.valore
            pol = Polygon([(xa, za), (xb, zb), (xb, zb - sp), (xa, za - sp)])
            if pol.area > 1e-6:
                tag.append(Tagliato(pol, "falda", f.id, f.manto))
    # --- terreno e pavimenti
    if tag:
        minx = min(t.poligono.bounds[0] for t in tag)
        maxx = max(t.poligono.bounds[2] for t in tag)
        tag.append(Tagliato(box(minx - 1.0, zt - PROFONDITA_TERRENO, maxx + 1.0, zt), "terreno", "terreno"))
    locali = []
    for loc in ed.locali:
        try:
            pl = poligono_locale(ed, loc)
        except ValueError:
            continue
        for seg in _linee(pl.intersection(linea)):
            xa, xb = sorted(X(c) for c in seg.coords)
            xm = (xa + xb) / 2
            locali.append((loc, xa, xb, xm, XY(xm)))

    tag_u = unary_union([t.poligono for t in tag]) if tag else Polygon()
    visti = []
    for p in proietta(facce(ed), v, piano_taglio=(p0, v)):
        vis = p.poligono2d.difference(tag_u.buffer(1e-7)) if not tag_u.is_empty else p.poligono2d
        if not vis.is_empty and vis.area > 1e-8:
            visti.append(Pezzo(vis, p.profondita, p.faccia))
    return GeometriaSezione(tag, visti, v, r, locali)


def _dir_x(g: GeometriaSezione) -> np.ndarray:
    """Vettore in pianta corrispondente a +1 sulla x di vista lungo la linea di taglio."""
    v = g.direzione
    u = np.array([-v[1], v[0]])  # perpendicolare alla vista = direzione della linea
    k = float(np.array([u[0], u[1], 0.0]) @ g.r)
    return u / k


def altezza_media(ed: Edificio, loc, passo: float = 0.05) -> float | None:
    """Altezza media ponderata (volume / superficie) dall'intradosso della copertura."""
    pl = poligono_locale(ed, loc)
    minx, miny, maxx, maxy = pl.bounds
    hs = []
    for x in np.arange(minx + passo / 2, maxx, passo):
        for y in np.arange(miny + passo / 2, maxy, passo):
            if pl.contains(Point(x, y)):
                q = quota_intradosso(ed, x, y)
                if q is None:
                    return None
                hs.append(q - loc.quota_pavimento.valore)
    return float(np.mean(hs)) if hs else None


def disegna_sezione(ed: Edificio, sez: LineaSezione, msp, scala: int = 50, origine=(0.0, 0.0),
                    quote: bool = True) -> Ingombro:
    g = geometria_sezione(ed, sez)
    sc = scala
    ds = aggiungi_dimstyle(msp.doc, scala)
    tag_pol = [t.poligono for t in g.tagliati if t.tipo != "terreno"]
    ing0 = disegna_pezzi(ed, f"SEZIONE {sez.nome}-{sez.nome}", sez.nome, sez.nome, g.visti, msp, scala, origine,
                         quote=quote, titolo=True, tagliati=tag_pol)
    # stessa origine usata da disegna_pezzi
    tutti = [p.poligono2d for p in g.visti] + tag_pol
    minx = unary_union(tutti).bounds[0]
    o = np.array([origine[0] - minx, origine[1]])

    def T(p):
        return (p[0] + o[0], p[1] + o[1])

    for t in g.tagliati:
        for pol in _poligoni(t.poligono):
            if t.tipo == "terreno":
                h = msp.add_hatch(dxfattribs={"layer": "SEZ_TRATTEGGI"})
                h.set_pattern_fill("EARTH", scale=sc / 1000 * 0.5)
                h.paths.add_polyline_path([T(q) for q in pol.exterior.coords[:-1]], is_closed=True)
                continue
            msp.add_lwpolyline([T(q) for q in pol.exterior.coords], close=True,
                               dxfattribs={"layer": "SEZ_TAGLIATO"})
            for rr in pol.interiors:
                msp.add_lwpolyline([T(q) for q in rr.coords], close=True, dxfattribs={"layer": "SEZ_TAGLIATO"})
            h = msp.add_hatch(dxfattribs={"layer": "SEZ_TRATTEGGI"})
            pat = retino(t.materiale) if t.tipo == "muro" else "ANSI36"
            h.set_pattern_fill(pat, scale=sc / 1000 * 0.6)
            h.paths.add_polyline_path([T(q) for q in pol.exterior.coords[:-1]], is_closed=True, flags=1)
            for rr in pol.interiors:
                h.paths.add_polyline_path([T(q) for q in rr.coords[:-1]], is_closed=True, flags=0)
    # linea di terra spessa
    terr = [t for t in g.tagliati if t.tipo == "terreno"]
    for t in terr:
        x0, _, x1, z1 = t.poligono.bounds
        msp.add_lwpolyline([T((x0, z1)), T((x1, z1))], dxfattribs={"layer": "TERRENO"})
    # pavimento dei locali, altezze e descrizione copertura
    from ..dxf.stile import testo
    for loc, xa, xb, xm, xy in g.locali:
        zp = loc.quota_pavimento.valore
        msp.add_lwpolyline([T((xa, zp)), T((xb, zp))], dxfattribs={"layer": "SEZ_TAGLIATO"})
        qi = quota_intradosso(ed, *xy)
        xq = xa + 0.22 * (xb - xa)
        if quote and qi is not None:
            qq = quota_intradosso(ed, *(xy + (xq - xm) * _dir_x(g)))
            if qq is not None:
                catena(msp, [T((xq, zp)), T((xq, qq))], (0, 1), mm(2, sc), ds)
        righe = [loc.nome.upper()]
        if loc.h_max is not None:
            righe.append(f"h min {fmt(loc.h_min.valore)} - h max {fmt(loc.h_max.valore)}")
        else:
            righe.append(f"h = {fmt(loc.h_min.valore)}")
        hm = altezza_media(ed, loc)
        if hm is not None:
            righe.append(f"h media {fmt(hm)} (da modello)")
        for i, rg in enumerate(righe):
            testo(msp, rg, T((xa + 0.6 * (xb - xa), zp + mm(14, sc) - i * mm(4, sc))), 2.2 if i else 2.6, sc,
                  "TESTI", "MIDDLE_CENTER")
    miny = ing0.miny
    return Ingombro(ing0.minx, miny, ing0.maxx, ing0.maxy)
