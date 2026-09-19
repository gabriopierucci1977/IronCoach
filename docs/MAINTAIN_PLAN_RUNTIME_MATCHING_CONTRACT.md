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

### 3.2 Set synchronization-wide ed evidence adiacente limitata

Il set **synchronization-wide**, usato esclusivamente per enumerare gli
snapshot del percorso prescription/window-driven, è l'unione deduplicata di
(a) ogni snapshot same-subject la
cui finestra interseca l'intervallo coperto e (b), per **ciascuna**
`ActualSession` coperta, i vicini temporali immediati same-subject attorno a
`session.start`. La parte (a) usa:

```text
snapshot.scheduled_window.start < coverage_end
AND snapshot.scheduled_window.end >= coverage_start
```

Per la parte (b), il predecessore è ogni riga con il massimo
`scheduled_window_end < session.start`; il successore è ogni riga con il minimo
`scheduled_window_start > session.start`. Tutti gli istanti sono canonical UTC
RFC 3339 prima del confronto. **Tutte** le righe a pari timestamp
estremo sono incluse. Finestre che contengono o toccano esattamente lo start
sono già evidence ordinaria; i confronti stretti non diventano una tolleranza.
Le query usano esclusivamente l'indice v8 e ordinano per estremi finestra e poi
`prescription_snapshot_id` UTF-8. Sono al massimo due gruppi di confine per
sessione, non ranking: sono vietati grace period, distanze inventate e scansione
della storia nel matcher.

La query fisica recupera soltanto righe indice con `subject_ref` esattamente
uguale che soddisfano (a) o (b). Ogni riga indice selezionata e il relativo
snapshot devono essere riletti e decodificati totalmente. Riga indice/snapshot
mancante, timestamp malformato, finestra invalida, ownership o duplicati
incoerenti causano errore tecnico e rollback dell'intero scope: non possono
essere omessi per ottenere un falso singleton.

Ogni riga nel perimetro deve essere decodificata e validata totalmente. Una
riga corrotta, metadata/payload incoerenti, timestamp non confrontabile o
ownership invalida causa errore tecnico e rollback dell'intero scope; non può
essere omessa per ottenere un falso singleton. Snapshot `NULL`/cross-subject
non sono candidati. Non esistono filtri per lifecycle, discipline,
composition, durata o similarità.

L'intersezione delimita lo scope ordinario; i soli vicini immediati ne sono
l'estensione strutturalmente limitata. Tutti vengono passati al matcher: anche
un vicino appena oltre una boundary di sincronizzazione conserva il check
temporale falso e conduce a `CONFIRMATION_REQUIRED`. Nessun altro periodo
storico partecipa alla cardinalità. Questo insieme non è mai passato in blocco
a una sessione e non determina la cardinalità della sua discovery.

### 3.3 Candidate set per-sessione

Per ogni sessione coperta `S` il repository costruisce un set distinto,
same-subject e deduplicato, composto soltanto da: (a) lo snapshot target di un
direct ID dopo validazione completa e risoluzione univoca, se presente; (b)
tutte le finestre che contengono `S.start`, con predicate inclusivo
`start <= S.start AND end >= S.start`; (c) l'intero gruppo predecessore con il
massimo `scheduled_window_end < S.start` e l'intero gruppo successore con il
minimo `scheduled_window_start > S.start`. Tutti gli exact tie del massimo o
minimo sono inclusi. Una finestra zero-length contiene la sessione quando i tre
istanti coincidono.

Le query sono separate per `S`, usano gli indici v8 e ordinano il risultato
deduplicato per `prescription_snapshot_id` byte UTF-8. La validazione strict,
le verifiche ownership/indice/payload e il rollback fail-closed del §3.2 si
applicano a ogni riga letta. I gruppi adiacenti conservano evidence
fuori-finestra, ma mantengono la cardinalità limitata; non sono tolleranza,
ranking o scansione storica. Il set synchronization-wide resta disponibile al
solo percorso senza sessione del §5 e non viene unito a questo set.

