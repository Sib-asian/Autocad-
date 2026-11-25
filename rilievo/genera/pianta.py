"""Generatore della pianta: muri tagliati con retino, aperture, locali, quote, simboli."""
from __future__ import annotations

import math
from dataclasses import dataclass

import ezdxf.bbox
import numpy as np
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import polylabel, unary_union

from ..dxf.quote import catena, fmt, fmt_quota, quota_allineata
from ..dxf.stile import aggiungi_dimstyle, larghezza_testo, mm, testo
from ..geometria import (apertura_mondo, direzione, normale_sx, perimetro_esterno, poligono_locale,
                         poligono_muro, poligoni_muri)
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
                   titolo: str | None = "PIANTA", schema: bool = False, linee_sezione: bool = True) -> Ingombro:
    """schema=True: pianta essenziale (muri, aperture, nomi dei locali, linee di sezione) per lo schema di
    riferimento delle sezioni."""
    P = _Penna(msp, origine, scala)
    P.schema = schema
    P.sigle = []
    P.ante = []
    P.ante_mondo = []
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
    for el in ([] if schema else ed.elementi):
        if el.poligono:
            P.poly(el.poligono, "ELEMENTI", chiusa=True)
            c = Polygon(el.poligono).representative_point()
            P.testo(el.tipo, (c.x, c.y), 1.8, "ELEMENTI")

    # --- copertura proiettata (solo se sporge dai muri)
    if ed.falde and not schema:
        tetto = unary_union([Polygon(f.poligono) for f in ed.falde])
        muri_pieni = unary_union(list(poligoni_muri(ed, con_aperture=False).values()))
        sagoma = unary_union([Polygon(p.exterior) for p in _poligoni(muri_pieni)])
        if tetto.difference(sagoma.buffer(0.02)).area > 0.05:
            for pol in _poligoni(tetto):
                P.poly(pol.exterior.coords, "COPERTURA_PIANTA", chiusa=True)

    # --- locali: nome, superficie, altezze, quota pavimento
    ante = unary_union(getattr(P, "ante_mondo", [])) if getattr(P, "ante_mondo", None) else None
    for loc in ed.locali:
        pol = poligono_locale(ed, loc)
        libero = pol
        if ante is not None and not schema:  # l'etichetta sta fuori dalle zone spazzate dalle ante
            resto = pol.difference(ante.buffer(mm(0.5, scala)))
            if not resto.is_empty:
                libero = max(getattr(resto, "geoms", [resto]), key=lambda g: g.area)
        c = polylabel(libero, tolerance=0.02)
        h = loc.h_min.valore
        if loc.h_max is not None and abs(loc.h_max.valore - h) > 0.005:
            htxt = f"h min {fmt(h)} - h max {fmt(loc.h_max.valore)}"
        else:
            htxt = f"h = {fmt(h)}"
        ipot = loc.h_min.ipotesi or (loc.h_max is not None and loc.h_max.ipotesi)
        lay = "IPOTESI_DA_VERIFICARE" if ipot else "TESTI"
        if schema:
            P.testo(loc.nome.upper(), (c.x, c.y), 2.2)
            continue
        nome = (loc.nome.upper(), "TESTI")
        sup = (f"S = {fmt(pol.area)} m²", "TESTI")
        alt = (htxt + (" (*)" if ipot else ""), lay)
        quota = (f"q. {fmt_quota(loc.quota_pavimento.valore)}", "TESTI")
        # la versione piu' completa che entra nel locale (nei locali piccoli si toglie il superfluo)
        breve = (_abbrevia(loc.nome), "TESTI")
        solo_s = (f"{fmt(pol.area)} m²", "TESTI")
        varianti = [([nome, sup, alt, quota], [3.0, 2.2, 2.0, 1.8], 4.2),
                    ([nome, sup, alt], [2.2, 1.8, 1.8], 3.0),
                    ([nome, sup], [1.8, 1.6], 2.5),
                    ([breve, solo_s], [1.8, 1.6], 2.5),
                    ([breve, solo_s], [1.6, 1.5], 2.2)]
        for area, centro in ((libero, c), (pol, polylabel(pol, tolerance=0.02))):
            for righe, alte, passo in varianti:
                if _etichetta_entra(area, centro, [t for t, _ in righe], alte, passo, scala):
                    break
            else:
                continue
            c = centro
            break
        y0 = c.y + mm(passo, scala) * (len(righe) - 1) / 2
        for k, ((t, ly), hh) in enumerate(zip(righe, alte)):
            P.testo(t, (c.x, y0 - k * mm(passo, scala)), hh, ly)

    if quote:
        _quote_esterne(P, ed, ds)
        _quote_interne(P, ed, ds)
    from shapely.affinity import translate
    occupati = _ingombri_testi(P.ent) + [translate(g, P.o[0], P.o[1]) for g in tagliati.values()] + P.ante
    for ap, a, b, n, h, lay_sigla in P.sigle:
        _etichetta_apertura(P, ed, ap, a, b, n, h, lay_sigla, occupati)

    # --- linee di sezione (solo se le sezioni fanno parte delle tavole)
    for sez in (ed.sezioni if linee_sezione else []):
        _linea_sezione(P, ed, sez)

    ing = Ingombro.da_entita(P.ent)
    _nord(P, ed, (ing.maxx - P.o[0] + mm(14, scala), ing.maxy - P.o[1] - mm(12, scala)))
    if titolo:
        P.testo(f"{titolo}  scala 1:{scala}", ((ing.minx + ing.maxx) / 2 - P.o[0], ing.miny - P.o[1] - mm(10, scala)),
                4.0, "TESTI")
    return Ingombro.da_entita(P.ent)


