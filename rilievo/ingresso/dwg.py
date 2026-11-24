"""Lettura di una pianta DWG/DXF esistente e ricostruzione di una bozza del modello.

Riconosce i muri come coppie di linee parallele a distanza 8-90 cm, le
aperture come interruzioni lungo lo stesso muro, i locali dai testi.
Le altezze non sono nel disegno: entrano come ipotesi da verificare.
"""
from __future__ import annotations

import math
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import ezdxf
import numpy as np
from shapely.geometry import Point

SP_MIN, SP_MAX = 0.08, 0.90
GAP_MIN, GAP_MAX = 0.35, 3.2
TOL_ANG = math.radians(0.5)
STRATI_MURO = re.compile(r"mur|wall|paret|tramez", re.I)
STRATI_ESCLUSI = re.compile(r"quot|dim|testi|text|retin|hatch|arred|cartigl|cornice|sez_|linee_sez|nord|copert|tetto|roof|falda", re.I)


@dataclass(eq=False)
class Seg:
    a: np.ndarray
    b: np.ndarray
    layer: str
    tratteggiata: bool = False

    @property
    def u(self):
        d = self.b - self.a
        return d / np.linalg.norm(d)

    @property
    def L(self):
        return float(np.linalg.norm(self.b - self.a))


@dataclass
class MuroDWG:
    p0: np.ndarray
    p1: np.ndarray
    spessore: float
    layer: str


@dataclass
class AperturaDWG:
    muro: int
    pa: np.ndarray  # estremi in pianta (metri)
    pb: np.ndarray
    tipo: str


@dataclass
class AnalisiDWG:
    muri: list[MuroDWG] = field(default_factory=list)
    aperture: list[AperturaDWG] = field(default_factory=list)
    testi: list[tuple[str, tuple[float, float], float]] = field(default_factory=list)
    fattore: float = 1.0
    avvisi: list[str] = field(default_factory=list)


def leggi_dwg(path: str | Path):
    """Apre un DWG (convertendolo in DXF con ODA) o un DXF."""
    path = Path(path)
    if path.suffix.lower() == ".dxf":
        return ezdxf.readfile(path)
    from ..esporta import dwg_a_dxf
    with tempfile.TemporaryDirectory() as t:
        dxf = dwg_a_dxf(path, Path(t) / (path.stem + ".dxf"))
        return ezdxf.readfile(dxf)


def _entita(msp):
    for e in msp:
        if e.dxftype() == "INSERT":
            try:
                yield from _entita(list(e.virtual_entities()))
            except Exception:
                continue
        else:
            yield e


def _tratteggiata(e, doc) -> bool:
    lt = e.dxf.get("linetype", "BYLAYER")
    if lt.upper() == "BYLAYER" and doc is not None and e.dxf.layer in doc.layers:
        lt = doc.layers.get(e.dxf.layer).dxf.linetype
    return lt.upper() not in ("CONTINUOUS", "BYBLOCK", "BYLAYER")


def _raccogli(doc):
    segs, archi, testi = [], [], []
    for e in _entita(doc.modelspace()):
        t = e.dxftype()
        lay = e.dxf.get("layer", "0")
        if t == "LINE":
            segs.append(Seg(np.array((e.dxf.start.x, e.dxf.start.y)),
                            np.array((e.dxf.end.x, e.dxf.end.y)), lay, _tratteggiata(e, doc)))
        elif t in ("LWPOLYLINE", "POLYLINE"):
            pts = [(p[0], p[1]) for p in (e.get_points("xy") if t == "LWPOLYLINE" else
                                          [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices])]
            chiusa = e.closed if t == "LWPOLYLINE" else e.is_closed
            if chiusa and pts:
                pts = pts + [pts[0]]
            for p, q in zip(pts, pts[1:]):
                segs.append(Seg(np.array(p, float), np.array(q, float), lay, _tratteggiata(e, doc)))
        elif t == "ARC":
            archi.append((np.array((e.dxf.center.x, e.dxf.center.y)), e.dxf.radius, lay))
        elif t == "TEXT":
            testi.append((e.dxf.text, (e.dxf.insert.x, e.dxf.insert.y), e.dxf.height, lay, e))
        elif t == "MTEXT":
            testi.append((e.plain_text(), (e.dxf.insert.x, e.dxf.insert.y), e.dxf.char_height, lay, e))
    segs = [s for s in segs if s.L > 1e-6]
    return segs, archi, testi


