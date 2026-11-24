"""Tavola comparativa: demolizioni in giallo, costruzioni in rosso.

Due modi di descrivere le modifiche:
- due modelli (stato legittimo -> stato di fatto, oppure stato di fatto -> stato di progetto);
- un solo modello con muri/aperture marcati `stato: demolire` o `stato: nuovo`.
"""
from __future__ import annotations

from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..dxf.stile import mm
from ..geometria import poligoni_muri
from ..modello import Edificio
from .pianta import Ingombro, _Penna, _poligoni, disegna_pianta

GIALLO, ROSSO = "COMPARATIVA_DEMOLIZIONI", "COMPARATIVA_COSTRUZIONI"


def _pulisci(g, tol=0.005):
    """Toglie le strisce sottili dovute ad arrotondamenti (sotto mezzo centimetro)."""
    if g.is_empty:
        return g
    return g.buffer(-tol, join_style="mitre").buffer(tol, join_style="mitre")


def _muratura(ed: Edificio):
    return unary_union(list(poligoni_muri(ed, con_aperture=True).values()))


def differenze(prima: Edificio, dopo: Edificio):
    """(demolito, costruito): muratura presente solo prima / solo dopo."""
    a, b = _muratura(prima), _muratura(dopo)
    return _pulisci(a.difference(b)), _pulisci(b.difference(a))


def stato_fatto(ed: Edificio) -> Edificio:
    """Lo stato attuale: senza i muri e le aperture nuovi."""
    return ed.model_copy(update={
        "muri": [m for m in ed.muri if m.stato != "nuovo"],
        "aperture": [a for a in ed.aperture if a.stato != "nuovo"],
        "stato": "fatto"})


def stato_progetto(ed: Edificio) -> Edificio:
    """Lo stato finale: senza i muri e le aperture da demolire (o da chiudere)."""
    muri = [m for m in ed.muri if m.stato != "demolire"]
    ids = {m.id for m in muri}
    return ed.model_copy(update={
        "muri": muri,
        "aperture": [a for a in ed.aperture if a.stato != "demolire" and a.muro in ids],
        "stato": "progetto"})


def differenze_da_stati(ed: Edificio):
    return differenze(stato_fatto(ed), stato_progetto(ed))


def disegna_comparativa(dopo: Edificio, msp, scala: int, origine, demolito, costruito,
                        titolo: str = "PIANTA COMPARATIVA") -> Ingombro:
    """Pianta dello stato finale con le demolizioni (giallo) e le costruzioni (rosso) sovrapposte."""
    ing = disegna_pianta(dopo, msp, scala, origine, quote=True, titolo=titolo)
    P = _Penna(msp, origine, scala)
    for g, layer in ((demolito, GIALLO), (costruito, ROSSO)):
        for pol in _poligoni(g):
            P.retino(pol, "SOLID", layer)
            P.poly(list(pol.exterior.coords), layer, chiusa=True)
    # legenda accanto al disegno
    s = scala / 1000
    x, y = ing.maxx - P.o[0] + mm(8, scala), ing.miny - P.o[1] + mm(30, scala)
    for i, (layer, txt) in enumerate(((GIALLO, "Demolizioni"), (ROSSO, "Nuove costruzioni"))):
        yy = y - i * 8 * s
        b = Polygon([(x, yy), (x + 12 * s, yy), (x + 12 * s, yy + 5 * s), (x, yy + 5 * s)])
        P.retino(b, "SOLID", layer)
        P.poly(list(b.exterior.coords), "TESTI", chiusa=True)
        P.testo(txt, (x + 16 * s, yy + 2.5 * s), 2.4, "TESTI", "MIDDLE_LEFT")
    return Ingombro(min(ing.minx, Ingombro.da_entita(P.ent).minx), min(ing.miny, Ingombro.da_entita(P.ent).miny),
                    max(ing.maxx, Ingombro.da_entita(P.ent).maxx), max(ing.maxy, Ingombro.da_entita(P.ent).maxy))