ABBREVIAZIONI = {"ANTIBAGNO": "ANTIB.", "DISIMPEGNO": "DISIMP.", "RIPOSTIGLIO": "RIP.", "SOGGIORNO": "SOGG.",
                 "INGRESSO": "ING.", "LAVANDERIA": "LAV.", "CORRIDOIO": "CORR.", "SGABUZZINO": "SGAB.",
                 "CAMERA": "CAM.", "CUCINA": "CUC.", "DEPOSITO": "DEP.", "MAGAZZINO": "MAG."}


def _abbrevia(nome: str) -> str:
    """Abbreviazione d'uso tecnico per i locali piccoli (come nelle planimetrie catastali: RIP., W.C.)."""
    parole = nome.upper().split()
    return " ".join(ABBREVIAZIONI.get(w, w if len(w) <= 6 else w[:4] + ".") for w in parole)


def _etichetta_entra(pol, c, testi, alte, passo, scala, margine=0.8) -> bool:
    """Il blocco di testo centrato in c sta dentro il locale con un margine (mm sulla carta)?"""
    from shapely.geometry import box
    larg = max(larghezza_testo(t, h) for t, h in zip(testi, alte))
    alt = passo * (len(testi) - 1) + max(alte)
    w, hh = mm(larg, scala) / 2, mm(alt, scala) / 2
    return box(c.x - w, c.y - hh, c.x + w, c.y + hh).within(pol.buffer(-mm(margine, scala)))


def disegna_schema_sezioni(ed: Edificio, msp, scala: int = 50, origine=(0.0, 0.0), rapporto: int = 4) -> Ingombro:
    """Piccola pianta (scala 1:scala*rapporto) con le tracce delle sezioni, da mettere nella tavola delle sezioni:
    chi legge la tavola vede subito dove sono stati fatti i tagli."""
    from ezdxf.math import Matrix44
    prima = {e.dxf.handle for e in msp}
    disegna_pianta(ed, msp, scala * rapporto, (0.0, 0.0), quote=False, titolo="SCHEMA DELLE SEZIONI", schema=True)
    nuove = [e for e in msp if e.dxf.handle not in prima]
    m = Matrix44.scale(1 / rapporto, 1 / rapporto, 1) @ Matrix44.translate(origine[0], origine[1], 0)
    for e in nuove:
        e.transform(m)
    return Ingombro.da_entita(nuove)