def _coppie(segs: list[Seg], fattore: float, sp_min=SP_MIN, sp_max=SP_MAX, rapporto=1.2, ov_min=0.2):
    """Coppie di segmenti paralleli a distanza da muro. Ritorna (i, j, distanza, s0, s1, u, n, c)."""
    out = []
    ang = [math.atan2(s.u[1], s.u[0]) % math.pi for s in segs]
    ordine = sorted(range(len(segs)), key=lambda i: ang[i])
    for ii, i in enumerate(ordine):
        si = segs[i]
        for j in ordine[ii + 1:]:
            da = abs(ang[j] - ang[i])
            if da > TOL_ANG and math.pi - da > TOL_ANG:
                if ang[j] - ang[i] > TOL_ANG:
                    break
                continue
            sj = segs[j]
            u = si.u
            n = np.array([-u[1], u[0]])
            dist = float(np.dot(sj.a - si.a, n)) * fattore
            if not (sp_min <= abs(dist) <= sp_max):
                continue
            pi = sorted([0.0, float(np.dot(si.b - si.a, u))])
            pj = sorted([float(np.dot(sj.a - si.a, u)), float(np.dot(sj.b - si.a, u))])
            s0, s1 = max(pi[0], pj[0]), min(pi[1], pj[1])
            ov = (s1 - s0) * fattore
            if ov < ov_min or ov < rapporto * abs(dist):
                continue
            out.append((i, j, abs(dist), s0, s1, u, n * np.sign(dist), si.a))
    return out


def analizza_pianta(doc) -> AnalisiDWG:
    segs, archi, testi = _raccogli(doc)
    an = AnalisiDWG()
    strati_muro = {s.layer for s in segs if STRATI_MURO.search(s.layer)}
    segs_muro = [s for s in segs if s.layer in strati_muro] if strati_muro else \
        [s for s in segs if not STRATI_ESCLUSI.search(s.layer)]
    altri = [s for s in segs if s not in segs_muro and not STRATI_ESCLUSI.search(s.layer)]
    if not strati_muro:
        an.avvisi.append("Nessun layer con nome da muro (MURI, WALL...): analizzate tutte le linee.")

    # --- unita' di misura: il fattore che produce piu' coppie da muro
    migliore = (0, 1.0)
    for f in (1.0, 0.01, 0.001):
        n = len(_coppie(segs_muro, f))
        if n > migliore[0]:
            migliore = (n, f)
    f = migliore[1]
    an.fattore = f
    if migliore[0] == 0:
        an.avvisi.append("Nessun muro riconosciuto: il disegno potrebbe non essere una pianta.")
        return an

    # --- candidati muro (e finestre: coppie con linee interne parallele)
    cand = []
    for i, j, dist, s0, s1, u, n, c in _coppie(segs_muro, f):
        a = (c + u * s0) * f + n * dist / 2
        b = (c + u * s1) * f + n * dist / 2
        cand.append((a, b, dist, segs_muro[i].layer))
    # secondo passaggio: pilastrini corti tra le aperture, solo sulle linee dei muri gia' trovati
    linee = [(a, b, d) for a, b, d, _ in cand]
    for i, j, dist, s0, s1, u, n, c in _coppie(segs_muro, f, rapporto=0.0, ov_min=0.15):
        a = (c + u * s0) * f + n * dist / 2
        b = (c + u * s1) * f + n * dist / 2
        if any(_sulla_stessa_retta((a, b, dist, ""), (la, lb, ld, "")) for la, lb, ld in linee):
            cand.append((a, b, dist, segs_muro[i].layer))
    cand = _togli_doppioni(cand)
    # se un candidato ha linee interne parallele (vetro) e' una finestra disegnata nel vano
    muri, finestre = [], []
    tutte = segs_muro + altri
    for a, b, dist, lay in cand:
        if _ha_linee_interne(a, b, dist, tutte, f):
            finestre.append((a, b, dist))
        else:
            muri.append([a, b, dist, lay])

    # --- unione dei tratti collineari: le interruzioni sono aperture
    muri_uniti, aperture = _unisci(muri, finestre, archi, altri, f, segs_muro)
    _aggancia_angoli(muri_uniti)
    validi = {}
    for k, (a, b, sp, lay) in enumerate(muri_uniti):
        if float(np.linalg.norm(b - a)) < 0.05:
            continue
        validi[k] = len(an.muri)
        an.muri.append(MuroDWG(a, b, sp, lay))
    aperture = [(validi[k], pa, pb, t) for k, pa, pb, t in aperture if k in validi]
    for k, pa, pb, tipo in aperture:
        an.aperture.append(AperturaDWG(k, pa, pb, tipo))
    for txt, pos, h, lay, _ in testi:
        an.testi.append((txt.strip(), (pos[0] * f, pos[1] * f), h * f))
    return an


