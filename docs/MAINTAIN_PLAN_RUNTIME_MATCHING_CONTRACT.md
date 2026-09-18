# Contratto normativo — runtime matching `PrescriptionSnapshot` / `ActualSession`

**Stato:** normativo contract-first; decisioni runtime approvate, implementazione assente

**Perimetro:** futura migrazione additiva v8; questo slice è solo documentazione

**Policy:** `maintain-plan-matching/1.0.0-draft`

## 1. Scopo e non-obiettivi

Questo documento definisce il futuro boundary che collega snapshot e sessioni
persistiti. Integra il [contratto outcome](MAINTAIN_PLAN_OUTCOME_CONTRACT.md),
il [contratto ActualSession](MAINTAIN_PLAN_RUNTIME_ACTUAL_SESSION_CONTRACT.md)
e il [contratto ownership](MAINTAIN_PLAN_SUBJECT_OWNERSHIP_CONTRACT.md). Le
invarianti più restrittive di ownership, immutabilità e append-only prevalgono.

Il boundary non esegue evaluation, report, learning, ripianificazione, Decision
Memory o Coach Engine. Questo documento non implementa codice runtime,
`schema.py`, migrazioni, repository o wiring di produzione.

## 2. Due invocazioni obbligatorie e loro ordine

Il solo flag futuro è `IRONCOACH_MAINTAIN_PLAN_MATCHING_ENABLED`, default
`false`, con parsing fail-closed. Flag falso/invalido e `--dry-run` vietano
apertura del repository, discovery e scritture.

Dopo **ogni sincronizzazione attività completata con successo**, il boundary
riceve il `SynchronizationCoverage` autorevole del §3 e, in quest'ordine:

1. persiste tutte le nuove `ActualSession` e completa il relativo commit;
2. esegue il percorso **session-driven** per ciascuna sessione coperta, ordinata
   per `(start, session_id UTF-8)`;
3. esegue il percorso **prescription/window-driven** per ciascuno snapshot
   rilevante la cui finestra è ormai chiusa, ordinato per
   `(scheduled_window.end, prescription_snapshot_id UTF-8)`;
4. committa gli artefatti di matching prima di qualsiasi consumer downstream.

Un sync fallito, parziale o best-effort degradato a warning non invoca nessuno
dei due percorsi. Il secondo percorso non dipende dalla presenza di una nuova
attività: è il trigger richiesto per una prescrizione scaduta senza sessione.
L'ordine session-first consente al percorso window-driven di rileggere i
risultati appena committati; non è un ranking né un tie-break.

## 3. Scope autorevole e limitato della sincronizzazione

### 3.1 Contratto richiesto

Il runtime corrente espone `GarminLiveSyncResult.start_date`, `end_date` e
`source_checked_at`, ma non persiste un intervallo timezone-aware associato al
soggetto. v8 DEVE quindi introdurre questo input immutabile prima di abilitare
il matching:

```yaml
synchronization_coverage:
  sync_scope_id: string
  artifact_version: "1"
  source: string
  subject_ref: string
  coverage_start: datetime       # inclusivo, timezone-aware
  coverage_end: datetime         # esclusivo, timezone-aware
  completed_at: datetime         # timezone-aware
  completion_status: SUCCEEDED
  source_request:
    start_date: string
    end_date: string
    timezone: string
  provenance: object
```

L'adapter crea questo artefatto soltanto dopo che fetch, conversione e
persistenza sono riusciti. `coverage_start` è l'inizio di `start_date` e
`coverage_end` l'inizio del giorno successivo a `end_date`, nel timezone
esplicito della richiesta sorgente; conversioni UTC preservano gli stessi
istanti. Sono vietati `now`, lookback inventati, grace period, lifecycle o
watermark dedotti. `coverage_start < coverage_end`; source, date e timezone
devono coincidere con la richiesta realmente completata.

`sync_scope_id` usa la canonicalizzazione del §9 sulla preimage:

```json
{"artifact_version":"1","completed_at":"<RFC3339>","coverage_end":"<RFC3339>","coverage_start":"<RFC3339>","source":"<source>","subject_ref":"<subject_ref>"}
```

