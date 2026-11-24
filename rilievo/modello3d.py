"""Modello 3D a facce piane, ricavato dal modello dell'edificio.

Serve a prospetti, sezioni e foto sintetiche: tutte le viste nascono dalle
stesse facce, quindi coincidono per costruzione.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.geometry.polygon import orient

from .geometria import (apertura_mondo, ingombro_muri, poligono_muro, profilo_apertura, quota_intradosso,
                        z_falda)
from .modello import Edificio

PASSO_PROFILO = 0.05
ALTEZZA_DI_RISERVA = 3.0
RIENTRO_INFISSO = 0.08


@dataclass
class Faccia:
    pts: np.ndarray  # (n, 3) contorno, piano
    tipo: str  # parete_est, parete_int, falda, bordo_falda, infisso
    materiale: str = ""
    rif_id: str = ""
    ipotesi: bool = False
    fori: list[np.ndarray] = field(default_factory=list)
    fori_id: list[str] = field(default_factory=list)
    n_imposta: np.ndarray | None = None  # normale imposta (es. infissi: quella della parete)

    @property
    def normale(self) -> np.ndarray:
        if self.n_imposta is not None:
            return self.n_imposta
        p = self.pts
        n = np.zeros(3)
        for a, b in zip(p, np.roll(p, -1, axis=0)):  # metodo di Newell
            n += np.array([(a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]), (a[0] - b[0]) * (a[1] + b[1])])
        L = np.linalg.norm(n)
        return n / L if L > 0 else n


def _anelli(geom):
    pols = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
    for pol in pols:
        pol = orient(pol, 1.0)
        yield "est", list(pol.exterior.coords)
        for r in pol.interiors:
            yield "int", list(r.coords)


def _muri_del_lato(ed: Edificio, p0, p1):
    """Muri il cui contorno si sovrappone al lato p0-p1, con lunghezza di sovrapposizione."""
    lato = LineString([p0, p1])
    out = []
    for m in ed.muri:
        sov = poligono_muro(ed, m).boundary.intersection(lato.buffer(1e-6)).length
        if sov > 0.01:
            out.append((sov, m))
    out.sort(key=lambda t: -t[0])
    return [m for _, m in out]


def _profilo_sommita(ed: Edificio, p0, p1, muri) -> tuple[list[tuple[float, float]], bool]:
    """Profilo (s, z) della sommita' della parete lungo il lato. Ritorna anche se e' ipotizzato."""
    p0, p1 = np.array(p0, float), np.array(p1, float)
    L = float(np.linalg.norm(p1 - p0))
    u = (p1 - p0) / L
    fisse = [m.altezza for m in muri if m.altezza is not None]
    n = max(2, int(math.ceil(L / PASSO_PROFILO)) + 1)
    ss = list(np.linspace(0, L, n))
    lato = LineString([tuple(p0), tuple(p1)])
    for f in ed.falde:  # punti di rottura: dove il lato attraversa i bordi delle falde (colmi, displuvi)
        inter = lato.intersection(Polygon(f.poligono).boundary)
        for g in getattr(inter, "geoms", [inter]):
            for c in getattr(g, "coords", []):
                ss.append(float(np.dot(np.array(c) - p0, u)))
    ss = sorted({round(min(max(s, 0.0), L), 9) for s in ss})
    prof, ipotesi = [], False
    for s in ss:
        x, y = p0 + u * s
        if fisse:
            z = fisse[0].valore
            ipotesi |= fisse[0].ipotesi
        else:
            z = quota_intradosso(ed, x, y)
            if z is None:
                z = _intradosso_vicino(ed, x, y)
            if z is None:
                z, ipotesi = ALTEZZA_DI_RISERVA, True
        prof.append((float(s), float(z)))
    return _semplifica(prof), ipotesi or any(q.ipotesi for f in ed.falde for q in f.quote)


def _intradosso_vicino(ed: Edificio, x: float, y: float, raggio: float = 0.30) -> float | None:
    """Intradosso della falda piu' vicina, se il punto ne resta fuori di pochi centimetri (spigoli dei muri)."""
    from shapely.geometry import Point
    from shapely.ops import nearest_points
    pt = Point(x, y)
    vicine = [(Polygon(f.poligono).distance(pt), f) for f in ed.falde]
    vicine = [(d, f) for d, f in vicine if d <= raggio]
    if not vicine:
        return None
    _, f = min(vicine, key=lambda t: t[0])
    q = nearest_points(Polygon(f.poligono), pt)[0]
    return z_falda(f, q.x, q.y) - f.spessore.valore


