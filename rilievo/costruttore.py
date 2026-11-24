"""Costruttore del modello a partire dal rilievo descritto "come si misura".

Si descrivono i locali (dimensioni interne, uno accanto all'altro), gli spessori dei muri, le aperture con
le quote progressive dal punto 0 e le coperture con le altezze misurate all'interno (H min / H max).
Muri, assi, spigoli, falde e sezioni si calcolano da soli. Esempio: esempi/rilievo_caso_2031.yaml.
"""
from __future__ import annotations

from dataclasses import dataclass

import ezdxf
import numpy as np
from shapely.geometry import Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from .modello import Apertura, Edificio, Falda, LineaSezione, Locale, Muro, Pratica, V

CARDINALI = {"sud": (0, -1), "nord": (0, 1), "est": (1, 0), "ovest": (-1, 0)}


@dataclass
class _Locale:
    nome: str
    pol: Polygon  # contorno interno
    dati: dict
    t_est: float


def _vertici(x0, y0, d: dict) -> list[tuple[float, float]]:
    if "poligono" in d:
        return [(x0 + x, y0 + y) for x, y in d["poligono"]]
    w = float(d["larghezza"])
    p = float(d["profondita"])
    wn = float(d.get("larghezza_nord", w))
    return [(x0, y0), (x0 + w, y0), (x0 + wn, y0 + p), (x0, y0 + p)]


def _piazza_locali(dati: dict) -> dict[str, _Locale]:
    sp = dati.get("spessori", {})
    t_int = float(sp.get("interni", 0.30))
    t_ext = float(sp.get("esterni", 0.40))
    out: dict[str, _Locale] = {}
    for d in dati["locali"]:
        nome = d["nome"]
        t = float(d.get("spessore_muro", t_int))
        off = float(d.get("scostamento", 0.0))
        rif = next((d[k] for k in ("a_destra_di", "a_sinistra_di", "sopra_di", "sotto_di") if k in d), None)
        if rif is not None and rif not in out:
            raise ValueError(f"Il locale {nome} e' posizionato rispetto a '{rif}', che non e' (ancora) descritto")
        if "origine" in d:
            x0, y0 = map(float, d["origine"])
        elif rif is None:
            x0, y0 = 0.0, 0.0
        else:
            minx, miny, maxx, maxy = out[rif].pol.bounds
            sud = [c for c in out[rif].pol.exterior.coords if abs(c[1] - miny) < 1e-6]
            if "a_destra_di" in d:
                x0, y0 = max(c[0] for c in sud) + t, miny + off
            elif "a_sinistra_di" in d:
                x0, y0 = minx - t - float(d["larghezza"]), miny + off
            elif "sopra_di" in d:
                x0, y0 = minx + off, maxy + t
            else:
                x0, y0 = minx + off, miny - t - float(d["profondita"])
        pol = Polygon(_vertici(x0, y0, d))
        out[nome] = _Locale(nome, pol, d, float(d.get("spessore_esterno", t_ext)))
    return out


def _cardinale(nout) -> str:
    return max(CARDINALI, key=lambda k: float(np.dot(nout, CARDINALI[k])))


def _contorno_esterno(loc: _Locale) -> Polygon:
    """Contorno del locale allargato lato per lato dello spessore del muro (spessori_lati, se indicati)."""
    lati = loc.dati.get("spessori_lati", {})
    if not lati:
        return loc.pol.buffer(loc.t_est, join_style="mitre")
    c = list(orient(loc.pol, 1.0).exterior.coords)[:-1]
    n = len(c)
    rette = []
    for i in range(n):
        p, q = np.array(c[i], float), np.array(c[(i + 1) % n], float)
        d = (q - p) / np.linalg.norm(q - p)
        nout = np.array([d[1], -d[0]])
        t = float(lati.get(_cardinale(nout), loc.t_est))
        rette.append((p + nout * t, d))
    pts = []
    for i in range(n):
        (p1, d1), (p2, d2) = rette[i - 1], rette[i]
        den = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(den) < 1e-9:
            pts.append(tuple(p2))
            continue
        t = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den
        pts.append(tuple(p1 + d1 * t))
    return Polygon(pts)


