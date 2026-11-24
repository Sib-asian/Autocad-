"""Modello unico dell'edificio.

Ogni grandezza numerica e' un `V`: valore + fonte (da dove viene il dato).
Nel YAML un numero nudo vale come misura presa sul posto.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

Fonte = Literal["misura", "dwg", "foto", "calcolo", "ipotesi"]
Pt = tuple[float, float]


class V(BaseModel):
    """Un valore con la sua provenienza."""

    model_config = ConfigDict(frozen=True)
    valore: float
    fonte: Fonte = "misura"
    confidenza: float = 1.0
    rif: str = ""
    nota: str = ""

    @model_validator(mode="before")
    @classmethod
    def _da_numero(cls, dati: Any) -> Any:
        if isinstance(dati, (int, float)) and not isinstance(dati, bool):
            return {"valore": float(dati)}
        return dati

    @model_serializer(mode="wrap")
    def _a_numero(self, handler):
        if self.fonte == "misura" and self.confidenza == 1.0 and not self.rif and not self.nota:
            return self.valore
        d = handler(self)
        return {k: v for k, v in d.items() if v not in ("", None) and not (k == "confidenza" and v == 1.0)}

    @property
    def ipotesi(self) -> bool:
        return self.fonte == "ipotesi"

    def __float__(self) -> float:
        return self.valore


def v(x: float | V | None) -> float | None:
    """Valore numerico di un V (o None)."""
    if x is None:
        return None
    return x.valore if isinstance(x, V) else float(x)


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Pratica(_Base):
    codice: str = "SENZA_CODICE"
    tipo: Literal["rilievo", "sanatoria", "cila", "scia", "permesso", "perizia", "progetto"] = "rilievo"
    titolo: str = ""
    committente: str = ""
    indirizzo: str = ""
    comune: str = ""
    foglio: str = ""
    particella: str = ""
    tecnico: str = ""
    data: str = ""
    note: str = ""


class Muro(_Base):
    """Muro definito dal suo asse (2 punti) e dallo spessore.

    `zero` e' la distanza, lungo l'asse a partire da asse[0], del "punto 0"
    da cui sono misurate le quote progressive delle aperture (di solito lo
    spigolo interno del locale).
    """

    id: str
    asse: list[Pt] = Field(min_length=2, max_length=2)
    spessore: V
    materiale: str = "muratura"
    ruolo: Literal["portante", "tramezzo"] = "portante"
    stato: Literal["esistente", "demolire", "nuovo"] = "esistente"
    altezza: V | None = None  # None = fino alla copertura
    zero: V = V(valore=0.0)

    @property
    def lunghezza(self) -> float:
        (x0, y0), (x1, y1) = self.asse
        return math.hypot(x1 - x0, y1 - y0)


class Apertura(_Base):
    id: str
    muro: str
    da: V
    a: V
    altezza: V
    davanzale: V = V(valore=0.0)
    tipo: Literal["porta", "finestra", "varco", "feritoia"] = "finestra"
    forma: Literal["rettangolare", "arco", "arco_ribassato"] = "rettangolare"
    freccia: V | None = None  # monta dell'arco (per arco ribassato)
    battente: Literal["sx", "dx", "doppio", "nessuno"] = "sx"
    lato: Literal["+", "-"] = "+"  # verso cui apre: + = a sinistra dell'asse
    infisso: str = ""
    stato: Literal["esistente", "demolire", "nuovo"] = "esistente"

    @property
    def larghezza(self) -> float:
        return self.a.valore - self.da.valore


class Locale(_Base):
    id: str
    nome: str
    destinazione: str = ""
    punto: Pt
    h_min: V
    h_max: V | None = None
    soffitto: str = ""
    quota_pavimento: V = V(valore=0.0)


class Falda(_Base):
    """Falda di copertura: poligono in pianta + quota dell'estradosso ai vertici."""

    id: str
    poligono: list[Pt] = Field(min_length=3)
    quote: list[V]
    spessore: V = V(valore=0.25)
    manto: str = "coppi"
    struttura: str = "travi in legno"


class Elemento(_Base):
    id: str
    tipo: str  # forno, camino, pluviale, scala, canna_fumaria, muretto...
    poligono: list[Pt] | None = None
    punto: Pt | None = None
    quota_base: V = V(valore=0.0)
    altezza: V | None = None
    nota: str = ""


class Lesione(_Base):
    id: str
    muro: str
    lato: Literal["esterno", "interno"] = "esterno"
    punti: list[Pt]  # (progressiva lungo il muro, quota z)
    ampiezza_mm: float | None = None
    foto: str = ""
    nota: str = ""


class Foto(_Base):
    id: str
    file: str
    punto: Pt | None = None
    direzione_gradi: float | None = None
    soggetto: str = ""


