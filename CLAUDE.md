# Rilievo → Tavole

Strumento per un tirocinante di ingegneria civile: dal sopralluogo (schizzo a mano, DWG, foto) alle tavole
tecniche (pianta, prospetti, sezioni) in DWG AutoCAD 2018 e PDF. Si risponde in italiano semplice.

- Procedura di lavoro: skill `rilievo` (`.claude/skills/rilievo/SKILL.md`).
- Progetto e decisioni: `docs/superpowers/specs/2026-11-24-rilievo-tavole-design.md`.
- Ambiente: `pip install -e .[test]`; il DWG richiede ODA File Converter + `xvfb-run` (vedi README).
- Test: `pytest -q` (circa un minuto).
- Ogni dato non misurato va nel modello con `fonte: ipotesi`: esce in rosso nelle tavole e nel registro.