def _muri_da_massa(locali: dict[str, _Locale], dati: dict) -> list[Muro]:
    """Massa muraria = locali allargati dello spessore esterno, meno i locali; poi assi come da un DWG."""
    from .ingresso.dwg import analizza_pianta
    stanze = unary_union([l.pol for l in locali.values()])
    massa = unary_union([_contorno_esterno(l) for l in locali.values()]).difference(stanze)
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    for g in getattr(massa, "geoms", [massa]):
        msp.add_lwpolyline(list(g.exterior.coords), close=True, dxfattribs={"layer": "MURI"})
        for r in g.interiors:
            msp.add_lwpolyline(list(r.coords), close=True, dxfattribs={"layer": "MURI"})
    an = analizza_pianta(doc)
    mat_def = dati.get("materiale", "muratura")
    muri = []
    for k, m in enumerate(an.muri):
        mid = Point(*(m.p0 + m.p1) / 2)
        # materiale del locale vicino con lo stesso spessore esterno (altrimenti quello generale)
        vicini = sorted(locali.values(), key=lambda l: l.pol.distance(mid))
        mat = mat_def
        for l in vicini[:2]:
            if abs(l.t_est - m.spessore) < 0.01 and "materiale" in l.dati:
                mat = l.dati["materiale"]
                break
        muri.append(Muro(id=f"M{k + 1}", asse=[tuple(map(float, m.p0)), tuple(map(float, m.p1))],
                         spessore=V(valore=round(m.spessore, 3)), materiale=mat))
    return muri


def _lato(loc: _Locale, lato: str):
    """Estremi (a, b) del lato del locale rivolto verso il punto cardinale dato."""
    n = np.array(CARDINALI[lato], float)
    pol = orient(loc.pol, 1.0)
    c = list(pol.exterior.coords)
    migliore = None
    for p, q in zip(c, c[1:]):
        d = np.subtract(q, p)
        L = np.linalg.norm(d)
        if L < 1e-6:
            continue
        nout = np.array([d[1], -d[0]]) / L  # antiorario: l'esterno e' a destra
        score = float(nout @ n)
        if migliore is None or score > migliore[0]:
            migliore = (score, np.array(p, float), np.array(q, float))
    return migliore[1], migliore[2]


def _punto_zero(a, b, lato: str, dal: str | None):
    asse_lungo = "x" if lato in ("sud", "nord") else "y"
    dal = dal or ("ovest" if asse_lungo == "x" else "sud")
    k = 0 if asse_lungo == "x" else 1
    verso_min = dal in ("ovest", "sud")
    inizio, fine = (a, b) if (a[k] <= b[k]) == verso_min else (b, a)
    u = (fine - inizio) / np.linalg.norm(fine - inizio)
    return inizio, u


def _aperture(dati: dict, locali: dict[str, _Locale], muri: list[Muro]) -> list[Apertura]:
    out = []
    contatori: dict[str, int] = {}
    for spec in dati.get("aperture", []):
        nome = spec["locale"]
        if nome not in locali:
            raise ValueError(f"Apertura su un locale non descritto: {nome}")
        loc = locali[nome]
        a, b = _lato(loc, spec["lato"])
        o, u = _punto_zero(a, b, spec["lato"], spec.get("dal"))
        pa, pb = o + u * float(spec["da"]), o + u * float(spec["a"])
        mid = (pa + pb) / 2
        best = None
        for m in muri:
            p0, p1 = np.array(m.asse[0]), np.array(m.asse[1])
            d = (p1 - p0) / np.linalg.norm(p1 - p0)
            if abs(abs(float(d @ u)) - 1) > 1e-3:
                continue
            nrm = np.array([-d[1], d[0]])
            dist = abs(float((mid - p0) @ nrm))
            t = float((mid - p0) @ d)
            if not (-0.01 <= t <= np.linalg.norm(p1 - p0) + 0.01):
                continue
            err = abs(dist - m.spessore.valore / 2)
            if err < 0.05 and (best is None or err < best[0]):
                best = (err, m, p0, d, nrm)
        if best is None:
            raise ValueError(f"Nessun muro trovato per l'apertura {spec} (controlla lato, 'dal' e progressive)")
        _, m, p0, d, nrm = best
        s0, s1 = sorted((float((pa - p0) @ d), float((pb - p0) @ d)))
        tipo = spec.get("tipo", "finestra" if V.model_validate(spec.get("davanzale", 0)).valore > 0 else "porta")
        pref = {"porta": "P", "finestra": "F", "varco": "V", "feritoia": "F"}[tipo]
        contatori[pref] = contatori.get(pref, 0) + 1
        lato_porta = "+" if float((np.array(loc.pol.centroid.coords[0]) - p0) @ nrm) > 0 else "-"
        w = s1 - s0
        out.append(Apertura(
            id=spec.get("id", f"{pref}{contatori[pref]}"), muro=m.id, da=V(valore=round(s0, 3)),
            a=V(valore=round(s1, 3)), altezza=V.model_validate(spec["altezza"]),
            davanzale=V.model_validate(spec.get("davanzale", 0.0)), tipo=tipo,
            forma=spec.get("forma", "rettangolare"), lato=lato_porta,
            battente=spec.get("battente", "doppio" if tipo == "porta" and w > 1.05 else "sx")))
    return out