def _semplifica(prof, tol=1e-4):
    out = [prof[0]]
    for i in range(1, len(prof) - 1):
        (s0, z0), (s1, z1), (s2, z2) = out[-1], prof[i], prof[i + 1]
        if abs((z2 - z0) * (s1 - s0) / (s2 - s0) + z0 - z1) > tol:
            out.append(prof[i])
    out.append(prof[-1])
    return out


def _facce_parete(ed: Edificio, tipo: str, p0, p1, z_base: float) -> list[Faccia]:
    muri = _muri_del_lato(ed, p0, p1)
    if not muri:
        return []
    pa, pb = np.array(p0, float), np.array(p1, float)
    L = float(np.linalg.norm(pb - pa))
    u = (pb - pa) / L
    prof, ipot = _profilo_sommita(ed, p0, p1, muri)
    pts2 = [(0.0, z_base), (L, z_base)] + [(s, z) for s, z in reversed(prof)]
    sagoma = Polygon(pts2)

    def a3d(s, z):
        x, y = pa + u * s
        return (x, y, z)

    fori, fori_id, infissi = [], [], []
    normale_out = np.array([u[1], -u[0]])  # materiale a sinistra del lato
    for m in muri:
        if abs(abs(float(np.dot(u, _dir(m)))) - 1) > 1e-6:
            continue
        for ap in ed.aperture_di(m.id):
            a, b = apertura_mondo(ed, ap)
            sa, sb = float(np.dot(np.array(a) - pa, u)), float(np.dot(np.array(b) - pa, u))
            if max(sa, sb) <= 1e-6 or min(sa, sb) >= L - 1e-6:
                continue
            s_ini = min(sa, sb)
            loc = profilo_apertura(ap)
            if sa > sb:  # il muro e' percorso al contrario rispetto al lato
                w = ap.larghezza
                loc = [(w - s, z) for s, z in loc]
            hole2 = Polygon([(s_ini + s, z) for s, z in loc])
            hole2 = hole2.intersection(sagoma)
            if hole2.is_empty or hole2.area < 1e-6:
                continue
            ring = [a3d(s, z) for s, z in list(hole2.exterior.coords)[:-1]]
            fori.append(np.array(ring))
            fori_id.append(ap.id)
            if tipo == "parete_est" and ap.tipo != "varco":
                rientro = -normale_out * min(RIENTRO_INFISSO, m.spessore.valore / 2)
                inf = np.array(ring) + np.array([rientro[0], rientro[1], 0.0])
                infissi.append(Faccia(inf, "infisso", materiale=ap.infisso or ap.tipo, rif_id=ap.id,
                                      ipotesi=ap.altezza.ipotesi or ap.davanzale.ipotesi,
                                      n_imposta=np.array([normale_out[0], normale_out[1], 0.0])))
    contorno = np.array([a3d(s, z) for s, z in pts2])
    f = Faccia(contorno, tipo, materiale=muri[0].materiale, rif_id=muri[0].id, ipotesi=ipot,
               fori=fori, fori_id=fori_id)
    return [f] + infissi


def _dir(m):
    (x0, y0), (x1, y1) = m.asse
    d = np.array([x1 - x0, y1 - y0], float)
    return d / np.linalg.norm(d)


