"""Riga di comando: `rilievo <comando> ...` (vedi `rilievo --help`)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MODELLO_VUOTO = """# Modello dell'edificio. Unita': metri. Un numero da solo = misura presa sul posto.
# Per un dato non misurato: {valore: 2.10, fonte: ipotesi, nota: "da foto"}
pratica:
  codice: {codice}
  tipo: rilievo        # rilievo | sanatoria | cila | scia | permesso | perizia | progetto
  titolo: ""
  committente: ""
  comune: ""
nord_gradi: 90         # direzione del Nord in pianta (90 = verso l'alto)
nord_ipotizzato: true
muri: []
aperture: []
locali: []
falde: []
sezioni: []
"""


def cmd_nuova(a) -> int:
    base = Path("pratiche") / a.codice
    for sub in ("input/schizzi", "input/dwg", "input/foto", "modello", "output"):
        (base / sub).mkdir(parents=True, exist_ok=True)
    m = base / "modello" / "edificio.yaml"
    if not m.exists():
        m.write_text(MODELLO_VUOTO.replace("{codice}", a.codice), encoding="utf-8")
    d = base / "modello" / "domande.md"
    if not d.exists():
        d.write_text(f"# Domande aperte - pratica {a.codice}\n\n", encoding="utf-8")
    print(f"Creata la pratica in {base}")
    return 0


def _carica(pratica: Path):
    from .modello import carica
    return carica(pratica / "modello" / "edificio.yaml")


def cmd_costruisci(a) -> int:
    """Dal rilievo descritto per locali (modello/rilievo.yaml) al modello completo (modello/edificio.yaml)."""
    import yaml

    from .costruttore import costruisci
    from .modello import salva
    base = Path(a.pratica)
    src = base / "modello" / "rilievo.yaml"
    if not src.exists():
        print(f"Manca {src}: vedi l'esempio esempi/rilievo_caso_2031.yaml")
        return 2
    try:
        ed = costruisci(yaml.safe_load(src.read_text(encoding="utf-8")))
    except (ValueError, KeyError) as e:
        print("Il rilievo ha un problema:", e)
        return 2
    err = ed.valida()
    salva(ed, base / "modello" / "edificio.yaml")
    print(f"Modello scritto: {len(ed.muri)} muri, {len(ed.aperture)} aperture, {len(ed.locali)} locali, "
          f"{len(ed.falde)} falde, {len(ed.sezioni)} sezioni")
    for e in err:
        print("Da controllare:", e)
    return 0 if not err else 1


def cmd_genera(a) -> int:
    from .esporta import esporta
    from .genera.tavola import componi_tavole
    from .verifica import verifica
    base = Path(a.pratica)
    ed = _carica(base)
    err = ed.valida()
    if err:
        print("Il modello ha errori da correggere prima di disegnare:")
        for e in err:
            print(" -", e)
        return 2
    altri = {}
    for nome in ("legittimo", "progetto"):
        f = base / "modello" / f"{nome}.yaml"
        if f.exists():
            from .modello import carica
            altri[nome] = carica(f)
            print(f"Letto lo stato {nome}: {f}")
    studio = _studio()
    try:
        tavole = {x.strip().lower() for x in a.tavole.split(",")} if a.tavole else None
        t = componi_tavole(ed, profilo=a.profilo, scala=a.scala, studio=studio, tavole=tavole, **altri)
    except ValueError as e:
        print("Impossibile comporre le tavole:", e)
        return 2
    out = esporta(t, base / "output", base.resolve().name, dwg=not a.no_dwg, pdf=a.pdf, versione=a.versione_dwg)
    if a.ape:  # pianta semplificata per i programmi dell'APE (Blumatica, Termolog, TerMus...)
        from .esporta import pianta_per_ape
        out.update({f"ape_{k}": v for k, v in pianta_per_ape(ed, base / "output", base.resolve().name).items()})
    if ed.foto:
        from .genera.perizia import documentazione_fotografica_pdf
        out["foto"] = documentazione_fotografica_pdf(ed, base / "output" / "documentazione_fotografica.pdf",
                                                     base=base)
    rep = verifica(ed, t, dwg=out.get("dwg"))
    (base / "output" / "verifica.md").write_text(rep.markdown(), encoding="utf-8")
    (base / "output" / "registro_ipotesi.md").write_text(registro(ed), encoding="utf-8")
    for k, v in out.items():
        print(f"{k}: {v}")
    print(f"Verifica: {'superata' if rep.ok else 'CON ERRORI'} (vedi output/verifica.md)")
    return 0 if rep.ok else 1


def _studio() -> dict:
    """Dati del tecnico per il cartiglio (config/studio.yaml), se presenti."""
    import yaml
    for p in (Path("config/studio.yaml"), Path.home() / ".config" / "rilievo" / "studio.yaml"):
        if p.exists():
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {}


def registro(ed) -> str:
    righe = [f"# Registro dei dati da verificare - {ed.pratica.codice}", ""]
    if ed.nord_ipotizzato:
        righe.append("- Orientamento del Nord: ipotizzato")
    for ogg, campo, val in ed.ipotesi():
        righe.append(f"- {ogg} - {campo}: {val.valore:.2f} m (ipotesi{': ' + val.nota if val.nota else ''})")
    fonti = {}
    from .modello import V

    def conta(o):
        for _, x in o:
            if isinstance(x, V):
                fonti[x.fonte] = fonti.get(x.fonte, 0) + 1
            elif isinstance(x, list):
                for y in x:
                    if isinstance(y, V):
                        fonti[y.fonte] = fonti.get(y.fonte, 0) + 1
    for g in (ed.muri, ed.aperture, ed.locali, ed.falde):
        for o in g:
            conta(o)
    righe += ["", "## Provenienza dei dati", ""] + [f"- {k}: {n}" for k, n in sorted(fonti.items())]
    return "\n".join(righe) + "\n"


def cmd_verifica(a) -> int:
    from .genera.tavola import componi_tavole
    from .verifica import verifica
    ed = _carica(Path(a.pratica))
    rep = verifica(ed, componi_tavole(ed))
    print(rep.markdown())
    return 0 if rep.ok else 1


def cmd_scheda(a) -> int:
    from .genera.scheda import scheda_sopralluogo
    if a.pratica == "-":
        p = scheda_sopralluogo(Path("scheda_sopralluogo.pdf"))
    else:
        base = Path(a.pratica)
        p = scheda_sopralluogo(base / "output" / "scheda_sopralluogo.pdf", _carica(base))
    print(p)
    return 0


def cmd_zoom(a) -> int:
    import cv2
    img = cv2.imread(a.immagine)
    if img is None:
        print("Immagine non leggibile")
        return 2
    x, y, w, h = a.x, a.y, a.w, a.h
    crop = img[y:y + h, x:x + w]
    crop = cv2.resize(crop, None, fx=a.fattore, fy=a.fattore, interpolation=cv2.INTER_CUBIC)
    out = a.out or str(Path(a.immagine).with_name(f"{Path(a.immagine).stem}_zoom_{x}_{y}.png"))
    cv2.imwrite(out, crop)
    print(out)
    return 0


def cmd_griglia(a) -> int:
    """Sovrappone una griglia numerata (in pixel) per scegliere le zone da ingrandire."""
    import cv2
    img = cv2.imread(a.immagine)
    H, W = img.shape[:2]
    for x in range(0, W, a.passo):
        cv2.line(img, (x, 0), (x, H), (0, 0, 255), 1)
        cv2.putText(img, str(x), (x + 3, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    for y in range(0, H, a.passo):
        cv2.line(img, (0, y), (W, y), (0, 0, 255), 1)
        cv2.putText(img, str(y), (3, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    out = a.out or str(Path(a.immagine).with_name(Path(a.immagine).stem + "_griglia.png"))
    cv2.imwrite(out, img)
    print(out)
    return 0


def cmd_analizza_dwg(a) -> int:
    from .ingresso.dwg import analizza_pianta, bozza_modello, leggi_dwg
    from .modello import salva
    doc = leggi_dwg(a.file)
    an = analizza_pianta(doc)
    ed = bozza_modello(an)
    out = Path(a.out or Path(a.file).with_suffix(".bozza.yaml"))
    salva(ed, out)
    print(f"Unita' del disegno: x{an.fattore} -> metri")
    print(f"Muri: {len(ed.muri)}, aperture: {len(ed.aperture)}, locali: {len(ed.locali)}")
    for av in an.avvisi:
        print("Avviso:", av)
    for e in ed.valida():
        print("Da controllare:", e)
    print(f"Bozza del modello: {out}")
    return 0


def cmd_punti(a) -> int:
    from .foto.raddrizza import pagina_punti
    out = pagina_punti(a.foto, a.out or Path(a.foto).with_suffix(".punti.html"))
    print(out)
    return 0


def cmd_raddrizza(a) -> int:
    import cv2
    from .foto.raddrizza import leggi_exif, raddrizza, stima_K, stima_k1
    img = cv2.imread(a.foto)
    ex = leggi_exif(a.foto)
    K = stima_K(img.shape[1], img.shape[0], focale_35mm=ex.get("focale_35mm"))
    k1, metodo = (a.k1, "fornito") if a.k1 is not None else stima_k1(img, K)
    dati = json.loads(Path(a.punti).read_text())
    out, H, ppm = raddrizza(img, dati["punti_px"][:4], dati["punti_m"], K=K, k1=k1, px_per_m=a.px_per_m)
    dest = a.out or str(Path(a.foto).with_name(Path(a.foto).stem + "_raddrizzata.jpg"))
    cv2.imwrite(dest, out)
    print(f"Distorsione k1 = {k1:.3f} ({metodo}); EXIF: {ex or 'assenti'}")
    print(f"Immagine raddrizzata ({ppm} px/m): {dest}")
    from .foto.raddrizza import misura_con_incertezza
    extra = dati["punti_px"][4:]
    if extra:
        for i, r in enumerate(misura_con_incertezza(dati["punti_px"][:4], dati["punti_m"], extra, K, k1), start=5):
            print(f"punto {i}: X = {r['X']:.3f} m, Z = {r['Z']:.3f} m  (incertezza +/- {r['incertezza_m'] * 100:.0f} cm)")
        print("Le misure da foto entrano nel modello con fonte: foto e la loro incertezza nella nota.")
    return 0


def cmd_banco(a) -> int:
    """Genera un caso inventato: verita' (nascosta), schizzo, DWG del 'collega', foto delle facciate."""
    from .banco.caso import genera_caso
    from .banco.foto_sintetiche import foto_facciata
    from .banco.schizzo import schizzo
    from .dxf.stile import nuovo_documento
    from .esporta import dxf_a_dwg, oda_disponibile
    from .genera.pianta import disegna_pianta
    from .genera.prospetti import lati_prospetto
    from .modello import salva
    ed = genera_caso(a.seed)
    base = Path(a.out) / f"caso_{a.seed}"
    (base / "_verita").mkdir(parents=True, exist_ok=True)
    salva(ed, base / "_verita" / "verita.yaml")
    schizzo(ed, base / "schizzo.jpg", seed=a.seed)
    doc = nuovo_documento(50)
    disegna_pianta(ed, doc.modelspace(), 50, quote=False, titolo=None)
    for e in list(doc.modelspace()):
        if e.dxf.layer in ("TESTI",) and e.dxftype() == "TEXT" and not e.dxf.text.isupper():
            doc.modelspace().delete_entity(e)
    doc.saveas(base / "pianta_collega.dxf")
    if oda_disponibile():
        dxf_a_dwg(base / "pianta_collega.dxf", base / "pianta_collega.dwg")
        (base / "pianta_collega.dxf").unlink()
    for i, v in enumerate(lati_prospetto(ed)):
        foto_facciata(ed, v, base / f"foto_{i + 1}_{v.nome.split()[-1].lower()}.jpg", k1=-0.14, seed=a.seed + i,
                      yaw=(-1) ** i * 10)
    print(base)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="rilievo", description="Dal rilievo alle tavole tecniche")
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("nuova", help="crea la cartella di una nuova pratica")
    s.add_argument("codice")
    s.set_defaults(f=cmd_nuova)
    s = sp.add_parser("costruisci", help="dal rilievo per locali (modello/rilievo.yaml) al modello completo")
    s.add_argument("pratica")
    s.set_defaults(f=cmd_costruisci)
    s = sp.add_parser("genera", help="disegna le tavole (DWG, PDF) e le verifica")
    s.add_argument("pratica")
    s.add_argument("--profilo", help="rilievo, sanatoria, cila, scia, permesso, progetto, perizia "
                                     "(se manca: il tipo scritto nel modello)")
    s.add_argument("--scala", type=int)
    s.add_argument("--no-dwg", action="store_true")
    s.add_argument("--tavole", help="solo queste, separate da virgola: pianta, prospetti, sezioni, comparativa, "
                                    "documentazione, quadro (se manca: tutte quelle del tipo di pratica)")
    s.add_argument("--pdf", action="store_true", help="produce anche il PDF (di norma solo DWG)")
    s.add_argument("--ape", action="store_true",
                   help="produce anche la pianta per i programmi APE: solo muri e porte, cm, AutoCAD 2000")
    s.add_argument("--versione-dwg", default="ACAD2018",
                   help="formato del DWG: ACAD2000, ACAD2004, ACAD2007, ACAD2010, ACAD2013, ACAD2018")
    s.set_defaults(f=cmd_genera)
    s = sp.add_parser("verifica", help="controlli automatici sul modello e sulle tavole")
    s.add_argument("pratica")
    s.set_defaults(f=cmd_verifica)
    s = sp.add_parser("scheda", help="scheda di sopralluogo (PDF); '-' per quella generica")
    s.add_argument("pratica")
    s.set_defaults(f=cmd_scheda)
    s = sp.add_parser("zoom", help="ritaglia e ingrandisce una zona di un'immagine (per leggere le cifre)")
    s.add_argument("immagine")
    for k in ("x", "y", "w", "h"):
        s.add_argument(k, type=int)
    s.add_argument("--fattore", type=float, default=3)
    s.add_argument("--out")
    s.set_defaults(f=cmd_zoom)
    s = sp.add_parser("griglia", help="sovrappone una griglia in pixel a un'immagine")
    s.add_argument("immagine")
    s.add_argument("--passo", type=int, default=200)
    s.add_argument("--out")
    s.set_defaults(f=cmd_griglia)
    s = sp.add_parser("analizza-dwg", help="ricava una bozza del modello da una pianta DWG/DXF")
    s.add_argument("file")
    s.add_argument("--out")
    s.set_defaults(f=cmd_analizza_dwg)
    s = sp.add_parser("punti", help="pagina HTML per segnare i punti su una foto")
    s.add_argument("foto")
    s.add_argument("--out")
    s.set_defaults(f=cmd_punti)
    s = sp.add_parser("raddrizza", help="raddrizza una foto di facciata e misura i punti")
    s.add_argument("foto")
    s.add_argument("punti", help="JSON con punti_px (4 + altri) e punti_m (4 coordinate reali X,Z)")
    s.add_argument("--k1", type=float)
    s.add_argument("--px-per-m", type=int, default=100)
    s.add_argument("--out")
    s.set_defaults(f=cmd_raddrizza)
    s = sp.add_parser("banco", help="genera un caso di prova inventato")
    s.add_argument("seed", type=int)
    s.add_argument("--out", default="banco_out")
    s.set_defaults(f=cmd_banco)
    a = p.parse_args(argv)
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())
