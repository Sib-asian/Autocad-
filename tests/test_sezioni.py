import pytest
from shapely.ops import unary_union

from rilievo.dxf.stile import nuovo_documento
from rilievo.genera.sezioni import disegna_sezione, geometria_sezione
from rilievo.modello import LineaSezione
from test_pianta import _testi

SEZ = LineaSezione(nome="A", p0=(3.0, -1.0), p1=(3.0, 4.7))


def test_muro_tagliato_spessore(ed_scatola):
    g = geometria_sezione(ed_scatola, SEZ)
    muri = [t for t in g.tagliati if t.tipo == "muro"]
    assert len(muri) == 2
    for t in muri:
        x0, _, x1, _ = t.poligono.bounds
        assert x1 - x0 == pytest.approx(0.40, abs=1e-6)


def test_falde_tagliate_con_spessore(ed_scatola):
    g = geometria_sezione(ed_scatola, SEZ)
    falde = [t for t in g.tagliati if t.tipo == "falda"]
    assert len(falde) == 2
    assert max(t.poligono.bounds[3] for t in falde) == pytest.approx(4.0, abs=1e-6)


def test_altezza_media_falda(ed_scatola):
    doc = nuovo_documento(50)
    disegna_sezione(ed_scatola, SEZ, doc.modelspace(), scala=50)
    t = " | ".join(_testi(doc))
    assert "h media" in t
    assert "SEZIONE A-A" in t


def test_nessun_visto_dietro_tagliato(ed_scatola):
    g = geometria_sezione(ed_scatola, SEZ)
    tag = unary_union([t.poligono for t in g.tagliati])
    for p in g.visti:
        assert p.poligono2d.intersection(tag).area < 1e-6


def test_porta_tagliata_lascia_vuoto():
    from conftest import scatola
    ed = scatola(aperture=[{"id": "P1", "muro": "MS", "da": 2.5, "a": 3.5, "altezza": 2.2, "tipo": "porta"}])
    g = geometria_sezione(ed, SEZ)
    sud = [t for t in g.tagliati if t.tipo == "muro" and t.rif == "MS"][0]
    # sotto l'architrave (z < 2.2) il muro non c'e'
    assert sud.poligono.bounds[1] == pytest.approx(2.2, abs=1e-6)


def test_sezione_parallela_al_colmo_non_vede_la_gronda_attraverso_il_tetto(ed_scatola):
    sez = LineaSezione(nome="B", p0=(-1, 1.0), p1=(7.5, 1.0), verso="dx")
    g = geometria_sezione(ed_scatola, sez)
    bordi = [p for p in g.visti if p.faccia.tipo == "bordo_falda"]
    assert sum(p.poligono2d.area for p in bordi) < 1e-6


def test_tavola_sezioni_con_schema_delle_tracce():
    """La tavola delle sezioni porta una piccola pianta con le tracce dei tagli (scala 1:200 se tavole 1:50)."""
    from rilievo.banco.caso import genera_caso
    from rilievo.genera.tavola import componi_tavole
    ed = genera_caso(7)
    t = componi_tavole(ed, tavole={"sezioni"})
    testi = [e.dxf.text for e in t.doc.modelspace().query("TEXT")]
    assert any(x.startswith("SCHEMA DELLE SEZIONI") and "1:200" in x for x in testi)
    foglio = t.fogli[0]
    x0, y0, x1, y1 = foglio.bbox
    for e in t.doc.modelspace().query("TEXT"):  # tutto dentro il foglio
        assert x0 <= e.dxf.insert.x <= x1 and y0 <= e.dxf.insert.y <= y1
