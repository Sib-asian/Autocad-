"""Generatore dei prospetti."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from shapely.geometry import LineString, MultiLineString
from shapely.ops import unary_union

from ..dxf.quote import catena, fmt_quota
from ..dxf.stile import aggiungi_dimstyle, mm
from ..geometria import direzione, perimetro_esterno, poligono_muro
from ..modello import Edificio
from ..modello3d import facce
from ..proiezione import Pezzo, assi_vista, proietta
from .pianta import Ingombro, _Penna, _poligoni

CARDINALI = ["NORD", "OVEST", "SUD", "EST"]


@dataclass
class Vista:
    nome: str
    direzione: np.ndarray  # verso cui guarda l'osservatore (3D, orizzontale)
    normale: np.ndarray  # normale uscente della facciata (2D)
    sinistra: str
    destra: str


def cardinale(vx: float, vy: float, nord_gradi: float) -> str:
    ang = math.degrees(math.atan2(vy, vx))
    delta = (ang - nord_gradi) % 360
    return CARDINALI[int(((delta + 45) % 360) // 90)]


def lati_prospetto(ed: Edificio) -> list[Vista]:
    lati = perimetro_esterno(ed)
    if not lati:
        return []
    p0, p1, n0 = max(lati, key=lambda t: math.dist(t[0], t[1]))
    base = math.atan2(n0[1], n0[0])
    tutte = facce(ed)
    viste = []
    for k in range(4):
        a = base + k * math.pi / 2
        n = np.array([math.cos(a), math.sin(a)])
        v3 = np.array([-n[0], -n[1], 0.0])
        if not any(f.tipo == "parete_est" and float(f.normale[:2] @ n) > 0.5 for f in tutte):
            continue
        _, r = assi_vista(v3)
        nome = "Prospetto " + cardinale(n[0], n[1], ed.nord_gradi).capitalize()
        viste.append(Vista(nome, v3, n, cardinale(-r[0], -r[1], ed.nord_gradi), cardinale(r[0], r[1], ed.nord_gradi)))
    return viste


def _linee(geom):
    if geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom]
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, LineString)]


def disegna_prospetto(ed: Edificio, vista: Vista, msp, scala: int = 50, origine=(0.0, 0.0),
                      quote: bool = True, titolo: bool = True) -> Ingombro:
    tutte = facce(ed)
    pezzi = proietta(tutte, vista.direzione)
    return disegna_pezzi(ed, vista.nome, vista.sinistra, vista.destra, pezzi, msp, scala, origine, quote, titolo,
                         vista=vista)


def disegna_pezzi(ed, nome, sinistra, destra, pezzi: list[Pezzo], msp, scala, origine, quote, titolo,
                  vista: Vista | None = None, tagliati=None, extra_quote_z=()) -> Ingombro:
    """Disegna i pezzi proiettati (comune a prospetti e sezioni)."""
    sc = scala
    ds = aggiungi_dimstyle(msp.doc, scala)
    if not pezzi and not tagliati:
        return Ingombro(origine[0], origine[1], origine[0], origine[1])
    tutti = [p.poligono2d for p in pezzi] + list(tagliati or [])
    sil = unary_union(tutti)
    minx, minz, maxx, maxz = sil.bounds
    o = (origine[0] - minx, origine[1])  # x=0 sul bordo sinistro dell'edificio
    P = _Penna(msp, o, scala)
    lay_contorno = "PROSPETTI_CONTORNO" if tagliati is None else "SEZ_VISTO"
    lay_dett = "PROSPETTI_DETTAGLI" if tagliati is None else "SEZ_VISTO"
    lay_spig = "PROSPETTI_SPIGOLI" if tagliati is None else "SEZ_VISTO"

    # --- spigoli visibili: le superfici sullo stesso piano si fondono (nessuna linea interna fra corpi
    #     allineati), il sottotetto non si disegna, i segmenti minuscoli si scartano
    piani: dict = {}
    for p in pezzi:
        if p.faccia.tipo in ("infisso", "intradosso_falda"):
            continue
        n = p.faccia.normale
        cat = {"falda": "falda", "bordo_falda": "bordo"}.get(p.faccia.tipo, "parete")  # muro e tetto distinti
        chiave = (cat, tuple(np.round(n, 3)), round(float(n @ p.faccia.pts[0]), 3))
        piani.setdefault(chiave, []).append(p.poligono2d)
    contorni = [unary_union(g).buffer(0.002, join_style="mitre").buffer(-0.002, join_style="mitre")
                for g in piani.values()]
    bordi = unary_union([c.boundary for c in contorni if not c.is_empty])
    if tagliati is None:  # cio' che sta sulla sagoma lo disegna gia' il contorno spesso: niente doppioni
        bordi = bordi.difference(unary_union([q.exterior for q in _poligoni(sil)]).buffer(0.003))
    for ln in _linee(bordi.simplify(0.003)):
        if ln.length >= 0.02:
            P.poly(list(ln.coords), lay_spig)
    # --- infissi: contorno (rosso se le misure sono stimate), telaio e ante
    for p in pezzi:
        if p.faccia.tipo == "infisso":
            _infisso(P, ed, p, "IPOTESI_DA_VERIFICARE" if p.faccia.ipotesi else lay_spig, lay_dett)
    # --- sagoma esterna spessa (solo prospetti)
    if tagliati is None:
        for pol in _poligoni(sil):
            P.poly(list(pol.exterior.coords), lay_contorno)
    # --- terreno
    zt = ed.quota_terreno.valore
    P.poly([(minx - 1.0, zt), (maxx + 1.0, zt)], "TERRENO")

    if vista is not None:
        _pluviali(P, ed, vista, pezzi, zt)
        _lesioni(P, ed, vista)

    # --- quote
    if quote:
        livelli = _livelli(ed, pezzi, zt) | set(extra_quote_z)
        if tagliati:
            livelli |= {round(t.bounds[3], 4) for t in tagliati}
        _quote_livello(P, sorted(livelli), minx, sc)
        punti = [(maxx, z) for z in sorted(livelli)]
        if len(punti) >= 2:
            c = catena(msp, [P.T(q) for q in punti], (0, 1), -mm(10, sc), ds, min_parziale=mm(7.5, sc))  # testo leggibile
            P.ent.extend(c.entita)
        xs = {minx, maxx}
        for p in pezzi:
            if p.faccia.tipo == "infisso" or (p.faccia.tipo.startswith("parete") and p.faccia.fori):
                if p.faccia.tipo == "infisso":
                    x0, _, x1, _ = p.poligono2d.bounds
                    xs |= {x0, x1}
        if len(xs) >= 2:
            c = catena(msp, [P.T((x, zt)) for x in sorted(xs)], (1, 0), -mm(12, sc), ds, totale=len(xs) > 2,
                       offset_totale=-mm(20, sc), min_parziale=mm(4.0, sc))
            P.ent.extend(c.entita)

    # --- orientamento alle estremita' e titolo
    if sinistra:
        P.testo(sinistra, (minx, maxz + mm(7, sc)), 2.5, "TESTI", "BOTTOM_LEFT")
    if destra:
        P.testo(destra, (maxx, maxz + mm(7, sc)), 2.5, "TESTI", "BOTTOM_RIGHT")
    ing = Ingombro.da_entita(P.ent)
    if titolo:
        P.testo(f"{nome.upper()}  scala 1:{scala}", ((minx + maxx) / 2, ing.miny - o[1] - mm(9, sc)), 4.0)
    return Ingombro.da_entita(P.ent)


def _livelli(ed: Edificio, pezzi, zt) -> set[float]:
    z = {round(zt, 4), 0.0}
    for p in pezzi:
        if p.faccia.tipo == "infisso":
            _, z0, _, z1 = p.poligono2d.bounds
            z |= {round(z0, 4), round(z1, 4)}
        elif p.faccia.tipo == "falda":
            z.add(round(p.poligono2d.bounds[3], 4))
        elif p.faccia.tipo == "bordo_falda":  # estradosso: gronda (punto basso) e colmo (punto alto)
            top = p.faccia.pts[[0, -1], 2]  # i due vertici in alto (a e b) del bordo
            z |= {round(float(top.min()), 4), round(float(top.max()), 4)}
    return z


def _quote_livello(P: _Penna, livelli, minx, sc):
    """Simboli di quota a sinistra: triangolino + valore. Prima gli estremi, poi i livelli che non si
    accavallano con quelli gia' scritti."""
    x = minx - mm(14, sc)
    passo = mm(4.5, sc)
    scelti: list[float] = []
    if livelli:
        ordine = [livelli[0], livelli[-1]] + list(livelli[1:-1])
        for z in ordine:
            if all(abs(z - w) >= passo for w in scelti):
                scelti.append(z)
    for z in sorted(scelti):
        t = mm(1.6, sc)
        P.poly([(x, z), (x - t, z + t * 1.2), (x + t, z + t * 1.2)], "QUOTE", chiusa=True)
        P.poly([(x - mm(6, sc), z), (x + mm(3, sc), z)], "QUOTE")
        P.testo(fmt_quota(z), (x - mm(1, sc), z + t * 1.6), 2.2, "QUOTE", "BOTTOM_RIGHT")


