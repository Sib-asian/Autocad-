"""Generatore della pianta: muri tagliati con retino, aperture, locali, quote, simboli."""
from __future__ import annotations

import math
from dataclasses import dataclass

import ezdxf.bbox
import numpy as np
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import polylabel, unary_union

from ..dxf.quote import catena, fmt, fmt_quota, quota_allineata
from ..dxf.stile import aggiungi_dimstyle, mm, testo
from ..geometria import (apertura_mondo, direzione, normale_sx, perimetro_esterno, poligono_locale,
                         poligoni_muri)
from ..modello import Edificio
from ..modello3d import _muri_del_lato


@dataclass
class Ingombro:
    minx: float
    miny: float
    maxx: float
    maxy: float

    @property
    def larghezza(self):
        return self.maxx - self.minx

    @property
    def altezza(self):
        return self.maxy - self.miny

    @staticmethod
    def da_entita(ent) -> "Ingombro":
        bb = ezdxf.bbox.extents(ent, fast=True)
        return Ingombro(bb.extmin.x, bb.extmin.y, bb.extmax.x, bb.extmax.y)


RETINO_MATERIALE = [
    ("lavic", "ANSI33"), ("pietra", "ANSI33"), ("blocc", "ANSI31"), ("tufo", "ANSI31"),
    ("lateriz", "ANSI32"), ("mattoni", "ANSI32"), ("calcestr", "AR-CONC"), ("c.a", "AR-CONC"),
]


def retino(materiale: str) -> str:
    m = materiale.lower()
    for chiave, pat in RETINO_MATERIALE:
        if chiave in m:
            return pat
    return "ANSI31"


def _poligoni(g):
    if g.is_empty:
        return []
    return list(g.geoms) if isinstance(g, MultiPolygon) else [g] if isinstance(g, Polygon) else \
        [x for x in getattr(g, "geoms", []) if isinstance(x, Polygon)]


class _Penna:
    """Raccoglie le entita' create e applica la traslazione dell'origine."""

    def __init__(self, msp, origine, scala):
        self.msp, self.o, self.scala, self.ent = msp, np.array(origine, float), scala, []

    def T(self, p):
        return tuple(np.array(p[:2], float) + self.o)

    def poly(self, pts, layer, chiusa=False, **kw):
        e = self.msp.add_lwpolyline([self.T(p) for p in pts], close=chiusa, dxfattribs={"layer": layer, **kw})
        self.ent.append(e)
        return e

    def linea(self, a, b, layer, **kw):
        e = self.msp.add_line(self.T(a), self.T(b), dxfattribs={"layer": layer, **kw})
        self.ent.append(e)
        return e

    def arco(self, c, r, a0, a1, layer):
        e = self.msp.add_arc(self.T(c), r, a0, a1, dxfattribs={"layer": layer})
        self.ent.append(e)

    def testo(self, txt, pos, h_mm, layer="TESTI", allinea="MIDDLE_CENTER", rot=0.0):
        e = testo(self.msp, txt, self.T(pos), h_mm, self.scala, layer, allinea, rot)
        self.ent.append(e)
        return e

    def retino(self, pol: Polygon, pattern, layer="RETINI"):
        h = self.msp.add_hatch(color=256, dxfattribs={"layer": layer})
        if pattern == "SOLID":
            h.set_solid_fill(color=256)
        else:
            h.set_pattern_fill(pattern, scale=self.scala / 1000 * 0.6)
        h.paths.add_polyline_path([self.T(p) for p in pol.exterior.coords[:-1]], is_closed=True, flags=1)
        for r in pol.interiors:
            h.paths.add_polyline_path([self.T(p) for p in r.coords[:-1]], is_closed=True, flags=0)
        self.ent.append(h)


