# MAINTAIN_PLAN runtime recovery adapter contract

Ultimo aggiornamento: 10 ottobre 2026

`backend/maintain_plan/runtime_recovery_adapter.py` è un confine puro tra
record recovery già disponibili al runtime e i contratti typed di
MAINTAIN_PLAN. Non legge l'archivio, non usa rete o database e non viene
importato dal percorso runtime attivo.

## Input obbligatori

Ogni record deve fornire `source`, `source_id`, `date`, `observed_at` e
`assessed_at`. I due timestamp devono essere espliciti, ISO-8601 e timezone
aware. Il contesto chiamante fornisce inoltre `subject_ref`, la sessione
reale, il binding della prescrizione, `captured_at`, `evaluated_at` e la
provenance.

Un `subject_ref` presente nel record deve coincidere esattamente con quello del
contesto. Un mismatch interrompe l'adattamento.

## Categoria recovery

La categoria è accettata solo quando il record contiene esplicitamente uno dei
valori `LOW`, `MODERATE`, `HIGH` o `CRITICAL` nel campo `category` o
`recovery_category`. `training_readiness`, Body Battery, stress e altri numeri
Garmin non vengono convertiti in una categoria.

Quando la categoria manca, l'assessment viene creato con
`CategoryMissingness.MISSING` e il campo canonico
`candidate_set.candidates[].category`; la valutazione stability resta quindi
`INSUFFICIENT_DATA` finché non esiste evidenza sufficiente.

Un timestamp mancante, naive o non interpretabile e una categoria esplicita
non riconosciuta producono un errore fail-closed. L'adapter non inventa la
mezzanotte UTC a partire da `date`.

## Stato di integrazione

L'archivio `GarminRecoveryArchive` attuale conserva solo record giornalieri con
`date` e valori descrittivi. Non viene modificato né collegato alla chain in
questa fase: i record esistenti non soddisfano ancora il requisito dei
timestamp espliciti e non contengono una categoria canonica. La chain e la
persistenza restano disattivate per default.