def _togli_doppioni(cand):
    out = []
    for a, b, d, lay in cand:
        dup = False
        for a2, b2, d2, _ in out:
            if abs(d - d2) < 0.005 and (np.linalg.norm(a - a2) + np.linalg.norm(b - b2) < 0.01 or
                                        np.linalg.norm(a - b2) + np.linalg.norm(b - a2) < 0.01):
                dup = True
                break
        if not dup:
            out.append((a, b, d, lay))
    return out


def _ha_linee_interne(a, b, sp, segs, f) -> bool:
    u = (b - a) / np.linalg.norm(b - a)
    n = np.array([-u[1], u[0]])
    L = float(np.linalg.norm(b - a))
    for s in segs:
        if s.tratteggiata or abs(abs(float(np.dot(s.u, u))) - 1) > 1e-3:
            continue
        pa, pb = s.a * f, s.b * f
        off = float(np.dot(pa - a, n))
        if abs(off) > sp / 2 - 0.01:
            continue
        t0, t1 = sorted([float(np.dot(pa - a, u)), float(np.dot(pb - a, u))])
        if min(t1, L) - max(t0, 0) > 0.5 * L:
            return True
    return False


def _sulla_stessa_retta(m1, m2, tol=0.01):
    a, b, sp, _ = m1
    c, d, sp2, _ = m2
    u = (b - a) / np.linalg.norm(b - a)
    v = (d - c) / np.linalg.norm(d - c)
    if abs(abs(float(np.dot(u, v))) - 1) > 1e-4 or abs(sp - sp2) > tol:
        return False
    n = np.array([-u[1], u[0]])
    return abs(float(np.dot(c - a, n))) < tol


def _unisci(muri, finestre, archi, altri, f, segs_muro=()):
    gruppi: list[list] = []
    for m in muri:
        for g in gruppi:
            if _sulla_stessa_retta(g[0], m):
                g.append(m)
                break
        else:
            gruppi.append([m])
    uniti, aperture = [], []
    for g in gruppi:
        a0, b0, sp, lay = g[0]
        u = (b0 - a0) / np.linalg.norm(b0 - a0)
        if abs(u[0]) < 1e-9 and u[1] < 0 or u[0] < -1e-9:
            u = -u
        tratti = sorted(([float(np.dot(m[0] - a0, u)), float(np.dot(m[1] - a0, u))] for m in g), key=min)
        tratti = [sorted(t) for t in tratti]
        catene = [[tratti[0]]]
        for t in tratti[1:]:
            ultimo = catene[-1][-1]
            gap = t[0] - ultimo[1]
            if gap <= GAP_MAX:
                catene[-1].append(t)
            else:
                catene.append([t])
        for cat in catene:
            s_ini, s_fin = cat[0][0], max(t[1] for t in cat)
            p0, p1 = a0 + u * s_ini, a0 + u * s_fin
            k = len(uniti)
            uniti.append([p0, p1, sp, lay])
            for t1, t2 in zip(cat, cat[1:]):
                g0, g1 = t1[1], t2[0]
                if g1 - g0 < 0.05:
                    continue
                pa, pb = a0 + u * g0, a0 + u * g1
                if _faccia_continua(pa, pb, sp, segs_muro, f) or not _ha_stipiti(pa, pb, sp, segs_muro, f):
                    continue  # innesto di muri perpendicolari, non un'apertura
                tipo = _tipo_apertura(pa, pb, sp, finestre, archi, altri, f)
                aperture.append([k, pa, pb, tipo])
    return uniti, aperture