## 4. Percorso session-driven e discovery

Per una sessione `S` coperta dallo scope, il repository rilegge `S`, verifica
che `S.subject_ref == scope.subject_ref` byte-per-byte e carica **soltanto** il
candidate set proprio di `S` dal §3.3. Senza direct ID risolto invoca
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
  matching_confirmation_ref: string | null
  matching_result_ref: string | null
  prescription_mapping_ref: string | null
  discovered_at: datetime
  provenance: object
```

Candidate ed evidence hanno uguale cardinalità e ordine. `ZERO` richiede
entrambe vuote, `SINGLE` una, `MULTIPLE` almeno due. La matrice normativa
completa è:

| kind | resolution status | `matching_result_ref` | `prescription_mapping_ref` | confirmation mechanism |
|---|---|---|---|---|
| `ZERO` | `CONFIRMATION_REQUIRED` | null | null | discovery-specific §6 |
| `ZERO` | `NOT_EVALUABLE` (risposta non selettiva) | null | null | discovery-specific §6 |
| `SINGLE` | `MATCHED` | non-null | non-null | nessuna se automatico; existing MatchingResult confirmation se derivato |
| `SINGLE` | `CONFIRMATION_REQUIRED` | **non-null** | null | existing `maintain_plan_confirmations` sul result |
| `SINGLE` | `NOT_EVALUABLE` | non-null | null | risposta existing MatchingResult confirmation |
| `MULTIPLE` | `CONFIRMATION_REQUIRED` | null | null | discovery-specific §6 |
| `MULTIPLE` | `NOT_EVALUABLE` (risposta non selettiva) | null | null | discovery-specific §6 |

Ogni altra combinazione è vietata dai CHECK v8. Un discovery derivato da
risposta ha `previous_discovery_result_ref` e precisamente uno tra
`discovery_confirmation_ref` (solo origine `ZERO`/`MULTIPLE`) e
`matching_confirmation_ref` (solo origine `SINGLE`); quello iniziale ha tutti
e tre null. In particolare il result puro `CONFIRMATION_REQUIRED` di un
`SINGLE` non viene mai scollegato dalla discovery.

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

Prima di invocare il matcher, la stessa transazione cerca ogni testa di catena
discovery session-driven ancora `CONFIRMATION_REQUIRED` la cui sessione
appartiene allo scope e il cui candidate set congelato contiene lo snapshot.
Una tale relazione snapshot/sessione impone di saltare deterministicamente lo
snapshot (anche al retry): non nasce risultato automatico né mapping. Il check
segue il commit di tutte le discovery session-driven e precede qualsiasi insert
window-driven. Una risposta non selettiva continua a vietare il mapping; dopo
un `SELECT_SNAPSHOT` valido, soltanto il percorso confirmation-aware del §6 può
crearlo. I due percorsi non competono e resta un solo mapping per sessione.

## 6. Confirmation: discovery dedicata e SINGLE esistente

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
    UNIQUE(request_ref),
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
set congelato. Per `ZERO`, può scegliere soltanto uno snapshot same-subject
rilevante per lo stesso scope secondo il §3.2, riletto e validato; ciò rappresenta
una correzione manuale dell'assenza iniziale, non amplia lo scope. In entrambi i
casi snapshot, sessione, discovery, confirmation e scope devono avere lo stesso
`subject_ref`; mismatch o dangling ref causa rollback.

`SELECT_SNAPSHOT` è conferma umana autorevole: crea un nuovo discovery
`SINGLE`, ma **non** reinvoca il matcher automatico invariato. Nella stessa
transazione crea direttamente un nuovo `MatchingResult MATCHED` e un
`PrescriptionMapping` con `resolution_method=ATHLETE_CONFIRMATION`; entrambi
riferiscono la confirmation di risposta, actor e `occurred_at`. Il result
conserva senza alterazioni candidate/direct evidence e gli esiti
incompatibile/fuori-finestra della discovery originaria. La scelta prova la
relazione snapshot/sessione, non l'aderenza del workout.

`NO_RELEVANT_PRESCRIPTION` e
`DONT_KNOW` creano un nuovo discovery con lo stesso candidate set e
`NOT_EVALUABLE`, senza result o mapping. Una seconda risposta alla stessa
request è un conflitto, salvo retry byte-equivalente dello stesso ID.

Un `SINGLE` non usa questa tabella. Se il matcher puro produce
`CONFIRMATION_REQUIRED`, la discovery conserva quel `matching_result_ref` e
apre la normale `maintain_plan_confirmations` già riferita a result e snapshot.
La sessione `S` deve appartenere all'insieme dichiarato congelato del result;
una conferma associativa valida usa l'answer esistente (`MANUAL_ASSOCIATION`,
oppure `SELECT_CANDIDATE` quando `S` era offerta) come decisione umana
autorevole. Non riesegue il matcher. Precalcola gli ID, crea mapping
`ATHLETE_CONFIRMATION`, result `MATCHED` che cita answer/actor/timestamp e un
discovery derivato `SINGLE` che cita discovery precedente, nuovo result e
mapping tramite `matching_confirmation_ref`. Evidence e failure check puri,
incluso fuori-finestra/incompatibilità, restano immutati nel nuovo result. Una
risposta non associativa crea invece result `NOT_EVALUABLE` e discovery
derivato `SINGLE`, entrambi collegati all'answer, senza mapping. Ownership,
membership, append-only, retry equivalente e conflitto divergente sono gli
stessi vincoli del flusso discovery-specific.

Request, answer e discovery derivato sono inseriti nella stessa
`BEGIN IMMEDIATE`. Gli ID di mapping e result sono sempre precalcolati. Per
`SELECT_SNAPSHOT` l'ordine eseguibile è: **answer, mapping, result, sidecar
confirmation-resolution, discovery derivato**; il medesimo ordine vale per
una risposta associativa `SINGLE` sulla confirmation esistente. Per risposte
non associative è answer, result `NOT_EVALUABLE` quando il flusso è `SINGLE`,
poi discovery derivato; per `ZERO`/`MULTIPLE` è answer, discovery derivato.
Le verifiche e la ricerca di mapping/sessione
preesistente precedono gli insert. Payload e colonne duplicate devono
coincidere. Trigger `BEFORE UPDATE` e `BEFORE DELETE` abortiscono sempre;
foreign key sono attive, nessun cascade è ammesso. Non vi è lock durante
l'interazione umana.

## 7. Persistenza v8 e atomicità

v8 aggiunge, senza cambiare v1–v7:

- `maintain_plan_sync_coverages`, con colonne del §3, FK ownership applicativa,
  indici `(subject_ref, coverage_start, coverage_end)` e trigger append-only;
- `maintain_plan_snapshot_window_index(snapshot_ref TEXT PRIMARY KEY,
  subject_ref TEXT NOT NULL, scheduled_window_start TEXT NOT NULL,
  scheduled_window_end TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(snapshot_ref) REFERENCES maintain_plan_prescription_snapshots
  (prescription_snapshot_id), CHECK(scheduled_window_start <=
  scheduled_window_end))`, con indici covering `(subject_ref,
  scheduled_window_start, scheduled_window_end, snapshot_ref)` e
  `(subject_ref, scheduled_window_end, scheduled_window_start, snapshot_ref)`;
  trigger `BEFORE UPDATE/DELETE` abortiscono sempre;
- `maintain_plan_matching_discoveries`, con colonne del §4 e FK a scope,
  sessione, discovery precedente, confirmation discovery, confirmation
  MatchingResult esistente, result e mapping. CHECK implementano esattamente
  la matrice del §4 e rendono mutuamente esclusivi i due confirmation ref;
- la tabella confirmation discovery del §6, indici per ogni FK e trigger
  append-only.
- `maintain_plan_matching_confirmation_resolutions(matching_result_ref TEXT
  PRIMARY KEY, prescription_mapping_ref TEXT NOT NULL UNIQUE,
  discovery_result_ref TEXT NOT NULL, discovery_confirmation_ref TEXT UNIQUE,
  matching_confirmation_ref TEXT UNIQUE, actor TEXT NOT NULL
  CHECK(length(actor)>0), confirmed_at TEXT NOT NULL, FOREIGN KEY ... ON DELETE
  NO ACTION, CHECK((discovery_confirmation_ref IS NULL) <>
  (matching_confirmation_ref IS NULL)))` come sidecar immutabile 1:1: le prime
  tre FK puntano rispettivamente a result `MATCHED`, mapping
  `ATHLETE_CONFIRMATION` e discovery originaria; l'unico confirmation ref punta
  a `ANSWER SELECT_SNAPSHOT` dedicata per `ZERO`/`MULTIPLE` oppure alla risposta
  existing `maintain_plan_confirmations` per `SINGLE`;
  payload, subject, snapshot e sessione devono coincidere tra tutte le righe;
- un indice univoco v8 su `maintain_plan_prescription_mappings
  (actual_session_ref)`, oltre ai trigger append-only esistenti, per rendere
  fisica l'invariante di un solo mapping per sessione.

Le FK immediate già presenti in `schema.py` sono state auditate: mapping punta
subito a snapshot e sessione, mentre result `MATCHED` punta subito al mapping;
confirmation punta subito a result e snapshot. Poiché non sono deferred e v8
non cambia v1–v7, il mapping deve precedere il result dopo la precomputazione
deterministica di entrambi gli ID.

Ogni unit of work apre `BEGIN IMMEDIATE` **prima** delle riletture, verifica
payload, metadata, ownership, scope e retry, esegue il matcher puro e inserisce
gli artefatti nell'ordine imposto dalle FK. Result, mapping e discovery
`MATCHED` diventano visibili nello stesso commit. Errore, race divergente,
corruzione o insert parziale eseguono rollback completo. Un retry equivalente
restituisce i record esistenti; nessun upsert distruttivo è ammesso.

L'upgrade v7→v8 è una singola transazione `BEGIN IMMEDIATE`. Dopo aver creato
le strutture, enumera in ordine byte UTF-8 di ID **ogni** snapshot v7 con
`subject_ref IS NOT NULL`, decodifica strict il payload, verifica subject
duplicato, finestra completa timezone-aware con `start <= end`, canonicalizza
i due istanti e calcola il digest del payload canonico; quindi inserisce
esattamente una riga indice per snapshot. Soltanto `start > end` è invalido,
coerentemente con il validator v7; una finestra puntuale valida deve essere
indicizzata. Riga eleggibile indecodificabile o incoerente, conflitto, ID
duplicato o violazione FK abortisce e rollbacka l'intero upgrade.

Prima di impostare `user_version=8` e committare, la migrazione verifica:
conteggio indice uguale al conteggio degli snapshot v7 non-null; nessun
eleggibile senza indice; nessun indice senza snapshot eleggibile; uguaglianza
byte-per-byte di subject e finestra decodificata per ogni coppia; e
`foreign_key_check` vuoto. Snapshot legacy con ownership null restano senza
indice e ineleggibili. Il matching non può essere abilitato su un database v8
parzialmente popolato.

Nella stessa validazione, eventuali mapping v7 duplicati per sessione o
resolution metadata contraddittori abortiscono l'upgrade prima di creare
l'indice univoco. La sidecar confirmation nasce vuota: popolare l'indice
finestre è struttura obbligatoria, mentre sintetizzare conferme storiche è
vietato.

## 8. Lifecycle degli output

Un `MatchingResult` `MATCHED` richiede un mapping. `CONFIRMATION_REQUIRED` e
`NOT_EVALUABLE` richiedono mapping null. Soltanto una risposta umana valida
produce un nuovo risultato `MATCHED` e mapping con
`resolution_method=ATHLETE_CONFIRMATION`, actor, timestamp e confirmation ref.
Un indice univoco sul mapping per `actual_session_ref` e la verifica preventiva
nella transazione impediscono un secondo mapping. Retry identico restituisce la
coppia esistente; contenuto divergente rollbacka.
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

Il discovery derivato aggiunge `confirmation_id`, che identifica l'answer
discovery-specific per `ZERO`/`MULTIPLE` oppure l'answer MatchingResult
esistente per `SINGLE`, e `previous_discovery_result_id`. Namespace
`maintain-plan:matching-discovery:v1:sha256:<hash>`.

Matching result automatico (valido per entrambi i percorsi automatici):

```json
{"confirmation_id":null,"direct_evidence_ids":[],"matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","prescription_snapshot_id":"<id>","session_ids":["<ordinati, anche vuoto>"],"sync_scope_id":"<id>"}
```

Namespace `maintain-plan:matching-result:v1:sha256:<hash>`. Il mapping mantiene
la preimage esistente con confirmation, snapshot, sessione e resolution method;
non esiste mapping nel caso zero sessioni.

Matching result da risposta associativa (selezione discovery o confirmation
MatchingResult di un `SINGLE`):

```json
{"actor":"<actor>","confirmation_id":"<answer id>","confirmed_at":"<RFC3339>","discovery_result_id":"<discovery originaria>","matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","prescription_snapshot_id":"<id scelto>","session_id":"<id>","subject_ref":"<ref>"}
```

Namespace `maintain-plan:matching-result:v1:sha256:<hash>`. La mapping preimage
aggiunge alla stessa forma `matching_result_id` e
`resolution_method:"ATHLETE_CONFIRMATION"`; namespace
`maintain-plan:prescription-mapping:v1:sha256:<hash>`. Actor e timestamp sono
parte dell'identità, non metadata sostituibili. Retry richiede equivalenza di
preimage, evidence conservata e payload; altrimenti è conflitto.

Per un `SINGLE`, `confirmation_id` nella preimage è l'ID della risposta
`maintain_plan_confirmations`; `discovery_result_id` è la discovery `SINGLE`
originaria. Questi input impediscono che una conferma sia riciclata su un'altra
discovery e preservano actor, timestamp, snapshot e sessione nell'identità.

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

Vettori normativi per `SELECT_SNAPSHOT` (`é` è U+00E9):

```text
result preimage: {"actor":"athlete-é","confirmation_id":"answer-é","confirmed_at":"2026-09-18T10:15:00Z","discovery_result_id":"discovery-é","matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","prescription_snapshot_id":"snapshot-é","session_id":"session-é","subject_ref":"subject-é"}
result SHA-256: 8695891d6cfd60a9fbd12cbd4d8ae7494297f4d2c66cfcc825cce434fca25d09
mapping preimage: {"actor":"athlete-é","confirmation_id":"answer-é","confirmed_at":"2026-09-18T10:15:00Z","discovery_result_id":"discovery-é","matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","matching_result_id":"maintain-plan:matching-result:v1:sha256:8695891d6cfd60a9fbd12cbd4d8ae7494297f4d2c66cfcc825cce434fca25d09","prescription_snapshot_id":"snapshot-é","resolution_method":"ATHLETE_CONFIRMATION","session_id":"session-é","subject_ref":"subject-é"}
mapping SHA-256: 090e65a0386027a4f69fc4bc2327137ed9abc7651165d64070a87c982dc7f2b3
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
17–18 settembre include le finestre intersecanti e, per le sessioni coperte, i
soli gruppi immediatamente adiacenti; snapshot di settembre occupano entrambi i
confini. Quelli di giugno non entrano nel conteggio e non causano `MULTIPLE`;
nessun lifecycle o grace period è inferito.

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
Il result e mapping nuovi citano risposta, actor e timestamp e mantengono
l'evidence incompatibile originale; il matcher non viene rieseguito.

