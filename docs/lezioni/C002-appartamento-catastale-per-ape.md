# C002: appartamento da planimetria catastale per APE

Pratica C002 (appartamento al 4° piano, 25/11/2026). Richiesta: disegno dritto, 1:100, muri esterni 30, interni
10, **un solo layer bianco con linee normali, niente quote, legende o scritte**: solo il disegno per Blumatica.

## Cosa ha funzionato
- Scansione ruotata: angolo trovato massimizzando la nitidezza delle proiezioni dei pixel (1,6 gradi), poi
  misure sul disegno raddrizzato. Scala dalla barra "10 metri" (1 px = 2,54 cm), come in C001.
- Finestre dalle coppie di trattini sui muri; porte interne dai varchi nelle linee dei tramezzi; ingresso dalla
  freccia del catastale. Spalletta debole verificata ingrandendo, non indovinata.
- Spazi aperti senza tramezzo (soggiorno + disimpegno + ingresso): locali rettangolari a contatto, così ogni
  finestra cade sul lato giusto e fra loro non nasce un muro.

## Errori al primo giro e rimedi permanenti
| Errore | Causa | Rimedio permanente |
|---|---|---|
| Il disimpegno largo 87 cm diventava un "muro da 87 cm" e due tramezzi si allungavano fino a metà corridoio | L'analizzatore cerca coppie di linee parallele e non sa dove sono i locali | Il costruttore tiene solo i muri il cui asse sta nella massa muraria e li accorcia al suo bordo (test C002) |
| Colonnina di muro di 1 cm accanto a un varco | Varco misurato a 1 cm dallo spigolo (rumore di misura) | Un'apertura a meno di 3 cm dallo spigolo arriva allo spigolo (solo se finisce entro il lato) |
| Segmenti da 0,1 mm nei contorni | Residui numerici dell'unione dei muri | Pulizia dei vertici nell'esportazione APE (tolleranza 0,5 mm) |
| Ingresso di 1,12 m a due ante | Regola automatica "porta > 1,05 m = due ante" | Portoncino d'appartamento: `battente: sx` |
| L'utente misura 498 invece di 4,98 | File APE in centimetri (scelta mia dopo C001) | Default in **metri** (1 unità = 1 m): "scala 1:100" per l'utente vuol dire disegno in metri; cm solo se chiesto |

## Regole
1. Pianta per APE (`--ape`): un solo layer bianco `PIANTA`, spessore di linea normale, nessuna scritta, nessuna
   quota, AutoCAD 2000, **in metri**. È il default. Prima di consegnare, misurare una stanza nel file.
2. Interpretazione da dichiarare all'utente: quali muri sono verso l'esterno, verso il vano scala o verso altre
   unità (serve per l'APE), il Nord, le linee sottili esterne (balconi?) non disegnate.
