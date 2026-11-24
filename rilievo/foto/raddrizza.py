"""Foto di facciata: correzione dell'obiettivo, raddrizzamento e misure.

Il raddrizzamento vale per superfici piane (una facciata): servono 4 punti
della foto di cui si conoscono le coordinate reali (X lungo la facciata, Z in
altezza), ad esempio gli spigoli del muro (larghezza dalla pianta, altezza
misurata) oppure gli spigoli di una porta misurata.
"""
from __future__ import annotations

import base64
import json
import math
from pathlib import Path

import cv2
import numpy as np


def stima_K(W: int, H: int, hfov: float = 70.0, focale_35mm: float | None = None) -> np.ndarray:
    """Matrice della camera. Con la focale equivalente 35 mm (dagli EXIF) e' piu' precisa."""
    if focale_35mm:
        hfov = math.degrees(2 * math.atan(36 / (2 * focale_35mm)))
    fx = (W / 2) / math.tan(math.radians(hfov) / 2)
    return np.array([[fx, 0, W / 2], [0, fx, H / 2], [0, 0, 1.0]])


def leggi_exif(path) -> dict:
    """Focale equivalente e modello dell'obiettivo, se presenti nella foto originale."""
    from PIL import Image
    try:
        ex = Image.open(path).getexif().get_ifd(0x8769)
    except Exception:
        return {}
    return {k: v for k, v in {"focale_35mm": ex.get(0xA405), "obiettivo": ex.get(0xA434),
                              "focale_mm": ex.get(0x920A)}.items() if v}


def correggi_punti(pts, K, k1: float) -> np.ndarray:
    pts = np.asarray(pts, np.float64).reshape(-1, 1, 2)
    if not k1:
        return pts.reshape(-1, 2)
    return cv2.undistortPoints(pts, np.asarray(K, float), np.array([k1, 0, 0, 0], float),
                               P=np.asarray(K, float)).reshape(-1, 2)


def correggi_immagine(img, K, k1: float):
    if not k1:
        return img
    H, W = img.shape[:2]
    m1, m2 = cv2.initUndistortRectifyMap(np.asarray(K, float), np.array([k1, 0, 0, 0], float), None,
                                         np.asarray(K, float), (W, H), cv2.CV_32FC1)
    return cv2.remap(img, m1, m2, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)


def _catene_dritte(gray, lung_min: int = 120, eps: float = 5.0) -> list[np.ndarray]:
    """Tratti di bordo quasi rettilinei (nella foto deformata) lunghi almeno `lung_min` pixel."""
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 1.2), 40, 120)
    cont, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    out = []
    for c in cont:
        c = c.reshape(-1, 2)
        if len(c) < lung_min:
            continue
        vert = cv2.approxPolyDP(c.reshape(-1, 1, 2), eps, False).reshape(-1, 2)
        idx = [int(np.argmin(np.abs(c - v).sum(axis=1))) for v in vert]
        for i0, i1 in zip(idx, idx[1:]):
            lo, hi = sorted((i0, i1))
            tratto = c[lo:hi + 1]
            if np.linalg.norm(tratto[-1] - tratto[0]) >= lung_min:
                out.append(tratto[::2].astype(np.float64))
    return out


def _residuo(tratti, K, k):
    tot = 0.0
    for t in tratti:
        q = correggi_punti(t, K, k)
        q = q - q.mean(axis=0)
        sv = np.linalg.svd(q, compute_uv=False)
        tot += (sv[1] / sv[0]) ** 2  # indipendente dalla scala
    return tot


