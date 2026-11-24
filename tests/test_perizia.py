import cv2
import numpy as np
import pymupdf
import pytest

from conftest import scatola
from rilievo.dxf.stile import nuovo_documento
from rilievo.genera.perizia import classe_lesione, disegna_coni, documentazione_fotografica_pdf
from rilievo.genera.tavola import componi_tavole
from rilievo.modello import Foto, Lesione
from test_pianta import _testi


@pytest.fixture
def ed_perizia(tmp_path):
    ed = scatola(aperture=[{"id": "P1", "muro": "MS", "da": 1.0, "a": 2.0, "altezza": 2.2, "tipo": "porta"}])
    ed.pratica.tipo = "perizia"
    for i in range(3):
        f = tmp_path / f"f{i}.jpg"
        cv2.imwrite(str(f), np.full((60, 80, 3), 120 + i * 30, np.uint8))
        ed.foto.append(Foto(id=str(i + 1), file=str(f), punto=(1 + i, -3), direzione_gradi=90,
                            soggetto=f"Facciata sud, vista {i + 1}"))
    ed.lesioni.append(Lesione(id="LES1", muro="MS", punti=[(2.3, 2.4), (2.5, 1.2)], ampiezza_mm=3.5,
                              foto="2", nota="sopra la porta"))
    ed.lesioni.append(Lesione(id="LES2", muro="MN", lato="interno", punti=[(1.0, 2.0), (1.2, 1.0)], ampiezza_mm=0.5))
    return ed


def test_classe_lesione():
    assert classe_lesione(0.5) == "capillare (< 1 mm)"
    assert classe_lesione(2.0) == "media (1-3 mm)"
    assert classe_lesione(4.0) == "grave (> 3 mm)"
    assert classe_lesione(None) == "non misurata"


def test_coni_ottici_numerati(ed_perizia):
    doc = nuovo_documento(50)
    disegna_coni(ed_perizia, doc.modelspace(), 50, (0, 0))
    assert len(doc.modelspace().query('*[layer=="FOTO"]')) >= 3
    assert {"1", "2", "3"} <= set(_testi(doc))


def test_profilo_perizia_tavole(ed_perizia):
    t = componi_tavole(ed_perizia)
    contenuti = [f.contenuto for f in t.fogli]
    assert "Documentazione fotografica" in contenuti and "Quadro fessurativo" in contenuti
    testi = " | ".join(_testi(t.doc))
    assert "LES1" in testi and "grave (> 3 mm)" in testi and "interno" in testi


def test_pdf_documentazione_fotografica(ed_perizia, tmp_path):
    out = documentazione_fotografica_pdf(ed_perizia, tmp_path / "foto.pdf", foto_per_pagina=2)
    with pymupdf.open(out) as pdf:
        assert pdf.page_count == 1 + 2  # pianta dei punti di ripresa + 3 foto a 2 per pagina


def test_punto_lontano_avvicinato_lungo_la_direzione():
    import math
    from shapely.geometry import Point, box
    from rilievo.genera.perizia import DISTANZA_MAX, _avvicina
    edificio = box(0, 0, 10, 4)
    q = _avvicina(edificio, np.array([5.0, -16.0]), math.radians(90))
    assert q[0] == pytest.approx(5.0) and edificio.distance(Point(q)) == pytest.approx(DISTANZA_MAX, abs=0.01)
