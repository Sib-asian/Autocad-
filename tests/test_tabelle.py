from decimal import Decimal

import pytest

from conftest import scatola
from rilievo.genera.tabelle import categoria, dati_generali, superficie_finestrata, tabella_superfici


def _con_nome(ed, nome):
    ed.locali[0] = ed.locali[0].model_copy(update={"nome": nome})
    return ed


def test_categoria_dalla_destinazione():
    ed = scatola()
    assert categoria(_con_nome(ed, "Cucina").locali[0]) == "abitabile"
    assert categoria(_con_nome(ed, "Bagno").locali[0]) == "accessorio"
    assert categoria(_con_nome(ed, "Deposito").locali[0]) == "non residenziale"


def test_superficie_finestrata_reale_solo_finestre_esterne():
    ed = scatola(aperture=[
        {"id": "P1", "muro": "MS", "da": 1.0, "a": 2.0, "altezza": 2.2, "tipo": "porta"},
        {"id": "F1", "muro": "MS", "da": 3.5, "a": 4.3, "altezza": 0.8, "davanzale": 1.2},
        {"id": "F2", "muro": "MN", "da": 1.0, "a": 2.0, "altezza": 1.2, "davanzale": 0.9},
    ])
    assert superficie_finestrata(ed, ed.locali[0]) == pytest.approx(0.64 + 1.2)


def test_esito_rapporto_aeroilluminante():
    ed = _con_nome(scatola(aperture=[{"id": "F1", "muro": "MS", "da": 3.5, "a": 4.3, "altezza": 0.8,
                                      "davanzale": 1.2}]), "Cucina")
    r = tabella_superfici(ed)[0][0]
    assert r.s_finestrata == Decimal("0.64") and r.rai_minimo == Decimal("2.94")
    assert r.esito_rai == "NO"
    ed2 = _con_nome(scatola(), "Deposito")
    assert tabella_superfici(ed2)[0][0].esito_rai == "n.r."


def test_esito_altezza_media_abitabile():
    r = tabella_superfici(_con_nome(scatola(), "Cucina"))[0][0]
    assert r.h_richiesta == Decimal("2.70")
    assert r.esito_h == ("OK" if r.h_media >= Decimal("2.70") else "NO")


def test_dati_generali_vuoto_per_pieno():
    d = dati_generali(scatola())
    assert d.superficie_lorda == Decimal("32.18")  # 7,15 x 4,50
    assert d.volume_vpp == pytest.approx(Decimal("112.61"), abs=Decimal("0.6"))  # h media esterna 3,50
    assert d.snr == Decimal("23.50") and d.su == Decimal("0.00")
