"""Tabelle e verifiche: superfici, altezze, volumi, rapporti aeroilluminanti, dati urbanistici.

Riferimenti (nazionali, da verificare con regolamento edilizio e norme regionali):
- D.M. 5/7/1975: vani abitabili h >= 2,70 m, accessori (bagni, corridoi, ripostigli) h >= 2,40 m;
  superficie finestrata apribile >= 1/8 del pavimento per i locali abitabili.
- D.M. 801/1977: superficie utile (SU) e superficie non residenziale (SNR) per il costo di costruzione.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from ..dxf.quote import arrotonda
from ..geometria import apertura_mondo, ingombro_muri, perimetro_esterno, poligono_locale, profilo_apertura, z_falda
from ..modello import Edificio

ABITABILI = ("cucin", "soggiorn", "camera", "letto", "studio", "pranzo", "salon", "tinello", "abitaz", "ufficio")
ACCESSORI = ("bagno", "wc", "servizi", "disimpegn", "corridoi", "ripostigl", "antibagno", "lavanderi", "spogliat")
H_MINIMA = {"abitabile": Decimal("2.70"), "accessorio": Decimal("2.40")}
DUE = Decimal("0.01")


def _q(x) -> Decimal:
    return Decimal(str(x)).quantize(DUE, rounding=ROUND_HALF_UP)


def categoria(loc) -> str:
    """abitabile | accessorio | non residenziale (dalla destinazione o, se manca, dal nome)."""
    t = f"{loc.destinazione} {loc.nome}".lower()
    if any(k in t for k in ABITABILI):
        return "abitabile"
    if any(k in t for k in ACCESSORI):
        return "accessorio"
    return "non residenziale"


def _su_perimetro(ed: Edificio, ap) -> bool:
    a, b = apertura_mondo(ed, ap)
    m = ed.muro(ap.muro)
    seg = LineString([a, b])
    return any(LineString([p0, p1]).distance(seg) <= m.spessore.valore / 2 + 0.02 for p0, p1, _ in perimetro_esterno(ed))


def _area_apertura(ap) -> float:
    return Polygon(profilo_apertura(ap)).area


def superficie_finestrata(ed: Edificio, loc) -> float:
    """Superficie delle finestre su muri esterni che si affacciano sul locale (porte vetrate comprese)."""
    pl = poligono_locale(ed, loc)
    tot = 0.0
    for ap in ed.aperture:
        vetrata = ap.tipo in ("finestra", "feritoia") or any(k in ap.infisso.lower() for k in ("vetr", "finestra"))
        if not vetrata or not _su_perimetro(ed, ap):
            continue
        a, b = apertura_mondo(ed, ap)
        m = ed.muro(ap.muro)
        if LineString([a, b]).distance(pl) <= m.spessore.valore / 2 + 0.02:
            tot += _area_apertura(ap)
    return tot


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
    categoria: str = ""
    s_finestrata: Decimal = Decimal(0)
    esito_rai: str = ""  # OK | NO | n.r. (non richiesto)
    h_richiesta: Decimal | None = None
    esito_h: str = ""


@dataclass
class DatiGenerali:
    superficie_lorda: Decimal  # ingombro dei muri esterni (vuoto per pieno)
    superficie_coperta: Decimal  # proiezione della copertura
    volume_vpp: Decimal  # dal terreno all'estradosso della copertura
    su: Decimal  # superficie utile residenziale (abitabili + accessori)
    snr: Decimal  # superficie non residenziale


def tabella_superfici(ed: Edificio) -> tuple[list[RigaSup], RigaSup]:
    from .sezioni import altezza_media
    righe = []
    for loc in ed.locali:
        s = arrotonda(poligono_locale(ed, loc).area)
        hm = altezza_media(ed, loc)
        if hm is None:
            hm = (loc.h_min.valore + loc.h_max.valore) / 2 if loc.h_max else loc.h_min.valore
        hmd = arrotonda(hm)
        vol = (s * hmd).quantize(DUE, rounding=ROUND_HALF_UP)
        cat = categoria(loc)
        sf = _q(superficie_finestrata(ed, loc))
        smin = (s / 8).quantize(DUE, rounding=ROUND_HALF_UP)
        esito_rai = "n.r." if cat != "abitabile" else ("OK" if sf >= smin else "NO")
        hr = H_MINIMA.get(cat)
        esito_h = "n.r." if hr is None else ("OK" if hmd >= hr else "NO")
        righe.append(RigaSup(loc.nome, s, arrotonda(loc.h_min.valore),
                             arrotonda(loc.h_max.valore) if loc.h_max else None, hmd, vol, smin,
                             loc.h_min.ipotesi or bool(loc.h_max and loc.h_max.ipotesi), cat, sf, esito_rai, hr,
                             esito_h))
    tot = RigaSup("TOTALE", sum((r.superficie for r in righe), Decimal(0)), Decimal(0), None, None,
                  sum((r.volume for r in righe), Decimal(0)), sum((r.rai_minimo for r in righe), Decimal(0)),
                  s_finestrata=sum((r.s_finestrata for r in righe), Decimal(0)))
    return righe, tot


def sagoma(ed: Edificio):
    """Ingombro pieno dell'edificio (muri esterni compresi, vuoti interni riempiti)."""
    u = ingombro_muri(ed)
    pols = list(getattr(u, "geoms", [u]))
    return unary_union([Polygon(p.exterior) for p in pols])


def dati_generali(ed: Edificio) -> DatiGenerali:
    sg = sagoma(ed)
    coperta = unary_union([Polygon(f.poligono) for f in ed.falde]).union(sg) if ed.falde else sg
    zt = ed.quota_terreno.valore
    # volume esatto: sotto ogni falda piana, area x altezza nel baricentro; le falde piu' alte prevalgono
    vol, coperto = 0.0, Polygon()
    for f in sorted(ed.falde, key=lambda f: -max(q.valore for q in f.quote)):
        parte = Polygon(f.poligono).intersection(sg).difference(coperto)
        for g in getattr(parte, "geoms", [parte]):
            if isinstance(g, Polygon) and g.area > 1e-9:
                c = g.centroid
                vol += g.area * (z_falda(f, c.x, c.y) - zt)
        coperto = coperto.union(Polygon(f.poligono))
    resto = sg.difference(coperto)
    if resto.area > 1e-6:
        # senza copertura nel modello: fino al soffitto dei locali (altezza interna; i solai non si conoscono)
        cime = [loc.quota_pavimento.valore + (loc.h_max or loc.h_min).valore for loc in ed.locali]
        h = max((m.altezza.valore for m in ed.muri if m.altezza), default=max(cime, default=3.0))
        vol += resto.area * (h - zt)
    su = snr = Decimal(0)
    # unita' non residenziale (bottega, deposito...): anche WC e ripostigli sono superficie non residenziale
    residenziale = any(categoria(loc) == "abitabile" for loc in ed.locali)
    for loc in ed.locali:
        s = arrotonda(poligono_locale(ed, loc).area)
        if categoria(loc) == "non residenziale" or not residenziale:
            snr += s
        else:
            su += s
    return DatiGenerali(_q(sg.area), _q(coperta.area), _q(vol), su, snr)
