"""Tabelle: superfici, altezze, volumi, rapporti aeroilluminanti."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from ..dxf.quote import arrotonda
from ..geometria import poligono_locale
from ..modello import Edificio


@dataclass
class RigaSup:
    nome: str
    superficie: Decimal
    h_min: Decimal
    h_max: Decimal | None
    h_media: Decimal | None
    volume: Decimal | None
    rai_minimo: Decimal  # superficie finestrata minima = S/8
    ipotesi: bool = False


def tabella_superfici(ed: Edificio) -> tuple[list[RigaSup], RigaSup]:
    from .sezioni import altezza_media
    righe = []
    for loc in ed.locali:
        s = arrotonda(poligono_locale(ed, loc).area)
        hm = altezza_media(ed, loc)
        if hm is None:
            hm = (loc.h_min.valore + loc.h_max.valore) / 2 if loc.h_max else loc.h_min.valore
        hmd = arrotonda(hm)
        vol = (s * hmd).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        righe.append(RigaSup(loc.nome, s, arrotonda(loc.h_min.valore),
                             arrotonda(loc.h_max.valore) if loc.h_max else None, hmd, vol,
                             (s / 8).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                             loc.h_min.ipotesi or bool(loc.h_max and loc.h_max.ipotesi)))
    tot = RigaSup("TOTALE", sum((r.superficie for r in righe), Decimal(0)), Decimal(0), None, None,
                  sum((r.volume for r in righe), Decimal(0)), sum((r.rai_minimo for r in righe), Decimal(0)))
    return righe, tot