def disegna_pianta(ed: Edificio, msp, scala: int = 50, origine=(0.0, 0.0), quote: bool = True,
                   titolo: str | None = "PIANTA") -> Ingombro:
    P = _Penna(msp, origine, scala)
    ds = aggiungi_dimstyle(msp.doc, scala)
    tagliati = poligoni_muri(ed, con_aperture=True)

    # --- muri: retino per materiale + contorno unico (portanti e tramezzi separati)
    for m in ed.muri:
        for pol in _poligoni(tagliati[m.id]):
            P.retino(pol, retino(m.materiale))
    for ruolo, layer in (("portante", "MURI"), ("tramezzo", "TRAMEZZI")):
        u = unary_union([tagliati[m.id] for m in ed.muri if m.ruolo == ruolo])
        for pol in _poligoni(u):
            P.poly(pol.exterior.coords, layer, chiusa=True)
            for r in pol.interiors:
                P.poly(r.coords, layer, chiusa=True)
    for m in ed.muri:
        if m.spessore.ipotesi:
            for pol in _poligoni(tagliati[m.id]):
                P.poly(pol.exterior.coords, "IPOTESI_DA_VERIFICARE", chiusa=True)

    # --- aperture
    for ap in ed.aperture:
        _disegna_apertura(P, ed, ap)

    # --- elementi (forni, camini, scale...)
    for el in ed.elementi:
        if el.poligono:
            P.poly(el.poligono, "ELEMENTI", chiusa=True)
            c = Polygon(el.poligono).representative_point()
            P.testo(el.tipo, (c.x, c.y), 1.8, "ELEMENTI")

    # --- copertura proiettata (solo se sporge dai muri)
    if ed.falde:
        tetto = unary_union([Polygon(f.poligono) for f in ed.falde])
        muri_pieni = unary_union(list(poligoni_muri(ed, con_aperture=False).values()))
        if tetto.difference(muri_pieni.buffer(0.02)).area > 0.05 and not muri_pieni.buffer(0.02).contains(tetto):
            for pol in _poligoni(tetto):
                P.poly(pol.exterior.coords, "COPERTURA_PIANTA", chiusa=True)

    # --- locali: nome, superficie, altezze, quota pavimento
    for loc in ed.locali:
        pol = poligono_locale(ed, loc)
        c = polylabel(pol, tolerance=0.02)
        h = loc.h_min.valore
        if loc.h_max is not None and abs(loc.h_max.valore - h) > 0.005:
            htxt = f"h min {fmt(h)} - h max {fmt(loc.h_max.valore)}"
        else:
            htxt = f"h = {fmt(h)}"
        ipot = loc.h_min.ipotesi or (loc.h_max is not None and loc.h_max.ipotesi)
        lay = "IPOTESI_DA_VERIFICARE" if ipot else "TESTI"
        dz = mm(4.2, scala)
        P.testo(loc.nome.upper(), (c.x, c.y + dz), 3.0)
        P.testo(f"S = {fmt(pol.area)} m²", (c.x, c.y), 2.2)
        P.testo(htxt + (" (*)" if ipot else ""), (c.x, c.y - dz), 2.0, lay)
        P.testo(f"q. {fmt_quota(loc.quota_pavimento.valore)}", (c.x, c.y - 2 * dz), 1.8)

    if quote:
        _quote_esterne(P, ed, ds)
        _quote_interne(P, ed, ds)

    # --- linee di sezione
    for sez in ed.sezioni:
        _linea_sezione(P, ed, sez)

    ing = Ingombro.da_entita(P.ent)
    _nord(P, ed, (ing.maxx - P.o[0] + mm(14, scala), ing.maxy - P.o[1] - mm(12, scala)))
    if titolo:
        P.testo(f"{titolo}  scala 1:{scala}", ((ing.minx + ing.maxx) / 2 - P.o[0], ing.miny - P.o[1] - mm(10, scala)),
                4.0, "TESTI")
    return Ingombro.da_entita(P.ent)


