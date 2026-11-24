"""Elaborati per le perizie: documentazione fotografica e quadro fessurativo."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from ..dxf.quote import fmt
from ..dxf.stile import mm
from ..modello import Edificio
from .pianta import Ingombro, _Penna, disegna_pianta
from .prospetti import _faccia_verso, disegna_prospetto, lati_prospetto

AMPIEZZA_CONO = 50  # gradi


def classe_lesione(ampiezza_mm: float | None) -> str:
    """Classe convenzionale per ampiezza (da adattare al protocollo della perizia)."""
    if ampiezza_mm is None:
        return "non misurata"
    if ampiezza_mm < 1:
        return "capillare (< 1 mm)"
    if ampiezza_mm <= 3:
        return "media (1-3 mm)"
    return "grave (> 3 mm)"


def disegna_coni(ed: Edificio, msp, scala: int, origine, titolo="PUNTI DI RIPRESA FOTOGRAFICA") -> Ingombro:
    """Pianta senza quote con i coni ottici numerati delle foto."""
    ing = disegna_pianta(ed, msp, scala, origine, quote=False, titolo=titolo)
    P = _Penna(msp, origine, scala)
    from .tabelle import sagoma
    sagoma_pianta = sagoma(ed)
    L, r = mm(16, scala), mm(3.2, scala)
    for f in ed.foto:
        if f.punto is None or f.direzione_gradi is None:
            continue
        c = np.array(f.punto, float)
        a = math.radians(f.direzione_gradi)
        c = _avvicina(sagoma_pianta, c, a)
        mezzo = math.radians(AMPIEZZA_CONO / 2)
        p1 = c + L * np.array([math.cos(a + mezzo), math.sin(a + mezzo)])
        p2 = c + L * np.array([math.cos(a - mezzo), math.sin(a - mezzo)])
        P.poly([p1, c, p2], "FOTO")
        e = msp.add_circle(P.T(c), r, dxfattribs={"layer": "FOTO"})
        P.ent.append(e)
        P.testo(f.id, c, 2.6, "FOTO")
    tot = Ingombro.da_entita(P.ent) if P.ent else ing
    return Ingombro(min(ing.minx, tot.minx), min(ing.miny, tot.miny), max(ing.maxx, tot.maxx), max(ing.maxy, tot.maxy))


DISTANZA_MAX = 2.5  # m: oltre, il punto di ripresa si disegna avvicinato lungo la direzione di scatto


def _avvicina(sagoma, c, a):
    """Punto sulla direzione di scatto a DISTANZA_MAX dall'edificio (se il punto vero e' piu' lontano)."""
    from shapely.geometry import LineString, Point
    d = sagoma.distance(Point(c))
    if d <= DISTANZA_MAX:
        return c
    u = np.array([math.cos(a), math.sin(a)])
    raggio = LineString([tuple(c), tuple(c + u * (d + 100))])
    inter = raggio.intersection(sagoma.buffer(DISTANZA_MAX).exterior)
    punti = [np.array(p.coords[0]) for p in getattr(inter, "geoms", [inter]) if not p.is_empty]
    if not punti:
        return c  # la direzione non punta verso l'edificio: resta dov'e'
    return min(punti, key=lambda p: float(np.linalg.norm(p - c)))


def _tabella(P, s, titolo, col, dati, h_mm=6):
    W = sum(w for _, w in col)
    Ht = h_mm * len(dati)
    P.testo(titolo, (0, (Ht + 4) * s), 3.0, "TESTI", "BOTTOM_LEFT")
    for i, riga in enumerate(dati):
        yb = (Ht - (i + 1) * h_mm) * s
        P.poly([(0, yb), (W * s, yb)], "NOTE")
        x = 0
        for (_, w), val in zip(col, riga):
            P.testo(str(val), ((x + 1.2) * s, yb + h_mm / 2 * s), 1.9, "TESTI", "MIDDLE_LEFT")
            x += w
    P.poly([(0, Ht * s), (W * s, Ht * s)], "NOTE")
    x = 0
    for _, w in col + [("", 0)]:
        P.poly([(x * s, 0), (x * s, Ht * s)], "NOTE")
        x += w


def tabella_foto(ed: Edificio, msp, origine, scala) -> Ingombro:
    P = _Penna(msp, origine, scala)
    col = [("N.", 10), ("Soggetto", 90), ("File", 60)]
    dati = [[c for c, _ in col]] + [[f.id, f.soggetto or "-", Path(f.file).name] for f in ed.foto]
    _tabella(P, scala / 1000, "ELENCO DELLE FOTO", col, dati)
    P.testo("I punti di ripresa lontani dall'edificio sono disegnati avvicinati, lungo la direzione di scatto.",
            (0, -4 * scala / 1000), 1.6, "NOTE", "TOP_LEFT")
    return Ingombro.da_entita(P.ent)