def _piano_copertura(c: dict, stanze) -> tuple:
    """(z(x, y) dell'estradosso, tagli per le falde) di una copertura, dalle altezze all'intradosso."""
    from shapely.geometry import box
    minx, miny, maxx, maxy = stanze.bounds
    sp = float(c.get("spessore", 0.30))
    G = 1000.0
    if c["tipo"] == "capanna":
        hi, hc = float(c["h_imposta"]), float(c["h_colmo"])
        if c.get("colmo", "x") == "x":
            m = (miny + maxy) / 2
            k = (hc - hi) / (m - miny)
            return (lambda x, y: hc + sp - k * abs(y - m)), [box(-G, -G, G, m), box(-G, m, G, G)]
        m = (minx + maxx) / 2
        k = (hc - hi) / (m - minx)
        return (lambda x, y: hc + sp - k * abs(x - m)), [box(-G, -G, m, G), box(m, -G, G, G)]
    if c["tipo"] == "una_falda":
        ha, hb = float(c["h_alta"]), float(c["h_bassa"])
        bassa = c.get("bassa", "nord")
        if bassa in ("nord", "sud"):
            ya, yb = (miny, maxy) if bassa == "nord" else (maxy, miny)
            return (lambda x, y: ha + sp + (hb - ha) * (y - ya) / (yb - ya)), [box(-G, -G, G, G)]
        xa, xb = (minx, maxx) if bassa == "est" else (maxx, minx)
        return (lambda x, y: ha + sp + (hb - ha) * (x - xa) / (xb - xa)), [box(-G, -G, G, G)]
    raise ValueError(f"Tipo di copertura sconosciuto: {c['tipo']} (capanna | una_falda)")