def _ha_stipiti(pa, pb, sp, segs, f) -> bool:
    """Un vano vero e' chiuso ai due lati da stipiti: segmenti trasversali che uniscono le due facce."""
    w = float(np.linalg.norm(pb - pa))
    u = (pb - pa) / w
    n = np.array([-u[1], u[0]])
    trovati = [False, False]
    for s in segs:
        if abs(float(np.dot(s.u, u))) > 1e-3:
            continue
        a, b = s.a * f, s.b * f
        t = float(np.dot(a - pa, u))
        r0, r1 = sorted([float(np.dot(a - pa, n)), float(np.dot(b - pa, n))])
        copre = min(r1, sp / 2) - max(r0, -sp / 2)
        if copre < 0.8 * sp or r0 < -sp / 2 - 0.02 or r1 > sp / 2 + 0.02:
            continue
        for k, t_fine in enumerate((0.0, w)):
            if abs(t - t_fine) < 0.02:
                trovati[k] = True
    return all(trovati)


def _faccia_continua(pa, pb, sp, segs, f) -> bool:
    """Vero se almeno una faccia del muro prosegue senza interruzione sopra il vano pa-pb."""
    w = float(np.linalg.norm(pb - pa))
    u = (pb - pa) / w
    n = np.array([-u[1], u[0]])
    for lato in (-1, 1):
        coperto = 0.0
        for s in segs:
            if abs(abs(float(np.dot(s.u, u))) - 1) > 1e-3:
                continue
            a, b = s.a * f, s.b * f
            if abs(float(np.dot(a - pa, n)) - lato * sp / 2) > 0.01:
                continue
            t0, t1 = sorted([float(np.dot(a - pa, u)), float(np.dot(b - pa, u))])
            coperto += max(0.0, min(t1, w) - max(t0, 0.0))
        if coperto > 0.8 * w:
            return True
    return False


def _tipo_apertura(pa, pb, sp, finestre, archi, altri, f) -> str:
    mid = (pa + pb) / 2
    w = float(np.linalg.norm(pb - pa))
    for a, b, d in finestre:
        if np.linalg.norm((a + b) / 2 - mid) < 0.05:
            return "finestra"
    # linee nel vano, parallele al muro e interne allo spessore: continue = finestra,
    # tratteggiate = finestra alta (sopra il piano di taglio della pianta)
    u = (pb - pa) / max(w, 1e-9)
    n = np.array([-u[1], u[0]])
    nel_vano = []
    for s in altri:
        if abs(abs(float(np.dot(s.u, u))) - 1) > 1e-3:
            continue
        m = (s.a + s.b) / 2 * f
        t = float(np.dot(m - pa, u))
        if 0.02 < t < w - 0.02 and abs(float(np.dot(m - pa, n))) < sp / 2 - 0.03:
            nel_vano.append(s)
    if nel_vano:
        return "finestra_alta" if all(s.tratteggiata for s in nel_vano) else "finestra"
    # arco di apertura con il centro su uno stipite: anta singola (raggio = luce) o doppia (meta')
    for c, r, _ in archi:
        rr = r * f
        cern = min(np.linalg.norm(c * f - pa), np.linalg.norm(c * f - pb))
        if cern < sp / 2 + 0.05 and (abs(rr - w) < 0.15 * w + 0.05 or abs(rr - w / 2) < 0.1 * w + 0.03):
            return "porta"
    return "varco"


