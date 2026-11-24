"""Schizzo di rilievo inventato: pianta stampata + misure a penna, correzioni e scarabocchi.

Imita lo schizzo reale di un sopralluogo: dimensioni interne dei locali,
quote progressive delle aperture dal punto 0, altezze (H min / H max),
valori barrati e riscritti, una cifra pasticciata, un tramezzo cancellato
con una riga ondulata. La foto del foglio e' leggermente storta.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import LineString
from shapely.geometry.polygon import orient

from ..geometria import apertura_mondo, direzione, normale_sx, perimetro_esterno, poligono_locale, poligoni_muri
from ..modello import Edificio

FONT = Path(__file__).resolve().parents[2] / "assets" / "fonts" / "Caveat.ttf"
INCHIOSTRO = (28, 45, 150)
GRIGIO = (70, 70, 70)


def _f(x: float) -> str:
    return f"{x:.2f}"


class Foglio:
    def __init__(self, ed: Edificio, W=2400, H=1700, rng=None):
        self.W, self.H = W, H
        self.img = Image.new("RGB", (W, H), (246, 246, 243))
        self.d = ImageDraw.Draw(self.img)
        self.rng = rng or random.Random(0)
        minx, miny, maxx, maxy = poligoni_unione(ed).bounds
        s = min((W * 0.72) / (maxx - minx), (H * 0.72) / (maxy - miny))
        self.s = s
        self.ox = W / 2 - s * (minx + maxx) / 2
        self.oy = H / 2 + s * (miny + maxy) / 2

    def P(self, p):
        return (self.ox + self.s * p[0], self.oy - self.s * p[1])

    def linea(self, a, b, col=GRIGIO, w=2):
        self.d.line([self.P(a), self.P(b)], fill=col, width=w)

    def penna(self, pts, w=3):
        """Tratto a mano: leggero tremolio."""
        q = []
        for x, y in (self.P(p) for p in pts):
            q.append((x + self.rng.uniform(-1.2, 1.2), y + self.rng.uniform(-1.2, 1.2)))
        self.d.line(q, fill=INCHIOSTRO, width=w, joint="curve")

    def scrivi(self, txt, p, ang=0.0, size=44, pixel=False, barra=False):
        size = int(size * self.rng.uniform(0.9, 1.1))
        font = ImageFont.truetype(str(FONT), size)
        bb = font.getbbox(txt)
        tw, th = bb[2] + 8, bb[3] + 10
        lay = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        dl = ImageDraw.Draw(lay)
        dl.text((4, 2), txt, font=font, fill=INCHIOSTRO + (255,))
        if barra:
            dl.line([(2, th * 0.62), (tw - 2, th * 0.42)], fill=INCHIOSTRO + (255,), width=4)
            dl.line([(2, th * 0.45), (tw - 2, th * 0.65)], fill=INCHIOSTRO + (255,), width=3)
        lay = lay.rotate(ang + self.rng.uniform(-4, 4), expand=True, resample=Image.BICUBIC)
        x, y = p if pixel else self.P(p)
        self.img.paste(lay, (int(x - lay.width / 2), int(y - lay.height / 2)), lay)
        return lay.width, lay.height

    def ondulata(self, a, b, ampiezza=8, onde=6):
        A, B = np.array(self.P(a)), np.array(self.P(b))
        u = B - A
        L = np.linalg.norm(u)
        n = np.array([-u[1], u[0]]) / L
        pts = [tuple(A + u * t + n * ampiezza * math.sin(t * onde * 2 * math.pi)) for t in np.linspace(0, 1, 60)]
        self.d.line(pts, fill=INCHIOSTRO, width=3, joint="curve")


def poligoni_unione(ed):
    from shapely.ops import unary_union
    return unary_union(list(poligoni_muri(ed, con_aperture=False).values()))


def schizzo(ed: Edificio, out: str | Path, seed: int = 0) -> Path:
    rng = random.Random(seed)
    F = Foglio(ed, rng=rng)
    # --- pianta "stampata": contorni dei muri con le aperture
    for m, pol in poligoni_muri(ed, con_aperture=True).items():
        for g in getattr(pol, "geoms", [pol]):
            c = list(g.exterior.coords)
            for a, b in zip(c, c[1:]):
                F.linea(a, b)
    for ap in ed.aperture:
        m = ed.muro(ap.muro)
        a, b = (np.array(p) for p in apertura_mondo(ed, ap))
        n = normale_sx(m) * m.spessore.valore / 2
        if ap.tipo in ("finestra", "feritoia"):
            F.linea(a, b, w=1)
            F.linea(a + n, b + n, w=1)
            F.linea(a - n, b - n, w=1)
        else:  # porta: segno a croce come nelle stampe catastali
            mid = (a + b) / 2
            F.linea(mid - n * 1.6, mid + n * 1.6, w=1)
    # tramezzo stampato che non esiste piu' (cancellato a penna)
    loc0 = poligono_locale(ed, ed.locali[0])
    minx, miny, maxx, maxy = loc0.bounds
    xt = minx + (maxx - minx) * 0.35
    p0, p1 = (xt, maxy - (maxy - miny) * 0.45), (xt, maxy)
    F.linea((p0[0] - 0.05, p0[1]), (p1[0] - 0.05, p1[1]))
    F.linea((p0[0] + 0.05, p0[1]), (p1[0] + 0.05, p1[1]))
    F.ondulata((xt, p0[1]), (xt, p1[1]), ampiezza=10, onde=4)

    numeri = []  # (valore, posizione, angolo) per correzioni e cifra pasticciata

    # --- dimensioni interne dei locali
    for loc in ed.locali:
        pol = orient(poligono_locale(ed, loc), 1.0)
        mrr = pol.minimum_rotated_rectangle
        c = list(pol.exterior.coords)
        if pol.area / mrr.area > 0.985:
            lati = [(c[i], c[i + 1]) for i in range(len(c) - 1) if math.dist(c[i], c[i + 1]) > 0.5][:2]
        else:
            lati = [(a, b) for a, b in zip(c, c[1:]) if math.dist(a, b) > 0.5]
        cen = np.array(pol.centroid.coords[0])
        for a, b in lati:
            a, b = np.array(a), np.array(b)
            u = (b - a) / np.linalg.norm(b - a)
            n_in = np.array([-u[1], u[0]])
            off = 0.35 + rng.uniform(0, 0.25)
            pa, pb = a + n_in * off, b + n_in * off
            F.penna([pa, pb], w=2)
            for q, s in ((pa, 1), (pb, -1)):  # frecce
                F.penna([q + u * s * 0.15 + n_in * 0.06, q, q + u * s * 0.15 - n_in * 0.06], w=2)
            ang = math.degrees(math.atan2(u[1], u[0]))
            if ang > 90 or ang <= -90:
                ang += 180
            pos = (pa + pb) / 2 + n_in * 0.18
            val = math.dist(a, b)
            numeri.append([val, pos, ang])
        # altezze
        h = loc.h_min.valore
        if loc.h_max is not None and abs(loc.h_max.valore - h) > 0.01:
            F.scrivi(f"H min {_f(h)}", cen + np.array([0, 0.45]), size=42)
            F.scrivi(f"H max {_f(loc.h_max.valore)}", cen + np.array([0, -0.05]), size=42)
        else:
            F.scrivi(f"H = {_f(h)}", cen + np.array([0, 0.2]), size=42)
        F.scrivi(loc.nome, cen + np.array([0, -0.6]), size=46)

    # --- quote progressive delle aperture dal punto 0 (spigolo interno), lungo ogni muro
    perim = perimetro_esterno(ed)
    for m in ed.muri:
        aps = ed.aperture_di(m.id)
        if not aps:
            continue
        d, nl = direzione(m), normale_sx(m)
        o = np.array(m.asse[0]) + d * m.zero.valore
        mid = np.array(m.asse).mean(axis=0)
        # lato su cui scrivere: verso l'esterno se il muro e' sul perimetro, altrimenti verso un locale
        esterno = None
        for p0, p1, nn in perim:
            if LineString([p0, p1]).distance(LineString(m.asse)) < m.spessore.valore * 0.6 and \
                    abs(float(np.dot(nn, nl))) > 0.99:
                esterno = np.array(nn)
        lato = esterno if esterno is not None else nl
        off = m.spessore.valore / 2 + 0.35
        base = o + lato * off
        F.penna([base, base + d * (aps[-1].a.valore + 0.2)], w=2)
        F.scrivi("0", tuple(base + lato * 0.2 - d * 0.1), size=36)
        k = 0
        for ap in aps:
            for s in (ap.da.valore, ap.a.valore):
                q = base + d * s
                F.penna([q - lato * 0.08, q + lato * 0.08], w=2)
                ang = math.degrees(math.atan2(d[1], d[0]))
                if ang > 90 or ang <= -90:
                    ang += 180
                pos = q + lato * (0.26 if k % 2 == 0 else 0.55)  # sfalsati per non sovrapporsi
                numeri.append([s, pos, ang])
                k += 1
            # altezze di porte e finestre accanto all'apertura, dentro il locale
            cin = (np.array(apertura_mondo(ed, ap)[0]) + np.array(apertura_mondo(ed, ap)[1])) / 2 - lato * (
                m.spessore.valore / 2 + 0.45)
            if ap.tipo == "porta":
                F.scrivi(f"h {_f(ap.altezza.valore)}" + (" arco" if ap.forma == "arco" else ""), tuple(cin), size=34)
            else:
                F.scrivi(f"h {_f(ap.altezza.valore)} dav {_f(ap.davanzale.valore)}", tuple(cin), size=34)

    # --- scrittura dei numeri: due corretti (barrati e riscritti), uno pasticciato
    idx = list(range(len(numeri)))
    rng.shuffle(idx)
    corretti = set(idx[:2])
    pasticciato = idx[2] if len(idx) > 2 else None
    for i, (val, pos, ang) in enumerate(numeri):
        txt = _f(val)
        if i in corretti:
            sbagliato = _f(val + rng.choice([-0.2, 0.1, 0.3]))
            w, _ = F.scrivi(sbagliato, tuple(pos), ang, size=40, barra=True)
            dx = np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))]) * (w / F.s + 0.05)
            F.scrivi(txt, tuple(pos + dx), ang, size=40)
        else:
            F.scrivi(txt, tuple(pos), ang, size=40)
            if i == pasticciato:
                x, y = F.P(pos)
                F.d.line([(x - 6, y - 14), (x + 10, y + 12), (x + 2, y - 10)], fill=INCHIOSTRO, width=3)
    # scarabocchi
    for _ in range(3):
        x, y = rng.uniform(0.05, 0.95) * F.W, rng.uniform(0.05, 0.2) * F.H
        pts = [(x + 25 * math.sin(t * 1.7) + t * 6, y + 18 * math.cos(t * 2.3)) for t in np.linspace(0, 6, 40)]
        F.d.line(pts, fill=INCHIOSTRO, width=2)

    # --- "foto" del foglio: prospettiva leggera, luce non uniforme, sfondo scuro
    img = cv2.cvtColor(np.array(F.img), cv2.COLOR_RGB2BGR)
    Hs, Ws = img.shape[:2]
    m = 120
    out_img = np.full((Hs + 2 * m, Ws + 2 * m, 3), (40, 42, 45), np.uint8)
    src = np.float32([[0, 0], [Ws, 0], [Ws, Hs], [0, Hs]])
    j = lambda: rng.uniform(-0.025, 0.025) * Ws
    dst = np.float32([[m + j(), m + j()], [m + Ws + j(), m + j()], [m + Ws + j(), m + Hs + j()],
                      [m + j(), m + Hs + j()]])
    M = cv2.getPerspectiveTransform(src, dst)
    cv2.warpPerspective(img, M, (out_img.shape[1], out_img.shape[0]), dst=out_img, borderMode=cv2.BORDER_TRANSPARENT)
    yy, xx = np.mgrid[0:out_img.shape[0], 0:out_img.shape[1]]
    luce = 0.85 + 0.15 * (xx / out_img.shape[1])
    out_img = np.clip(out_img * luce[..., None], 0, 255).astype(np.uint8)
    out_img = cv2.GaussianBlur(out_img, (3, 3), 0.6)
    cv2.imwrite(str(out), out_img, [cv2.IMWRITE_JPEG_QUALITY, 88] if str(out).lower().endswith("jpg") else [])
    return Path(out)