### 10.5 Boundary di sincronizzazione e guard tra percorsi

Uno scope inizia alle 00:00; una finestra termina alle 23:59 del giorno prima e
una sessione coperta inizia alle 00:01. La finestra non interseca lo scope, ma è
il predecessore immediato same-subject e quindi entra nell'evidence: l'esito è
`CONFIRMATION_REQUIRED`, mai `ZERO`. Se due snapshot vicini producono
`MULTIPLE`, il percorso window-driven li salta entrambi finché la discovery è
irrisolta. Dopo `SELECT_SNAPSHOT`, il solo mapping è quello confirmation-aware.

### 10.6 Scope multi-day, finestra puntuale e SINGLE

Uno scope di tre giorni contiene una prescrizione lunedì e una mercoledì. La
sessione di lunedì riceve il proprio set del §3.3, non l'unione multi-day: la
prescrizione mercoledì non la trasforma artificialmente in `MULTIPLE`. Una
finestra puntuale con `start == end == S.start` è valida, viene indicizzata e
contiene inclusivamente `S.start`.

Se l'unico snapshot candidato è appena fuori finestra, nasce discovery
`SINGLE/CONFIRMATION_REQUIRED` con `matching_result_ref` non-null e mapping
null. La request `maintain_plan_confirmations` riferisce quel result. Una
risposta associativa valida genera, nell'ordine answer, mapping, result,
sidecar e discovery derivato, un `SINGLE/MATCHED`; result e mapping citano
answer, actor e timestamp, mentre l'evidence fuori-finestra resta auditabile.