def _infisso(P: _Penna, ed: Edificio, p: Pezzo, lay_vano, layer):
    """Vano dell'apertura (lay_vano) e, sottili, telaio, ante, doghe o grata (layer)."""
    ap = next((a for a in ed.aperture if a.id == p.faccia.rif_id), None)
    for pol in _poligoni(p.poligono2d):
        telaio = pol.buffer(-0.05, join_style="mitre")
        P.poly(list(pol.exterior.coords), lay_vano)
        if telaio.is_empty:
            continue
        for t in _poligoni(telaio):
            P.poly(list(t.exterior.coords), layer)
        x0, z0, x1, z1 = pol.bounds
        w = x1 - x0
        if ap is not None and (ap.battente == "doppio" or (ap.tipo == "finestra" and w > 0.7) or
                               (ap.tipo == "porta" and w > 1.1)):
            xm = (x0 + x1) / 2
            for ln in _linee(LineString([(xm, z0), (xm, z1)]).intersection(telaio)):
                P.poly(list(ln.coords), layer)
        if ap is not None and "grata" in ap.infisso.lower():  # grata a losanghe
            passo = 0.16
            righe = []
            for k in np.arange(-(z1 - z0), (x1 - x0) + (z1 - z0), passo):
                righe.append([(x0 + k, z0), (x0 + k + (z1 - z0), z1)])
                righe.append([(x0 + k + (z1 - z0), z0), (x0 + k, z1)])
            for ln in _linee(MultiLineString(righe).intersection(telaio)):
                P.poly(list(ln.coords), layer)
            continue
        if ap is not None and ap.tipo == "porta":
            # doghe verticali del portone in legno
            n = max(2, int(w / 0.12))
            for i in range(1, n):
                xx = x0 + 0.05 + (w - 0.1) * i / n
                for ln in _linee(LineString([(xx, z0), (xx, z1)]).intersection(telaio)):
                    P.poly(list(ln.coords), layer)