def _disegna_apertura(P: _Penna, ed: Edificio, ap):
    m = ed.muro(ap.muro)
    a, b = (np.array(p) for p in apertura_mondo(ed, ap))
    n = normale_sx(m)
    h = m.spessore.valore / 2
    alta = ap.davanzale.valore > 1.5
    lay = "APERTURE_NASCOSTE" if alta else "APERTURE"
    # in pianta il vano e' rosso solo se larghezza o posizione sono ipotizzate; se manca solo l'altezza o il
    # davanzale, e' rossa la sola sigla (il disegno del vano e' misurato)
    lay_i = "IPOTESI_DA_VERIFICARE" if (ap.da.ipotesi or ap.a.ipotesi) else None
    lay_sigla = "IPOTESI_DA_VERIFICARE" if (lay_i or ap.altezza.ipotesi or ap.davanzale.ipotesi) else "TESTI"
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
            # zona spazzata dall'anta: le sigle non ci vanno sopra
            zona = [pc, chiusa + faccia, chiusa + faccia + n * lato * r, pf]
            P.ante.append(Polygon([tuple(P.T(q)) for q in zona]))
            P.ante_mondo.append(Polygon([tuple(q) for q in zona]))
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
    if not getattr(P, "schema", False):  # le sigle si posano alla fine, dove c'e' posto
        P.sigle.append((ap, a, b, n, h, lay_sigla))


def _ingombri_testi(entita) -> list:
    """Zone occupate da testi, testi delle quote e linee delle quote gia' disegnati."""
    import ezdxf.bbox
    from shapely.geometry import box
    out = []
    for e in entita:
        t = e.dxftype()
        if t == "DIMENSION":
            for v in e.virtual_entities():
                if v.dxftype() == "LINE":
                    out.append(LineString([(v.dxf.start.x, v.dxf.start.y), (v.dxf.end.x, v.dxf.end.y)]))
        ents = [e] if t in ("TEXT", "MTEXT") else (
            [v for v in e.virtual_entities() if v.dxftype() in ("TEXT", "MTEXT")] if t == "DIMENSION" else [])
        for x in ents:
            bb = ezdxf.bbox.extents([x], fast=False)
            if bb.has_data:
                out.append(box(bb.extmin.x, bb.extmin.y, bb.extmax.x, bb.extmax.y))
    return out


