from pathlib import Path

import pytest
import yaml

from rilievo.banco.caso import genera_caso
from rilievo.banco.confronta import confronta
from rilievo.costruttore import costruisci
from rilievo.geometria import poligono_locale

ESEMPIO = Path(__file__).parents[1] / "esempi" / "rilievo_caso_2031.yaml"


def _dati(**agg):
    d = {"spessori": {"esterni": 0.40, "interni": 0.30},
         "locali": [{"nome": "A", "larghezza": 4.0, "profondita": 3.0, "h_min": 2.7},
                    {"nome": "B", "a_destra_di": "A", "larghezza": 3.0, "profondita": 3.0, "h_min": 2.7}],
         "aperture": [{"locale": "A", "lato": "sud", "dal": "ovest", "da": 1.0, "a": 2.0, "altezza": 2.1,
                       "tipo": "porta"},
                      {"locale": "B", "lato": "ovest", "dal": "sud", "da": 0.5, "a": 1.3, "altezza": 2.0,
                       "tipo": "porta"}]}
    d.update(agg)
    return d


def test_due_locali_affiancati():
    ed = costruisci(_dati())
    assert ed.valida() == []
    assert len(ed.muri) == 5  # 4 esterni + 1 interno
    aree = sorted(round(poligono_locale(ed, l).area, 3) for l in ed.locali)
    assert aree == [9.0, 12.0]
    interni = [m for m in ed.muri if abs(m.spessore.valore - 0.30) < 1e-6]
    assert len(interni) == 1 and interni[0].asse[0][0] == pytest.approx(4.15)


def test_aperture_su_muro_giusto():
    ed = costruisci(_dati())
    porta_b = next(a for a in ed.aperture if a.altezza.valore == 2.0)
    assert ed.muro(porta_b.muro).spessore.valore == pytest.approx(0.30)


def test_coperture_e_sezioni_automatiche():
    d = _dati(coperture=[{"locali": ["A", "B"], "tipo": "capanna", "colmo": "x", "h_imposta": 2.7,
                          "h_colmo": 3.5, "spessore": 0.3, "sporto": 0.2}])
    ed = costruisci(d)
    assert len(ed.falde) == 2 and len(ed.sezioni) == 2
    from rilievo.geometria import quota_intradosso
    assert quota_intradosso(ed, 2.0, 0.0) == pytest.approx(2.7, abs=1e-6)  # faccia interna sud
    assert quota_intradosso(ed, 2.0, 1.5) == pytest.approx(3.5, abs=1e-6)  # colmo a meta'


def test_caso_2031_dal_rilievo_per_locali():
    ed = costruisci(yaml.safe_load(ESEMPIO.read_text()))
    assert ed.valida() == []
    r = confronta(genera_caso(2031), ed)
    assert not r.mancanti and not r.in_piu, (r.mancanti, r.in_piu)
    assert r.errore_max_cm <= 2.0, r.markdown()


def test_errore_chiaro_locale_inesistente():
    with pytest.raises(ValueError, match="Cucinotto"):
        costruisci(_dati(aperture=[{"locale": "Cucinotto", "lato": "sud", "da": 1, "a": 2, "altezza": 2}]))


def test_spessori_diversi_per_lato():
    d = _dati()
    d["locali"][0]["spessori_lati"] = {"nord": 0.60, "sud": 0.49, "ovest": 0.35}
    ed = costruisci(d)
    assert ed.valida() == []
    sp = sorted(round(m.spessore.valore, 2) for m in ed.muri)
    assert 0.60 in sp and 0.49 in sp and 0.35 in sp
    from rilievo.genera.tabelle import sagoma
    minx, miny, maxx, maxy = sagoma(ed).bounds
    assert minx == pytest.approx(-0.35) and miny == pytest.approx(-0.49)


def test_copertura_che_si_appoggia_al_vicino():
    d = _dati(coperture=[
        {"locali": ["A"], "tipo": "una_falda", "bassa": "ovest", "h_alta": 3.5, "h_bassa": 2.2, "spessore": 0.3,
         "sporto": 0.2, "si_appoggia_a": ["B"]},
        {"locali": ["B"], "tipo": "capanna", "colmo": "x", "h_imposta": 2.7, "h_colmo": 3.5, "spessore": 0.3,
         "sporto": 0.2}])
    ed = costruisci(d)
    from shapely.geometry import Polygon
    falde_a = [f for f in ed.falde if f.id.startswith("T1")]
    # la falda di A si ferma alla faccia interna del muro verso B (x = 4,00): non copre il muro in comune
    assert max(max(x for x, _ in f.poligono) for f in falde_a) == pytest.approx(4.0, abs=1e-3)


