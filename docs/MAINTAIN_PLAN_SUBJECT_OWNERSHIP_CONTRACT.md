# Contratto normativo — Subject ownership binding

**Stato:** normativo e implementato  
**Perimetro schema:** `SCHEMA_VERSION = 7`  
**Artefatti:** `PrescriptionSnapshot`, `ActualSession`, `PrescriptionMapping`

## 1. Scopo e autorità

`subject_ref` è il binding di ownership immutabile comune alla prescrizione e
alla sessione reale. Deriva **esclusivamente** da
`context["athlete"]["source_id"]`, cioè dalla stessa identità atleta
autorevole usata dalla cattura runtime di `ActualSession`.

È vietato derivarlo, sostituirlo o recuperarlo da `activity_id`, dal
`source_id` di un'attività, `file_hash`, `record_id`, `decision_id`,
`workout_id`, nome atleta o qualunque altro identificativo tecnico. Non
esistono fallback o inferenze.

## 2. Forma e validazione

Il valore è una stringa opaca, esplicita, non vuota, non composta unicamente
da whitespace, case-sensitive e codificabile integralmente come UTF-8 strict.
La rappresentazione viene conservata e confrontata byte-for-byte: sono vietati
trim, case folding, normalizzazione Unicode, cleanup e coercizioni. Unicode
valido è ammesso; un surrogate isolato è invalido.

Ogni nuovo `PrescriptionSnapshot` e `ActualSession` DEVE contenere un
`subject_ref` valido. Modello, codec e repository lo conservano senza
trasformazioni; le colonne v7 devono corrispondere esattamente al payload.

## 3. Associazione e mismatch

Prima di persistere un `PrescriptionMapping`, il repository DEVE risolvere
entrambi gli artefatti e verificare che i rispettivi `subject_ref` siano
presenti, validi e identici con confronto esatto. Binding mancante, malformato
o discordante è un errore fail-closed e non produce alcuna scrittura. Nessuna
associazione cross-athlete è permessa.

Questo controllo non modifica il matcher puro, le sue finestre, i tie-break o
gli stati. Non autorizza candidate discovery runtime né sintetizza
`returned_prescription_id`.

## 4. Persistenza, retry e idempotenza

La migrazione v7 è append-only: aggiunge una colonna `subject_ref` nullable a
ciascuna delle due tabelle per preservare i record storici, indici dedicati e
guardie sugli insert futuri. Non modifica le migrazioni v1–v6 né i relativi
checksum e non esegue backfill.

Per i nuovi record il repository valida il binding prima dell'insert. Un retry
è idempotente soltanto se il contenuto semantico, incluso `subject_ref`, è
equivalente secondo le regole già definite per l'artefatto. Lo stesso ID o lo
stesso `decision_id` con binding differente è un conflitto divergente: rollback
e nessun overwrite.

## 5. Legacy v1–v6

I payload storici privi del campo restano decodificabili come
`subject_ref=None` e le righe migrate conservano `NULL`. Questa tolleranza è
riservata alla lettura. Un artefatto legacy senza binding non è eleggibile per
mapping e non viene associato automaticamente. È vietato qualunque backfill
euristico.

## 6. Confini dello slice

Questo slice introduce esclusivamente ownership comune, persistenza v7,
validazione fail-closed e wiring dell'identità autorevole nella cattura della
prescrizione. Restano fuori scope: modifiche al matcher, candidate discovery,
evaluation, reporting, learning, modifica del piano e Coach Engine.

## 7. Boundary del futuro matching ridotto

Il futuro [contratto runtime di matching](MAINTAIN_PLAN_RUNTIME_MATCHING_CONTRACT.md)
usa questo binding senza modificarlo. Prima della candidate evaluation deve
validare ownership sull'intero scope: binding mancante, malformato, non
codificabile o discordante, compreso quello raggiunto tramite direct ID,
fallisce chiuso senza ripiegare su un sottoinsieme. Un direct ID non supera mai
ownership.

L'unico mapping automatico ammesso dal boundary ridotto conserva unicità
bidirezionale fra snapshot e sessione. Prima dell'insert il repository futuro
deve aprire `BEGIN IMMEDIATE`, rileggere sotto la medesima transazione entrambi
gli artefatti, entrambi i `subject_ref` e i due lati del mapping, quindi
ricontrollare tutte le invarianti. Conflitto o modifica concorrente impone
rollback; un retry semanticamente identico è idempotente e non duplica il
mapping. Questa sezione non introduce schema, migrazioni, DDL o wiring.

Quando è fornito l'input separato `DirectIdEvidence`, il suo `session_id` deve
risolvere una `ActualSession` valida nello scope; ownership è verificata
esclusivamente sui `subject_ref` persistiti della sessione e dello snapshot
risolto. Evidence cross-subject o con envelope persistito corrotto fallisce
l'intero scope. Nessun campo dell'evidence crea, sostituisce o normalizza un
`subject_ref`.
