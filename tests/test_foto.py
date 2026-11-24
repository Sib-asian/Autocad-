import cv2
import numpy as np
import pytest

from rilievo.banco.caso import genera_caso
from rilievo.banco.foto_sintetiche import foto_facciata
from rilievo.foto.raddrizza import (correggi_punti, omografia_facciata, pagina_punti, raddrizza, stima_k1,
                                    stima_K)
from rilievo.genera.prospetti import lati_prospetto


@pytest.fixture(scope="module")
def foto(tmp_path_factory):
    ed = genera_caso(2)
    v = [x for x in lati_prospetto(ed) if x.nome == "Prospetto Sud"][0]
    p = tmp_path_factory.mktemp("f") / "sud.jpg"
    info = foto_facciata(ed, v, p, k1=-0.15, seed=2, yaw=12)
    return ed, info, p


def _larghezze(ed, info, K, k1):
    ang = correggi_punti(info["angoli_facciata_px"], K, k1)
    H = omografia_facciata(ang, info["angoli_facciata_m"])
    err = []
    for aid, pts in info["aperture_px"].items():
        q = correggi_punti(pts, K, k1)
        m = cv2.perspectiveTransform(np.array(q, np.float64).reshape(-1, 1, 2), H).reshape(-1, 2)
        w = abs(m[1, 0] - m[0, 0])
        h = abs(m[2, 1] - m[1, 1])
        ap = next(a for a in ed.aperture if a.id == aid)
        err += [abs(w - ap.larghezza), abs(h - ap.altezza.valore)]
    return max(err)


def test_misure_da_foto_con_k1_noto(foto):
    ed, info, _ = foto
    assert _larghezze(ed, info, np.array(info["K"]), info["k1"]) < 0.02


def test_stima_k1_senza_exif_migliora(foto):
    ed, info, p = foto
    img = cv2.imread(str(p))
    K = stima_K(img.shape[1], img.shape[0], hfov=70)
    k1, metodo = stima_k1(img, K)
    assert metodo == "linee"
    assert k1 == pytest.approx(-0.15, abs=0.05)
    senza = _larghezze(ed, info, K, 0.0)
    con = _larghezze(ed, info, K, k1)
    assert con < senza
    assert con < 0.04


def test_raddrizza_immagine(foto):
    ed, info, p = foto
    img = cv2.imread(str(p))
    K = np.array(info["K"])
    out, H, ppm = raddrizza(img, info["angoli_facciata_px"], info["angoli_facciata_m"], K=K, k1=info["k1"],
                            px_per_m=100)
    larg = max(x for x, _ in info["angoli_facciata_m"])
    assert out.shape[1] == pytest.approx(larg * 100 + 2 * 20, abs=3)


def test_pagina_punti(foto, tmp_path):
    _, _, p = foto
    html = pagina_punti(p, tmp_path / "punti.html")
    testo = html.read_text()
    assert "<canvas" in testo and "data:image/jpeg;base64," in testo


def test_scala_verticale_senza_altezze_note(foto):
    """Con la camera nota (EXIF) bastano larghezze note: l'altezza della porta si ricava dalla foto."""
    from rilievo.foto.raddrizza import scala_verticale
    ed, info, _ = foto
    K = np.array(info["K"])
    ang = info["angoli_facciata_px"]
    larg = max(x for x, _ in info["angoli_facciata_m"])
    pid, ppx = next((k, v) for k, v in info["aperture_px"].items() if k.startswith("P"))
    ap = next(a for a in ed.aperture if a.id == pid)
    # coordinate X note dalla pianta; Z relative: 0 alla base, 1 = sommita' della porta (incognita)
    P = np.array(ppx)
    from rilievo.foto.raddrizza import correggi_punti, omografia_facciata
    Hgt = omografia_facciata(correggi_punti(ang, K, info["k1"]), info["angoli_facciata_m"])
    xs = cv2.perspectiveTransform(correggi_punti(P, K, info["k1"]).reshape(-1, 1, 2), Hgt).reshape(-1, 2)[:, 0]
    punti_px = [ang[0], ang[1], ppx[2], ppx[3]]
    punti_rel = [(0, 0), (larg, 0), (xs[2], 1.0), (xs[3], 1.0)]
    s = scala_verticale(punti_px, punti_rel, K, info["k1"])
    assert s == pytest.approx(ap.altezza.valore, abs=0.03)


def test_incertezza_cresce_fuori_dal_riquadro(foto):
    from rilievo.foto.raddrizza import misura_con_incertezza
    ed, info, _ = foto
    K = np.array(info["K"])
    ang, m = info["angoli_facciata_px"], info["angoli_facciata_m"]
    centro = np.mean(np.array(ang), axis=0)
    fuori = np.array(ang[2]) + (np.array(ang[2]) - centro) * 0.8
    r = misura_con_incertezza(ang, m, [centro.tolist(), fuori.tolist()], K, info["k1"], sigma_px=1.5)
    assert r[0]["incertezza_m"] < r[1]["incertezza_m"]
    assert r[0]["incertezza_m"] < 0.05
