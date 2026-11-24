"""Impaginazione delle viste su fogli UNI con cornice, cartiglio, tabelle e note."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from shapely.ops import unary_union

from ..dxf.quote import fmt
from ..dxf.stile import mm, nuovo_documento, testo
from ..geometria import ingombro_muri
from ..modello import Edificio
from .pianta import Ingombro, _Penna, disegna_pianta, retino
from .prospetti import disegna_prospetto, lati_prospetto
from .sezioni import disegna_sezione
from .tabelle import tabella_superfici

FORMATI = [("A3", 420, 297), ("A2", 594, 420), ("A1", 841, 594), ("A0", 1189, 841)]
MARG_SX, MARG = 20, 10  # mm: margine di rilegatura a sinistra
CARTIGLIO = (185, 62)  # mm
SPAZIO = 14  # mm tra le viste

Vista = Callable[[object, tuple], Ingombro]  # (msp, origine) -> ingombro


@dataclass
class Foglio:
    numero: int
    contenuto: str
    formato: str
    larghezza_mm: float
    altezza_mm: float
    bbox: tuple[float, float, float, float]  # in metri di disegno


@dataclass
class Tavole:
    doc: object
    fogli: list[Foglio] = field(default_factory=list)
    scala: int = 50


def scala_automatica(ed: Edificio) -> int:
    minx, miny, maxx, maxy = ingombro_muri(ed).bounds
    return 50 if max(maxx - minx, maxy - miny) <= 20 else 100


def _misura(vista: Vista, scala: int) -> Ingombro:
    prova = nuovo_documento(scala)
    return vista(prova.modelspace(), (0.0, 0.0))


def _impagina(viste: list[tuple[Vista, Ingombro]], scala: int):
    """Sceglie il formato piu' piccolo in cui le viste stanno a righe. Ritorna (formato, posizioni)."""
    s = scala / 1000
    for nome, W, H in FORMATI:
        utile_w = (W - MARG_SX - MARG - 2 * 5) * s
        utile_h = (H - 2 * MARG - CARTIGLIO[1] - 2 * 5) * s
        x = y = alt_riga = 0.0
        pos = []
        ok = True
        for _, ing in viste:
            w, h = ing.larghezza, ing.altezza
            if w > utile_w:
                ok = False
                break
            if x > 0 and x + w > utile_w:
                y += alt_riga + SPAZIO * s
                x, alt_riga = 0.0, 0.0
            pos.append((x, y))
            x += w + SPAZIO * s
            alt_riga = max(alt_riga, h)
        if ok and y + alt_riga <= utile_h:
            return nome, W, H, pos, y + alt_riga
    raise ValueError("Le viste non entrano neanche in un A0: dividere la tavola")


def componi_tavole(ed: Edificio, profilo: str = "rilievo", scala: int | None = None,
                   studio: dict | None = None) -> Tavole:
    scala = scala or scala_automatica(ed)
    doc = nuovo_documento(scala)
    msp = doc.modelspace()
    t = Tavole(doc, [], scala)
    gruppi: list[tuple[str, list[Vista]]] = []

    viste_pianta: list[Vista] = [lambda m, o: disegna_pianta(ed, m, scala, o)]
    if ed.locali:
        viste_pianta.append(lambda m, o: _tabella(ed, m, o, scala))
    viste_pianta.append(lambda m, o: _legenda(ed, m, o, scala))
    viste_pianta.append(lambda m, o: _note(ed, m, o, scala))
    gruppi.append(("Pianta", viste_pianta))
    pros = [(lambda vv: (lambda m, o: disegna_prospetto(ed, vv, m, scala, o)))(v) for v in lati_prospetto(ed)]
    if pros:
        gruppi.append(("Prospetti", pros))
    sez = [(lambda ss: (lambda m, o: disegna_sezione(ed, ss, m, scala, o)))(s) for s in ed.sezioni]
    if sez:
        gruppi.append(("Sezioni", sez))

    x_foglio = 0.0
    s = scala / 1000
    for i, (contenuto, viste) in enumerate(gruppi, start=1):
        misurate = [(v, _misura(v, scala)) for v in viste]
        nome, W, H, pos, alt_tot = _impagina(misurate, scala)
        x0, y0 = x_foglio, 0.0
        # le viste partono dall'alto del riquadro utile
        top = y0 + (H - MARG - 5) * s
        for (v, ing), (px, py) in zip(misurate, pos):
            X = x0 + (MARG_SX + 5) * s + px
            Y = top - py - ing.altezza
            v(msp, (X - ing.minx, Y - ing.miny))
        _cornice_e_cartiglio(ed, msp, (x0, y0), W, H, scala, i, contenuto, nome, studio or {})
        t.fogli.append(Foglio(i, contenuto, nome, W, H, (x0, y0, x0 + W * s, y0 + H * s)))
        x_foglio += (W + 40) * s
    return t


