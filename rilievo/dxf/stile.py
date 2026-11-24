"""Documento DXF con layer, tipi di linea, stili di testo e di quota standard."""
from __future__ import annotations

import ezdxf
from ezdxf.enums import TextEntityAlignment

# nome: (colore ACI, spessore in 1/100 mm, tipo di linea)
LAYER = {
    "MURI": (7, 50, "Continuous"),
    "TRAMEZZI": (7, 35, "Continuous"),
    "RETINI": (8, 9, "Continuous"),
    "APERTURE": (4, 18, "Continuous"),
    "APERTURE_NASCOSTE": (4, 18, "DASHED"),
    "ELEMENTI": (3, 18, "Continuous"),
    "QUOTE": (2, 18, "Continuous"),
    "TESTI": (7, 25, "Continuous"),
    "PROSPETTI_CONTORNO": (7, 50, "Continuous"),
    "PROSPETTI_DETTAGLI": (7, 18, "Continuous"),
    "COPERTURA": (30, 25, "Continuous"),
    "COPERTURA_PIANTA": (30, 18, "DASHED"),
    "TERRENO": (7, 70, "Continuous"),
    "SEZ_TAGLIATO": (7, 50, "Continuous"),
    "SEZ_VISTO": (8, 18, "Continuous"),
    "SEZ_TRATTEGGI": (8, 9, "Continuous"),
    "LINEE_SEZIONE": (1, 35, "DASHDOT"),
    "DEGRADO": (6, 25, "Continuous"),
    "IPOTESI_DA_VERIFICARE": (1, 25, "Continuous"),
    "COMPARATIVA_DEMOLIZIONI": (2, 25, "Continuous"),
    "COMPARATIVA_COSTRUZIONI": (1, 25, "Continuous"),
    "NOTE": (7, 18, "Continuous"),
    "CARTIGLIO": (7, 35, "Continuous"),
    "CORNICE": (7, 70, "Continuous"),
}

FONT = "arial.ttf"


def mm(valore_mm: float, scala: int) -> float:
    """Converte una misura sulla carta (mm) in metri di disegno alla scala data."""
    return valore_mm * scala / 1000.0


def nuovo_documento(scala: int = 50) -> ezdxf.document.Drawing:
    doc = ezdxf.new("R2018", setup=True)
    doc.units = 6  # metri
    doc.header["$INSUNITS"] = 6
    doc.header["$MEASUREMENT"] = 1
    doc.header["$LTSCALE"] = scala / 1000.0 * 1.0
    doc.header["$PSLTSCALE"] = 0
    doc.header["$LWDISPLAY"] = 1
    for nome, (col, lw, lt) in LAYER.items():
        if nome not in doc.layers:
            doc.layers.add(nome, color=col, lineweight=lw, linetype=lt)
    if "RIL" not in doc.styles:
        doc.styles.add("RIL", font=FONT)
    aggiungi_dimstyle(doc, scala)
    return doc


def aggiungi_dimstyle(doc, scala: int) -> str:
    nome = f"RIL_{scala}"
    if nome in doc.dimstyles:
        return nome
    ds = doc.dimstyles.new(nome)
    ds.dxf.dimscale = scala / 1000.0
    ds.dxf.dimtxt = 2.2
    ds.dxf.dimtxsty = "RIL"
    ds.dxf.dimasz = 1.5
    ds.dxf.dimtsz = 1.2  # tick architettonici
    ds.dxf.dimexo = 1.0
    ds.dxf.dimexe = 1.2
    ds.dxf.dimgap = 0.8
    ds.dxf.dimtad = 1
    ds.dxf.dimtih = 0
    ds.dxf.dimtoh = 0
    ds.dxf.dimdec = 2
    ds.dxf.dimdsep = ord(",")
    ds.dxf.dimzin = 0
    ds.dxf.dimlunit = 2
    ds.dxf.dimclrd = 256
    ds.dxf.dimclre = 256
    ds.dxf.dimclrt = 256
    ds.dxf.dimtix = 0
    ds.dxf.dimtmove = 2  # testo spostabile senza linea di richiamo
    return nome


def testo(msp, txt: str, pos, h_mm: float, scala: int, layer: str = "TESTI",
          allinea: str = "MIDDLE_CENTER", rot: float = 0.0):
    t = msp.add_text(txt, height=mm(h_mm, scala), rotation=rot,
                     dxfattribs={"layer": layer, "style": "RIL"})
    t.set_placement(tuple(pos), align=TextEntityAlignment[allinea])
    return t
