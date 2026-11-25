"""Esportazione: DXF, DWG (AutoCAD 2018 via ODA File Converter), PDF in scala, anteprime PNG."""
from __future__ import annotations

import collections
import shutil
import subprocess
import tempfile
from pathlib import Path

import ezdxf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from ezdxf.addons.drawing import Frontend, RenderContext  # noqa: E402
from ezdxf.addons.drawing.config import (BackgroundPolicy, ColorPolicy, Configuration,  # noqa: E402
                                         LineweightPolicy)
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402


def oda_disponibile() -> bool:
    return shutil.which("ODAFileConverter") is not None


VERSIONI_DWG = ("ACAD2000", "ACAD2004", "ACAD2007", "ACAD2010", "ACAD2013", "ACAD2018")


def _oda(cartella_in: Path, cartella_out: Path, formato: str, filtro: str, versione: str = "ACAD2018") -> None:
    if versione not in VERSIONI_DWG:
        raise ValueError(f"Versione DWG sconosciuta: {versione} ({', '.join(VERSIONI_DWG)})")
    cmd = ["ODAFileConverter", str(cartella_in), str(cartella_out), versione, formato, "0", "1", filtro]
    if shutil.which("xvfb-run"):
        cmd = ["xvfb-run", "-a"] + cmd
    subprocess.run(cmd, check=True, capture_output=True, timeout=300)


def dxf_a_dwg(dxf: Path, dwg: Path, versione: str = "ACAD2018") -> Path:
    with tempfile.TemporaryDirectory() as tin, tempfile.TemporaryDirectory() as tout:
        shutil.copy(dxf, Path(tin) / dxf.name)
        _oda(Path(tin), Path(tout), "DWG", "*.dxf", versione)
        prodotto = Path(tout) / (dxf.stem + ".dwg")
        if not prodotto.exists():
            raise RuntimeError("La conversione in DWG non ha prodotto il file")
        shutil.copy(prodotto, dwg)
    return dwg


def dwg_a_dxf(dwg: Path, dxf: Path) -> Path:
    with tempfile.TemporaryDirectory() as tin, tempfile.TemporaryDirectory() as tout:
        shutil.copy(dwg, Path(tin) / dwg.name)
        _oda(Path(tin), Path(tout), "DXF", "*.dwg")
        prodotto = Path(tout) / (dwg.stem + ".dxf")
        if not prodotto.exists():
            raise RuntimeError("La conversione da DWG non ha prodotto il file")
        shutil.copy(prodotto, dxf)
    return dxf


def conta_entita(doc) -> dict[str, int]:
    return dict(collections.Counter(e.dxftype() for e in doc.modelspace()))


def roundtrip_ok(dwg: str | Path, doc) -> bool:
    with tempfile.TemporaryDirectory() as t:
        back = dwg_a_dxf(Path(dwg), Path(t) / "rt.dxf")
        return conta_entita(ezdxf.readfile(back)) == conta_entita(doc)


COLORI_STAMPA = {"IPOTESI_DA_VERIFICARE": 1, "COMPARATIVA_DEMOLIZIONI": 2, "COMPARATIVA_COSTRUZIONI": 1, "FOTO": 5, "DEGRADO": 6, "LINEE_SEZIONE": 7, "RETINI": 8, "SEZ_TRATTEGGI": 8,
                 "SEZ_VISTO": 8, "COPERTURA_PIANTA": 8}


def _figura(doc):
    """Disegna il modelspace in nero su bianco; ipotesi in rosso e degrado in magenta."""
    originali = {ly.dxf.name: ly.dxf.color for ly in doc.layers}
    try:
        for ly in doc.layers:
            ly.dxf.color = COLORI_STAMPA.get(ly.dxf.name, 7)
        fig = plt.figure()
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_axis_off()
        cfg = Configuration(color_policy=ColorPolicy.COLOR, lineweight_policy=LineweightPolicy.ABSOLUTE,
                            background_policy=BackgroundPolicy.WHITE, min_lineweight=0.1)
        Frontend(RenderContext(doc), MatplotlibBackend(ax, adjust_figure=False), config=cfg).draw_layout(
            doc.modelspace(), finalize=False)
    finally:
        for ly in doc.layers:
            ly.dxf.color = originali[ly.dxf.name]
    return fig, ax


