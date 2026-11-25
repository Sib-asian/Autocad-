"""Controlli automatici sulle tavole prodotte, con spiegazioni per chi impara."""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

import ezdxf.bbox
import numpy as np
from shapely.geometry import box

from .modello import Edificio


@dataclass
class Controllo:
    nome: str
    spiegazione: str
    atteso: str
    trovato: str
    esito: str  # OK, ATTENZIONE, ERRORE
    dettagli: list[str] = field(default_factory=list)


@dataclass
class Report:
    righe: list[Controllo] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.esito != "ERRORE" for c in self.righe)

    def markdown(self) -> str:
        out = ["# Report di verifica", "", "| Controllo | Perche' serve | Atteso | Trovato | Esito |",
               "|---|---|---|---|---|"]
        for c in self.righe:
            out.append(f"| {c.nome} | {c.spiegazione} | {c.atteso} | {c.trovato} | {c.esito} |")
        for c in self.righe:
            if c.dettagli:
                out += ["", f"## {c.nome}", ""] + [f"- {d}" for d in c.dettagli[:40]]
        return "\n".join(out) + "\n"


def _val(t: str) -> Decimal | None:
    try:
        return Decimal(t.replace("±", "").replace(",", "."))
    except Exception:
        return None


def controlla_catene(doc) -> Controllo:
    """Le quote parziali sulla stessa linea devono sommare alla quota totale che le abbraccia."""
    linee = defaultdict(list)
    tutte = []
    for d in doc.modelspace().query("DIMENSION"):
        if d.dimtype not in (0, 1) or not d.dxf.text:
            continue
        a = math.radians(d.dxf.get("angle", 0.0))
        u = np.array([math.cos(a), math.sin(a)])
        n = np.array([-u[1], u[0]])
        dp = np.array([d.dxf.defpoint.x, d.dxf.defpoint.y])
        s1, s2 = (float(np.dot(np.array([p.x, p.y]), u)) for p in (d.dxf.defpoint2, d.dxf.defpoint3))
        v = _val(d.dxf.text)
        if v is None:
            continue
        chiave = (round(math.degrees(a) % 180, 3), round(float(np.dot(dp, n)), 4))
        voce = (min(s1, s2), max(s1, s2), v, chiave)
        linee[chiave].append(voce)
        tutte.append(voce)
    errori, verificate = [], 0
    catene = []  # sulla stessa retta possono stare catene di disegni diversi: si separano i tratti contigui
    for chiave, voci in linee.items():
        corrente = []
        for v in sorted(voci):
            if corrente and abs(v[0] - corrente[-1][1]) > 1e-3:
                catene.append((chiave, corrente))
                corrente = []
            corrente.append(v)
        catene.append((chiave, corrente))
    for chiave, voci in catene:
        if len(voci) < 2:
            continue
        lo, hi = min(v[0] for v in voci), max(v[1] for v in voci)
        somma = sum(v[2] for v in voci)
        tot = [v for v in tutte if v[3] != chiave and v[3][0] == chiave[0] and abs(v[0] - lo) < 1e-3
               and abs(v[1] - hi) < 1e-3]
        for t in tot:
            verificate += 1
            if t[2] != somma:
                errori.append(f"parziali {' + '.join(str(v[2]) for v in sorted(voci))} = {somma}, totale scritto {t[2]}")
    return Controllo("Catene di quote", "la somma delle quote parziali deve dare il totale scritto",
                     "somme = totali", f"{verificate} catene verificate, {len(errori)} errori",
                     "ERRORE" if errori else "OK", errori)