def _disegna_apertura(P: _Penna, ed: Edificio, ap):
    m = ed.muro(ap.muro)
    a, b = (np.array(p) for p in apertura_mondo(ed, ap))
    d, n = direzione(m), normale_sx(m)
    h = m.spessore.valore / 2
    w = ap.larghezza
    alta = ap.davanzale.valore > 1.5
    lay = "APERTURE_NASCOSTE" if alta else "APERTURE"
    if ap.altezza.ipotesi or ap.davanzale.ipotesi:
        lay_i = "IPOTESI_DA_VERIFICARE"
    else:
        lay_i = None
    if ap.tipo in ("finestra", "feritoia"):
        for k in (-1, 1):
            P.linea(a + n * h * k, b + n * h * k, lay)
        P.linea(a, b, lay)
        P.linea(a + n * 0.03, b + n * 0.03, lay)
    elif ap.tipo == "porta":
        lato = 1 if ap.lato == "+" else -1
        faccia = n * h * lato
        ante = [(a, b)] if ap.battente in ("sx", "dx", "nessuno") else [(a, (a + b) / 2), (b, (a + b) / 2)]
        if ap.battente == "dx":
            ante = [(b, a)]
        for cern, chiusa in ante:
            r = float(np.linalg.norm(chiusa - cern))
            pc = cern + faccia
            pf = pc + n * lato * r
            P.linea(pc, pf, "APERTURE")
            ang_a = math.degrees(math.atan2(*(pf - pc)[::-1]))
            ang_b = math.degrees(math.atan2(*((chiusa + faccia) - pc)[::-1]))
            # arco nel verso antiorario corto
            a0, a1 = (ang_a, ang_b) if (ang_b - ang_a) % 360 < 180 else (ang_b, ang_a)
            P.arco(pc, r, a0, a1, "APERTURE")
        P.linea(a - n * h, b - n * h, "APERTURE")  # soglia
        P.linea(a + n * h, b + n * h, "APERTURE")
    elif ap.tipo == "varco" and ap.forma != "rettangolare":
        for k in (-1, 1):
            P.linea(a + n * h * k, b + n * h * k, "APERTURE_NASCOSTE")
    if lay_i:
        P.poly([a + n * h, b + n * h, b - n * h, a - n * h], lay_i, chiusa=True)


def _quote_esterne(P: _Penna, ed: Edificio, ds: str):
    sc = P.scala
    for p0, p1, nrm in perimetro_esterno(ed):
        L = math.dist(p0, p1)
        if L < 0.3:
            continue
        pa, pb = np.array(p0), np.array(p1)
        u = (pb - pa) / L
        punti = [pa, pb]
        for m in _muri_del_lato(ed, p0, p1):
            if abs(abs(float(np.dot(u, direzione(m)))) - 1) > 1e-6:
                continue
            for ap in ed.aperture_di(m.id):
                for q in apertura_mondo(ed, ap):
                    s = float(np.dot(np.array(q) - pa, u))
                    if 0 < s < L:
                        punti.append(pa + u * s)
        # direzione invertita: la catena va a sinistra di (p1->p0), cioe' verso l'esterno
        c = catena(P.msp, [P.T(p) for p in punti], tuple(-u), mm(10, sc), ds, totale=True,
                   offset_totale=mm(18, sc))
        P.ent.extend(c.entita)