def _coperture(dati: dict, locali: dict[str, _Locale]) -> list[Falda]:
    """Falde: ogni copertura copre i propri locali con i loro muri e sporge verso l'esterno. Dove due
    coperture si incontrano, la piu' alta copre il muro in comune (e sporge sopra l'altra), la piu' bassa
    si ferma contro il muro."""
    from shapely.ops import nearest_points
    gruppi = []
    for c in dati.get("coperture", []):
        grp = [locali[n] for n in c["locali"]]
        stanze = unary_union([l.pol for l in grp])
        z, tagli = _piano_copertura(c, stanze)
        base = unary_union([_contorno_esterno(l) for l in grp])
        sporto = float(c.get("sporto", 0.0))
        if sporto > 0:
            base = base.buffer(sporto, join_style="mitre")
        gruppi.append((c, grp, stanze, z, tagli, base))
    falde = []
    for i, (c, grp, stanze, z, tagli, base) in enumerate(gruppi, start=1):
        for c2, grp2, stanze2, z2, _, _ in gruppi:
            if c2 is c:
                continue
            for o in grp2:
                gap = stanze.distance(o.pol)
                if gap >= 1.0:
                    continue
                p1, p2 = nearest_points(stanze, o.pol)
                mx, my = (p1.x + p2.x) / 2, (p1.y + p2.y) / 2
                if z(mx, my) < z2(mx, my) - 1e-6:  # siamo piu' bassi: ci fermiamo contro il muro
                    muro_alto = o.pol.buffer(gap, join_style="mitre").union(
                        _contorno_esterno(o).buffer(float(c.get("sporto", 0.0)) + 0.01, join_style="mitre")
                        .difference(stanze.buffer(gap / 2, join_style="mitre")))
                    base = base.difference(muro_alto)
                elif abs(z(mx, my) - z2(mx, my)) <= 1e-6:  # stessa quota: a meta' del muro
                    base = base.difference(o.pol.buffer(gap / 2, join_style="mitre"))
        sp = float(c.get("spessore", 0.30))
        nota = c.get("ipotesi")  # es. "spessore e sporto stimati dalle foto"
        mk = (lambda x: V(valore=x, fonte="ipotesi", nota=nota)) if nota else (lambda x: V(valore=x))
        j = 0
        for taglio in tagli:
            g = base.intersection(taglio)
            for q in getattr(g, "geoms", [g]):
                if not isinstance(q, Polygon) or q.area < 0.01:
                    continue
                j += 1
                q = q.simplify(0.001)
                pts = [(round(x, 4), round(y, 4)) for x, y in orient(q, 1.0).exterior.coords[:-1]]
                falde.append(Falda(id=f"T{i}{j}", poligono=pts, quote=[mk(round(z(x, y), 4)) for x, y in pts],
                                   spessore=mk(sp), manto=c.get("manto", "coppi"),
                                   struttura=c.get("struttura", "travi in legno")))
    return falde


def _sezioni(ed: Edificio, locali: dict[str, _Locale], dati: dict) -> list[LineaSezione]:
    if dati.get("sezioni"):
        return [LineaSezione(**s) for s in dati["sezioni"]]
    tutto = unary_union([l.pol for l in locali.values()])
    minx, miny, maxx, maxy = tutto.bounds
    grande = max(locali.values(), key=lambda l: l.pol.area)
    c = grande.pol.centroid
    gminx, gminy, gmaxx, gmaxy = grande.pol.bounds
    colmo_y = any(cp.get("tipo") == "capanna" and cp.get("colmo") == "y" for cp in dati.get("coperture", []))
    if colmo_y:
        return [LineaSezione(nome="A", p0=(minx - 1.5, c.y), p1=(maxx + 1.5, c.y), verso="dx"),
                LineaSezione(nome="B", p0=(gminx + 0.35 * (gmaxx - gminx), miny - 1.5),
                             p1=(gminx + 0.35 * (gmaxx - gminx), maxy + 1.5))]
    return [LineaSezione(nome="A", p0=(c.x, miny - 1.5), p1=(c.x, maxy + 1.5)),
            LineaSezione(nome="B", p0=(minx - 1.5, gminy + 0.35 * (gmaxy - gminy)),
                         p1=(maxx + 1.5, gminy + 0.35 * (gmaxy - gminy)), verso="dx")]


def costruisci(dati: dict) -> Edificio:
    locali = _piazza_locali(dati)
    muri = _muri_da_massa(locali, dati)
    ed = Edificio(pratica=Pratica(**dati.get("pratica", {})), muri=muri,
                  nord_gradi=float(dati.get("nord_gradi", 90.0)),
                  nord_ipotizzato=bool(dati.get("nord_ipotizzato", "nord_gradi" not in dati)),
                  quota_terreno=V.model_validate(dati.get("quota_terreno", 0.0)))
    ed.aperture = _aperture(dati, locali, muri)
    for k, l in enumerate(locali.values(), start=1):
        d = l.dati
        hmin = d.get("h_min", d.get("h"))
        if hmin is None:
            hmin = V(valore=2.70, fonte="ipotesi", nota="altezza non indicata nel rilievo")
        p = l.pol.representative_point()
        ed.locali.append(Locale(id=f"L{k}", nome=l.nome, destinazione=d.get("destinazione", ""), punto=(p.x, p.y),
                                h_min=hmin, h_max=d.get("h_max"), soffitto=d.get("soffitto", "")))
    ed.falde = _coperture(dati, locali)
    ed.sezioni = _sezioni(ed, locali, dati)
    return ed