def _box_testi(doc):
    out = []
    for e in doc.modelspace():
        tipo = e.dxftype()
        if tipo in ("TEXT", "MTEXT"):
            ents = [e]
            etichetta = e.dxf.text if tipo == "TEXT" else e.plain_text()
        elif tipo == "DIMENSION":
            ents = [v for v in e.virtual_entities() if v.dxftype() in ("TEXT", "MTEXT")]
            etichetta = e.dxf.text
        else:
            continue
        for t in ents:
            bb = ezdxf.bbox.extents([t], fast=False)
            if bb.has_data:
                b = box(bb.extmin.x, bb.extmin.y, bb.extmax.x, bb.extmax.y)
                out.append((b, etichetta, e.dxf.layer))
    return out


def testi_sovrapposti(doc) -> list[str]:
    scatole = _box_testi(doc)
    out = []
    for i in range(len(scatole)):
        bi, ti, _ = scatole[i]
        ri = bi.buffer(-0.08 * min(bi.bounds[2] - bi.bounds[0], bi.bounds[3] - bi.bounds[1]))
        for j in range(i + 1, len(scatole)):
            bj, tj, _ = scatole[j]
            if ri.intersects(bj) and ri.intersection(bj).area > 0.15 * min(bi.area, bj.area):
                out.append(f"'{ti}' si sovrappone a '{tj}' vicino a ({bi.centroid.x:.2f}, {bi.centroid.y:.2f})")
    return out


