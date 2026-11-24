"""Scheda di sopralluogo stampabile: cosa misurare e come fotografare.

Se si passa un modello, la scheda elenca anche i dati che mancano o sono
ipotizzati per quella pratica.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

from ..dxf.quote import fmt  # noqa: E402
from ..modello import Edificio  # noqa: E402

GENERALE = [
    ("PRIMA DI PARTIRE", [
        "Stampa della pianta (catastale o di progetto) su cui scrivere, penna di 2 colori, metro, distanziometro laser",
        "Telefono carico: foto con obiettivo 1x (non 0,5x grandangolo) per le facciate da misurare",
        "Bussola o app per il Nord; se possibile foto aerea del lotto",
    ]),
    ("PIANTA - PER OGNI LOCALE", [
        "Dimensioni interne: tutte e due le diagonali se il locale non e' rettangolare (servono a chiudere la forma)",
        "Spessore di ogni muro (si misura sulle porte o sulle finestre)",
        "Aperture: quote PROGRESSIVE dal punto 0 (spigolo interno) lungo ogni muro, senza azzerare il metro",
        "Altezza di porte e finestre, altezza del davanzale, forma (rettangolare / arco)",
        "Altezza netta: H min e H max se il soffitto e' inclinato, oppure H unica",
        "Tipo di soffitto (travi a vista, cannucciato, solaio) e di pavimento; dislivelli tra locali",
    ]),
    ("ESTERNO E COPERTURA", [
        "Altezza della gronda e del colmo dal terreno (laser), sporto della gronda",
        "Quota del terreno rispetto al pavimento interno (gradini, rampe)",
        "Pluviali, canne fumarie, comignoli, scale esterne, muretti",
        "Materiale dei muri (pietra, blocchi, laterizio) e del manto (coppi, tegole, lamiera)",
    ]),
    ("FOTO", [
        "Una foto frontale di ogni facciata, con il telefono dritto, da piu' lontano possibile",
        "Facciate lunghe: piu' foto sovrapposte di un terzo, sempre alla stessa distanza",
        "Mettere nella foto una misura nota (es. la porta misurata) per il raddrizzamento",
        "Foto di ogni locale dagli angoli; foto ravvicinate di lesioni con un metro accanto",
        "Caricare le foto ORIGINALI (non dalla chat): contengono focale e obiettivo",
        "Annotare sulla pianta il punto e la direzione di ogni foto (numero foto)",
    ]),
    ("DEGRADO E LESIONI (per perizie)", [
        "Posizione della lesione sul muro (progressiva e quota), andamento, ampiezza in mm",
        "Distacchi di intonaco, umidita' di risalita, parti mancanti della copertura",
    ]),
]


def voci_mancanti(ed: Edificio) -> list[str]:
    out = []
    if ed.nord_ipotizzato:
        out.append("Orientamento del Nord")
    for ogg, campo, val in ed.ipotesi():
        out.append(f"{ogg}: {campo} (ora ipotizzato {fmt(val.valore)}{' - ' + val.nota if val.nota else ''})")
    for loc in ed.locali:
        if loc.h_max is None and "falda" in loc.soffitto.lower():
            out.append(f"{loc.nome}: H max (soffitto inclinato)")
    if not ed.falde:
        out.append("Copertura: quote di gronda e colmo")
    if not ed.foto:
        out.append("Foto di riferimento delle facciate (con punto di scatto)")
    return out


def scheda_sopralluogo(out: str | Path, ed: Edificio | None = None) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sezioni = list(GENERALE)
    if ed is not None:
        mancanti = voci_mancanti(ed)
        if mancanti:
            sezioni.insert(0, (f"DA MISURARE PER QUESTA PRATICA ({ed.pratica.codice})", mancanti))
    with PdfPages(out) as pp:
        fig = plt.figure(figsize=(8.27, 11.69))
        y = 0.95
        fig.text(0.07, y, "SCHEDA DI SOPRALLUOGO", fontsize=16, weight="bold")
        y -= 0.035
        for titolo, voci in sezioni:
            if y < 0.12:
                pp.savefig(fig)
                plt.close(fig)
                fig = plt.figure(figsize=(8.27, 11.69))
                y = 0.95
            fig.text(0.07, y, titolo, fontsize=11, weight="bold")
            y -= 0.025
            for v in voci:
                righe = _a_capo(v, 95)
                fig.text(0.08, y, "□", fontsize=10)
                for i, r in enumerate(righe):
                    fig.text(0.105, y - i * 0.018, r, fontsize=9)
                y -= 0.018 * len(righe) + 0.006
            y -= 0.015
        fig.text(0.07, 0.04, "Note:", fontsize=10)
        pp.savefig(fig)
        plt.close(fig)
    return out


def _a_capo(t: str, n: int) -> list[str]:
    parole, righe, r = t.split(), [], ""
    for p in parole:
        if len(r) + len(p) + 1 > n:
            righe.append(r)
            r = p
        else:
            r = (r + " " + p).strip()
    return righe + [r]
