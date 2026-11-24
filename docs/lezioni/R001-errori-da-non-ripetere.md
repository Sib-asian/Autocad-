# R001: errori da non ripetere mai più

Pratica R001 (rustico, 24/11/2026). Richiesta semplice: 4 prospetti e 2 sezioni da una pianta DWG con le altezze
scritte dall'utente. Risultato: tavole rifatte molte volte, utente che ha perso il pomeriggio. Da leggere prima di
ogni prospetto o sezione.

## Cosa è andato storto

| Errore | Causa | Rimedio permanente |
|---|---|---|
| Tetti cambiati due volte | Forma dei tetti ricavata da foto sgranate invece che dalle H min / H max scritte in pianta | Regola: si usano le altezze dell'utente; le foto servono solo per aperture e materiali |
| Sporti, coppi, travi disegnati | Elementi aggiunti di mia iniziativa, mai dati dall'utente | `sporto: 0` se non è indicato; niente manto né orditura inventati |
| Interno dell'edificio visibile nei prospetti | Unione di poligoni con coordinate quasi uguali (2,0063000000000017 / 2,006299999999958) | Coordinate su griglia 1e-6 in `proiezione.py`; controllo "Prospetti puliti" |
| Gronde sparite | Testate delle falde con la normale verso l'interno, scartate come facce nascoste; muro e testa del tetto fusi in un'unica superficie | Normale verso l'esterno; muro, testa e manto distinti nel disegno |
| Linee storte di pochi gradi | Altezza del muro letta sullo spigolo (vale il tetto del vicino) o campionata ogni 5 cm dove il tetto cambia | Altezza letta 3 mm dentro la parete; salto verticale dove cambia la falda |
| Linee verticali spurie negli angoli | Dentelli e smussi di 1-5 cm nell'unione dei muri | `_pulisci` sul contorno esterno |
| Totale 11,36 contro 11,35 della pianta | Vano 3 posizionato 1 cm fuori rispetto al DWG | Controllare le coordinate del DWG: i fili esterni allineati restano allineati |
| Tutte le linee uguali in AutoCAD | Spigoli sul layer dei dettagli | PROSPETTI_CONTORNO 0,50, PROSPETTI_SPIGOLI 0,30, PROSPETTI_DETTAGLI 0,13 grigio |
| Difetti visti dall'utente prima che da me | Controllavo solo le anteprime PNG; un trattino storto "minuscolo" liquidato come trascurabile | Guardare il DXF come in AutoCAD; nessun difetto è trascurabile; si corregge con un test prima di consegnare |

## Regole

1. Le altezze scritte dall'utente comandano. Niente interpretazioni.
2. Si disegna solo ciò che esiste nei dati: muri, tetti alle quote date, aperture. Il resto si chiede.
3. Prima consegna = consegna giusta: `rilievo verifica` senza ERRORE (compreso "Prospetti puliti"), totali dei
   prospetti uguali alla pianta, controllo visivo del DXF come in AutoCAD.
4. Se un controllo trova un difetto, si corregge il programma e si aggiunge un test, poi si rigenera.
5. Il caso R001 è un test permanente (`tests/test_casi_reali.py`): ogni modifica al programma deve superarlo.