Namespace: `maintain-plan:sync-coverage:v1:sha256:<64 hex>`. Retry con stesso
ID e contenuto equivalente restituisce la riga esistente; contenuto divergente
fallisce. Nessun matching è consentito usando il solo state file legacy.

### 3.2 Relevance scope

Uno snapshot same-subject è rilevante per uno scope se e soltanto se la sua
finestra interseca l'intervallo coperto:

```text
snapshot.scheduled_window.start < coverage_end
AND snapshot.scheduled_window.end >= coverage_start
```

La query fisica recupera soltanto righe con `subject_ref` esattamente uguale e
potenzialmente appartenenti allo scope; poiché la finestra è in `payload_json`,
v8 DEVE fornire colonne indicizzate immutabili `scheduled_window_start` e
`scheduled_window_end`, duplicate e validate byte-per-byte rispetto al payload.
Così il repository delimita autorevolmente le righe prima della decodifica,
senza scansionare tutta la storia.

Ogni riga nel perimetro deve essere decodificata e validata totalmente. Una
riga corrotta, metadata/payload incoerenti, timestamp non confrontabile o
ownership invalida causa errore tecnico e rollback dell'intero scope; non può
essere omessa per ottenere un falso singleton. Snapshot `NULL`/cross-subject
non sono candidati. Non esistono filtri per lifecycle, discipline,
composition, durata o similarità.

La finestra delimita lo **scope**, non elimina evidence. Tutti gli snapshot
rilevanti vengono passati al matcher: anche uno snapshot per cui la sessione è
fuori finestra resta evidence e conduce a `CONFIRMATION_REQUIRED`. Nessun
periodo storico estraneo allo scope partecipa alla cardinalità.

## 4. Percorso session-driven e discovery

Per una sessione `S` coperta dallo scope, il repository rilegge `S`, verifica
che `S.subject_ref == scope.subject_ref` byte-per-byte e carica gli snapshot
rilevanti del §3. Li ordina per ID UTF-8. Senza direct ID risolto invoca
`backend.maintain_plan.matching_service.match(snapshot, (S,))` separatamente
per ogni snapshot, senza algoritmo alternativo:

- zero snapshot produce `MatchingDiscoveryResult.ZERO`, non un
  `MatchingResult`;
- uno produce `SINGLE` e il `MatchingResult` puro;
- almeno due produce `MULTIPLE`; gli esiti per-snapshot sono evidence
  transitoria, non risultati pubblicati, e nessun mapping viene persistito.

`ZERO` e `MULTIPLE` hanno `CONFIRMATION_REQUIRED`. Nessun primo elemento,
ranking, fuzzy match o tie-break è ammesso. Un direct ID esplicito, valido,
same-subject e risolto univocamente seleziona lo snapshot indicato anche in un
set multiplo. Un ID ben formato ma dangling, non verificabile, duplicato o
contraddittorio è un esito `CONFIRMATION_REQUIRED`; un ID malformato o
cross-subject è errore tecnico.

```yaml
matching_discovery_result:
  discovery_result_id: string
  artifact_version: "1"
  sync_scope_ref: string
  status: ZERO | SINGLE | MULTIPLE
  resolution_status: MATCHED | CONFIRMATION_REQUIRED | NOT_EVALUABLE
  actual_session_ref: string
  subject_ref: string
  candidate_snapshot_refs: [string]
  candidate_evidence: [object]
  direct_id_evidence: [object]
  previous_discovery_result_ref: string | null
  discovery_confirmation_ref: string | null
  matching_result_ref: string | null
  prescription_mapping_ref: string | null
  discovered_at: datetime
  provenance: object
```

Candidate ed evidence hanno uguale cardinalità e ordine. `ZERO` richiede
entrambe vuote, `SINGLE` una, `MULTIPLE` almeno due. I riferimenti result e
mapping sono entrambi presenti soltanto per `MATCHED`. Un discovery derivato
da risposta ha entrambi `previous_discovery_result_ref` e
`discovery_confirmation_ref`; quello iniziale li ha entrambi null.