def testi_sui_muri(doc) -> list[str]:
    """Scritte che cadono sopra un muro tagliato in pianta: non si leggono (errore della pianta C001)."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    muri = []
    for e in doc.modelspace().query('LWPOLYLINE[layer=="MURI" | layer=="TRAMEZZI"]'):
        pts = [(x, y) for x, y, *_ in e.get_points()]
        if e.closed and len(pts) >= 3:
            muri.append(Polygon(pts).buffer(0))
    if not muri:
        return []
    massa = unary_union(muri)
    out = []
    for b, t, layer in _box_testi(doc):
        if layer.startswith("QUOTE") or layer in ("CARTIGLIO", "CORNICE"):
            continue
        dentro = b.buffer(-0.15 * min(b.bounds[2] - b.bounds[0], b.bounds[3] - b.bounds[1]))
        if dentro.intersects(massa) and dentro.intersection(massa).area > 0.2 * dentro.area:
            out.append(f"'{t}' scritto sopra un muro vicino a ({b.centroid.x:.2f}, {b.centroid.y:.2f})")
    return out


def controlla_aperture(ed: Edificio) -> Controllo:
    from .genera.prospetti import lati_prospetto
    from .modello3d import facce
    from .proiezione import proietta
    tutte = facce(ed)
    viste_ok = {}
    for v in lati_prospetto(ed):
        for p in proietta(tutte, v.direzione):
            if p.faccia.tipo == "infisso":
                x0, z0, x1, z1 = p.poligono2d.bounds
                viste_ok.setdefault(p.faccia.rif_id, []).append((v.nome, x1 - x0, z0, z1))
    errori, controllate = [], 0
    for ap in ed.aperture:
        if ap.tipo == "varco" or ap.id not in viste_ok:
            continue
        nome, w, z0, z1 = max(viste_ok[ap.id], key=lambda t: t[1])
        controllate += 1
        attesi = (ap.larghezza, ap.davanzale.valore, ap.davanzale.valore + ap.altezza.valore)
        if any(abs(a - b) > 0.002 for a, b in zip(attesi, (w, z0, z1))):
            errori.append(f"{ap.id} in {nome}: larghezza {w:.3f} (attesa {attesi[0]:.3f}), "
                          f"quote {z0:.3f}-{z1:.3f} (attese {attesi[1]:.3f}-{attesi[2]:.3f})")
    esterne = sum(1 for a in ed.aperture if a.tipo != "varco")
    nascoste = esterne - controllate
    det = errori + ([f"{nascoste} aperture interne non compaiono nei prospetti (normale)"] if nascoste else [])
    return Controllo("Aperture pianta/prospetti", "ogni finestra o porta deve avere la stessa misura in pianta e "
                     "in prospetto", "differenze <= 2 mm", f"{controllate} aperture confrontate",
                     "ERRORE" if errori else "OK", det)


def controlla_colmo(ed: Edificio, tavole) -> Controllo:
    if not any(k in f.contenuto.lower() for f in tavole.fogli for k in ("prospett", "sezion")):
        return Controllo("Quota di colmo", "il colmo deve essere alla stessa quota in tutte le viste", "-",
                         "nessun prospetto o sezione richiesto", "OK")
    if not ed.falde:
        return Controllo("Quota di colmo", "il colmo deve essere alla stessa quota in tutte le viste", "-",
                         "nessuna copertura nel modello", "ATTENZIONE")
    zmax = max(q.valore for f in ed.falde for q in f.quote)
    from .dxf.quote import fmt_quota
    atteso = fmt_quota(zmax)
    testi = [e.dxf.text for e in tavole.doc.modelspace().query("TEXT")]
    n = testi.count(atteso)
    return Controllo("Quota di colmo", "il colmo deve essere alla stessa quota in tutte le viste",
                     f"{atteso} in prospetti e sezioni", f"{n} etichette {atteso}", "OK" if n >= 1 else "ERRORE")


def controlla_ipotesi(ed: Edificio, tavole) -> Controllo:
    ipo = ed.ipotesi()
    n_rossi = len(tavole.doc.modelspace().query('*[layer=="IPOTESI_DA_VERIFICARE"]'))
    if not ipo and not ed.nord_ipotizzato:
        return Controllo("Dati ipotizzati", "cio' che non e' misurato deve essere evidenziato in rosso", "0",
                         "nessuna ipotesi", "OK")
    esito = "ATTENZIONE" if n_rossi else "ERRORE"
    return Controllo("Dati ipotizzati", "cio' che non e' misurato deve essere evidenziato in rosso e verificato",
                     "tutte in rosso e nelle note", f"{len(ipo)} dati ipotizzati, {n_rossi} elementi in rosso",
                     esito, [f"{o}: {c} = {v.valore:.2f} ({v.nota or 'da verificare'})" for o, c, v in ipo])


def controlla_requisiti(ed: Edificio) -> Controllo:
    from .genera.tabelle import tabella_superfici
    righe, _ = tabella_superfici(ed)
    no = [f"{r.nome}: " + ", ".join(x for x in (
        f"finestre {r.s_finestrata} m² < {r.rai_minimo} m² (1/8)" if r.esito_rai == "NO" else "",
        f"altezza media {r.h_media} < {r.h_richiesta}" if r.esito_h == "NO" else "") if x) for r in righe
          if "NO" in (r.esito_rai, r.esito_h)]
    controllati = sum(1 for r in righe if r.esito_rai != "n.r." or r.esito_h != "n.r.")
    return Controllo("Requisiti igienico-sanitari", "i locali abitabili devono avere finestre >= 1/8 e altezza minima",
                     "tutti OK", f"{controllati} locali verificati, {len(no)} non conformi",
                     "ATTENZIONE" if no else "OK", no)


def controlla_linee_prospetti(doc) -> list[str]:
    """Linee quasi verticali ma storte di pochi gradi nei prospetti: sono sempre un difetto del disegno
    (salti di quota calcolati male, dentelli negli angoli). Gli archi no: un tratto che continua in un altro
    tratto con una piega dolce (2-25 gradi), anche di un'altra polilinea, fa parte di una curva."""
    segs = []
    for e in doc.modelspace().query('LWPOLYLINE[layer=="PROSPETTI_CONTORNO" | layer=="PROSPETTI_SPIGOLI"]'):
        pts = [(x, y) for x, y, *_ in e.get_points()]
        if e.closed and len(pts) > 2:
            pts.append(pts[0])
        segs += [(a, b) for a, b in zip(pts, pts[1:]) if math.dist(a, b) > 1e-6]

    def ang(sg):
        (a, b) = sg
        return math.atan2(b[1] - a[1], b[0] - a[0])

    def piega(s1, s2):  # angolo fra le due rette, 0-90 gradi
        d = abs(math.degrees(ang(s1) - ang(s2))) % 180
        return min(d, 180 - d)

    out = []
    for sg in segs:
        a, b = sg
        L = math.dist(a, b)
        dal_verticale = 90 - piega(sg, ((0, 0), (1, 0)))
        if not (0.5 < dal_verticale < 8.0 and L > 0.10):
            continue
        vicini = [t for t in segs if t is not sg and any(math.dist(p, q) < 1e-3 for p in sg for q in t)]
        if any(2.0 < piega(sg, t) < 25.0 for t in vicini):
            continue  # pezzo di un arco
        out.append(f"linea storta di {dal_verticale:.1f} gradi lunga {L:.2f} vicino a ({a[0]:.2f}, {a[1]:.2f})")
    return out