class LineaSezione(_Base):
    nome: str
    p0: Pt
    p1: Pt
    verso: Literal["sx", "dx"] = "sx"  # lato verso cui si guarda rispetto a p0->p1


class Edificio(_Base):
    pratica: Pratica = Pratica()
    stato: Literal["fatto", "legittimo", "progetto"] = "fatto"
    nord_gradi: float = 90.0  # direzione del Nord in pianta, gradi da +x (90 = in alto)
    nord_ipotizzato: bool = True
    quota_terreno: V = V(valore=0.0)
    muri: list[Muro] = []
    aperture: list[Apertura] = []
    locali: list[Locale] = []
    falde: list[Falda] = []
    elementi: list[Elemento] = []
    lesioni: list[Lesione] = []
    foto: list[Foto] = []
    sezioni: list[LineaSezione] = []

    def muro(self, id_: str) -> Muro:
        for m in self.muri:
            if m.id == id_:
                return m
        raise KeyError(f"muro {id_} inesistente")

    def aperture_di(self, id_muro: str) -> list[Apertura]:
        return sorted((a for a in self.aperture if a.muro == id_muro), key=lambda a: a.da.valore)

    def valida(self) -> list[str]:
        """Controlli di coerenza. Ritorna messaggi leggibili (lista vuota = ok)."""
        err: list[str] = []
        ids: dict[str, int] = {}
        for gruppo in (self.muri, self.aperture, self.locali, self.falde, self.elementi, self.lesioni, self.foto):
            for o in gruppo:
                ids[o.id] = ids.get(o.id, 0) + 1
        err += [f"L'identificativo {k} e' usato {n} volte" for k, n in ids.items() if n > 1]

        muri = {m.id: m for m in self.muri}
        for m in self.muri:
            if m.lunghezza < 0.01:
                err.append(f"Il muro {m.id} ha lunghezza nulla")
        for ap in self.aperture:
            m = muri.get(ap.muro)
            if m is None:
                err.append(f"L'apertura {ap.id} e' su un muro inesistente ({ap.muro})")
                continue
            if ap.a.valore <= ap.da.valore:
                err.append(f"L'apertura {ap.id}: la progressiva finale ({ap.a.valore}) deve superare l'iniziale ({ap.da.valore})")
            fine = m.zero.valore + ap.a.valore
            if fine > m.lunghezza + 1e-6 or m.zero.valore + ap.da.valore < -1e-6:
                err.append(
                    f"L'apertura {ap.id} (progressive {ap.da.valore}-{ap.a.valore} dal punto 0) "
                    f"supera la lunghezza del muro {m.id} ({m.lunghezza:.2f} m)"
                )
            if ap.altezza.valore <= 0:
                err.append(f"L'apertura {ap.id} ha altezza non valida")
        for m in self.muri:
            aps = self.aperture_di(m.id)
            for a1, a2 in zip(aps, aps[1:]):
                if a2.da.valore < a1.a.valore - 1e-6:
                    err.append(f"L'apertura {a2.id} si sovrappone a {a1.id} sul muro {m.id}")
        for f in self.falde:
            if len(f.quote) != len(f.poligono):
                err.append(f"La falda {f.id} ha {len(f.poligono)} vertici ma {len(f.quote)} quote")
        for loc in self.locali:
            if loc.h_max is not None and loc.h_max.valore < loc.h_min.valore:
                err.append(f"Il locale {loc.nome}: H max minore di H min")
        for les in self.lesioni:
            if les.muro not in muri:
                err.append(f"La lesione {les.id} e' su un muro inesistente ({les.muro})")
        return err

    def ipotesi(self) -> list[tuple[str, str, V]]:
        """Elenco (oggetto, campo, valore) dei dati non misurati da verificare."""
        out = []

        def scan(nome: str, obj: BaseModel):
            for campo, val in obj:
                if isinstance(val, V) and val.fonte == "ipotesi":
                    out.append((nome, campo, val))
                elif isinstance(val, list):
                    for i, x in enumerate(val):
                        if isinstance(x, V) and x.fonte == "ipotesi":
                            out.append((nome, f"{campo}[{i}]", x))

        for gruppo in (self.muri, self.aperture, self.locali, self.falde, self.elementi):
            for o in gruppo:
                scan(getattr(o, "nome", None) or o.id, o)
        if self.quota_terreno.ipotesi:
            out.append(("terreno", "quota", self.quota_terreno))
        return out


def carica(path: str | Path) -> Edificio:
    with open(path, encoding="utf-8") as fh:
        return Edificio.model_validate(yaml.safe_load(fh) or {})


def salva(ed: Edificio, path: str | Path) -> None:
    dati = ed.model_dump(mode="json", exclude_defaults=True)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(dati, fh, sort_keys=False, allow_unicode=True, default_flow_style=None, width=110)
