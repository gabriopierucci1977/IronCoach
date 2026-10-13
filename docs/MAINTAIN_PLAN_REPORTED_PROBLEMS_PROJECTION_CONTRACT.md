# MAINTAIN_PLAN reported-problems projection contract

`runtime_reported_problems_capture.py` conserva una proiezione canonica già
costruita dal chiamante. Non legge il log degli eventi, non interpreta testo
libero e non calcola automaticamente safety signal o risultato.

La proiezione è validata con `validate_projection_structure`, deve riferire una
sessione `actual-session` già persistita e il suo `subject_ref` deve coincidere
con quello della sessione. La migration 14 aggiunge la tabella
`maintain_plan_reported_problems_projections` con metadata scalari verificabili
e payload tipizzato serializzato.

La persistenza è append-only e default-off: stesso `projection_id` e payload
identico sono un retry idempotente; lo stesso ID con contenuto diverso viene
rifiutato senza sovrascrittura. Nuove proiezioni devono usare un ID distinto.
Il modulo di cattura non è collegato a `backend/main.py`.

## Consumo runtime opt-in

`runtime_reported_problems_bridge.py` carica una sola proiezione persistita per
ID esplicito e la inserisce in un `GeneralStabilityInput` validato. Il bridge
è richiamato dai due ingressi `provide_runtime_stability_from_*` dell'adapter
recovery quando `enable_reported_problems_projection=True`; il chiamante deve
fornire anche `reported_problems_projection_id` e `projection_database_path`.

Soggetto e riferimento completo della sessione devono coincidere con il
contesto corrente. ID mancante o sconosciuto, database inesistente, ownership
incoerente e metadata alterati interrompono la chiamata. Una proiezione già
presente nell'input non viene sovrascritta. Il bridge non sceglie la proiezione
più recente e non produce nuovo contenuto.

La validità temporale e la disponibilità della proiezione sono valutate dal
servizio stability esistente. Una finestra diversa o controlli del canale
incompleti non diventano automaticamente `NO_KNOWN_ISSUE` o `STABLE`.
Con il flag disattivato non avviene alcun accesso al database.
