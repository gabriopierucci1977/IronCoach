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
Il modulo non è collegato a `backend/main.py` e non modifica la valutazione
stability esistente.