def _faccia_verso(ed: Edificio, muro_id: str, vista: Vista) -> bool:
    m = ed.muro(muro_id)
    pm = poligono_muro(ed, m)
    d = direzione(m)
    for p0, p1, n in perimetro_esterno(ed):
        if abs(float(np.dot(d, n))) > 1e-3:  # il lato deve essere parallelo al muro
            continue
        if pm.boundary.intersection(LineString([p0, p1]).buffer(1e-6)).length > 0.05:
            if float(np.dot(n, vista.normale)) > 0.7:
                return True
    return False


def _pluviali(P: _Penna, ed: Edificio, vista: Vista, pezzi, zt):
    _, r = assi_vista(vista.direzione)
    for el in ed.elementi:
        if el.tipo != "pluviale" or el.punto is None:
            continue
        pt = np.array(el.punto)
        vicino = False
        for p0, p1, n in perimetro_esterno(ed):
            if float(np.dot(n, vista.normale)) > 0.7 and LineString([p0, p1]).distance(
                    LineString([tuple(pt), tuple(pt)])) < 0.4:
                vicino = True
        if not vicino:
            continue
        x = float(np.array([pt[0], pt[1], 0]) @ r)
        ztop = el.altezza.valore if el.altezza else max(q.valore for f in ed.falde for q in f.quote) if ed.falde else 3
        d = 0.05
        for xx in (x - d, x + d):
            P.poly([(xx, zt + 0.15), (xx, ztop - 0.05)], "PROSPETTI_DETTAGLI")
        P.poly([(x - 0.12, ztop), (x + 0.12, ztop), (x + d, ztop - 0.2), (x - d, ztop - 0.2)],
               "PROSPETTI_DETTAGLI", chiusa=True)


def _lesioni(P: _Penna, ed: Edificio, vista: Vista):
    _, r = assi_vista(vista.direzione)
    for les in ed.lesioni:
        if les.lato != "esterno" or not _faccia_verso(ed, les.muro, vista):
            continue
        m = ed.muro(les.muro)
        d = direzione(m)
        o = np.array(m.asse[0], float)
        pts = []
        for s, z in les.punti:
            q = o + d * (m.zero.valore + s)
            pts.append((float(np.array([q[0], q[1], 0.0]) @ r), z))
        P.poly(pts, "DEGRADO")
        if pts:
            etichetta = les.id + (f" ({les.ampiezza_mm:g} mm)" if les.ampiezza_mm is not None else "")
            P.testo(etichetta, (pts[0][0] + mm(2, P.scala), pts[0][1]), 1.8, "DEGRADO", "MIDDLE_LEFT")