def pianta_per_ape(ed, cartella: str | Path, nome: str, versione: str = "ACAD2000") -> dict:
    """Pianta da importare nei programmi per l'APE (Blumatica, Termolog, TerMus...): solo muri, porte e nomi
    con superfici dei locali, in centimetri, spigolo esterno in basso a sinistra nell'origine, formato vecchio
    (AutoCAD 2000) e DXF di riserva. Lezione della pratica C001: Blumatica Energy 6.2 non apre il DWG 2018
    ("File non valido") e si confonde con tabelle, retini e quote."""
    from ezdxf.math import Matrix44
    from .dxf.stile import nuovo_documento
    from .genera.pianta import disegna_pianta
    from .geometria import ingombro_muri
    cartella = Path(cartella)
    cartella.mkdir(parents=True, exist_ok=True)
    tmp = nuovo_documento(100)
    disegna_pianta(ed, tmp.modelspace(), 100, (0.0, 0.0), quote=False, titolo=None, linee_sezione=False)
    minx, miny, _, _ = ingombro_muri(ed).bounds
    m = Matrix44.translate(-minx, -miny, 0) @ Matrix44.scale(100, 100, 1)  # metri -> centimetri
    geo = {"MURI", "TRAMEZZI", "APERTURE", "APERTURE_NASCOSTE"}
    doc = ezdxf.new("R2000", setup=False)
    doc.header["$INSUNITS"] = 5  # centimetri
    doc.header["$MEASUREMENT"] = 1
    for ly in tmp.layers:
        if ly.dxf.name in geo | {"TESTI"} and ly.dxf.name not in doc.layers:
            doc.layers.add(ly.dxf.name, color=ly.dxf.color, lineweight=ly.dxf.lineweight)
    msp = doc.modelspace()
    for e in tmp.modelspace():
        t, lay = e.dxftype(), e.dxf.layer
        if t == "TEXT" and lay == "TESTI":
            testo = e.dxf.text.strip()
            if testo == "N" or testo.startswith("q."):
                continue  # nord senza simbolo e quote di pavimento: non servono al programma
        elif t not in ("LINE", "ARC", "LWPOLYLINE") or lay not in geo:
            continue  # retini, quote, sigle, simboli
        c = e.copy()
        c.transform(m)
        if t == "TEXT":
            c.dxf.style = "Standard"
        msp.add_entity(c)
    dxf = cartella / f"{nome}_APE_cm_{versione}.dxf"
    doc.saveas(dxf)
    out = {"dxf": dxf}
    if oda_disponibile():
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / dxf.name
            shutil.copy(dxf, src)
            out["dwg"] = dxf_a_dwg(src, cartella / f"{nome}_APE_cm_{versione}.dwg", versione)
    return out


def esporta(tavole, cartella: str | Path, nome: str, dwg: bool = True, pdf: bool = True,
            png: bool = True, versione: str = "ACAD2018") -> dict:
    cartella = Path(cartella)
    cartella.mkdir(parents=True, exist_ok=True)
    out: dict = {}
    dxf = cartella / f"{nome}.dxf"
    tavole.doc.saveas(dxf)
    out["dxf"] = dxf
    if dwg and oda_disponibile():
        out["dwg"] = dxf_a_dwg(dxf, cartella / f"{nome}.dwg", versione)
    if pdf or png:
        fig, ax = _figura(tavole.doc)
        if pdf:
            out["pdf"] = cartella / f"{nome}.pdf"
            with PdfPages(out["pdf"]) as pp:
                for f in tavole.fogli:
                    _inquadra(fig, ax, f)
                    pp.savefig(fig)
        if png:
            out["png"] = []
            for f in tavole.fogli:
                _inquadra(fig, ax, f)
                (cartella / "anteprime").mkdir(exist_ok=True)
                p = cartella / "anteprime" / f"{nome}_tav{f.numero}.png"
                fig.savefig(p, dpi=110)
                out["png"].append(p)
        plt.close(fig)
    return out


def _inquadra(fig, ax, foglio):
    fig.set_size_inches(foglio.larghezza_mm / 25.4, foglio.altezza_mm / 25.4)
    x0, y0, x1, y1 = foglio.bbox
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal", adjustable="box")