def controlla_prospetti(ed: Edificio, tavole) -> Controllo:
    """Errori della pratica R001 da non ripetere: interno dell'edificio visibile nei prospetti e linee storte."""
    nome = "Prospetti puliti"
    spieg = "dall'esterno non si vede l'interno dell'edificio e gli spigoli verticali sono verticali"
    if not any("prospett" in f.contenuto.lower() for f in tavole.fogli):
        return Controllo(nome, spieg, "-", "nessun prospetto richiesto", "OK")
    from .genera.prospetti import lati_prospetto
    from .modello3d import facce
    from .proiezione import proietta
    tutte = facce(ed)
    problemi = []
    for v in lati_prospetto(ed):
        for p in proietta(tutte, v.direzione):
            # una parete interna si puo' vedere solo sopra un tetto piu' basso, mai da terra
            if p.faccia.tipo == "parete_int" and p.poligono2d.area > 0.01 and p.poligono2d.bounds[1] < 1.0:
                problemi.append(f"{v.nome}: si vede l'interno del muro {p.faccia.rif_id} "
                                f"(da quota {p.poligono2d.bounds[1]:.2f})")
    problemi += controlla_linee_prospetti(tavole.doc)
    return Controllo(nome, spieg, "0 difetti", f"{len(problemi)} difetti", "ERRORE" if problemi else "OK", problemi)


def verifica(ed: Edificio, tavole, dwg=None) -> Report:
    rep = Report()
    err = ed.valida()
    rep.righe.append(Controllo("Dati del modello", "progressive crescenti, aperture dentro i muri, niente doppioni",
                               "0 errori", f"{len(err)} errori", "ERRORE" if err else "OK", err))
    rep.righe.append(controlla_catene(tavole.doc))
    rep.righe.append(controlla_aperture(ed))
    rep.righe.append(controlla_colmo(ed, tavole))
    rep.righe.append(controlla_prospetti(ed, tavole))
    if ed.locali:
        rep.righe.append(controlla_requisiti(ed))
    sov = testi_sovrapposti(tavole.doc)
    rep.righe.append(Controllo("Testi sovrapposti", "una scritta coperta da un'altra non si legge in stampa",
                               "0", str(len(sov)), "ATTENZIONE" if sov else "OK", sov))
    sui = testi_sui_muri(tavole.doc)
    rep.righe.append(Controllo("Scritte sui muri", "una scritta sopra un muro tagliato non si legge",
                               "0", str(len(sui)), "ATTENZIONE" if sui else "OK", sui))
    rep.righe.append(controlla_ipotesi(ed, tavole))
    if dwg is not None:
        from .esporta import roundtrip_ok
        ok = roundtrip_ok(dwg, tavole.doc)
        rep.righe.append(Controllo("File DWG", "il DWG riletto deve contenere gli stessi oggetti del disegno",
                                   "stesso numero di entita'", "uguale" if ok else "diverso",
                                   "OK" if ok else "ERRORE"))
    return rep
