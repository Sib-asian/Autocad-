import shutil
from decimal import Decimal

import pytest

from rilievo.esporta import esporta, roundtrip_ok
from rilievo.genera.tabelle import tabella_superfici
from rilievo.genera.tavola import componi_tavole
from rilievo.modello import LineaSezione


@pytest.fixture
def ed_completo(ed_scatola):
    ed = ed_scatola.model_copy(deep=True)
    ed.sezioni.append(LineaSezione(nome="A", p0=(3, -1), p1=(3, 4.7)))
    ed.pratica.titolo = "Rilievo deposito"
    return ed


def test_tabella_totali_somma_arrotondati(ed_completo):
    righe, tot = tabella_superfici(ed_completo)
    assert righe[0].superficie == Decimal("23.50")
    assert tot.superficie == sum(r.superficie for r in righe)
    assert righe[0].rai_minimo == Decimal("2.94")  # 23,50 / 8 = 2,9375 -> 2,94


def test_componi_tre_tavole(ed_completo):
    t = componi_tavole(ed_completo)
    assert [f.contenuto for f in t.fogli] == ["Pianta", "Prospetti", "Sezioni"]
    assert t.scala == 50
    for f in t.fogli:
        assert f.formato in ("A3", "A2", "A1", "A0")


def test_pdf_creato(ed_completo, tmp_path):
    t = componi_tavole(ed_completo)
    out = esporta(t, tmp_path, "prova", dwg=False)
    import pymupdf as fitz
    with fitz.open(out["pdf"]) as pdf:
        assert pdf.page_count == 3
        w_mm = pdf[0].rect.width / 72 * 25.4
        assert w_mm == pytest.approx(t.fogli[0].larghezza_mm, abs=1)


@pytest.mark.skipif(shutil.which("ODAFileConverter") is None, reason="ODA File Converter assente")
def test_dwg_ac1032_roundtrip(ed_completo, tmp_path):
    t = componi_tavole(ed_completo)
    out = esporta(t, tmp_path, "prova")
    with open(out["dwg"], "rb") as fh:
        assert fh.read(6) == b"AC1032"
    assert roundtrip_ok(out["dwg"], t.doc)


def test_pianta_per_software_ape(tmp_path):
    """Per i programmi APE (es. Blumatica, che non apre il DWG 2018): solo muri, porte e locali, in centimetri,
    nell'origine, formato AutoCAD 2000 (pratica C001)."""
    import collections
    import ezdxf
    from rilievo.banco.caso import genera_caso
    from rilievo.esporta import pianta_per_ape
    ed = genera_caso(3)
    out = pianta_per_ape(ed, tmp_path, "prova")
    doc = ezdxf.readfile(out["dxf"])
    assert doc.dxfversion == "AC1015" and doc.header["$INSUNITS"] == 6  # metri (pratica C002: 1:100 = metri)
    tipi = collections.Counter(e.dxftype() for e in doc.modelspace())
    assert not ({"HATCH", "DIMENSION", "MTEXT", "INSERT"} & set(tipi))
    # pratica C002: un solo layer bianco, linee normali, nessuna scritta
    assert {e.dxf.layer for e in doc.modelspace()} == {"PIANTA"} and "TEXT" not in tipi
    ly = doc.layers.get("PIANTA")
    assert ly.dxf.color == 7 and ly.dxf.lineweight < 0  # spessore di default
    assert all(not e.dxf.hasattr("lineweight") and not e.dxf.hasattr("color") for e in doc.modelspace())
    bb = ezdxf.bbox.extents(doc.modelspace().query("LWPOLYLINE"))  # i muri
    assert abs(bb.extmin.x) < 1e-6 and abs(bb.extmin.y) < 1e-6 and 2 < bb.extmax.x < 60  # metri
    if "dwg" in out:
        assert open(out["dwg"], "rb").read(6) == b"AC1015"
