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


def test_travi_tagliate_nella_sezione_parallela_al_colmo(ed_scatola):
    from rilievo.genera.sezioni import stratigrafia_copertura
    sez = LineaSezione(nome="B", p0=(-1, 1.0), p1=(7.5, 1.0), verso="dx")
    s = stratigrafia_copertura(ed_scatola, sez)
    # falda larga 7,15 + sporti: travi ogni 0,60 m
    assert 10 <= len(s.travi_tagliate) <= 14
    for t in s.travi_tagliate:
        x0, z0, x1, z1 = t.bounds
        assert x1 - x0 == pytest.approx(0.12, abs=1e-6) and z1 - z0 == pytest.approx(0.16, abs=1e-6)
    assert s.linee_manto


def test_trave_vista_nella_sezione_lungo_la_pendenza(ed_scatola):
    from rilievo.genera.sezioni import stratigrafia_copertura
    s = stratigrafia_copertura(ed_scatola, SEZ)
    assert not s.travi_tagliate and len(s.travi_viste) == 2  # una per falda