def _quote_interne(P: _Penna, ed: Edificio, ds: str):
    sc = P.scala
    for loc in ed.locali:
        pol = orient(poligono_locale(ed, loc), 1.0)
        mrr = pol.minimum_rotated_rectangle
        if mrr.area > 0 and pol.area / mrr.area > 0.985:
            # rettangolo: due quote che passano vicino al centro, fuori dall'etichetta del locale
            c = [np.array(q) for q in list(orient(mrr, 1.0).exterior.coords)[:4]]
            for i, (sposta_mm) in ((0, 14), (1, 24)):
                a, b = c[i], c[i + 1]
                prof = float(np.linalg.norm(c[(i + 2) % 4] - b))
                off = max(min(prof / 2 - mm(sposta_mm, sc), prof - mm(5, sc)), mm(5, sc))
                P.ent.extend(quota_allineata(P.msp, P.T(a), P.T(b), off, ds))
        else:
            c = list(pol.exterior.coords)
            for a, b in ((a, b) for a, b in zip(c, c[1:]) if math.dist(a, b) > 0.3):
                P.ent.extend(quota_allineata(P.msp, P.T(a), P.T(b), mm(7, sc), ds))
    # larghezza delle porte interne (non sul perimetro)
    perim = [LineStringSafe(p0, p1) for p0, p1, _ in perimetro_esterno(ed)]
    for ap in ed.aperture:
        a, b = apertura_mondo(ed, ap)
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        m = ed.muro(ap.muro)
        if min(l.distance_to(mid) for l in perim) > m.spessore.valore / 2 + 0.01:
            n = normale_sx(m)
            h = m.spessore.valore / 2
            pa = np.array(a) - n * h
            pb = np.array(b) - n * h
            P.ent.extend(quota_allineata(P.msp, P.T(pb), P.T(pa), mm(4, sc), ds))


class LineStringSafe:
    def __init__(self, p0, p1):
        self.a, self.b = np.array(p0, float), np.array(p1, float)

    def distance_to(self, p):
        p = np.array(p, float)
        ab = self.b - self.a
        t = np.clip(np.dot(p - self.a, ab) / np.dot(ab, ab), 0, 1)
        return float(np.linalg.norm(self.a + ab * t - p))


def _linea_sezione(P: _Penna, ed: Edificio, sez):
    sc = P.scala
    p0, p1 = np.array(sez.p0, float), np.array(sez.p1, float)
    u = (p1 - p0) / np.linalg.norm(p1 - p0)
    n = np.array([-u[1], u[0]]) * (1 if sez.verso == "sx" else -1)
    # la linea attraversa tutto l'edificio e supera le catene di quote esterne
    minx, miny, maxx, maxy = unary_union(list(poligoni_muri(ed, con_aperture=False).values())).bounds
    ss = [float(np.dot(np.array(q) - p0, u)) for q in ((minx, miny), (minx, maxy), (maxx, miny), (maxx, maxy))]
    p1 = p0 + u * max(ss)
    p0 = p0 + u * min(ss)
    est = mm(28, sc)
    P.linea(p0 - u * est, p1 + u * est, "LINEE_SEZIONE")
    for q, s in ((p0 - u * est, 1), (p1 + u * est, -1)):
        e = P.poly([q, q + u * s * mm(8, sc)], "LINEE_SEZIONE")
        e.dxf.const_width = mm(0.8, sc)
        punta = q + n * mm(6, sc)
        P.poly([q, punta], "LINEE_SEZIONE")
        P.poly([punta, punta - n * mm(2, sc) + u * mm(1, sc), punta - n * mm(2, sc) - u * mm(1, sc)],
               "LINEE_SEZIONE", chiusa=True)
        P.testo(sez.nome, q + n * mm(9, sc), 5.0, "LINEE_SEZIONE")


def _nord(P: _Penna, ed: Edificio, pos):
    sc = P.scala
    r = mm(8, sc)
    c = np.array(pos, float)
    lay = "IPOTESI_DA_VERIFICARE" if ed.nord_ipotizzato else "TESTI"
    e = P.msp.add_circle(P.T(c), r, dxfattribs={"layer": lay})
    P.ent.append(e)
    a = math.radians(ed.nord_gradi)
    u = np.array([math.cos(a), math.sin(a)])
    n = np.array([-u[1], u[0]])
    P.poly([c + u * r, c - u * r * 0.6 + n * r * 0.4, c - u * r * 0.3, c - u * r * 0.6 - n * r * 0.4], lay,
           chiusa=True)
    P.testo("N", c + u * (r + mm(4, sc)), 4.0, lay)
    if ed.nord_ipotizzato:
        P.testo("Nord da verificare", c - u * (r + mm(4, sc)), 1.8, lay)
