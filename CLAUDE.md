# Rilievo → Tavole

Strumento per un tirocinante di ingegneria civile: dal sopralluogo (schizzo a mano, DWG, foto) alle tavole
tecniche (pianta, prospetti, sezioni) in DWG AutoCAD 2018 e PDF. Si risponde in italiano semplice.

- Procedura di lavoro: skill `rilievo` (`.claude/skills/rilievo/SKILL.md`).
- Si producono solo le tavole che l'utente chiede; di norma si consegna solo il DWG pulito (PDF solo su richiesta).
- Progetto e decisioni: `docs/superpowers/specs/2026-11-24-rilievo-tavole-design.md`.
- Ambiente: `pip install -e .[test]`; il DWG richiede ODA File Converter + `xvfb-run` (vedi README).
- Test: `pytest -q` (circa un minuto).
- Ogni dato non misurato va nel modello con `fonte: ipotesi`: esce in rosso nelle tavole e nel registro.
- Prima di disegnare prospetti o sezioni leggere `docs/lezioni/R001-errori-da-non-ripetere.md`: altezze dell'utente
  senza interpretazioni, niente elementi inventati, `rilievo verifica` senza ERRORE e DXF guardato come in AutoCAD.
