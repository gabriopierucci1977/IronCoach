# MAINTAIN_PLAN recovery candidate set contract

`runtime_recovery_candidate_capture.py` conserva il candidate set recovery
costruito dal chiamante per una sessione reale. Riceve solo record già scoping,
la loro provenance, la sessione, il soggetto e il cutoff temporale. Non legge
l'archivio Garmin, non seleziona il follow-up e non deduce categorie da numeri.

## Identità e validazione

Il chiamante fornisce un `candidate_set_id` stabile. Il payload deve contenere
un `VersionedArtifactRef` di tipo `actual-session`, un soggetto non vuoto,
timestamp timezone-aware, cutoff non precedente a `captured_at`, provenance
valida e assessment con timestamp entro il cutoff. La categoria resta valida
solo quando è esplicita; dati mancanti restano `CategoryMissingness.MISSING`.

La persistenza richiede che la sessione esista già e che il suo `subject_ref`
coincida con quello del candidate set. La migration 13 aggiunge la tabella
`maintain_plan_recovery_candidate_sets`, con metadata verificabili e payload
serializzato. Un retry con lo stesso ID e contenuto identico restituisce il
payload già salvato; un contenuto diverso viene rifiutato senza sovrascrittura.

## Attivazione

`RuntimeRecoveryCandidateSetCapture` è default-off. Quando è abilitato, valida
prima il candidate set e apre SQLite solo per l'acquisizione append-only. Il
bridge stability può poi ricevere il candidate set insieme alla baseline
persistita; la valutazione e la selezione del follow-up restano pure.
