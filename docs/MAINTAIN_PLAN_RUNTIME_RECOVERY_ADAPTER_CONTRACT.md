# MAINTAIN_PLAN runtime recovery adapter contract

Ultimo aggiornamento: 13 ottobre 2026

`backend/maintain_plan/runtime_recovery_adapter.py` adatta i record recovery
espliciti ai contratti typed di MAINTAIN_PLAN. I builder restano puri. Le due
funzioni `provide_runtime_stability_from_*` possono leggere una proiezione
reported-problems persistita quando il chiamante abilita il flag descritto
sotto. Il modulo non viene importato dal percorso runtime legacy attivo.

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

## Bridge con la baseline persistita

`build_runtime_stability_input_from_prescription_baseline` riceve una
`PrescriptionRecoveryBaseline` già catturata e usa il suo
`RecoveryAssessment` senza ricrearlo. I record successivi vengono adattati con
lo stesso `AnalyzerRef` della baseline, così la compatibilità confronta
assessment prodotti dalla stessa identità dichiarata.

`provide_runtime_stability_from_prescription_baseline` esegue poi il provider
pure. Il builder verifica il tipo della baseline, la sua validità e la
coincidenza del `subject_ref` con la sessione.

## Wiring della proiezione reported-problems persistita

Entrambi gli ingressi `provide_runtime_stability_from_recovery_records` e
`provide_runtime_stability_from_prescription_baseline` espongono tre nuovi
parametri keyword opzionali:

| Parametro | Default | Significato |
| --- | --- | --- |
| `enable_reported_problems_projection` | `False` | Solo `True` abilita il lookup. |
| `reported_problems_projection_id` | `None` | ID esatto della proiezione già persistita. |
| `projection_database_path` | `None` | Percorso del database SQLite esistente. |

Con il flag disabilitato il bridge restituisce l'input senza aprire SQLite.
Con il flag abilitato `runtime_reported_problems_bridge.py` valida il contesto,
carica la proiezione per ID, verifica metadata e payload tramite il repository
e controlla che soggetto e riferimento completo della sessione coincidano.
Il database deve esistere e l'ID deve risolversi; altrimenti la chiamata fallisce
senza cercare una proiezione alternativa o generare una nuova evidenza.

La proiezione viene inserita nell'input immutabile passato al provider puro.
I controlli canonici su finestra degli eventi, cutoff, stato del canale e
safety signal restano nella valutazione stability: una proiezione incompleta
o riferita a una finestra diversa conserva `INSUFFICIENT_DATA`.

Questo collegamento aggiunge la lettura al confine runtime esplicito. Non
attiva `backend/main.py`, non interpreta eventi e non pubblica un final outcome.