def stima_k1(img, K, minimo: float = -0.40, massimo: float = 0.15) -> tuple[float, str]:
    """Stima la distorsione radiale (metodo del filo a piombo): il k1 che raddrizza i bordi lunghi."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    tratti = _catene_dritte(gray)
    # solo i tratti gia' quasi dritti: le andate-e-ritorno dei contorni e le curve vere vanno scartate
    tratti = [t for t in tratti if _residuo([t], K, 0.0) < 0.015 ** 2]
    if len(tratti) < 4:
        return 0.0, "nessuna (poche linee dritte nella foto)"
    cand = np.linspace(minimo, massimo, 56)
    res = [_residuo(tratti, K, k) for k in cand]
    k_best = cand[int(np.argmin(res))]
    fine = np.linspace(k_best - 0.01, k_best + 0.01, 21)
    k_best = fine[int(np.argmin([_residuo(tratti, K, k) for k in fine]))]
    return float(k_best), "linee"


def omografia_facciata(punti_px, punti_m) -> np.ndarray:
    """Omografia dai pixel (gia' corretti) alle coordinate di facciata (X, Z) in metri."""
    src = np.asarray(punti_px, np.float64).reshape(-1, 2)
    dst = np.asarray(punti_m, np.float64).reshape(-1, 2)
    if len(src) == 4:
        return cv2.getPerspectiveTransform(src.astype(np.float32), dst.astype(np.float32)).astype(np.float64)
    H, _ = cv2.findHomography(src, dst, 0)
    return H


def pixel_a_facciata(H, pts_px) -> np.ndarray:
    return cv2.perspectiveTransform(np.asarray(pts_px, np.float64).reshape(-1, 1, 2), H).reshape(-1, 2)


def misura(H, p1_px, p2_px) -> float:
    a, b = pixel_a_facciata(H, [p1_px, p2_px])
    return float(np.linalg.norm(a - b))


def raddrizza(img, punti_px, punti_m, K=None, k1: float = 0.0, px_per_m: int = 200, margine: int = 20):
    """Ritorna (immagine raddrizzata in scala, omografia pixel->metri, pixel per metro)."""
    H_img, W_img = img.shape[:2]
    if K is None:
        K = stima_K(W_img, H_img)
    corr = correggi_immagine(img, K, k1)
    src = correggi_punti(punti_px, K, k1)
    m = np.asarray(punti_m, float)
    xmin, xmax = m[:, 0].min(), m[:, 0].max()
    zmin, zmax = m[:, 1].min(), m[:, 1].max()
    dst = np.column_stack([(m[:, 0] - xmin) * px_per_m + margine, (zmax - m[:, 1]) * px_per_m + margine])
    Hp = cv2.getPerspectiveTransform(src.astype(np.float32), dst.astype(np.float32))
    W = int(round((xmax - xmin) * px_per_m + 2 * margine))
    Hh = int(round((zmax - zmin) * px_per_m + 2 * margine))
    out = cv2.warpPerspective(corr, Hp, (W, Hh), flags=cv2.INTER_LINEAR)
    return out, omografia_facciata(src, m), px_per_m


def pagina_punti(foto, out_html, max_lato: int = 1600) -> Path:
    """Pagina HTML autonoma: si clicca sui punti della foto e si copia il JSON con le coordinate."""
    img = cv2.imread(str(foto))
    H, W = img.shape[:2]
    s = min(1.0, max_lato / max(W, H))
    small = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else img
    ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 88])
    b64 = base64.b64encode(buf.tobytes()).decode()
    nome = json.dumps(Path(foto).name)
    html = f"""<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Punti sulla foto</title>
<style>body{{font-family:system-ui,sans-serif;margin:16px;background:#f6f6f4;color:#222}}
canvas{{max-width:100%;border:1px solid #999;cursor:crosshair}}pre{{background:#fff;padding:8px;border:1px solid #ccc}}
button{{padding:6px 12px;margin-right:8px}}</style></head><body>
<h1>Segna i punti sulla foto</h1>
<p>Clicca nell'ordine: 1 spigolo in basso a sinistra, 2 in basso a destra, 3 in alto a destra, 4 in alto a sinistra.
Poi gli altri punti da misurare (spigoli di finestre e porte). Il JSON va incollato nella chat.</p>
<button id="annulla">Annulla ultimo</button><button id="copia">Copia JSON</button>
<canvas id="c"></canvas><pre id="out">[]</pre>
<script>
const S={s};const img=new Image();const c=document.getElementById('c');const ctx=c.getContext('2d');const pts=[];
img.onload=()=>{{c.width=img.width;c.height=img.height;draw();}};
img.src="data:image/jpeg;base64,{b64}";
function draw(){{ctx.drawImage(img,0,0);ctx.font='bold 22px sans-serif';pts.forEach((p,i)=>{{
ctx.fillStyle='#e00';ctx.beginPath();ctx.arc(p[0]*S,p[1]*S,6,0,7);ctx.fill();ctx.fillText(i+1,p[0]*S+8,p[1]*S-8);}});
document.getElementById('out').textContent=JSON.stringify({{foto:{nome},punti_px:pts}});}}
c.addEventListener('click',e=>{{const r=c.getBoundingClientRect();const x=(e.clientX-r.left)*c.width/r.width/S;
const y=(e.clientY-r.top)*c.height/r.height/S;pts.push([+x.toFixed(1),+y.toFixed(1)]);draw();}});
document.getElementById('annulla').onclick=()=>{{pts.pop();draw();}};
document.getElementById('copia').onclick=()=>navigator.clipboard.writeText(document.getElementById('out').textContent);
</script></body></html>"""
    out = Path(out_html)
    out.write_text(html, encoding="utf-8")
    return out