## 11. Errori, upgrade e decisioni residue

Sono errori tecnici: scope assente/non riuscito/incoerente; righe nel perimetro
corrotte; ownership discordante; direct evidence malformata; timestamp naive;
FK dangling; payload/colonne discordanti; risposta non appartenente al set o
allo scope; retry divergente. Sono esiti di dominio: zero/più snapshot,
zero/più sessioni, fuori finestra, mismatch, direct ID ben formato ma
irrisolto, e risposta non risolutiva.

DB v1–v7 non abilita questo boundary. La futura v8 è additiva e richiede tutte
le tabelle, indici, trigger e checksum coerenti. “Nessun backfill storico” vale
per discovery, result, confirmation e mapping: non inventa outcome per sync
passati. **Non** vale per la popolazione strutturale obbligatoria dell'indice
finestre durante v7→v8 (§7). Record legacy con ownership nulla restano non
indicizzati e ineleggibili.

### 11.1 Audit interno di coerenza

L'audit normativo completo ha verificato: (1) ordine session-driven prima del
window-driven e guardia sulle discovery irrisolte; (2) transizioni `ZERO`,
`SINGLE`, `MULTIPLE`, `MATCHED`, `CONFIRMATION_REQUIRED` e `NOT_EVALUABLE`;
(3) confirmation snapshot-centric e discovery-specific senza riuso di shape
incompatibili; (4) `SELECT_SNAPSHOT` confirmation-aware senza secondo giudizio
automatico; (5) upgrade v7→v8 tutto-o-niente con popolazione e conteggi esatti;
(6) FK immediate effettive di `schema.py` e ordine answer→mapping→result→
sidecar→discovery; (7) retry equivalenti idempotenti e conflitti divergenti
fail-closed; (8) un solo mapping per sessione tra entrambi i percorsi; (9) set
per-sessione separati dall'unione synchronization-wide; (10) invariant v7
`start <= end`, incluse finestre zero-length; (11) matrice completa dei ref e
uso della confirmation MatchingResult esistente esclusivamente per `SINGLE`.

**Non resta alcuna decisione normativa bloccante.** Restano lavoro
implementativo: definire modelli/codec, migrazione v8, repository, adapter dello
scope, flag/wiring e test di race/rollback. Fino ad allora tutto il comportamento
descritto resta non implementato e disabilitato.
