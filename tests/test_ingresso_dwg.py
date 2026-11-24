import math
import shutil

import ezdxf
import pytest

from rilievo.dxf.stile import nuovo_documento
from rilievo.genera.pianta import disegna_pianta
from rilievo.geometria import apertura_mondo
from rilievo.ingresso.dwg import analizza_pianta, bozza_modello


def _pianta_dxf(ed, tmp_path, quote=True):
    doc = nuovo_documento(50)
    disegna_pianta(ed, doc.modelspace(), 50, quote=quote)
    p = tmp_path / "pianta.dxf"
    doc.saveas(p)
    return p


def _confronta(ed, bozza):
    assert len(bozza.muri) == len(ed.muri)
    for m in bozza.muri:
        assert m.spessore.valore == pytest.approx(0.40, abs=0.01)
        assert m.spessore.fonte == "dwg"
    assert len(bozza.aperture) == len(ed.aperture)
    for ap in ed.aperture:
        a, b = apertura_mondo(ed, ap)
        trovata = min(bozza.aperture, key=lambda x: math.dist(apertura_mondo(bozza, x)[0], a) +
                      math.dist(apertura_mondo(bozza, x)[1], b))
        ta, tb = apertura_mondo(bozza, trovata)
        assert math.dist(ta, a) + math.dist(tb, b) < 0.02 or math.dist(ta, b) + math.dist(tb, a) < 0.02
        assert trovata.tipo == ap.tipo
        assert trovata.altezza.fonte == "ipotesi"


def test_ritrova_muri_e_aperture_da_dxf(ed_scatola, tmp_path):
    doc = ezdxf.readfile(_pianta_dxf(ed_scatola, tmp_path))
    bozza = bozza_modello(analizza_pianta(doc))
    _confronta(ed_scatola, bozza)
    assert bozza.valida() == []


def test_locale_dal_testo(ed_scatola, tmp_path):
    doc = ezdxf.readfile(_pianta_dxf(ed_scatola, tmp_path))
    bozza = bozza_modello(analizza_pianta(doc))
    assert [l.nome for l in bozza.locali] == ["DEPOSITO"]


def test_disegno_in_centimetri(ed_scatola, tmp_path):
    doc = ezdxf.readfile(_pianta_dxf(ed_scatola, tmp_path, quote=False))
    for e in doc.modelspace():
        e.scale_uniform(100)  # come un collega che disegna in cm
    an = analizza_pianta(doc)
    assert an.fattore == pytest.approx(0.01)
    _confronta(ed_scatola, bozza_modello(an))


@pytest.mark.skipif(shutil.which("ODAFileConverter") is None, reason="ODA assente")
def test_da_dwg_vero(ed_scatola, tmp_path):
    from rilievo.esporta import dxf_a_dwg
    from rilievo.ingresso.dwg import leggi_dwg
    dwg = dxf_a_dwg(_pianta_dxf(ed_scatola, tmp_path), tmp_path / "pianta.dwg")
    _confronta(ed_scatola, bozza_modello(analizza_pianta(leggi_dwg(dwg))))


def test_muro_spesso_con_pilastrini_corti(tmp_path):
    """Muro da 55 cm con tratti pieni di 50-60 cm tra le aperture e un tramezzo innestato (caso del banco 2044)."""
    from rilievo.banco.caso import genera_caso
    from rilievo.banco.confronta import confronta
    ed = genera_caso(2044)
    doc = nuovo_documento(50)
    disegna_pianta(ed, doc.modelspace(), 50, quote=False)
    bozza = bozza_modello(analizza_pianta(doc))
    r = confronta(ed, bozza)
    assert not r.mancanti and not r.in_piu, (r.mancanti, r.in_piu)
    piano = [x for x in r.righe if "estremo" in x.grandezza or x.grandezza in ("spessore", "posizione asse")]
    assert max(x.errore_cm for x in piano) <= 1.0
