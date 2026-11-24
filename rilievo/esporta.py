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


def _oda(cartella_in: Path, cartella_out: Path, formato: str, filtro: str) -> None:
    cmd = ["ODAFileConverter", str(cartella_in), str(cartella_out), "ACAD2018", formato, "0", "1", filtro]
    if shutil.which("xvfb-run"):
        cmd = ["xvfb-run", "-a"] + cmd
    subprocess.run(cmd, check=True, capture_output=True, timeout=300)


def dxf_a_dwg(dxf: Path, dwg: Path) -> Path:
    with tempfile.TemporaryDirectory() as tin, tempfile.TemporaryDirectory() as tout:
        shutil.copy(dxf, Path(tin) / dxf.name)
        _oda(Path(tin), Path(tout), "DWG", "*.dxf")
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


COLORI_STAMPA = {"IPOTESI_DA_VERIFICARE": 1, "DEGRADO": 6, "LINEE_SEZIONE": 7, "RETINI": 8, "SEZ_TRATTEGGI": 8,
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


def esporta(tavole, cartella: str | Path, nome: str, dwg: bool = True, pdf: bool = True,
            png: bool = True) -> dict:
    cartella = Path(cartella)
    cartella.mkdir(parents=True, exist_ok=True)
    out: dict = {}
    dxf = cartella / f"{nome}.dxf"
    tavole.doc.saveas(dxf)
    out["dxf"] = dxf
    if dwg and oda_disponibile():
        out["dwg"] = dxf_a_dwg(dxf, cartella / f"{nome}.dwg")
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
                p = cartella / f"{nome}_tav{f.numero}.png"
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
