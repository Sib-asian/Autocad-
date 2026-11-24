"""Foto sintetiche in prospettiva di una facciata, con texture e distorsione dell'obiettivo.

Servono a provare raddrizzamento e misure da foto quando si conosce la verita'.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np

from ..modello import Edificio
from ..modello3d import Faccia, facce

SU = np.array([0.0, 0.0, 1.0])


class Camera:
    def __init__(self, C, target, W, H, hfov_gradi):
        self.C = np.array(C, float)
        f = np.array(target, float) - self.C
        self.f = f / np.linalg.norm(f)
        r = np.cross(self.f, SU)
        self.r = r / np.linalg.norm(r)
        self.u = np.cross(self.r, self.f)
        self.W, self.H = W, H
        self.fx = (W / 2) / math.tan(math.radians(hfov_gradi) / 2)
        self.cx, self.cy = W / 2, H / 2

    @property
    def K(self):
        return np.array([[self.fx, 0, self.cx], [0, self.fx, self.cy], [0, 0, 1.0]])

    def cam(self, P):
        d = np.atleast_2d(P) - self.C
        return np.column_stack([d @ self.r, d @ self.u, d @ self.f])

    def pixel(self, P):
        c = self.cam(P)
        return np.column_stack([self.cx + self.fx * c[:, 0] / c[:, 2], self.cy - self.fx * c[:, 1] / c[:, 2]])


def distorci_punti(px, cam: Camera, k1):
    px = np.atleast_2d(px)
    x = (px[:, 0] - cam.cx) / cam.fx
    y = (px[:, 1] - cam.cy) / cam.fx
    r2 = x * x + y * y
    s = 1 + k1 * r2
    return np.column_stack([cam.cx + cam.fx * x * s, cam.cy + cam.fx * y * s])


def _clip_vicino(pts_cam, z0=0.1):
    out = []
    n = len(pts_cam)
    for i in range(n):
        a, b = pts_cam[i], pts_cam[(i + 1) % n]
        da, db = a[2] - z0, b[2] - z0
        if da >= 0:
            out.append(a)
        if (da >= 0) != (db >= 0):
            out.append(a + (b - a) * (da / (da - db)))
    return np.array(out)


def _texture(tipo, W, H, rng):
    rumore = rng.normal(0, 1, (H // 4 + 1, W // 4 + 1)).astype(np.float32)
    rumore = cv2.resize(cv2.GaussianBlur(rumore, (0, 0), 2), (W, H))
    fine = rng.normal(0, 1, (H, W)).astype(np.float32)
    if tipo == "pietra":
        base = np.array([95, 98, 102], np.float32)
        macchie = cv2.resize(rng.normal(0, 1, (H // 25 + 1, W // 25 + 1)).astype(np.float32), (W, H),
                             interpolation=cv2.INTER_NEAREST)
        img = base + 22 * macchie[..., None] + 8 * rumore[..., None] + 6 * fine[..., None]
    elif tipo == "blocchi":
        base = np.array([128, 130, 128], np.float32)
        img = base + 10 * rumore[..., None] + 6 * fine[..., None]
        img[::38, :] *= 0.75
        for y0 in range(0, H, 38):
            off = 0 if (y0 // 38) % 2 else 40
            img[y0:y0 + 38, off::80] *= 0.75
    elif tipo == "intonaco":
        base = np.array([150, 152, 150], np.float32)
        img = base + 14 * rumore[..., None] + 7 * fine[..., None]
    elif tipo == "legno":
        base = np.array([55, 80, 110], np.float32)  # BGR marrone
        righe = np.sin(np.arange(W) / 3.0)[None, :] * 10
        img = base + righe[..., None] + 6 * fine[..., None]
    elif tipo == "coppi":
        base = np.array([60, 95, 160], np.float32)
        righe = (np.abs(np.sin(np.arange(W) / 7.0))[None, :] * 35)
        img = base + righe[..., None] + 10 * rumore[..., None]
    else:  # interno scuro
        img = np.full((H, W, 3), 30, np.float32) + 5 * fine[..., None]
    return np.clip(img, 0, 255).astype(np.uint8)


def _tipo_texture(f: Faccia) -> str:
    m = f.materiale.lower()
    if f.tipo in ("falda", "bordo_falda"):
        return "coppi"
    if f.tipo == "infisso":
        return "legno"
    if f.tipo == "intradosso_falda":
        return "interno"
    if "blocc" in m:
        return "blocchi"
    if "pietra" in m:
        return "pietra"
    return "intonaco"


def foto_facciata(ed: Edificio, vista, out: str | Path, k1: float = -0.12, seed: int = 0, W: int = 1600,
                  H: int = 1200, hfov: float = 70.0, yaw: float = 0.0, rumore: bool = True) -> dict:
    rng = np.random.default_rng(seed)
    tutte = facce(ed)
    n = np.array([vista.normale[0], vista.normale[1], 0.0])
    fronte = [f for f in tutte if f.tipo == "parete_est" and float(f.normale @ n) > 0.95]
    principale = max(fronte, key=lambda f: np.ptp(f.pts[:, :2] @ np.array([n[1], -n[0]])))
    P = principale.pts
    centro = P.mean(axis=0)
    larg = float(np.linalg.norm(P[1, :2] - P[0, :2]))
    alt = float(P[:, 2].max())
    dist = max(3.0, (larg / 2) / math.tan(math.radians(hfov) / 2 * 0.8))
    a = math.radians(yaw)
    dirx = np.array([math.cos(a) * n[0] - math.sin(a) * n[1], math.sin(a) * n[0] + math.cos(a) * n[1], 0.0])
    C = np.array([centro[0], centro[1], 1.6]) + dirx * dist
    target = np.array([centro[0], centro[1], alt * 0.45])
    cam = Camera(C, target, W, H, hfov)

    img = np.zeros((H, W, 3), np.uint8)
    # cielo e terreno
    for y in range(H):
        t = y / H
        img[y] = (235 - 60 * t, 200 - 40 * t, 150 - 40 * t)
    terra = np.array([[C[0] + dx, C[1] + dy, ed.quota_terreno.valore] for dx, dy in
                      ((-60, -60), (60, -60), (60, 60), (-60, 60))])
    _riempi(img, cam, terra, [], np.full((H, W, 3), (60, 110, 85), np.uint8))
    textures = {}
    vis = []
    for f in tutte:
        if float(f.normale @ (C - f.pts[0])) <= 0:
            continue
        vis.append((float(np.linalg.norm(f.pts.mean(axis=0) - C)), f))
    luce = np.array([0.4, -0.6, 0.7])
    luce /= np.linalg.norm(luce)
    for _, f in sorted(vis, key=lambda t: -t[0]):
        tipo = _tipo_texture(f)
        if tipo not in textures:
            textures[tipo] = _texture(tipo, W, H, rng)
        k = 0.65 + 0.35 * max(0.0, float(f.normale @ luce))
        _riempi(img, cam, f.pts, f.fori, (textures[tipo] * k).astype(np.uint8))

    # distorsione dell'obiettivo
    if k1:
        gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
        pts = np.stack([gx.ravel(), gy.ravel()], axis=1).reshape(-1, 1, 2)
        und = cv2.undistortPoints(pts, cam.K, np.array([k1, 0, 0, 0], float), P=cam.K).reshape(H, W, 2)
        img = cv2.remap(img, und[..., 0], und[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    if rumore:
        img = np.clip(img.astype(np.float32) + rng.normal(0, 4, img.shape), 0, 255).astype(np.uint8)
        yy, xx = np.mgrid[0:H, 0:W]
        vign = 1 - 0.25 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        img = np.clip(img * vign[..., None], 0, 255).astype(np.uint8)
    cv2.imwrite(str(out), img, [cv2.IMWRITE_JPEG_QUALITY, 90])

    def px(P3):
        return distorci_punti(cam.pixel(np.atleast_2d(P3)), cam, k1).tolist()

    # angoli della facciata principale: base e sommita' alle due estremita'
    base = P[:2]
    top_a = P[np.argmin(np.linalg.norm(P[2:, :2] - P[0, :2], axis=1) + 1e3 * (P[2:, 2] < 0.01)) + 2]
    top_b = P[np.argmin(np.linalg.norm(P[2:, :2] - P[1, :2], axis=1) + 1e3 * (P[2:, 2] < 0.01)) + 2]
    angoli = [base[0], base[1], top_b, top_a]
    aperture = {}
    for fid, h in zip(principale.fori_id, principale.fori):
        xs = h[:, :2] @ (P[1, :2] - P[0, :2]) / larg
        zs = h[:, 2]
        i0, i1 = np.argmin(xs), np.argmax(xs)
        p0 = h[i0].copy()
        p1 = h[i1].copy()
        rett = [np.r_[p0[:2], zs.min()], np.r_[p1[:2], zs.min()], np.r_[p1[:2], zs.max()], np.r_[p0[:2], zs.max()]]
        aperture[fid] = px(np.array(rett))
    info = {
        "file": str(out), "dimensioni": [W, H], "K": cam.K.tolist(), "k1": k1,
        "angoli_facciata_px": px(np.array(angoli)),
        "angoli_facciata_m": [[0, float(base[0][2])], [larg, float(base[1][2])], [larg, float(top_b[2])],
                              [0, float(top_a[2])]],
        "facciata": principale.rif_id, "aperture_px": aperture, "camera": C.tolist(),
    }
    Path(str(out) + ".json").write_text(json.dumps(info, indent=1))
    return info


def _riempi(img, cam: Camera, pts3, fori, tex):
    H, W = img.shape[:2]
    mask = np.zeros((H, W), np.uint8)

    def poly(p3):
        c = _clip_vicino(cam.cam(p3))
        if len(c) < 3:
            return None
        uv = np.column_stack([cam.cx + cam.fx * c[:, 0] / c[:, 2], cam.cy - cam.fx * c[:, 1] / c[:, 2]])
        uv = np.clip(uv, -4 * W, 5 * W)
        return np.round(uv * 4).astype(np.int32)

    p = poly(pts3)
    if p is None:
        return
    cv2.fillPoly(mask, [p], 255, lineType=cv2.LINE_AA, shift=2)
    for h in fori:
        q = poly(h)
        if q is not None:
            cv2.fillPoly(mask, [q], 0, lineType=cv2.LINE_AA, shift=2)
    m = (mask.astype(np.float32) / 255)[..., None]
    img[:] = (img * (1 - m) + tex * m).astype(np.uint8)
