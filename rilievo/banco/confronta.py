"""Confronto tra il modello vero (banco di prova) e quello ricostruito dallo strumento."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..geometria import apertura_mondo, poligono_locale
from ..modello import Edificio

SOGLIA_MATCH = 0.6


@dataclass
class Riga:
    oggetto: str
    grandezza: str
    vero: float
    letto: float

    @property
    def errore_cm(self) -> float:
        return round(abs(self.letto - self.vero) * 100, 2)


@dataclass
class RapportoErrori:
    righe: list[Riga] = field(default_factory=list)
    mancanti: list[str] = field(default_factory=list)
    in_piu: list[str] = field(default_factory=list)
    superfici: list[tuple[str, float, float]] = field(default_factory=list)

    @property
    def errore_max_cm(self) -> float:
        return max((r.errore_cm for r in self.righe), default=0.0)

    @property
    def errore_medio_cm(self) -> float:
        return round(float(np.mean([r.errore_cm for r in self.righe])), 2) if self.righe else 0.0

    def markdown(self) -> str:
        out = ["| Oggetto | Grandezza | Vero | Ricostruito | Errore (cm) |", "|---|---|---|---|---|"]
        for r in sorted(self.righe, key=lambda r: -r.errore_cm):
            out.append(f"| {r.oggetto} | {r.grandezza} | {r.vero:.2f} | {r.letto:.2f} | {r.errore_cm:.1f} |")
        out.append("")
        out.append(f"Errore massimo {self.errore_max_cm:.1f} cm, medio {self.errore_medio_cm:.1f} cm "
                   f"su {len(self.righe)} grandezze.")
        if self.superfici:
            out += ["", "| Locale | S vera (m²) | S ricostruita (m²) |", "|---|---|---|"]
            out += [f"| {n} | {a:.2f} | {b:.2f} |" for n, a, b in self.superfici]
        if self.mancanti:
            out.append("\nMancanti nel ricostruito: " + ", ".join(self.mancanti))
        if self.in_piu:
            out.append("\nIn piu' nel ricostruito: " + ", ".join(self.in_piu))
        return "\n".join(out) + "\n"


def _match(veri, letti, dist):
    usati, coppie = set(), []
    for v in veri:
        cand = [(dist(v, l), i) for i, l in enumerate(letti) if i not in usati]
        if not cand:
            coppie.append((v, None))
            continue
        d, i = min(cand)
        if d < SOGLIA_MATCH:
            usati.add(i)
            coppie.append((v, letti[i]))
        else:
            coppie.append((v, None))
    extra = [l for i, l in enumerate(letti) if i not in usati]
    return coppie, extra


def confronta(vero: Edificio, letto: Edificio) -> RapportoErrori:
    r = RapportoErrori()

    # --- aperture: estremi in pianta e quote
    def ends(ed, ap):
        a, b = apertura_mondo(ed, ap)
        return sorted([a, b])

    def d_ap(v, l):
        (a, b), (c, d) = ends(vero, v), ends(letto, l)
        return max(math.dist(a, c), math.dist(b, d))

    coppie, extra = _match(vero.aperture, letto.aperture, d_ap)
    for v, l in coppie:
        if l is None:
            r.mancanti.append(f"apertura {v.id}")
            continue
        (a, b), (c, d) = ends(vero, v), ends(letto, l)
        r.righe.append(Riga(v.id, "estremo 1 (scarto in pianta)", 0.0, math.dist(a, c)))
        r.righe.append(Riga(v.id, "estremo 2 (scarto in pianta)", 0.0, math.dist(b, d)))
        r.righe.append(Riga(v.id, "altezza", v.altezza.valore, l.altezza.valore))
        r.righe.append(Riga(v.id, "davanzale", v.davanzale.valore, l.davanzale.valore))
    r.in_piu += [f"apertura {l.id}" for l in extra]

    # --- muri: spessore e posizione dell'asse
    def mid(m):
        return np.mean(np.array(m.asse, float), axis=0)

    def d_mu(v, l):
        dv = np.subtract(*v.asse[::-1])
        dl = np.subtract(*l.asse[::-1])
        par = abs(float(np.dot(dv, dl)) / (np.linalg.norm(dv) * np.linalg.norm(dl)))
        if par < 0.98:
            return 99
        n = np.array([-dv[1], dv[0]]) / np.linalg.norm(dv)
        return abs(float(np.dot(mid(l) - np.array(v.asse[0]), n))) + 0.1 * float(np.linalg.norm(mid(l) - mid(v))) / 5

    coppie, extra = _match(vero.muri, letto.muri, d_mu)
    for v, l in coppie:
        if l is None:
            r.mancanti.append(f"muro {v.id}")
            continue
        r.righe.append(Riga(v.id, "spessore", v.spessore.valore, l.spessore.valore))
        dv = np.subtract(*v.asse[::-1])
        n = np.array([-dv[1], dv[0]]) / np.linalg.norm(dv)
        r.righe.append(Riga(v.id, "posizione asse", 0.0, abs(float(np.dot(mid(l) - np.array(v.asse[0]), n)))))
    r.in_piu += [f"muro {l.id}" for l in extra]

    # --- locali: superficie e altezze
    def d_lo(v, l):
        try:
            pv = poligono_locale(vero, v)
            return 0.0 if pv.contains(poligono_locale(letto, l).representative_point()) else 99
        except ValueError:
            return 99

    coppie, extra = _match(vero.locali, letto.locali, d_lo)
    for v, l in coppie:
        if l is None:
            r.mancanti.append(f"locale {v.nome}")
            continue
        r.superfici.append((v.nome, poligono_locale(vero, v).area, poligono_locale(letto, l).area))
        r.righe.append(Riga(v.nome, "h min", v.h_min.valore, l.h_min.valore))
        if v.h_max is not None and l.h_max is not None:
            r.righe.append(Riga(v.nome, "h max", v.h_max.valore, l.h_max.valore))
    r.in_piu += [f"locale {l.nome}" for l in extra]
    return r