def _cornice_e_cartiglio(ed, msp, o, W, H, scala, n, contenuto, formato, studio):
    s = scala / 1000
    P = _Penna(msp, o, scala)
    P.poly([(0, 0), (W * s, 0), (W * s, H * s), (0, H * s)], "CARTIGLIO", chiusa=True)
    P.poly([(MARG_SX * s, MARG * s), ((W - MARG) * s, MARG * s), ((W - MARG) * s, (H - MARG) * s),
            (MARG_SX * s, (H - MARG) * s)], "CORNICE", chiusa=True)
    cw, ch = CARTIGLIO
    x1, y0 = (W - MARG) * s, MARG * s
    x0, y1 = x1 - cw * s, y0 + ch * s
    P.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], "CARTIGLIO", chiusa=True)
    pr = ed.pratica
    righe = [
        (16, [(1.0, (pr.titolo or "Rilievo dello stato di fatto").upper(), 4.0)]),
        (10, [(0.5, f"Committente: {pr.committente or '-'}", 2.2),
              (0.5, f"Comune: {pr.comune or '-'}  {pr.indirizzo}", 2.2)]),
        (8, [(0.5, f"Fg. {pr.foglio or '-'}  Part. {pr.particella or '-'}", 2.2),
             (0.5, f"Pratica: {pr.codice}  ({pr.tipo})", 2.2)]),
        (10, [(0.5, f"TAV. {n} - {contenuto.upper()}", 3.2), (0.25, f"Scala 1:{scala}", 2.5),
              (0.25, f"Formato {formato}", 2.5)]),
        (8, [(0.5, f"Tecnico: {studio.get('tecnico') or pr.tecnico or '-'}", 2.2),
             (0.5, f"Data: {pr.data or date.today().strftime('%d/%m/%Y')}", 2.2)]),
        (10, [(1.0, "Elaborato da verificare e firmare a cura del tecnico abilitato. "
                    "In rosso: dati ipotizzati da verificare.", 1.8)]),
    ]
    y = y1
    for h, celle in righe:
        y_b = y - h * s
        P.poly([(x0, y_b), (x1, y_b)], "CARTIGLIO")
        xc = x0
        for frac, txt, th in celle:
            w = cw * frac * s
            if xc > x0:
                P.poly([(xc, y_b), (xc, y)], "CARTIGLIO")
            P.testo(txt, (xc + 2 * s, (y + y_b) / 2), th, "CARTIGLIO", "MIDDLE_LEFT")
            xc += w
        y = y_b


def _griglia(P, x0, y_top, col, dati, s, hr=6, evidenzia=None):
    """Tabella a griglia: col = [(intestazione, larghezza mm)], dati = righe di testi."""
    W = sum(c[1] for c in col)
    Ht = hr * len(dati)
    for i, riga in enumerate(dati):
        yb = y_top - (i + 1) * hr * s
        P.poly([(x0, yb), (x0 + W * s, yb)], "NOTE")
        x = 0
        for (_, w), val in zip(col, riga):
            lay = "IPOTESI_DA_VERIFICARE" if evidenzia and evidenzia(val) else "TESTI"
            P.testo(str(val), (x0 + (x + 1.2) * s, yb + hr / 2 * s), 1.9, lay, "MIDDLE_LEFT")
            x += w
    P.poly([(x0, y_top), (x0 + W * s, y_top)], "NOTE")
    x = 0
    for _, w in col + [("", 0)]:
        P.poly([(x0 + x * s, y_top - Ht * s), (x0 + x * s, y_top)], "NOTE")
        x += w
    return Ht