## 5. Percorso prescription/window-driven: nessuna sessione catturata

Per ogni snapshot rilevante con `scheduled_window.end < coverage_end`, il
boundary rilegge le sessioni same-subject dello **stesso scope** e già
persistite, ordinate per `(start, session_id UTF-8)`, quindi invoca una sola
volta il matcher esistente con lo snapshot e l'intera tupla. Non crea un
`MatchingDiscoveryResult`: `ZERO` in discovery significa zero snapshot per
una sessione esistente e non deve essere confuso con zero sessioni per uno
snapshot.

Con tupla vuota il matcher produce il normale `MatchingResult` snapshot-centric
con `status=CONFIRMATION_REQUIRED`, `candidate_session_refs=[]`, evidence
vuota, mapping null e warning normativo:
“Non ho trovato un'attività associabile alla seduta prevista”. Si usa quindi la
confirmation esistente, che possiede esattamente un `matching_result_ref` e un
`prescription_snapshot_ref`, per chiedere: non svolta, svolta ma non
sincronizzata, oppure associazione manuale. Non si presume che la seduta non
sia stata svolta.

L'identità del tentativo include `sync_scope_ref` (§9). Ripetere lo stesso
scope produce lo stesso ID e non duplica richiesta o risultato. Uno scope
successivo produce un nuovo risultato append-only e può includere una sessione
tardiva; non modifica né cancella il precedente. Prima di creare il caso zero,
il repository verifica che nello scope non esista già per quello snapshot un
risultato con candidate session o un mapping prodotto dal percorso
session-driven. Questa verifica e l'insert sono atomici. Una risposta chiude la
richiesta tramite un nuovo record append-only; non aggiorna il risultato.

## 6. Confirmation discovery dedicata

`maintain_plan_confirmations` non è riusata per `ZERO`/`MULTIPLE`: richiede un
singolo `MatchingResult`, uno snapshot e seleziona una sessione. v8 introduce
invece `maintain_plan_matching_discovery_confirmations`:

```sql
CREATE TABLE maintain_plan_matching_discovery_confirmations (
    discovery_confirmation_id TEXT PRIMARY KEY,
    artifact_version TEXT NOT NULL CHECK (artifact_version = '1'),
    request_ref TEXT REFERENCES maintain_plan_matching_discovery_confirmations(discovery_confirmation_id),
    discovery_result_ref TEXT NOT NULL REFERENCES maintain_plan_matching_discoveries(discovery_result_id),
    sync_scope_ref TEXT NOT NULL REFERENCES maintain_plan_sync_coverages(sync_scope_id),
    subject_ref TEXT NOT NULL,
    record_kind TEXT NOT NULL CHECK (record_kind IN ('REQUEST','ANSWER')),
    answer_type TEXT CHECK (answer_type IN ('SELECT_SNAPSHOT','NO_RELEVANT_PRESCRIPTION','DONT_KNOW')),
    selected_snapshot_ref TEXT REFERENCES maintain_plan_prescription_snapshots(prescription_snapshot_id),
    actor TEXT,
    occurred_at TEXT NOT NULL,
    payload_schema_version TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    CHECK (
      (record_kind='REQUEST' AND request_ref IS NULL AND answer_type IS NULL AND selected_snapshot_ref IS NULL AND actor IS NULL)
      OR
      (record_kind='ANSWER' AND request_ref IS NOT NULL AND answer_type IS NOT NULL AND actor IS NOT NULL
       AND ((answer_type='SELECT_SNAPSHOT' AND selected_snapshot_ref IS NOT NULL)
            OR (answer_type<>'SELECT_SNAPSHOT' AND selected_snapshot_ref IS NULL)))
    )
);
```

