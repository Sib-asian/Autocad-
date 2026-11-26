# Lezioni dalle pratiche reali

Ogni pratica insegna qualcosa. Qui si raccolgono gli errori fatti e i rimedi, perché non si ripetano.
Prima di iniziare una pratica si leggono tutte le lezioni del tipo di lavoro richiesto.

| Pratica | Lavoro | Lezione |
|---|---|---|
| R001 | prospetti e sezioni da pianta DWG + altezze | [R001-errori-da-non-ripetere.md](R001-errori-da-non-ripetere.md) |
| C001 | pianta da planimetria catastale (PDF) per APE | [C001-pianta-catastale-per-ape.md](C001-pianta-catastale-per-ape.md) |
| C002 | appartamento da catastale storto per APE (solo disegno) | [C002-appartamento-catastale-per-ape.md](C002-appartamento-catastale-per-ape.md) |
| C003 | catastale con muri inclinati per APE (assi a mano) | [C003-catastale-muri-inclinati-per-ape.md](C003-catastale-muri-inclinati-per-ape.md) |
| C004 | catastale ortogonale per APE con `rilievo assi` | [C004-catastale-ortogonale-assi.md](C004-catastale-ortogonale-assi.md) |
| C005 | appartamento stretto per APE; vani e facce dei tramezzi | [C005-catastale-appartamento-stretto.md](C005-catastale-appartamento-stretto.md) |

## Alla fine di ogni pratica (obbligatorio, anche se è andata bene)

1. **Lezione**: `docs/lezioni/<codice>-<argomento>.md` con la tabella errore / causa / rimedio permanente e le
   regole nuove. Una riga in più nella tabella qui sopra. Se non ci sono stati errori, si annota cosa ha funzionato
   e cosa ha chiesto l'utente (preferenze di disegno, formato di consegna).
2. **Test del caso reale**: in `tests/test_casi_reali.py`, con i dati del modello (`modello/rilievo.yaml`), mai con
   foto, DWG o PDF del cliente (il repository è pubblico). Il test pretende ciò che l'utente ha corretto.
3. **Controllo automatico**: se l'errore si può riconoscere da un programma, si aggiunge a `rilievo/verifica.py`
   (con un test che lo fa scattare) così vale per tutte le pratiche future.
4. **Procedura**: le regole nuove vanno nella skill `rilievo` (`.claude/skills/rilievo/SKILL.md`), sezione giusta.
5. **Suite completa** (`pytest -q`) verde, poi commit e push.

Un errore che l'utente ha dovuto segnalare due volte è un errore della procedura, non solo del disegno.