def _etichetta_apertura(P: _Penna, ed: Edificio, ap, a, b, n, h, layer, occupati=None):
    """Sigla dell'apertura (L x H in cm, davanzale) accanto al vano: dal lato preferito, altrimenti nel primo
    posto libero (lato opposto, piu' lontano), cosi' non copre nomi dei locali o quote."""
    from shapely.affinity import rotate
    from shapely.geometry import box
    cm = lambda x: f"{round(x * 100):d}"
    txt = f"{ap.id} {cm(ap.larghezza)}x{cm(ap.altezza.valore)}"
    if ap.davanzale.valore > 0.005:
        txt += f" dav.{cm(ap.davanzale.valore)}"
    lato = -1
    for p0, p1, nrm in perimetro_esterno(ed):
        if LineString([p0, p1]).distance(LineString([tuple(a), tuple(b)])) <= h + 0.02:
            lato = -1 if float(np.dot(nrm, n)) > 0 else 1  # verso l'interno dell'edificio
            break
    else:
        lato = -1 if ap.lato == "+" else 1  # muro interno: dal lato opposto all'apertura della porta
    esterno = any(LineString([p0, p1]).distance(LineString([tuple(a), tuple(b)])) <= h + 0.02
                  for p0, p1, _ in perimetro_esterno(ed))
    d = b - a
    ang = math.degrees(math.atan2(d[1], d[0]))
    if ang > 90 or ang <= -90:
        ang -= 180
    sc = P.scala
    u = d / np.linalg.norm(d)
    candidati = [(lato, 3.5, 0.0)] + ([] if esterno else [(-lato, 3.5, 0.0)]) + [(lato, 7.5, 0.0)]
    if esterno:  # anche davanti al vano, fra il muro e la prima catena di quote
        candidati += [(lato, 11.5, 0.0), (lato, 13.5, 0.0), (-lato, 3.5, 0.0)]
    else:  # porta interna: anche piu' vicina al muro, o spostata di lato rispetto al vano
        candidati += [(sg, 2.2, 0.0) for sg in (lato, -lato)]
        candidati += [(sg, dd, k) for dd in (3.5, 2.2) for sg in (lato, -lato) for k in (-1, 1)]

    def cerca(testo):
        lw, lh = mm(larghezza_testo(testo, 1.8), sc), mm(1.8, sc)
        for sgn, dist, lungo in candidati:
            pos = (a + b) / 2 + n * sgn * (h + mm(dist, sc)) + u * lungo * (lw / 2 + float(np.linalg.norm(d)) / 2)
            q = P.T(pos)
            rett = rotate(box(q[0] - lw / 2, q[1] - lh / 2, q[0] + lw / 2, q[1] + lh / 2), ang, origin=(q[0], q[1]))
            prova = rett.buffer(-mm(0.25, sc))  # sfiorarsi non e' sovrapporsi
            if occupati is None or not any(prova.intersects(o) for o in occupati):
                return pos, rett
        return None

    scelta = cerca(txt)
    if scelta is None and not esterno and occupati is not None:
        txt = ap.id  # niente posto per la sigla completa: almeno il nome, le misure sono nelle note
        scelta = cerca(txt)
        if scelta is None:
            return
    if scelta is None:
        pos = (a + b) / 2 + n * lato * (h + mm(3.5, sc))
        q = P.T(pos)
        lw, lh = mm(larghezza_testo(txt, 1.8), sc), mm(1.8, sc)
        scelta = (pos, rotate(box(q[0] - lw / 2, q[1] - lh / 2, q[0] + lw / 2, q[1] + lh / 2), ang,
                              origin=(q[0], q[1])))
    P.testo(txt, scelta[0], 1.8, layer, "MIDDLE_CENTER", rot=ang)
    if occupati is not None:
        occupati.append(scelta[1])


def _quote_esterne(P: _Penna, ed: Edificio, ds: str):
    sc = P.scala
    P.campate_esterne = []
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
        # catena dei vani: facce dei muri interni che si innestano su questo lato
        vani = [pa, pb]
        paralleli = [m for m in _muri_del_lato(ed, p0, p1) if abs(abs(float(np.dot(u, direzione(m)))) - 1) < 1e-6]
        sp_lato = max((m.spessore.valore for m in paralleli), default=0.0)
        n_in = -np.array(nrm)
        faccia_int = LineString([tuple(pa + n_in * sp_lato), tuple(pb + n_in * sp_lato)])
        for m in ed.muri:
            if m in paralleli or abs(float(np.dot(u, direzione(m)))) > 0.999:
                continue
            inter = poligono_muro(ed, m).intersection(faccia_int)
            for g in getattr(inter, "geoms", [inter]):
                for q in getattr(g, "coords", []):
                    sq = float(np.dot(np.array(q) - pa, u))
                    if 0.01 < sq < L - 0.01:
                        vani.append(pa + u * sq)
        # direzione invertita: la catena va a sinistra di (p1->p0), cioe' verso l'esterno.
        # Dall'interno verso l'esterno: aperture (se ci sono), muri e vani (se ci sono), totale una volta sola.
        livello = 10
        for pts in (punti, _estremi_distinti(vani, u, pa)):
            if len(pts) > 2:
                c = catena(P.msp, [P.T(p) for p in pts], tuple(-u), mm(livello, sc), ds)
                P.ent.extend(c.entita)
                livello += 8
        c = catena(P.msp, [P.T(pa), P.T(pb)], tuple(-u), mm(livello, sc), ds)
        P.ent.extend(c.entita)
        for pts in (punti, vani, [pa, pb]):  # misure gia' scritte fuori: dentro non si ripetono
            ss = sorted(float(np.dot(np.array(q) - pa, u)) for q in pts)
            P.campate_esterne += [(u, pa + u * s0, pa + u * s1) for s0, s1 in zip(ss, ss[1:])]