def facce(ed: Edificio) -> list[Faccia]:
    out: list[Faccia] = []
    u = ingombro_muri(ed)
    z_ter = ed.quota_terreno.valore
    for tipo_anello, coords in _anelli(u):
        tipo = "parete_est" if tipo_anello == "est" else "parete_int"
        for p0, p1 in zip(coords, coords[1:]):
            if math.dist(p0, p1) < 1e-6:
                continue
            out += _facce_parete(ed, tipo, p0, p1, z_ter if tipo == "parete_est" else 0.0)
    for f in ed.falde:
        top = np.array([(x, y, z_falda(f, x, y)) for x, y in f.poligono])
        ipot = any(q.ipotesi for q in f.quote)
        out.append(Faccia(top, "falda", materiale=f.manto, rif_id=f.id, ipotesi=ipot))
        sp = f.spessore.valore
        sotto = (top - [0, 0, sp])[::-1]  # intradosso, normale verso il basso
        out.append(Faccia(sotto, "intradosso_falda", materiale=f.struttura, rif_id=f.id, ipotesi=ipot))
        for a, b in zip(top, np.roll(top, -1, axis=0)):
            bordo = np.array([a, a - [0, 0, sp], b - [0, 0, sp], b])  # normale verso l'esterno della falda
            out.append(Faccia(bordo, "bordo_falda", materiale=f.manto, rif_id=f.id, ipotesi=ipot))
    return out + _muri_emergenti(ed)


def _muri_emergenti(ed: Edificio) -> list[Faccia]:
    """Muratura che sale sopra una copertura piu' bassa per sostenere la testata di una piu' alta (es. tetto
    a una falda appoggiato al timpano del vicino): senza, sotto la testata si vedrebbe un vuoto."""
    from shapely.geometry import Point
    pol = {f.id: Polygon(f.poligono) for f in ed.falde}
    muri = ingombro_muri(ed).buffer(0.02)  # la muratura sale solo sopra un muro, non sotto gli sporti
    out = []
    for f in ed.falde:
        sp = f.spessore.valore
        altre = [g for g in ed.falde if g.id != f.id]
        if not altre:
            continue
        cc = f.poligono + f.poligono[:1]
        for a, b in zip(cc, cc[1:]):
            lato = LineString([a, b])
            L = lato.length
            if L < 1e-6:
                continue
            ss = {0.0, L}
            for g in altre:
                inter = lato.intersection(pol[g.id].boundary)
                for q in getattr(inter, "geoms", [inter]):
                    for c in getattr(q, "coords", []):
                        ss.add(min(max(lato.project(Point(c)), 0.0), L))
            ss = sorted(ss)
            fondo = []
            for t0, t1 in zip(ss, ss[1:]):  # in ogni tratto la falda sottostante e' la stessa
                if t1 - t0 < 1e-6:
                    continue
                m = lato.interpolate((t0 + t1) / 2)
                dx, dy = b[0] - a[0], b[1] - a[1]
                dentro = Point(m.x - 0.05 * dy / L, m.y + 0.05 * dx / L)  # falda antioraria: interno a sinistra
                # la falda bassa deve stare oltre il bordo, non sotto la nostra (sporto sopra un altro tetto)
                sotto = [g for g in altre if pol[g.id].buffer(1e-3).covers(m) and not pol[g.id].covers(dentro)] \
                    if muri.covers(m) else []
                for t in (t0, t1):
                    q = lato.interpolate(t)
                    cima = z_falda(f, q.x, q.y) - sp
                    zs = [z_falda(g, q.x, q.y) for g in sotto]
                    fondo.append((q.x, q.y, min(max(zs), cima) if zs else cima))
            if max(z_falda(f, x, y) - sp - z for x, y, z in fondo) < 0.01:
                continue
            ta = (a[0], a[1], z_falda(f, *a) - sp)
            tb = (b[0], b[1], z_falda(f, *b) - sp)
            pts = np.array([ta] + fondo + [tb])  # stesso verso del bordo: normale verso l'esterno
            out.append(Faccia(pts, "parete_est", materiale="muratura", rif_id=f.id,
                              ipotesi=any(q.ipotesi for q in f.quote)))
    return out
