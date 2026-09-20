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

Il boundary che potrà usare questo binding per discovery e associazione è
definito separatamente nel
[contratto runtime matching](MAINTAIN_PLAN_RUNTIME_MATCHING_CONTRACT.md), che
estende la stessa uguaglianza byte-per-byte allo scope di sincronizzazione e
alle confirmation discovery e prescrive che v7→v8 indicizzi
transazionalmente ogni snapshot ownership-bound valido, lasciando non
indicizzati quelli legacy con ownership nulla. Un direct ID dichiarato ma
dangling, ambiguo o cross-subject fallisce chiuso. Quando è valido,
`DIRECT_ID` resta source/evidence della discovery mentre il mapping usa l'enum
esistente `AUTOMATIC`. Request e answer sono
rivalidate in transazioni separate senza lock durante l'attesa; il
presente documento non ne abilita il wiring. La reconciliation tardiva usa una
answer relation dedicata con FK alla propria request immutabile, membership
same-subject esatta e closure append-only. L'expiry pre-processing committa
prima di entrambi i percorsi. Il successore zero-sessioni è il gruppo
same-subject immediatamente seguente per start canonico (anche overlapping o
end/start adiacente); una reconciliation usa invece un boundary proprio al
primo gruppo con start successivo al suo `created_at` committato, eventualmente
scoperto da una sync futura. Expiry e reconciliation tardiva rivalidano inoltre
ownership byte-per-byte di snapshot, subject, scope e ogni
sessione congelata sotto `BEGIN IMMEDIATE`; nessuna sessione cross-subject può
essere offerta o selezionata e la guardia opera prima di entrambi i percorsi.

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

### Addendum normativo v8 — overlap, expiry e origine confirmation

La verifica ownership v8 è globale rispetto agli scope sovrapposti: la guard
pre-matcher usa `actual_session_ref` e le catene autorevoli, non
`sync_scope_ref`, per stabilire se una relazione è già gestita. Il fingerprint
semantico include subject, payload canonici, finestre, candidate e direct
evidence, ma esclude la provenance dello scope.

I gruppi same-subject sono processati cronologicamente e in ordine ID UTF-8; se
la request appena creata per A ha il successore B già noto e raggiunto, expiry e
creazione di A committano nella stessa `BEGIN IMMEDIATE` prima di B. Una sidecar
di late-session reconciliation richiede answer dedicata e discovery nulla;
una sidecar discovery richiede discovery e vieta la reconciliation answer.
Ownership uguale non rende intercambiabili relazioni diverse: una sessione
same-subject già trattata per B viene esclusa dalla tupla di A, ma non prova che
A sia gestito. Se A non possiede propri mapping/discovery, result/request
zero-sessioni, reconciliation o terminali e la tupla residua è vuota, deve
nascere l'unico outcome zero-sessioni di A.

La futura v8 aggiunge inoltre una sidecar result/snapshot 1:1 con FK immediate a
entrambi gli artefatti e `subject_ref` canonico. L'upgrade deve popolarla
transazionalmente per ogni result eleggibile v7; ogni write successiva inserisce
result e sidecar nella stessa unit of work. Riferimenti mancanti, dangling o
cross-subject, digest divergenti e cardinalità diversa da 1:1 rollbackano.
Lookup e guard usano la relazione e il suo indice
`(prescription_snapshot_ref,matching_result_ref)`, non estrazione JSON né una
colonna inesistente sulla tabella result.

### Addendum normativo v8 — ownership e unicità bidirezionale

La tupla sessioni consegnata al matcher per uno snapshot contiene soltanto
record con `subject_ref` byte-identico e viene validata interamente prima della
chiamata unica. La futura v8 impone `UNIQUE(actual_session_ref)` e
`UNIQUE(prescription_snapshot_ref)` sui mapping; la migrazione rifiuta e
rollbacka duplicati legacy in entrambe le direzioni. Nessun binding ownership
consente di scegliere implicitamente tra più sessioni compatibili.
