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


TRAVE_B, TRAVE_H, INTERASSE = 0.12, 0.16, 0.60  # schema dell'orditura se non rilevata
MANTO, TAVOLATO = 0.05, 0.025


@dataclass
class Stratigrafia:
    linee_manto: list  # LineString in coordinate di vista
    travi_tagliate: list  # Polygon
    travi_viste: list  # Polygon


def stratigrafia_copertura(ed: Edificio, sez: LineaSezione) -> Stratigrafia:
    """Manto, tavolato e travi dell'orditura (schematici) dove la sezione taglia le falde."""
    from ..geometria import piano_falda
    p0, u, v = direzione_sezione(sez)
    _, r = assi_vista(v)
    linea = LineString([tuple(p0 - u * 1000), tuple(p0 + u * 1000)])
    out = Stratigrafia([], [], [])
    for f in ed.falde:
        sp = f.spessore.valore
        a, b, _ = piano_falda(f)
        grad = np.array([a, b])
        for seg in _linee(Polygon(f.poligono).intersection(linea)):
            (ax, ay), (bx, by) = seg.coords[0], seg.coords[-1]
            xa = float(np.array([ax, ay, 0.0]) @ r)
            xb = float(np.array([bx, by, 0.0]) @ r)
            za, zb = z_falda(f, ax, ay), z_falda(f, bx, by)
            if xb < xa:
                xa, xb, za, zb = xb, xa, zb, za
            if sp >= 0.12:
                for d in (MANTO, MANTO + TAVOLATO):
                    out.linee_manto.append(LineString([(xa, za - d), (xb, zb - d)]))
            if "trav" not in f.struttura.lower():
                continue
            pend = float(np.linalg.norm(grad))
            lungo_pendenza = pend > 1e-6 and abs(float(u @ grad) / pend) > 0.7
            zi = lambda x: za - sp + (zb - za) * (x - xa) / (xb - xa) if xb > xa else za - sp
            if lungo_pendenza:
                out.travi_viste.append(Polygon([(xa, zi(xa)), (xb, zi(xb)), (xb, zi(xb) - TRAVE_H),
                                                (xa, zi(xa) - TRAVE_H)]))
            else:
                x = xa + INTERASSE / 2
                while x + TRAVE_B / 2 <= xb:
                    z = zi(x)
                    out.travi_tagliate.append(Polygon([(x - TRAVE_B / 2, z - TRAVE_H), (x + TRAVE_B / 2, z - TRAVE_H),
                                                       (x + TRAVE_B / 2, z), (x - TRAVE_B / 2, z)]))
                    x += INTERASSE
    return out


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
    st = stratigrafia_copertura(ed, sez)
    for ln in st.linee_manto:
        msp.add_lwpolyline([T(q) for q in ln.coords], dxfattribs={"layer": "SEZ_VISTO"})
    for pol in st.travi_tagliate:
        msp.add_lwpolyline([T(q) for q in pol.exterior.coords], close=True, dxfattribs={"layer": "SEZ_TAGLIATO"})
        h = msp.add_hatch(dxfattribs={"layer": "SEZ_TRATTEGGI"})
        h.set_pattern_fill("ANSI32", scale=sc / 1000 * 0.3)
        h.paths.add_polyline_path([T(q) for q in pol.exterior.coords[:-1]], is_closed=True)
    for pol in st.travi_viste:
        msp.add_lwpolyline([T(q) for q in pol.exterior.coords], close=True, dxfattribs={"layer": "SEZ_VISTO"})
    for f in ed.falde:
        if any(t.tipo == "falda" and t.rif == f.id for t in g.tagliati):
            t = next(t for t in g.tagliati if t.tipo == "falda" and t.rif == f.id)
            x0, z0, x1, z1 = t.poligono.bounds
            testo(msp, f"{f.manto} su {f.struttura}", T(((x0 + x1) / 2, z1 + mm(4, sc))), 1.8, sc, "NOTE")
            break
    miny = ing0.miny
    if st.travi_tagliate or st.travi_viste:
        nota = (f"Orditura del tetto schematica: travi {round(TRAVE_B * 100)}x{round(TRAVE_H * 100)} cm ogni "
                f"{fmt(INTERASSE)} m, da rilevare.")
        miny = ing0.miny - mm(7, sc)
        testo(msp, nota, ((ing0.minx + ing0.maxx) / 2, ing0.miny - mm(3, sc)), 1.8, sc, "NOTE")
    return Ingombro(ing0.minx, miny, ing0.maxx, ing0.maxy)