Ogni `REQUEST` punta a un discovery irrisolto `ZERO` o `MULTIPLE`; al massimo
una request logica è consentita dalla sua identità deterministica, non tramite
update. Ogni `ANSWER` punta alla request, allo stesso discovery e scope. Per
`MULTIPLE`, `SELECT_SNAPSHOT` deve scegliere esattamente un membro del candidate
set congelato. Per `ZERO`, può scegliere soltanto uno snapshot same-subject la
cui finestra appartiene allo stesso scope, riletto e validato; ciò rappresenta
una correzione manuale dell'assenza iniziale, non amplia lo scope. In entrambi i
casi snapshot, sessione, discovery, confirmation e scope devono avere lo stesso
`subject_ref`; mismatch o dangling ref causa rollback.

`SELECT_SNAPSHOT` crea un nuovo discovery `SINGLE`, ricollega la confirmation
di risposta e solo allora invoca il matcher. `NO_RELEVANT_PRESCRIPTION` e
`DONT_KNOW` creano un nuovo discovery con lo stesso candidate set e
`NOT_EVALUABLE`, senza result o mapping. Una seconda risposta alla stessa
request è un conflitto, salvo retry byte-equivalente dello stesso ID.

Request, answer e discovery derivato sono inseriti nella stessa
`BEGIN IMMEDIATE` nell'ordine delle foreign key. Payload e colonne duplicate
devono coincidere. Trigger `BEFORE UPDATE` e `BEFORE DELETE` abortiscono sempre;
foreign key sono attive, nessun cascade è ammesso. Non vi è lock durante
l'interazione umana.

## 7. Persistenza v8 e atomicità

v8 aggiunge, senza cambiare v1–v7:

- `maintain_plan_sync_coverages`, con colonne del §3, FK ownership applicativa,
  indici `(subject_ref, coverage_start, coverage_end)` e trigger append-only;
- `scheduled_window_start/end` agli snapshot tramite nuova tabella indice
  immutabile 1:1 (non alterazione distruttiva), FK allo snapshot e trigger
  append-only;
- `maintain_plan_matching_discoveries`, con colonne del §4 e FK a scope,
  sessione, discovery precedente, confirmation discovery, result e mapping;
- la tabella confirmation discovery del §6, indici per ogni FK e trigger
  append-only.

Ogni unit of work apre `BEGIN IMMEDIATE` **prima** delle riletture, verifica
payload, metadata, ownership, scope e retry, esegue il matcher puro e inserisce
gli artefatti nell'ordine imposto dalle FK. Result, mapping e discovery
`MATCHED` diventano visibili nello stesso commit. Errore, race divergente,
corruzione o insert parziale eseguono rollback completo. Un retry equivalente
restituisce i record esistenti; nessun upsert distruttivo è ammesso.

## 8. Lifecycle degli output

Un `MatchingResult` `MATCHED` richiede un mapping. `CONFIRMATION_REQUIRED` e
`NOT_EVALUABLE` richiedono mapping null. Soltanto una risposta umana valida
produce un nuovo risultato `MATCHED` e mapping con
`resolution_method=ATHLETE_CONFIRMATION`, actor, timestamp e confirmation ref.
«Non svolta», «non sincronizzata» e «non lo so» non producono mapping.

Gli artefatti precedenti rimangono immutabili. Evaluation e consumer possono
partire soltanto da un mapping persistito univoco. Un direct ID risolto prova
la relazione; differenze di finestra o composizione restano future differenze
di aderenza.

## 9. Identità canoniche e vettori

Ogni preimage usa JSON con `ensure_ascii=False`, `sort_keys=True`, separatori
`(',', ':')`, UTF-8 strict senza BOM e nessuna normalizzazione Unicode. Liste
ordinate usano byte UTF-8 degli ID. SHA-256 è hex lowercase.

Discovery iniziale:

```json
{"artifact_version":"1","direct_evidence_ids":[],"matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","prescription_snapshot_ids":["<ordinati>"],"session_id":"<id>","subject_ref":"<ref>","sync_scope_id":"<id>"}
```

Il discovery derivato aggiunge `confirmation_id` e
`previous_discovery_result_id`. Namespace
`maintain-plan:matching-discovery:v1:sha256:<hash>`.

Matching result (valido per entrambi i percorsi):