def _lunghezza(punti) -> float:
    return sum(math.dist(a, b) for a, b in zip(punti, punti[1:]))


def tabella_lesioni(ed: Edificio, msp, origine, scala) -> Ingombro:
    P = _Penna(msp, origine, scala)
    col = [("Lesione", 18), ("Muro", 14), ("Lato", 16), ("Lungh. (m)", 18), ("Ampiezza", 18), ("Classe", 32),
           ("Foto", 12), ("Note", 60)]
    dati = [[c for c, _ in col]]
    for les in ed.lesioni:
        amp = f"{les.ampiezza_mm:g} mm" if les.ampiezza_mm is not None else "-"
        dati.append([les.id, les.muro, les.lato, fmt(_lunghezza(les.punti)), amp, classe_lesione(les.ampiezza_mm),
                     les.foto or "-", les.nota or ("lesione interna: vedi foto" if les.lato == "interno" else "")])
    _tabella(P, scala / 1000, "QUADRO FESSURATIVO - ELENCO DELLE LESIONI", col, dati)
    P.testo("Classi di ampiezza indicative: capillare < 1 mm, media 1-3 mm, grave > 3 mm. Le lesioni esterne sono "
            "riportate sui prospetti (in magenta), quelle interne nell'elenco con la foto.", (0, -4 * scala / 1000),
            1.6, "NOTE", "TOP_LEFT")
    return Ingombro.da_entita(P.ent)


def gruppi_perizia(ed: Edificio, scala: int):
    gruppi = []
    if ed.foto:
        gruppi.append(("Documentazione fotografica", [lambda m, o: disegna_coni(ed, m, scala, o),
                                                      lambda m, o: tabella_foto(ed, m, o, scala)]))
    if ed.lesioni:
        viste = []
        for v in lati_prospetto(ed):
            if any(les.lato == "esterno" and _faccia_verso(ed, les.muro, v) for les in ed.lesioni):
                viste.append((lambda vv: (lambda m, o: disegna_prospetto(ed, vv, m, scala, o, quote=False)))(v))
        viste.append(lambda m, o: tabella_lesioni(ed, m, o, scala))
        gruppi.append(("Quadro fessurativo", viste))
    return gruppi


def documentazione_fotografica_pdf(ed: Edificio, out, foto_per_pagina: int = 4, base: Path | None = None) -> Path:
    """PDF A4: pianta con i punti di ripresa, poi le foto con numero e didascalia."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.image as mpimg
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    from ..dxf.stile import nuovo_documento
    from ..esporta import _figura
    out = Path(out)
    scala = 100
    doc = nuovo_documento(scala)
    ing = disegna_coni(ed, doc.modelspace(), scala, (0, 0))
    with PdfPages(out) as pp:
        fig, ax = _figura(doc)
        fig.set_size_inches(8.27, 11.69)
        mx, my = ing.larghezza * 0.05, ing.altezza * 0.05
        ax.set_xlim(ing.minx - mx, ing.maxx + mx)
        ax.set_ylim(ing.miny - my, ing.maxy + my)
        ax.set_aspect("equal", adjustable="datalim")
        fig.text(0.5, 0.96, f"DOCUMENTAZIONE FOTOGRAFICA - {ed.pratica.titolo or ed.pratica.codice}",
                 ha="center", fontsize=13, weight="bold")
        pp.savefig(fig)
        plt.close(fig)
        foto = list(ed.foto)
        for i in range(0, len(foto), foto_per_pagina):
            fig = plt.figure(figsize=(8.27, 11.69))
            gruppo = foto[i:i + foto_per_pagina]
            righe = math.ceil(len(gruppo) / 2) if foto_per_pagina > 2 else len(gruppo)
            colonne = 2 if foto_per_pagina > 2 else 1
            for k, f in enumerate(gruppo):
                ax = fig.add_subplot(max(righe, 1), colonne, k + 1)
                p = Path(f.file)
                if not p.is_absolute() and base is not None:
                    p = base / p
                try:
                    ax.imshow(mpimg.imread(str(p)))
                except Exception:
                    ax.text(0.5, 0.5, "foto non trovata", ha="center")
                ax.set_axis_off()
                ax.set_title(f"Foto {f.id} - {f.soggetto}", fontsize=9)
            pp.savefig(fig)
            plt.close(fig)
    return out