def test_la_copertura_alta_non_sporge_sopra_quella_che_le_si_appoggia():
    """Dove un tetto si appoggia al muro del vicino, il vicino non deve sporgere sopra di lui (dalle foto: il
    manto prosegue senza gradino); i timpani in pietra non hanno sporto se sporto_timpani = 0."""
    d = _dati(coperture=[
        {"locali": ["A"], "tipo": "una_falda", "bassa": "ovest", "h_alta": 3.5, "h_bassa": 2.2, "spessore": 0.3,
         "sporto": 0.2, "si_appoggia_a": ["B"]},
        {"locali": ["B"], "tipo": "capanna", "colmo": "x", "h_imposta": 2.7, "h_colmo": 3.5, "spessore": 0.3,
         "sporto": 0.2, "sporto_timpani": 0.0}])
    ed = costruisci(d)
    falde_b = [f for f in ed.falde if f.id.startswith("T2")]
    xs = [x for f in falde_b for x, _ in f.poligono]
    ys = [y for f in falde_b for _, y in f.poligono]
    assert min(xs) >= 4.0 - 1e-3          # niente sporto sopra il locale A
    assert max(xs) == pytest.approx(7.70, abs=1e-3)  # timpano est a filo muro (7,30 + 0,40)
    assert min(ys) == pytest.approx(-0.60, abs=1e-3)  # la gronda invece sporge (0,40 + 0,20)


def test_testate_delle_falde_rivolte_verso_l_esterno():
    """Il bordo (testata) della falda deve essere visibile da fuori: se e' rivolto verso l'interno il
    prospetto mostra l'interno dell'edificio sotto la gronda."""
    from shapely.geometry import Point, Polygon
    from rilievo.modello3d import facce
    d = _dati(coperture=[{"locali": ["A", "B"], "tipo": "capanna", "colmo": "x", "h_imposta": 2.7,
                          "h_colmo": 3.5, "spessore": 0.3, "sporto": 0.2}])
    ed = costruisci(d)
    falde = {f.id: Polygon(f.poligono) for f in ed.falde}
    for f in facce(ed):
        if f.tipo == "bordo_falda":
            c = f.pts.mean(axis=0)
            assert not falde[f.rif_id].contains(Point(c[0] + 0.01 * f.normale[0], c[1] + 0.01 * f.normale[1]))


def test_contorno_senza_dentelli_negli_angoli():
    """I dentelli di pochi cm lasciati dall'unione dei muri spariscono; gli spigoli veri restano."""
    from rilievo.modello3d import _togli_dentelli
    anello = [(11.0, -0.49), (11.0, 3.81), (11.033, 3.81), (11.033, 3.816), (11.056, 3.818), (11.033, 4.063),
              (11.033, 4.31), (11.011, 4.31), (10.713, 7.548), (10.713, 7.62), (10.707, 7.62), (10.706, 7.627),
              (10.635, 7.62), (6.03, 7.62), (6.03, 4.31), (-0.35, 4.31), (-0.35, -0.49), (11.0, -0.49)]
    pulito = _togli_dentelli(anello)
    assert len(pulito) == 7
    assert (6.03, 4.31) in pulito and (-0.35, 4.31) in pulito  # il risalto vero del Vano 3 resta


def test_apertura_a_un_centimetro_dallo_spigolo_arriva_allo_spigolo():
    """Un varco che finisce a 1 cm dall'angolo lascerebbe una colonnina di muro di 1 cm (pratica C002)."""
    d = _dati()
    d["aperture"] = [{"locale": "A", "lato": "sud", "dal": "ovest", "da": 2.0, "a": 3.99, "altezza": 2.1,
                      "tipo": "varco"}]
    ed = costruisci(d)
    ap = ed.aperture[0]
    assert ap.larghezza == pytest.approx(2.0, abs=1e-3)