```json
{"confirmation_id":null,"direct_evidence_ids":[],"matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","prescription_snapshot_id":"<id>","session_ids":["<ordinati, anche vuoto>"],"sync_scope_id":"<id>"}
```

Namespace `maintain-plan:matching-result:v1:sha256:<hash>`. Il mapping mantiene
la preimage esistente con confirmation, snapshot, sessione e resolution method;
non esiste mapping nel caso zero sessioni.

Confirmation discovery request:

```json
{"artifact_version":"1","discovery_result_id":"<id>","record_kind":"REQUEST","sync_scope_id":"<id>"}
```

Answer: stessa preimage con `record_kind:"ANSWER"`, `request_id`, `answer_type`
e `selected_snapshot_id` (null se non selettiva). Namespace
`maintain-plan:matching-discovery-confirmation:v1:sha256:<hash>`.

Vettore normativo per il percorso zero-sessioni (`é` è U+00E9):

```text
preimage: {"confirmation_id":null,"direct_evidence_ids":[],"matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","prescription_snapshot_id":"prescrizione-é","session_ids":[],"sync_scope_id":"sync-é"}
SHA-256: 18f679e4657f2976e75e2ede0b63c6c8ebac21f571a86867d1a1fe0d97043856
matching_result_id: maintain-plan:matching-result:v1:sha256:18f679e4657f2976e75e2ede0b63c6c8ebac21f571a86867d1a1fe0d97043856
```

## 10. Esempi normativi

### 10.1 Sessione appena fuori finestra

Lo scope copre `[2026-09-17T00:00+02:00, 2026-09-19T00:00+02:00)`; uno
snapshot ha finestra 17 settembre 08:00–09:00 e la sessione inizia alle 09:01.
La finestra interseca lo scope, quindi lo snapshot è candidato. Il matcher
conserva il check temporale falso e produce `CONFIRMATION_REQUIRED`; non viene
degradato a discovery `ZERO`.

### 10.2 Storia non pertinente

Nello stesso database esistono snapshot di giugno e settembre. Uno scope del
17–18 settembre include soltanto finestre che lo intersecano. Gli snapshot di
giugno non entrano nel conteggio e non causano `MULTIPLE`; nessun lifecycle o
grace period è inferito.

### 10.3 Finestra chiusa senza attività

Dopo un sync riuscito che copre fino all'inizio del 19 settembre, una finestra
terminata il 18 non ha sessioni coperte. Dopo il percorso session-driven, quello
window-driven chiama `match(snapshot, ())`, persiste il `MatchingResult`
`CONFIRMATION_REQUIRED` e la request esistente snapshot-centric. Un retry dello
stesso scope non duplica nulla.

### 10.4 Discovery MULTIPLE

Una sessione e due snapshot rilevanti producono discovery `MULTIPLE` e una
request nella tabella dedicata. La risposta seleziona uno dei due ID congelati;
nella stessa transazione vengono verificati ownership e FK e nasce un nuovo
discovery `SINGLE`. La vecchia discovery e la request non sono aggiornate.

## 11. Errori, upgrade e decisioni residue

Sono errori tecnici: scope assente/non riuscito/incoerente; righe nel perimetro
corrotte; ownership discordante; direct evidence malformata; timestamp naive;
FK dangling; payload/colonne discordanti; risposta non appartenente al set o
allo scope; retry divergente. Sono esiti di dominio: zero/più snapshot,
zero/più sessioni, fuori finestra, mismatch, direct ID ben formato ma
irrisolto, e risposta non risolutiva.

DB v1–v7 non abilita questo boundary. La futura v8 è additiva, nasce senza
backfill storico e richiede tutte le tabelle, indici, trigger e checksum
coerenti. Record legacy con ownership nulla restano ineleggibili.

**Non resta alcuna decisione normativa bloccante.** Restano lavoro
implementativo: definire modelli/codec, migrazione v8, repository, adapter dello
scope, flag/wiring e test di race/rollback. Fino ad allora tutto il comportamento
descritto resta non implementato e disabilitato.