def _tabella(ed: Edificio, msp, o, scala) -> Ingombro:
    from .tabelle import dati_generali
    righe, tot = tabella_superfici(ed)
    P = _Penna(msp, o, scala)
    s = scala / 1000
    col = [("Locale", 34), ("Uso", 24), ("S (m²)", 15), ("h min", 12), ("h max", 12), ("h media", 14),
           ("V (m³)", 16), ("S fin.", 13), ("S/8", 12), ("1/8", 10), ("h", 10)]
    dati = [[c[0] for c in col]]
    for r in righe:
        dati.append([r.nome + (" (*)" if r.ipotesi else ""), r.categoria, fmt(r.superficie), fmt(r.h_min),
                     fmt(r.h_max) if r.h_max is not None else "-", fmt(r.h_media) if r.h_media else "-",
                     fmt(r.volume) if r.volume is not None else "-", fmt(r.s_finestrata), fmt(r.rai_minimo),
                     r.esito_rai, r.esito_h])
    dati.append(["TOTALE", "", fmt(tot.superficie), "", "", "", fmt(tot.volume), fmt(tot.s_finestrata), "", "", ""])
    dg = dati_generali(ed)
    gen = [["Dato", "Valore"], ["Superficie lorda (v.p.p.)", f"{fmt(dg.superficie_lorda)} m²"],
           ["Superficie coperta", f"{fmt(dg.superficie_coperta)} m²"],
           ["Volume vuoto per pieno (fino all'estradosso)", f"{fmt(dg.volume_vpp)} m³"],
           ["Superficie utile residenziale (SU)", f"{fmt(dg.su)} m²"],
           ["Superficie non residenziale (SNR)", f"{fmt(dg.snr)} m²"]]
    alt_gen = 6 * len(gen)
    alt_tab = 6 * len(dati)
    top = (alt_tab + alt_gen + 22) * s
    P.testo("TABELLA SUPERFICI, ALTEZZE E VERIFICHE", (0, top + 4 * s), 3.0, "TESTI", "BOTTOM_LEFT")
    _griglia(P, 0, top, col, dati, s, evidenzia=lambda v: v == "NO")
    y2 = top - (alt_tab + 10) * s
    P.testo("DATI GENERALI", (0, y2 + 3 * s), 2.6, "TESTI", "BOTTOM_LEFT")
    _griglia(P, 0, y2, [("Dato", 80), ("Valore", 30)], gen, s)
    note = ["S fin. = superficie delle finestre esterne del locale; S/8 = minimo richiesto (D.M. 5/7/1975, locali "
            "abitabili). h: minimo 2,70 abitabili, 2,40 accessori (altezza media).",
            "n.r. = verifica non richiesta per l'uso del locale. Norme regionali, regolamento edilizio e D.L. 69/2024 "
            "possono prevedere valori diversi: verificare. Volume e superfici secondo le definizioni del Comune."]
    for i, t in enumerate(note):
        P.testo(t, (0, y2 - (alt_gen + 4 + i * 3.5) * s), 1.6, "NOTE", "TOP_LEFT")
    return Ingombro.da_entita(P.ent)


def _legenda(ed: Edificio, msp, o, scala) -> Ingombro:
    P = _Penna(msp, o, scala)
    s = scala / 1000
    materiali = sorted({m.materiale for m in ed.muri})
    P.testo("LEGENDA MURATURE", (0, (len(materiali) * 8 + 4) * s), 3.0, "TESTI", "BOTTOM_LEFT")
    from shapely.geometry import box
    for i, mat in enumerate(materiali):
        y = (len(materiali) - 1 - i) * 8 * s
        b = box(0, y, 14 * s, y + 5 * s)
        P.retino(b, retino(mat))
        P.poly(list(b.exterior.coords), "MURI")
        P.testo(mat, (18 * s, y + 2.5 * s), 2.2, "TESTI", "MIDDLE_LEFT")
    return Ingombro.da_entita(P.ent)


def righe_note(ed: Edificio) -> list[str]:
    """Ipotesi raggruppate per oggetto e motivo (una riga per falda, non una per vertice)."""
    gruppi: dict[tuple, list[float]] = {}
    for ogg, campo, val in ed.ipotesi():
        chiave = (ogg, campo.split("[")[0], val.nota)
        gruppi.setdefault(chiave, []).append(val.valore)
    righe = ["Orientamento del Nord ipotizzato."] if ed.nord_ipotizzato else []
    for (ogg, campo, nota), valori in gruppi.items():
        lo, hi = min(valori), max(valori)
        v = fmt(lo) if abs(hi - lo) < 0.005 else f"{fmt(lo)}-{fmt(hi)}"
        righe.append(f"{ogg}: {campo} = {v}" + (f" - {nota}" if nota else ""))
    return righe or ["Nessun dato ipotizzato: tutte le misure provengono dal rilievo."]


def _note(ed: Edificio, msp, o, scala) -> Ingombro:
    P = _Penna(msp, o, scala)
    s = scala / 1000
    righe = righe_note(ed)
    righe = righe[:30] + ([f"... e altre {len(righe) - 30} voci (vedi registro)"] if len(righe) > 30 else [])
    P.testo("NOTE E DATI DA VERIFICARE", (0, (len(righe) * 4 + 3) * s), 3.0, "TESTI", "BOTTOM_LEFT")
    for i, rg in enumerate(righe):
        P.testo("- " + rg, (0, (len(righe) - i - 1) * 4 * s), 2.0, "IPOTESI_DA_VERIFICARE", "BOTTOM_LEFT")
    return Ingombro.da_entita(P.ent)
