"""Generatore di casi inventati ma coerenti: un rustico in pietra con annesso.

Somiglia ai casi reali: locali in fila sotto un tetto a capanna, un muro
storto, un annesso in blocchi con tetto a una falda, porte ad arco, finestre
piccole, una lesione sopra una porta.
"""
from __future__ import annotations

import random

import numpy as np

from ..geometria import poligono_locale, quota_intradosso
from ..modello import (Apertura, Edificio, Elemento, Falda, Lesione, LineaSezione, Locale, Muro, Pratica, V)

NOMI = ["Deposito", "Magazzino", "Cucina", "Stalla", "Cantina", "Ripostiglio", "Palmento"]


def _r(rng, a, b, passo=0.05):
    return round(round(rng.uniform(a, b) / passo) * passo, 2)


def genera_caso(seed: int) -> Edificio:
    rng = random.Random(seed)
    n = rng.choice([2, 3, 3])
    te = _r(rng, 0.45, 0.60)  # muri esterni in pietra
    ti = _r(rng, 0.30, 0.45)  # muri interni
    D = _r(rng, 3.6, 5.0)  # profondita' interna
    larghezze = [_r(rng, 3.0, 6.4) for _ in range(n)]
    storto = _r(rng, 0.20, 0.50)  # spostamento dell'estremo nord del muro est

    muri: list[Muro] = []
    h = te / 2
    xs = [0.0]
    for i, w in enumerate(larghezze):
        xs.append(xs[-1] + w + (ti if i < n - 1 else 0))
    L = xs[-1]  # fine interna dell'ultimo locale (lato sud)
    ys, yn = -h, D + h
    xe_s, xe_n = L + h, L + h + storto
    m = lambda id_, a, b, sp, mat, zero=0.0: Muro(id=id_, asse=[a, b], spessore=V(valore=sp), materiale=mat,
                                                  zero=V(valore=zero))
    muri.append(m("MS", (-h, ys), (xe_s, ys), te, "pietra lavica", h))  # sud, da ovest a est
    muri.append(m("ME", (xe_s, ys), (xe_n, yn), te, "pietra lavica", h))  # est (storto)
    muri.append(m("MN", (xe_n, yn), (-h, yn), te, "pietra lavica", h))  # nord, da est a ovest
    muri.append(m("MO", (-h, yn), (-h, ys), te, "pietra lavica", h))  # ovest
    # tramezzi portanti tra i locali
    bordi = []
    x = 0.0
    for i, w in enumerate(larghezze[:-1]):
        x += w
        xa = x + ti / 2
        muri.append(m(f"MI{i + 1}", (xa, ys), (xa, yn), ti, "pietra lavica", h))
        bordi.append((x, x + ti))
        x += ti
    # annesso in blocchi dietro un locale
    k = rng.randrange(n)
    ta = _r(rng, 0.25, 0.30)
    a0 = xs[k] + _r(rng, 0.0, 0.6)
    aw = min(_r(rng, 2.6, 4.2), xs[k + 1] - (ti if k < n - 1 else 0) - a0 + 1.0, L + storto - a0 - ta)
    aw = round(aw, 2)
    ad = _r(rng, 2.4, 3.6)
    yb = D + te  # faccia esterna del muro nord
    yt = yb + ad + ta / 2
    muri.append(m("AO", (a0 - ta / 2, yn), (a0 - ta / 2, yt), ta, "blocchi di cls", 0))
    muri.append(m("AN", (a0 - ta / 2, yt), (a0 + aw + ta / 2, yt), ta, "blocchi di cls", ta / 2))
    muri.append(m("AE", (a0 + aw + ta / 2, yt), (a0 + aw + ta / 2, yn), ta, "blocchi di cls", ta / 2))

    # coperture
    gronda = _r(rng, 2.8, 3.3)
    colmo = round(gronda + _r(rng, 0.8, 1.2), 2)
    sp = 0.30
    ym = D / 2
    xmax = xe_n + te + 0.30  # la copertura sporge anche oltre il muro storto
    e = te / 2 + 0.25  # sporto di gronda
    falde = [
        Falda(id="T1", poligono=[(-te, ys - e + h), (xmax, ys - e + h), (xmax, ym), (-te, ym)],
              quote=[V(valore=gronda)] * 2 + [V(valore=colmo)] * 2, spessore=V(valore=sp)),
        Falda(id="T2", poligono=[(-te, ym), (xmax, ym), (xmax, yn + e), (-te, yn + e)],
              quote=[V(valore=colmo)] * 2 + [V(valore=gronda)] * 2, spessore=V(valore=sp)),
    ]
    za = round(gronda - 0.35, 2)
    falde.append(Falda(id="T3", poligono=[(a0 - ta, yn + h), (a0 + aw + ta, yn + h), (a0 + aw + ta, yt + ta),
                                         (a0 - ta, yt + ta)],
                       quote=[V(valore=za), V(valore=za), V(valore=round(za - 0.45, 2)), V(valore=round(za - 0.45, 2))],
                       spessore=V(valore=0.20), manto="coppi", struttura="travetti in legno"))

    ed = Edificio(pratica=Pratica(codice=f"BANCO-{seed}", titolo=f"Caso di prova {seed}"), muri=muri,
                  falde=falde, nord_ipotizzato=False)

    # aperture
    aps: list[Apertura] = []
    for i in range(n):
        x0, x1 = xs[i], xs[i] + larghezze[i]
        w = _r(rng, 0.95, 1.30)
        da = _r(rng, x0 + 0.4, max(x0 + 0.45, x1 - w - 0.4))
        arco = rng.random() < 0.5
        aps.append(Apertura(id=f"P{i + 1}", muro="MS", da=V(valore=da), a=V(valore=round(da + w, 2)),
                            altezza=V(valore=_r(rng, 2.1, 2.4)), tipo="porta",
                            forma="arco" if arco else "rettangolare", battente="doppio", lato="+"))
        if larghezze[i] > 3.6:
            fw = _r(rng, 0.6, 0.9)
            fda = round(min(da + w + 0.6, x1 - fw - 0.3), 2)
            if fda > da + w + 0.3:
                aps.append(Apertura(id=f"F{i + 1}", muro="MS", da=V(valore=fda), a=V(valore=round(fda + fw, 2)),
                                    altezza=V(valore=_r(rng, 0.7, 1.0)), davanzale=V(valore=_r(rng, 1.0, 1.3))))
    # finestrella sul lato ovest e feritoie sul nord
    fo = _r(rng, 0.8, D - 1.4)
    aps.append(Apertura(id="FO", muro="MO", da=V(valore=fo), a=V(valore=round(fo + 0.6, 2)),
                        altezza=V(valore=0.45), davanzale=V(valore=1.6)))
    # passaggi interni (spesso ad arco)
    for i in range(n - 1):
        da = _r(rng, 0.6, D - 1.6)
        aps.append(Apertura(id=f"PI{i + 1}", muro=f"MI{i + 1}", da=V(valore=da), a=V(valore=round(da + 0.9, 2)),
                            altezza=V(valore=_r(rng, 1.9, 2.2)), tipo="porta", forma="arco", battente="sx"))
    # porta verso l'annesso nel muro nord (progressive da est verso ovest)
    s_mid = (xe_n - (a0 + aw / 2))  # distanza dall'origine dell'asse nord
    pa = round(s_mid - h - 0.4, 2)
    aps.append(Apertura(id="PA", muro="MN", da=V(valore=pa), a=V(valore=round(pa + 0.8, 2)),
                        altezza=V(valore=1.8), tipo="porta", battente="sx"))
    # finestrella dell'annesso
    aps.append(Apertura(id="FA", muro="AN", da=V(valore=round(aw / 2 - 0.25, 2)), a=V(valore=round(aw / 2 + 0.25, 2)),
                        altezza=V(valore=0.4), davanzale=V(valore=1.4)))
    ed.aperture = aps

    # locali
    nomi = rng.sample(NOMI, n)
    for i in range(n):
        p = (xs[i] + larghezze[i] / 2, D / 2)
        ed.locali.append(Locale(id=f"L{i + 1}", nome=nomi[i], punto=p, h_min=V(valore=0), soffitto="travi a vista"))
    ed.locali.append(Locale(id="LA", nome="Forno", punto=(a0 + aw / 2, yb + ad / 2), h_min=V(valore=0)))
    for i, loc in enumerate(ed.locali):
        hmin, hmax = _altezze(ed, loc)
        ed.locali[i] = loc.model_copy(update={"h_min": V(valore=hmin), "h_max": V(valore=hmax)})
    ed.elementi.append(Elemento(id="FORNO", tipo="forno", poligono=[(a0 + 0.1, yt - ta / 2 - 1.2),
                                                                    (a0 + 1.3, yt - ta / 2 - 1.2),
                                                                    (a0 + 1.3, yt - ta / 2), (a0 + 0.1, yt - ta / 2)],
                                altezza=V(valore=1.6)))
    ed.elementi.append(Elemento(id="PL1", tipo="pluviale", punto=(xe_s - 0.3, ys - h - 0.06)))
    # lesione sopra la prima porta interna o sulla facciata
    pi = next((a for a in aps if a.id == "PI1"), aps[0])
    sm = (pi.da.valore + pi.a.valore) / 2
    ed.lesioni.append(Lesione(id="LES1", muro=pi.muro, lato="interno" if pi.muro != "MS" else "esterno",
                              punti=[(sm, pi.altezza.valore + 0.05), (sm + 0.15, pi.altezza.valore + 0.5),
                                     (sm + 0.05, pi.altezza.valore + 0.9)], ampiezza_mm=3))
    ed.lesioni.append(Lesione(id="LES2", muro="MS", punti=[(aps[0].a.valore + 0.2, 2.0), (aps[0].a.valore + 0.35, 1.4),
                                                       (aps[0].a.valore + 0.3, 0.9)], ampiezza_mm=2))
    xc = xs[n // 2] + larghezze[n // 2] / 2
    ed.sezioni = [LineaSezione(nome="A", p0=(xc, ys - 1), p1=(xc, yt + 1)),
                  LineaSezione(nome="B", p0=(-2, D * 0.35), p1=(xe_n + 2, D * 0.35), verso="dx")]
    return ed


def _altezze(ed: Edificio, loc) -> tuple[float, float]:
    pl = poligono_locale(ed, loc)
    zs = []
    for x, y in list(pl.exterior.coords):
        q = quota_intradosso(ed, x, y)
        if q is not None:
            zs.append(q)
    c = pl.centroid
    for t in np.linspace(0, 1, 21):
        minx, miny, maxx, maxy = pl.bounds
        for pt in ((c.x, miny + (maxy - miny) * t), (minx + (maxx - minx) * t, c.y)):
            from shapely.geometry import Point
            if pl.buffer(-1e-6).contains(Point(pt)):
                q = quota_intradosso(ed, *pt)
                if q is not None:
                    zs.append(q)
    return round(min(zs), 2), round(max(zs), 2)
