# MAINTAIN_PLAN recovery baseline contract

Ultimo aggiornamento: 11 ottobre 2026

`runtime_recovery_baseline_capture.py` conserva il recovery che il chiamante
dichiara essere stato usato per comunicare una prescrizione. Non cerca il
record più recente, non ricalcola l'analyzer e non converte numeri Garmin in
categorie.

La baseline è valida solo quando contiene:

- lo stesso `subject_ref` della `PrescriptionSnapshot` persistita;
- il riferimento esatto a snapshot, decisione e attestazione di uso;
- `observed_at`, `assessed_at` e `captured_at` timezone-aware;
- il riferimento alla sorgente recovery e la provenance dell'analyzer;
- l'output JSON deterministico dell'analyzer, con `level` esplicito;
- la versione dell'analyzer vincolata all'hash dei suoi sorgenti.

`LOW`, `MODERATE`, `HIGH` e `CRITICAL` vengono accettati solo se presenti nel
risultato esplicito dell'analyzer. `UNKNOWN` resta `NOT_ASSESSABLE` con il
campo mancante canonico `baseline_assessment.category`.

La persistenza è append-only e ammette una sola baseline per snapshot. Un retry
semanticamente identico restituisce la riga già conservata; un retry con
contenuto diverso fallisce senza sovrascrivere la baseline.

La cattura è opt-in, non viene importata da `backend/main.py` e non attiva la
shadow chain. La migration 12 crea solo la tabella isolata
`maintain_plan_recovery_baselines`.