def _aggancia_angoli(muri):
    """Porta le estremita' degli assi sull'intersezione con l'asse del muro che incontrano."""
    for i, m in enumerate(muri):
        for k in (0, 1):
            e = m[k]
            migliore = None
            for j, w in enumerate(muri):
                if i == j:
                    continue
                a, b, spw = w[0], w[1], w[2]
                u = (m[1] - m[0]) / np.linalg.norm(m[1] - m[0])
                v = (b - a) / np.linalg.norm(b - a)
                den = u[0] * v[1] - u[1] * v[0]
                if abs(den) < 1e-6:
                    continue
                # intersezione delle rette degli assi
                t = ((a[0] - m[0][0]) * v[1] - (a[1] - m[0][1]) * v[0]) / den
                X = m[0] + u * t
                s = float(np.dot(X - a, v))
                if s < -spw - m[2] or s > np.linalg.norm(b - a) + spw + m[2]:
                    continue
                d = float(np.linalg.norm(X - e))
                if d <= spw / 2 + m[2] / 2 + 0.03 and (migliore is None or d < migliore[0]):
                    migliore = (d, X, j, s)
            if migliore is not None:
                d, X, j, s = migliore
                m[k] = X
                w = muri[j]
                vv = (w[1] - w[0]) / np.linalg.norm(w[1] - w[0])
                L = float(np.linalg.norm(w[1] - w[0]))
                if s < 0:  # allunga anche l'altro muro fino all'incrocio
                    w[0] = w[0] + vv * s
                elif s > L:
                    w[1] = w[0] + vv * s


def bozza_modello(an: AnalisiDWG):
    """Edificio con muri e aperture dal DWG; altezze ipotizzate (da verificare)."""
    from ..geometria import celle
    from ..modello import Apertura, Edificio, Locale, Muro, V
    ed = Edificio()
    for k, m in enumerate(an.muri):
        ed.muri.append(Muro(id=f"M{k + 1}", asse=[tuple(map(float, m.p0)), tuple(map(float, m.p1))],
                            spessore=V(valore=round(m.spessore, 3), fonte="dwg", rif=f"layer {m.layer}")))
    for n, ap in enumerate(an.aperture, start=1):
        m = an.muri[ap.muro]
        u = (m.p1 - m.p0) / np.linalg.norm(m.p1 - m.p0)
        s0 = float(np.dot(ap.pa - m.p0, u))
        s1 = float(np.dot(ap.pb - m.p0, u))
        s0, s1 = sorted((s0, s1))
        if ap.tipo == "porta" or ap.tipo == "varco":
            alt, dav = V(valore=2.10, fonte="ipotesi", nota="altezza tipica porta"), V(valore=0.0)
        elif ap.tipo == "finestra_alta":
            alt = V(valore=0.40, fonte="ipotesi", nota="feritoia alta, da verificare")
            dav = V(valore=1.80, fonte="ipotesi", nota="feritoia alta, da verificare")
        else:
            alt = V(valore=1.20, fonte="ipotesi", nota="altezza tipica finestra")
            dav = V(valore=0.90, fonte="ipotesi", nota="davanzale tipico")
        ed.aperture.append(Apertura(id=f"A{n}", muro=f"M{ap.muro + 1}", da=V(valore=round(s0, 3), fonte="dwg"),
                                    a=V(valore=round(s1, 3), fonte="dwg"), altezza=alt, davanzale=dav,
                                    tipo="finestra" if ap.tipo == "finestra_alta" else ap.tipo))
    # locali: un testo "parola" dentro ogni spazio chiuso
    try:
        spazi = celle(ed)
    except Exception:
        spazi = []
    usati = set()
    for txt, pos, h in an.testi:
        if (not re.search(r"[A-Za-z]{3,}", txt) or re.match(r"^(S|h|q)\b", txt) or "scala" in txt.lower()
                or re.search(r"\d+\s*x\s*\d+", txt)):  # sigle delle aperture (es. "F1 80x120")
            continue
        for i, c in enumerate(spazi):
            if i not in usati and c.contains(Point(pos)):
                usati.add(i)
                ed.locali.append(Locale(id=f"L{len(ed.locali) + 1}", nome=txt.split("\n")[0].strip(),
                                        punto=tuple(pos), h_min=V(valore=2.70, fonte="ipotesi",
                                                                  nota="altezza non presente nel DWG")))
                break
    return ed