def _estremi_distinti(punti, u, pa, tol=0.005):
    """Punti ordinati lungo u, senza doppioni; restituisce i punti originali (nessun arrotondamento qui:
    lo fa la catena, cosi' parziali e totale coincidono)."""
    coppie = sorted(((float(np.dot(np.array(p) - pa, u)), np.array(p)) for p in punti), key=lambda t: t[0])
    out = []
    for s, p in coppie:
        if not out or s - out[-1][0] > tol:
            out.append((s, p))
    return [p for _, p in out]


def _gia_quotata(P: _Penna, a, b) -> bool:
    """La misura a-b e' gia' in una catena esterna (stessa direzione, stessi estremi entro 1 cm)?"""
    a, b = np.array(a, float), np.array(b, float)
    for u, p, q in getattr(P, "campate_esterne", []):
        if abs(abs(float(np.dot(u, (b - a) / np.linalg.norm(b - a)))) - 1) > 1e-3:
            continue
        sa, sb = sorted((float(np.dot(a, u)), float(np.dot(b, u))))
        sp, sq = sorted((float(np.dot(p, u)), float(np.dot(q, u))))
        if abs(sa - sp) < 0.01 and abs(sb - sq) < 0.01:
            return True
    return False


def _quote_interne(P: _Penna, ed: Edificio, ds: str):
    sc = P.scala
    for loc in ed.locali:
        pol = orient(poligono_locale(ed, loc), 1.0)
        mrr = pol.minimum_rotated_rectangle
        if mrr.area > 0 and pol.area / mrr.area > 0.985:
            # rettangolo: una quota per direzione, sotto e a destra dell'etichetta del locale
            c = [np.array(q) for q in list(orient(mrr, 1.0).exterior.coords)[:4]]
            lab = polylabel(pol, tolerance=0.02)
            fatti = set()
            for i in range(4):
                a, b = c[i], c[(i + 1) % 4]
                u = (b - a) / np.linalg.norm(b - a)
                verticale = abs(u[1]) > abs(u[0])
                if verticale in fatti:
                    continue
                if _gia_quotata(P, a, b):
                    fatti.add(verticale)
                    continue
                n_in = np.array([-u[1], u[0]])
                # distanza dal lato a cui passare: oltre l'ingombro dell'etichetta (meta' larghezza/altezza)
                d_lab = float(np.dot(np.array([lab.x, lab.y]) - a, n_in))
                ingombro = mm(20, sc) if verticale else mm(13, sc)
                prof = float(np.linalg.norm(c[(i + 2) % 4] - b))
                for off in (d_lab + ingombro, d_lab - ingombro):
                    if mm(5, sc) <= off <= prof - mm(5, sc):
                        break
                else:
                    off = mm(6, sc)
                P.ent.extend(quota_allineata(P.msp, P.T(a), P.T(b), off, ds))
                fatti.add(verticale)
        else:
            c = list(pol.exterior.coords)
            for a, b in ((a, b) for a, b in zip(c, c[1:]) if math.dist(a, b) > 0.3):
                if not _gia_quotata(P, a, b):
                    P.ent.extend(quota_allineata(P.msp, P.T(a), P.T(b), mm(7, sc), ds))


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
