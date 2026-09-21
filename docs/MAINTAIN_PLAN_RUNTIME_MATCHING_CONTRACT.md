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
2. dopo che input autorevoli e boundary dell'indice successor sono disponibili,
   esegue e committa la fase obbligatoria di **synchronization pre-processing**:
   scheduling dei boundary appena rivelati e sweep expiry di tutte le request
   zero-sessioni **e reconciliation** pending same-subject il cui rispettivo
   boundary deterministico è raggiunto;
3. soltanto dopo quel commit esegue il percorso **session-driven** per ciascuna
   sessione coperta, ordinata per `(start, session_id UTF-8)`;
4. quindi esegue il percorso **prescription/window-driven** per ciascuno snapshot
   rilevante la cui finestra è ormai chiusa, in gruppi same-subject ordinati per
   `scheduled_window.start`; tutti gli exact same-start restano nello stesso
   gruppo e sono ordinati internamente per `prescription_snapshot_id` secondo
   l'ordinamento canonico byte UTF-8 già definito;
5. committa gli artefatti di matching prima di qualsiasi consumer downstream.

Un sync fallito, parziale o best-effort degradato a warning non invoca nessuno
dei due percorsi. Il secondo percorso non dipende dalla presenza di una nuova
attività: è il trigger richiesto per una prescrizione scaduta senza sessione.
L'ordine globale è dunque **expiry pre-processing → session-driven →
prescription/window-driven**. Il session-first tra i due percorsi consente al
secondo di rileggere i risultati appena committati; non è un ranking né un
tie-break. Se la stessa sincronizzazione rivela il successore B e importa una
sessione di B, deve prima scadere e committare A: nessuna discovery, result o
mapping di B può precedere quel commit.

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

### 3.2 Set synchronization-wide

Il set **synchronization-wide**, usato esclusivamente per enumerare gli
snapshot del percorso prescription/window-driven, contiene tutte e sole le
finestre same-subject che intersecano l'intervallo autorevole coperto:

```text
snapshot.scheduled_window.start < coverage_end
AND snapshot.scheduled_window.end >= coverage_start
```

Non vi si aggiungono predecessori o successori di alcuna sessione. Questi
gruppi appartengono soltanto al fallback per-sessione del §3.3 quando nessuna
finestra contiene `S.start`; in particolare un vicino esterno alla coverage
non può rendere uno snapshot eleggibile per il caso zero-sessioni. Gli istanti
sono canonical UTC RFC 3339. Le query usano esclusivamente l'indice v8 e
ordinano per `(scheduled_window_start, scheduled_window_end,
prescription_snapshot_id UTF-8)`. Sono vietati grace period, distanze
inventate e scansioni storiche.

La query fisica recupera soltanto righe indice con `subject_ref` esattamente
uguale che soddisfano il predicato d'intersezione. Ogni riga indice selezionata e il relativo
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

L'intersezione delimita integralmente questo set. Nessun periodo esterno alla
coverage partecipa all'enumerazione window-driven. Questo insieme non è mai
passato in blocco a una sessione e non determina la cardinalità della sua
discovery.

L'intersezione rende una finestra **enumerabile**, non dimostra da sola
l'assenza di sessioni. Per la decisione zero-sessioni si ordinano gli intervalli
successful dello stesso soggetto per `(coverage_start, coverage_end,
sync_scope_ref UTF-8)`, si fondono intervalli sovrapposti o adiacenti e si
richiede che una componente continua della union contenga l'intera finestra
secondo la convenzione half-open: `union_start <= window.start` e
`window.end < union_end`. Due frammenti con un gap non sono copertura completa.
Per una point window `start == end == t`, serve `union_start <= t < union_end`:
un punto esattamente a `union_end` non è coperto. Tail-only, head-only o middle-
only consentono comunque di valutare sessioni effettivamente osservate, ma non
autorizzano result/request zero-sessioni, scheduling expiry o processing del
successore per quella assenza; lo snapshot resta non gestito a tale scopo fino
a una sync successiva che completi la coverage.

### 3.3 Candidate set per-sessione

Per ogni sessione coperta `S` il repository costruisce un set distinto,
same-subject e deduplicato in due passi. Prima carica **tutte e sole** le
finestre che contengono `S.start`, con predicate inclusivo
`start <= S.start AND end >= S.start`. Se questo insieme non è vuoto, esso è
l'intero set temporale: predecessore e successore non vengono né caricati né
contati. Soltanto se non esiste alcuna finestra contenente, il set temporale è
l'unione dell'intero gruppo predecessore con il massimo
`scheduled_window_end < S.start` e dell'intero gruppo successore con il minimo
`scheduled_window_start > S.start`. Tutti gli exact tie del massimo o minimo
sono inclusi. Una finestra zero-length contiene la sessione quando i tre
istanti coincidono.

Un direct ID, quando presente, viene risolto e validato **prima** di pubblicare
la discovery. Deve essere sintatticamente valido, esistere in modo univoco,
decodificarsi strict e avere `subject_ref` identico byte-per-byte a `S`; valore
mancante, dangling, ambiguo, indecodificabile o cross-subject fallisce chiuso
come errore tecnico e rollbacka, senza confirmation sostitutiva. Il target
validato è evidence autorevole: viene unito al set temporale se non vi è già,
ma non abilita il caricamento incondizionato dei gruppi adiacenti. Quindi può
selezionare un membro di un set contenente multiplo o aggiungere una sola
evidence fuori-finestra al set adiacente limitato; non tronca mai le evidence.

Le query sono separate per `S`, usano gli indici v8 e ordinano il risultato
deduplicato per `prescription_snapshot_id` byte UTF-8. La validazione strict,
le verifiche ownership/indice/payload e il rollback fail-closed del §3.2 si
applicano a ogni riga letta. I gruppi adiacenti conservano evidence
fuori-finestra, ma mantengono la cardinalità limitata; non sono tolleranza,
ranking o scansione storica. Il set synchronization-wide resta disponibile al
solo percorso senza sessione del §5 e non viene unito a questo set.

## 4. Percorso session-driven e discovery snapshot-centric

Il percorso session-driven **non** è un ciclo che esegue
`match(snapshot, (S,))` indipendentemente per ogni coppia. In una singola
sincronizzazione costruisce prima, per tutte le sessioni coperte dello stesso
soggetto, i candidate set del §3.3 e congela le discovery `ZERO`, `SINGLE` o
`MULTIPLE` relative alla scelta dello snapshot. Una `MULTIPLE` snapshot-side
non viene risolta scegliendo il primo snapshot: resta una discovery
`CONFIRMATION_REQUIRED`. Ciascuna coppia congelata è chiusa per quella sessione
fino alla risposta e, dopo una risoluzione, resta chiusa per quella stessa
sessione; questa chiusura relation-level non consuma globalmente gli snapshot
non selezionati.

Dalle relazioni non già handled ricava poi una **worklist di snapshot**: unione
deduplicata dei candidate snapshot, ordinata per
`(scheduled_window.start, prescription_snapshot_id UTF-8)`. Ciascuno snapshot
compare al massimo una volta per synchronization, anche se è candidato di più
sessioni. Per ogni snapshot `P`, sotto `BEGIN IMMEDIATE`, il repository:

1. applica le guardie simmetriche del §4.3 sia per `actual_session_ref` sia per
   `prescription_snapshot_ref`;
2. carica dal perimetro autorevole dello scope la tupla **completa** di tutte e
   sole le sessioni same-subject eleggibili per `P` secondo le regole
   scope/window/candidate dei §§3.1–3.3, senza perdere sessioni soltanto perché
   incompatibili;
3. deduplica per `session_id`, valida payload e ownership e ordina la tupla per
   `(start, session_id UTF-8)`;
4. invoca il futuro matcher puro **esattamente una volta** come
   `match(P, tuple_completa)`. È vietato decomporla in chiamate singleton,
   fermarsi alla prima sessione o riprovare lo stesso snapshot più avanti nel
   medesimo sync.

Il matcher valuta la compatibilità di ogni membro senza ranking. Zero sessioni
post-filtro non viene deciso qui: si applica il predicato snapshot-level del §5
e, soltanto se `P` è realmente non gestito, il caso viene deferito al percorso
window-driven zero-sessioni. Con una sola sessione compatibile si crea il
normale mapping automatico anche se altre sessioni della tupla sono
incompatibili. Con almeno due compatibili si crea **un solo** `MatchingResult`
`CONFIRMATION_REQUIRED` e una sola request, con l'intera tupla canonica
congelata in `candidate_session_ids`/evidence; non nasce alcun mapping prima
della selezione. L'athlete può in seguito selezionare esattamente un membro di
quella tupla congelata: il percorso confirmation-aware crea un solo mapping
verso quel membro, senza rieseguire il matcher. Zero compatibili conserva
l'esito domain previsto dal matcher. Sono vietati ranking, fuzzy matching,
tie-break impliciti e first-session-wins.

Il `MatchingResult` prodotto da questa chiamata appartiene all'**evaluation di
P contro l'intera tupla congelata**, non alla sola sessione selezionata. Per
ogni `S` rappresentata dalla tupla deve già esistere la propria discovery
snapshot-side `SINGLE`; il result condiviso viene quindi distribuito tramite
una resolution terminale 1:1 per discovery (§4.1). Il mapping, se esiste,
appartiene soltanto alla resolution della sessione selezionata. Una resolution
di una sessione non selezionata può citare il result condiviso, ma non può
citare, incorporare o far intendere il mapping della sessione selezionata.

La discovery snapshot-side conserva comunque la sua cardinalità reale:

- zero snapshot per una sessione produce `MatchingDiscoveryResult.ZERO`, non un
  `MatchingResult`;
- uno produce `SINGLE` e rende la coppia disponibile alla worklist;
- almeno due produce `MULTIPLE`; nessun risultato per-snapshot o mapping viene
  pubblicato prima della risoluzione autorevole.

Un direct ID valido conserva l'intera evidence e seleziona autorevolmente lo
snapshot; quella relazione entra nella worklist dello snapshot selezionato. Un
ID mancante, dangling, ambiguo, indecodificabile o cross-subject fallisce
chiuso come nel §3.3.

```yaml
matching_discovery_result:
  discovery_result_id: string
  artifact_version: "1"
  sync_scope_ref: string
  status: ZERO | SINGLE | MULTIPLE
  resolution_status: PENDING | MATCHED | CONFIRMATION_REQUIRED | NOT_EVALUABLE
  actual_session_ref: string
  subject_ref: string
  candidate_snapshot_refs: [string]
  candidate_evidence: [object]
  direct_id_evidence: [object]
  selected_snapshot_ref: string | null
  resolution_source: AUTOMATIC | DIRECT_ID | ATHLETE_CONFIRMATION | null
  previous_discovery_result_ref: string | null
  discovery_confirmation_ref: string | null
  matching_confirmation_ref: string | null
  matching_result_ref: string | null
  prescription_mapping_ref: string | null
  discovered_at: datetime
  provenance: object
```

Candidate ed evidence hanno uguale cardinalità e ordine. Questa matrice descrive
la scelta snapshot-side e non basta, da sola, a dichiarare terminali le
discovery per-sessione: per ogni `SINGLE` rappresentato la terminalità e la
presenza legale del mapping sono definite esclusivamente dalla resolution
1:1 del §4.1. La kind conserva sempre la cardinalità congelata (`ZERO=0`,
`SINGLE=1`, `MULTIPLE>=2`):

| kind | resolution | result ref | mapping ref | meccanismo |
|---|---|---|---|---|
| `ZERO` | `CONFIRMATION_REQUIRED` | null | null | discovery confirmation |
| `ZERO` | `NOT_EVALUABLE` | null | null | risposta non selettiva |
| `ZERO` | `MATCHED` | non-null | non-null | `SELECT_SNAPSHOT` |
| `SINGLE` | `PENDING` | null | null | attende evaluation/fan-out snapshot-level |
| `SINGLE` | `MATCHED` | non-null | non-null | automatic/direct ID o confirmation |
| `SINGLE` | `CONFIRMATION_REQUIRED` | non-null | null | existing result confirmation |
| `SINGLE` | `NOT_EVALUABLE` | non-null | null | existing result confirmation |
| `MULTIPLE` | `CONFIRMATION_REQUIRED` | null | null | discovery confirmation |
| `MULTIPLE` | `NOT_EVALUABLE` | null | null | risposta non selettiva |
| `MULTIPLE` | `MATCHED` | non-null | non-null | direct ID o `SELECT_SNAPSHOT` |

Nel percorso full-tuple, ogni discovery `SINGLE` nasce immutabile come
`PENDING`; non viene riscritta né trasformata in una falsa discovery `MATCHED`.
La sua resolution 1:1 ne costituisce la terminalità. Le righe `SINGLE` legacy
della matrice restano le shape per evaluation veramente singleton e per le
catene derivate già descritte, ma anch'esse devono avere la resolution
terminale coerente; la colonna mapping della discovery può essere valorizzata
solo se la sua resolution è `SELECTED_MATCH`.

`MATCHED` richiede `selected_snapshot_ref` e `resolution_source`; la selezione
deve appartenere alla tupla congelata (salvo la regola same-scope già definita
per `ZERO`). `DIRECT_ID` richiede evidence strict e usa mapping method
`AUTOMATIC`; la selezione umana usa `ATHLETE_CONFIRMATION`. I ref confirmation
restano mutuamente esclusivi e il result `CONFIRMATION_REQUIRED` di `SINGLE`
resta collegato alla discovery.

Per il risultato snapshot-centric session-side vale inoltre questa matrice
normativa:

| sessioni compatibili nella tupla completa | outcome | mapping prima della risposta | candidate tuple pubblicata |
|---:|---|---|---|
| 0 | `CONFIRMATION_REQUIRED` o `NOT_EVALUABLE` secondo il matcher | nessuno | intera tupla canonica |
| 1 | `MATCHED` automatico | esattamente uno | intera tupla canonica |
| >=2 | `CONFIRMATION_REQUIRED` | nessuno | intera tupla canonica |
| >=2, selezione athlete valida | `MATCHED` confirmation-aware | esattamente uno verso il membro selezionato | tupla originaria immutata |

La presenza di sessioni incompatibili non sopprime l'unica compatibile. Ogni
result/mapping derivato cita lo snapshot, la tupla congelata e l'evidence
fingerprint; una selezione fuori tupla o divergente fallisce chiusa. Ogni
discovery `SINGLE` rappresentata resta pending finché l'evaluation è pending e
termina poi esattamente una volta secondo la fan-out del §4.1.

Con direct ID validato, una singola `BEGIN IMMEDIATE` rilegge entrambi i lati,
l'intero candidate set e le guardie del §4.3, precalcola gli ID, inserisce il
mapping prima del result per le FK immediate e infine la discovery terminale.
Retry equivalente restituisce la stessa catena; una diversa risoluzione o un
mapping concorrente su **uno qualunque dei due lati** rollbacka.

#### Direct ID con discovery `MULTIPLE` nella fan-out

Un direct ID valido può risolvere autorevolmente la discovery frozen `MULTIPLE`
della sessione diretta senza inventare una discovery `SINGLE`. Lo snapshot
selezionato entra nella evaluation full-tuple e ogni relazione rappresentata
può originare da (a) una discovery `SINGLE` che contiene quello snapshot oppure
(b) la sola relazione `selected_snapshot_ref` di una discovery
`MULTIPLE/MATCHED` con `resolution_source=DIRECT_ID`, purché lo snapshot appartenga
al candidate set congelato. Il `MULTIPLE` conserva candidate set completo,
direct-ID evidence e stato `MATCHED`; soltanto la relazione selezionata può
portare il mapping. Tutti gli altri snapshot del suo candidate set restano guardati dalla catena
terminale **soltanto rispetto alla sessione diretta**: non possono essere
riproposti a quella sessione, ma restano eleggibili per relazioni con altre
sessioni. Solo lo snapshot selezionato viene consumato globalmente dal mapping
o da un eventuale result/chain terminale che sia proprietario di quello
snapshot.

La fan-out chiude ogni membership rappresentata: la relazione direct-ID riceve
`SELECTED_MATCH`; ogni altra sessione candidata allo snapshot selezionato riceve
`INCOMPATIBLE` o `COMPATIBLE_NOT_SELECTED`, senza borrowed mapping. Discovery
kind miste `MULTIPLE`/`SINGLE` sono legali nella stessa fan-out; cardinalità e
selection membership vengono rivalidate prima del commit.

### 4.1 Fan-out terminale delle discovery per-sessione

La resolution additiva, separata dalla discovery immutabile, ha questa shape:

```yaml
matching_discovery_resolution:
  discovery_resolution_id: string
  discovery_result_ref: string
  matching_result_ref: string
  prescription_snapshot_ref: string  # relation snapshot
  decision_snapshot_ref: string      # snapshot del result sidecar
  actual_session_ref: string
  disposition: SELECTED_MATCH | INCOMPATIBLE | COMPATIBLE_NOT_SELECTED | CANDIDATE_SNAPSHOT_NOT_SELECTED | NON_ASSOCIATIVE_CLOSURE
  prescription_mapping_ref: string | null
  selected_session_ref: string | null
  frozen_session_refs: [string]
  compatibility_decision: object
  evidence_fingerprint: string
  previous_chain_head_ref: string | null
  resolved_at: datetime
```

`matching_result_ref` identifica sempre il result snapshot-level condiviso;
`frozen_session_refs` ripete integralmente la tupla canonica e
`compatibility_decision` contiene la decisione per **ogni** membro, snapshot,
policy/version e reason evidence. Se una sessione è stata scelta,
`selected_session_ref` è identico in tutte le resolution della fan-out; è null
per una chiusura non associativa. Le disposition sono mutuamente esclusive:

| disposition | sessione della riga | result | mapping | significato |
|---|---|---|---|---|
| `SELECTED_MATCH` | uguale a `selected_session_ref` | required | required | unica sessione associata |
| `INCOMPATIBLE` | decisione incompatibile | required | **null** | candidata valutata ma incompatibile |
| `COMPATIBLE_NOT_SELECTED` | compatibile, diversa dalla sessione selezionata per lo stesso snapshot | required | **null** | confirmation ha scelto un'altra sessione |
| `CANDIDATE_SNAPSHOT_NOT_SELECTED` | sessione originaria, snapshot diverso da quello selezionato | required | **null** | `MULTIPLE` ha scelto un'altra prescrizione; chiude solo questa relation |
| `NON_ASSOCIATIVE_CLOSURE` | qualunque membro ancora rappresentato | required | **null** | rejection, risposta non associativa o result `NOT_EVALUABLE`; expiry solo per catene zero-session/reconciliation |

Mapping presence è legale **solo** per `SELECTED_MATCH`. Quella riga richiede
`mapping.actual_session_ref = resolution.actual_session_ref =
selected_session_ref` e `mapping.prescription_snapshot_ref =
result.prescription_snapshot_ref = resolution.prescription_snapshot_ref`.
Tutte le altre righe impongono `prescription_mapping_ref IS NULL`; in
particolare non possono prendere in prestito il mapping selezionato.

Per `SELECTED_MATCH`, `INCOMPATIBLE`, `COMPATIBLE_NOT_SELECTED` e
`NON_ASSOCIATIVE_CLOSURE`, `prescription_snapshot_ref == decision_snapshot_ref
== result_sidecar.prescription_snapshot_ref` resta obbligatorio. La sola
`CANDIDATE_SNAPSHOT_NOT_SELECTED` usa la validazione alternativa stretta:
l'origine è `MULTIPLE/MATCHED` con source `DIRECT_ID|ATHLETE_CONFIRMATION`;
relation snapshot P e selected snapshot Q sono membri della stessa tupla frozen;
Q è `discovery.selected_snapshot_ref == decision_snapshot_ref ==
result_sidecar.prescription_snapshot_ref`; P è diverso da Q; sessione, subject e
discovery coincidono; mapping è null. La riga chiude soltanto `(session,P)`, non
consuma P globalmente e non può riferire o prendere in prestito il mapping di Q.

Lifecycle normativo:

* una compatibile e le altre incompatibili: un result snapshot-level
  `MATCHED`, un mapping, `SELECTED_MATCH` per la compatibile e `INCOMPATIBLE`
  per tutte le altre;
* più compatibili: un result `CONFIRMATION_REQUIRED` e la request; **nessuna**
  resolution terminale viene inserita e tutte le discovery restano pending.
  Dopo una selezione valida si crea un nuovo result confirmation-aware
  `MATCHED`, un mapping, `SELECTED_MATCH` per la scelta,
  `COMPATIBLE_NOT_SELECTED` per le altre compatibili e `INCOMPATIBLE` per le
  incompatibili;
* rejection, risposta non associativa o `NOT_EVALUABLE` crea/conserva
  un result snapshot-level senza mapping e terminalizza tutti i membri come
  `NON_ASSOCIATIVE_CLOSURE` (le decisioni individuali rimangono evidence);
* direct ID e `SELECT_SNAPSHOT` applicano la stessa fan-out e aggiungono una
  `CANDIDATE_SNAPSHOT_NOT_SELECTED` per ciascun altro snapshot congelato nella
  `MULTIPLE` originaria. Queste resolution chiudono tutte le relation della
  sessione, ma non consumano globalmente gli snapshot respinti.

La fan-out completa è una singola unit of work. Per automatic matching gli ID
di result e mapping sono precalcolati; a causa della FK immediata v1–v7 da
result `MATCHED` a mapping, l'ordine SQL eseguibile è **mapping → result →
result-snapshot sidecar → tutte le resolution** (ordine logico evaluation →
mapping, ma mai insert result prima della FK). Per athlete selection è
**answer → mapping → result → result-snapshot sidecar/confirmation sidecar →
tutte le resolution → successor event**. Prima delle write si rileggono
confirmation/head e le teste di tutte le discovery. Qualunque resolution non
inseribile, fan-out parziale, seconda selezione o mapping concorrente rollbacka
l'intera transazione. Nessun result snapshot-level terminale può committare se
una discovery rappresentata resta pending.

### 4.2 Contratto puro composition-aware

L'implementazione futura DEVE correggere l'ordine oggi presente in
`matching_service.match`: l'early return che tratta ogni composition diversa
da `single` come bisognosa di brick policy precede oggi
`validate_prescription`. Questo rende impossibile `MULTISPORT`, perché il
validator richiede la policy per `BRICK` e la vieta per ogni composition non
`BRICK`. Il dispatch normativo, dopo la validazione canonica di snapshot e
sessioni uniche, è invece esattamente:

1. `SINGLE` conserva il comportamento attuale: una componente, nessuna brick
   policy e consecutività vera per definizione;
2. `BRICK` conserva il comportamento attuale: brick policy completa
   obbligatoria e controlli di consecutività/transizione di `_consecutivity`;
3. `MULTISPORT` è un branch valido distinto: almeno due componenti, brick
   policy obbligatoriamente assente e nessun controllo di consecutività,
   transition-gap o brick policy. Una brick policy presente è input invalido,
   non un modo per entrare nel branch `BRICK`.

Per `MULTISPORT` senza direct ID la compatibilità usa un branch futuro
esplicito; **non** può riusare `_component_checks` invariato. Il predicato
completo, senza fallback, è: (a) `scheduled_window.start <= S.start <=
scheduled_window.end`; (b) `S.composition is MULTISPORT`; (c) uguale cardinalità
di componenti planned/observed; (d) dopo aver validato su entrambi i lati che
ogni `component_index` sia un intero comparabile e unico, ordinare separatamente
planned e observed per indice e richiedere per ogni posizione
`planned.component_index == observed.component_index`; (e) solo dopo tale
uguaglianza, confrontare discipline e sostituzioni della coppia con quell'indice.
Non si rinumera, compatta o normalizza alcuna sequenza: `(0,2)` contro `(0,1)` e
due sequenze traslate ma disuguali sono mismatch esatti; `(0,2)` contro `(0,2)`
può essere valido. Duplicati, tipi malformati o indici non comparabili producono
`NOT_EVALUABLE` con evidence strutturale esplicita; un indice valido ma diverso
produce `CONFIRMATION_REQUIRED` incompatibile e non può mappare automaticamente.
Cardinalità, uguaglianza indici, disciplina e sostituzione sono valutate insieme:
nessun pairing per posizione può saltare l'uguaglianza dell'indice.

Per una `allowed_substitution`, un vincolo planned `environment`/`mode` assente
non vincola quella dimensione; se il vincolo esiste e il valore observed è
presente deve essere identico; se il valore optional observed manca, **solo**
quella dimensione è `UNKNOWN/NOT_EVALUABLE` nell'evidence e non rende da sola la
sessione incompatibile né forza confirmation. Un valore presente e confliggente
è incompatibile. Il matcher futuro deve quindi aggregare le dimensioni note e
non può riusare l'helper corrente se tratta `None` come mismatch. Ownership byte-esatta, persistenza canonica,
validazione `validate_prescription`/`validate_actual_session`, finestra e
candidate tuple restano quelli dei §§3–4. Non si aggiungono similarità,
ranking, distanza, tolleranza, inferenza di transizioni o tie-break.

Il risultato è deterministico. Con esattamente una sessione same-subject nella
tupla, tutti e cinque i predicati veri producono `MATCHED`, mapping automatico
e gli stessi `candidate_session_ids`, `CandidateEvidence`, component/block/
repetition/transition mapping e provenance usati dagli altri match automatici
non ambigui. Uno o più predicati falsi producono
`CONFIRMATION_REQUIRED`, nessun mapping, warning esistente quando non rimane
alcuna candidata e reason keys esatte fra `scheduled_window`, `composition`,
`component_cardinality`, `component_order`, `disciplines`. Più sessioni
compatibili producono `CONFIRMATION_REQUIRED`, mai una scelta implicita.

Un input canonico valido ma privo di struttura sufficiente a calcolare uno di
questi predicati produce `NOT_EVALUABLE`, mapping nullo e reason esplicita
`multisport compatibility input is structurally incomplete`; non deve essere
reinterpretato come incompatibilità o brick-policy mancante. Payload, enum,
timestamp, ownership, riferimenti o versioni che falliscono i validator/codec
restano invece errori tecnici fail-closed e rollbackano: non vengono trasformati
in outcome di dominio. Il direct-ID strict conserva il percorso autorevole del
§4 e non altera queste regole per il caso senza direct ID.

### 4.3 Guard pre-matcher simmetrica, cross-scope e identità semantica

Prima di inserire uno snapshot nella worklist e ancora sotto la
`BEGIN IMMEDIATE` che precede il matcher, il repository esegue lookup
**indipendenti su entrambi i lati**, senza filtro su `sync_scope_ref`:

1. mapping per `actual_session_ref` e mapping per
   `prescription_snapshot_ref`;
2. discovery membership per la coppia esatta sessione/snapshot e discovery
   resolution autorevole per la sessione;
3. per la guard snapshot globale, mapping e sidecar di result/chain
   snapshot-owning; la sola membership non selezionata non vi partecipa;
4. confirmation pending/answered, catene zero-sessioni o reconciliation,
   teste terminali e precedenti evidence fingerprint, classificati per origine
   relation-, session- o snapshot-owning.

Ogni lookup usa l'indice relazionale v8, poi ID UTF-8; tutte le FK, ownership,
membership, tuple congelate e teste uniche sono rivalidate. Se la sessione è
già mappata, si osserva quel mapping e non la si valuta per un altro snapshot.
Se lo snapshot è già mappato, si osserva quel mapping e non lo si valuta per
un'altra sessione. Se la coppia esatta ha una discovery, si riprende o osserva quella catena e la
sessione non acquisisce un altro snapshot dopo mapping o resolution autorevole.
Se lo snapshot ha una evaluation snapshot-owning pending, la si riprende senza
crearne una parallela; se ha mapping o result/chain snapshot-owning terminale è
consumato globalmente. Una membership non selezionata in una `MULTIPLE` chiude
la coppia originaria ma non blocca relazioni con altre sessioni. Queste regole
restano identiche in scope sovrapposti successivi.

Un mapping trovato da un lato deve essere ritrovato identico dall'altro. Due
mapping discordanti per la stessa sessione o snapshot, una catena forked, una
membership incoerente o una request parallela sono corruzione fail-closed. Una
testa terminale non mappata con lo stesso fingerprint rende il tentativo no-op;
un nuovo tentativo append-only è lecito soltanto per evidence autorevole
realmente diversa e cita il precedente head. `sync_scope_ref` è sola
provenienza e non cambia l'identità semantica.

Subito prima di inserire qualunque `PrescriptionMapping`, la medesima
`BEGIN IMMEDIATE` rilegge nuovamente **sia** `actual_session_ref` **sia**
`prescription_snapshot_ref`. Se nessuno è occupato, l'insert può procedere. Se
esiste la stessa mapping canonica (stesso ID, sessione, snapshot, subject,
metodo ed evidence), il retry la riusa idempotentemente. Se uno dei due lati è
già associato diversamente, rollbacka senza result/discovery parziali. Gli
indici univoci sui due riferimenti decidono anche la race: un solo concorrente
vince; il perdente equivalente rilegge/restituisce, quello confliggente fallisce
chiuso. Queste guardie precedono ogni discovery, chiamata al matcher, risposta
umana e percorso window-driven.

## 5. Percorso prescription/window-driven: nessuna sessione catturata

Per ogni snapshot del set synchronization-wide, il boundary valuta prima la
**zero-session eligibility** separata dalla mera enumerazione. La union canonica
degli intervalli di coverage autorevoli riusciti applicabili deve coprire senza
buchi l'intero intervallo eleggibile degli start della finestra. Per un solo
intervallo half-open la condizione esatta è
`coverage_start <= scheduled_window.start AND scheduled_window.end < coverage_end`.
Solo dopo che tale predicato è vero il boundary apre `BEGIN IMMEDIATE`,
rilegge lo snapshot e tutte le sessioni same-subject già persistite dagli scope
successful che formano la componente continua di coverage usata per la prova,
ordinate per `(start, session_id UTF-8)`, e distingue due predicati
che non sono intercambiabili:

- **relation handled**, keyed esattamente da
  `(actual_session_ref, prescription_snapshot_ref)`: esiste una discovery o
  resolution che rappresenta quella coppia. Una terminale `MULTIPLE` chiude
  tutte le proprie coppie per la sessione originaria, incluse le candidate non
  selezionate;
- **session handled**: una mapping o resolution autorevole impedisce alla
  sessione di acquisire un altro snapshot; una catena relation-level viene
  ripresa/osservata invece di essere duplicata;
- **snapshot handled globalmente**: esiste una mapping verso lo snapshot oppure
  un result/chain terminale **snapshot-owning** che lo consuma (inclusi i
  boundary zero-session/reconciliation). La mera membership non selezionata in
  una discovery `MULTIPLE` di un'altra sessione non soddisfa mai questo
  predicato e non rende lo snapshot indisponibile. Una evaluation
  snapshot-owning ancora pending viene ripresa e serializzata, non duplicata,
  ma non è confusa con consumo terminale;
- **session handled elsewhere**: la sessione è esclusa dalla tupla corrente per
  il proprio artefatto autorevole, ma ciò non rende handled uno snapshot
  estraneo.

Il lookup snapshot-level avviene prima del filtro sessioni e nell'ordine fisso:
(1) mapping per `prescription_snapshot_ref`; (2) result/chain terminali
snapshot-owning, result e request zero-sessioni per lo snapshot; (3)
reconciliation e answer collegate; (4) per la sola guard relation-level,
discovery complete che contengono **insieme** snapshot e sessione; (5) eventi
terminali delle relative catene. Il punto (4) non alimenta la guard globale
dello snapshot quando la relation è non selezionata. Entro ogni classe ordina per chiave primaria UTF-8 e ricalcola
la testa unica della catena. Soltanto un artefatto trovato in questa ricerca,
con ownership, FK, evidence e relazione esatta valide, consente di saltare lo
snapshot o la coppia rappresentata. Un artefatto riferito soltanto a un'altra
prescrizione non soddisfa mai il predicato snapshot-level.

Se lo snapshot non è handled, il boundary costruisce la tupla **remaining**
partendo dalle sessioni persistite dello scope ed escludendo quelle già gestite
in modo autorevole da altre relazioni. Una sessione mappata o scoperta per
un'altra prescrizione non viene reinterpretata come candidata dello snapshot
corrente. Se `remaining` è non vuota, invoca una sola volta il matcher puro con
lo snapshot e quella tupla. Se `remaining` è vuota e lo snapshot non è handled,
entra invece obbligatoriamente nel boundary zero-sessioni sotto descritto,
anche quando la tupla originaria conteneva sessioni tutte escluse. Non crea un
`MatchingDiscoveryResult`: `ZERO` in discovery significa zero snapshot per una
sessione esistente e non deve essere confuso con zero sessioni rimanenti per uno
snapshot mai gestito.

Se la tupla `remaining` è vuota, il boundary **non invoca** il matcher di compatibilità.
Crea invece direttamente il deterministico outcome di assenza sessioni usando
la rappresentazione `MatchingResult` snapshot-centric esistente, con
`status=CONFIRMATION_REQUIRED`, `candidate_session_refs=[]`, candidate evidence
vuota, mapping null e warning normativo:
“Non ho trovato un'attività associabile alla seduta prevista”. Si usa quindi la
confirmation esistente, che possiede esattamente un `matching_result_ref` e un
`prescription_snapshot_ref`. Poiché `declared_session_refs=[]`, la request
iniziale offre **soltanto** `NOT_PERFORMED`, `NOT_SYNCHRONIZED` e
`DONT_KNOW`: `MANUAL_ASSOCIATION` e `SELECT_CANDIDATE` sono illegali. Non si
presume che la seduta non sia stata svolta. Una sessione non può essere
iniettata successivamente nella tupla vuota congelata: il solo modo di offrirla
è la reconciliation append-only del §5.2. Questa regola si applica uniformemente a snapshot validi
`SINGLE`, `MULTISPORT` e `BRICK`, indipendentemente dalla brick policy: è un
outcome di **assenza**, non un algoritmo alternativo di compatibilità o
ranking. Il matcher puro è invocato soltanto quando la tupla contiene almeno
una `ActualSession` persistita; il suo ordine di validazione e i suoi early
return restano invariati.

L'identità semantica del tentativo usa l'`evidence_fingerprint` del §9 e **non**
`sync_scope_ref`: lo scope è soltanto provenienza. Ripetere lo stesso scope o
osservare la stessa evidence in uno scope sovrapposto restituisce gli stessi
artefatti. Uno scope successivo può fissare l'expiry o avviare la reconciliation
di una sessione tardiva secondo §§5.1–5.2, senza modificare né cancellare il
precedente. Prima di creare il caso zero, il repository applica la guard cross-scope
del §4.1 alle sessioni ma decide lo skip esclusivamente con il predicato
snapshot-level appena definito. Verifica globalmente che non esistano mapping o result/chain snapshot-owning,
result/request zero-sessioni, reconciliation o artefatti terminali che
consumino lo snapshot; una discovery che lo cita soltanto come candidato non
selezionato chiude la coppia originaria ma non supera questa guard globale; il fatto che tutte le sessioni
siano gestite **altrove** non è uno skip. Lookup, filtro, ricalcolo di
`remaining`, creazione deterministica di result/request e insert avvengono
nella stessa `BEGIN IMMEDIATE`. Un writer concorrente viene quindi osservato al
re-read: artefatto equivalente causa no-op, una relazione divergente fallisce
chiusa. Una risposta chiude la richiesta tramite un nuovo record append-only;
non aggiorna il risultato.

Matrice normativa della decisione window-driven:

| snapshot handled esatto | `remaining` dopo filtro | azione |
|---|---:|---|
| sì | qualunque | skip/restituisce la catena autorevole; nessun duplicato |
| no | non vuota | matcher puro una volta sulla sola tupla `remaining` |
| no | vuota, anche per filtro di sessioni gestite altrove | crea esattamente un result/request zero-sessioni |

La matrice preserva sia la guard pre-matcher cross-scope sia l'invariante di un
solo mapping per sessione: escludere una sessione già mappata evita di
ricandidarla, ma non attribuisce il suo mapping a uno snapshot estraneo.

Prima di processare ogni coppia snapshot/sessione, la stessa `BEGIN IMMEDIATE`
ricerca deterministicamente **tutte** le catene discovery append-only della
sessione, ordinate per `(discovered_at, discovery_result_id UTF-8)`, ne valida
link e testa corrente univoca e controlla l'evidence congelata di ogni origine.
La relazione è già gestita se compare in qualsiasi catena, qualunque sia lo
stato della testa (`CONFIRMATION_REQUIRED`, `MATCHED` o `NOT_EVALUABLE`). Per un'origine `MULTIPLE`, ogni coppia del candidate set congelato è gestita
per quella sessione, inclusi gli snapshot non selezionati dopo una risoluzione
autorevole. Questi ultimi non sono però globalmente consumati: la stessa
prescrizione può partecipare a una relazione diversa con un'altra sessione. La
sola coppia originaria viene quindi saltata deterministicamente: una testa terminale non consente
reprocessing, mapping duplicati o insert destinati a violare l'unicità.

La lettura completa, il calcolo della testa, il controllo di mapping/result e
l'eventuale insert window-driven avvengono nella medesima transazione. Catene
malformate, fork, teste multiple o stato divergente falliscono chiuso e
rollbackano; un retry equivalente osserva lo stesso ordine e restituisce gli
artefatti esistenti. Il check segue il commit di tutte le discovery
session-driven e precede qualsiasi insert window-driven. Dopo una selezione
valida soltanto il percorso confirmation-aware del §6 può creare il mapping;
una risposta non associativa resta terminale e non riapre il rapporto.

### 5.1 Expiry deterministica della request zero-sessioni

La fase A del caso zero committa atomicamente result e request insieme a
`expiry_boundary_at` e `expiry_successor_snapshot_refs`. Per ogni subject gli
snapshot formano gruppi canonici ordinati esclusivamente per
`scheduled_window.start`: tutti gli snapshot con start identico sono congelati
nello stesso gruppo, ordinati internamente per `prescription_snapshot_id`
secondo i byte UTF-8 canonici, senza usare `end` come tie-break fra gruppi. Per
uno snapshot o gruppo A, il successore di expiry è il gruppo immediatamente
seguente con start **strettamente maggiore dello start canonico di A**; il
boundary è precisamente quello start. Non si richiede mai che lo start del
successore sia successivo a `A.scheduled_window.end`: sovrapposizione,
contenimento ed esatta adiacenza end/start sono tutti validi.

Tutti i ref del gruppo successor sono congelati nella tupla. Questi sono input
autorevoli dell'indice §3, non un timeout di parete né un grace period. Se
nessun gruppo successivo è ancora noto, boundary e tupla sono null/vuoti e la
request resta pending. Ogni sincronizzazione successiva che scopre il primo
gruppo successore appende un record `EXPIRY_SCHEDULED` con gli stessi input
canonici; non aggiorna request o result. Gli snapshot exact same-start di A non
sono successori reciproci e condividono il medesimo successore; una finestra
puntuale (`start=end`) segue esattamente la stessa regola.

Il loop window-driven usa questo medesimo ordine per gruppi e non separa mai un
gruppo same-start, neppure se i suoi `end` differiscono. Dopo aver creato il caso
zero di A, rivalida immediatamente il successore autorevole: se il boundary è
già raggiunto all'istante di creazione della request, **nella stessa
`BEGIN IMMEDIATE`** inserisce result e request originari, scheduling, quindi il **distinto** result
terminale `NOT_EVALUABLE`, la sua sidecar e infine l'evento `EXPIRED` di A. Soltanto il commit consente di processare un
qualsiasi membro del gruppo B. Finestre parzialmente sovrapposte o contenute
restano contemporaneamente candidate e possono quindi produrre discovery
`MULTIPLE`; ciò non allenta l'obbligo di chiudere A prima di processare il
gruppo ordinato successivo. Il loop non può mai creare discovery, matching o
confirmation per B mentre A è pending quando B costituisce già il suo boundary.
ID, one-successor e race con un answer seguono le regole append-only sotto
indicate; l'unità atomica evita qualsiasi finestra osservabile intermedia.

Nella fase obbligatoria di synchronization pre-processing del §2, **prima di
entrambi i percorsi**, il boundary identifica sia request zero-sessioni sia
request reconciliation pending con il rispettivo boundary raggiunto. Le ordina
insieme per `(effective_expiry_boundary_at, request_kind,
request_id UTF-8)` (`ZERO_SESSION` prima di `RECONCILIATION`) e non processa
alcun membro del gruppo finché tutte le expiry dovute non sono committate. Per ciascuna, una
`BEGIN IMMEDIATE` rilegge request, result, catena, boundary e indice e valida
che il gruppo sia ancora quello canonico. Se la request è ancora pending,
precalcola un ID distinto secondo §9 e appende un
`MatchingResult NOT_EVALUABLE` terminale con warning ed evidence originali,
`candidate_session_refs=[]`, `prescription_mapping_ref=null`, reason
`UNANSWERED_BEFORE_NEXT_PRESCRIPTION`, e un evento `EXPIRED`; non crea answer,
actor o mapping e non muta/cancella la request originaria. Solo dopo il commit
dell'intero sweep possono partire discovery o matching session-driven e poi
window-driven del gruppo successor. Se il successore diventa noto nella stessa
sync, scheduling e sweep precedono persino una sessione importata per quel
gruppo.

L'ID di scheduling deriva da `(request_id, expiry_boundary_at,
expiry_successor_snapshot_refs)`; quello di expiry aggiunge il chain-head ID e
la reason. Tupla, timestamp RFC3339 canonico, subject, snapshot originario,
warning/evidence digest e policy version sono duplicati nel payload e validati.
Retry byte-equivalente rilegge/no-op; input divergenti, fork o una boundary non
minima falliscono chiusi. Answer, avvio reconciliation tardiva ed expiry aprono
ciascuno `BEGIN IMMEDIATE`, rileggono la testa corrente e competono sul vincolo
unico `(origin_request_ref, previous_chain_head_ref)`: esattamente un successore
vince. Il perdente equivalente rilegge il nuovo head e fa no-op; una diversa
intenzione restituisce conflitto chiuso. Un answer arrivato dopo `EXPIRED` è
stale e non può creare mapping.

### 5.2 Reconciliation di sessioni tardive prima del mapping

Prima che **sia il percorso session-driven sia quello window-driven** elabori
una `ActualSession`, cerca per `(subject_ref, snapshot_ref)` ogni catena
snapshot-centric zero-sessioni precedente la sessione corrente, pending o
terminale. Il lookup usa il candidate set per-sessione del §3.3 per stabilire
quali snapshot copre la relazione e avviene prima del matcher e di ogni mapping.
Se ne esiste una, il normale percorso automatico è vietato.

Una `BEGIN IMMEDIATE` rilegge la testa e congela tutte e sole le sessioni
persistite eleggibili: stesso `subject_ref` byte-per-byte, non già mappate,
presenti nel corrente scope autorevole e aventi quello snapshot nel proprio set
§3.3. La tupla `candidate_session_refs == declared_session_refs` è non vuota,
ordinata per `(start, session_id UTF-8)`, include la nuova sessione e conserva
per ciascun membro payload digest, scope/evidence e ownership verificati. Riga
malformata, dangling, cross-subject o set divergente rollbacka l'intera unità.
Il boundary appende un `LATE_SESSION_RECONCILIATION` result/attempt e una nuova
request collegati a result e request zero originari e alla testa precedente;
non altera la tupla vuota né l'evidence originaria.

Ogni request di reconciliation persiste il proprio
`reconciliation_expiry_boundary_at` e
`reconciliation_expiry_successor_snapshot_refs`, distinti dal boundary ormai
trascorso della request zero-sessioni. Il boundary di reconciliation è lo start
canonico del primo gruppo di prescrizioni same-subject con
`scheduled_window.start` **strettamente successivo** al `created_at` committato
della request di reconciliation; la tupla evidence contiene l'intero gruppo
same-start in ordine byte UTF-8. `created_at` è parte immutabile della request e
della sua identità canonica; non si riusa mai l'expiry originaria.

Se al commit non è noto alcun gruppo futuro, boundary e tupla sono null/vuoti e
la reconciliation resta pending. Una sincronizzazione autorevole successiva
che scopre il primo gruppo futuro appende un unico scheduling con FK alla
request, boundary e tupla; la coppia immutabile request+scheduling è la deadline
persistita propria della reconciliation e non muta la request. La lettura
canonica `effective_reconciliation_expiry_*` usa i campi request quando già
noti, altrimenti quelli dell'unico scheduling, e fallisce chiusa se entrambi
sono valorizzati ma differiscono.
Il pre-processing globale rivalida e committa l'expiry reconciliation prima che
uno dei due percorsi elabori un membro del gruppo. Se il boundary è già dovuto
quando viene scoperto, nella stessa unità serializzata appende prima result
`NOT_EVALUABLE` ed evento `EXPIRED`. L'expiry non crea answer né mapping,
conserva original result/request zero-sessioni, request/evidence reconciliation
e tuple congelate, e non aggiorna alcuna request.

Solo questa nuova request può offrire `MANUAL_ASSOCIATION`/`SELECT_CANDIDATE`.
La risposta è persistita esclusivamente nella relazione dedicata
`maintain_plan_late_session_reconciliation_answers` del §7, mai nella answer
che referenzia `maintain_plan_confirmations`. La selezione associativa deve
appartenere byte-per-byte alla tupla congelata. Una risposta associativa crea,
in ordine FK-immediate-safe **reconciliation answer → mapping → result → sidecar → evento testa**,
un mapping `ATHLETE_CONFIRMATION` e conserva original result/request,
reconciliation request, actor e timestamp. Expiry o risposta non associativa precalcola tutti gli ID e usa **answer (se
presente) → result `NOT_EVALUABLE` distinto → result/snapshot sidecar → fan-out
terminale applicabile → evento testa**, senza mapping; l'expiry automatica omette
l'answer ma mantiene lo stesso ordine. L'evento è sempre ultimo. Nessuna
risposta produce un
nuovo report visibile per una vecchia seduta già superata.

Answer ed expiry della reconciliation competono sotto la stessa
`BEGIN IMMEDIATE`: rileggono request e chain head, rivalidano boundary/evidence e
usano il vincolo one-successor sul precedente head. Il vincitore appende l'unico
terminale; il retry byte-identico del perdente rilegge/no-op, mentre intenzione
divergente o answer stale fallisce chiusa. Nessun percorso può mutare request,
answer o evidence originali.

Una catena pending, già expired/`NOT_EVALUABLE` o già risolta non viene
ignorata: genera al massimo una reconciliation per la medesima tupla canonica.
Per una precedente risposta non associativa o expiry la reconciliation è una
nuova decisione esplicita, mai riapertura/mutazione; per una precedente
associazione valida il mapping esistente rende ogni nuovo tentativo un no-op
verificato. Sessioni concorrenti serializzano, la vincitrice congela l'intera
tupla allora visibile e la perdente rilegge/no-op se equivalente o fallisce
chiusa se divergente. L'indice unico per sessione e la guard pre-matcher
impediscono mapping duplicati.

Matrice normativa della catena snapshot-centric:

| testa osservata / evento | nuova testa append-only | tuple sessioni | opzioni associative | mapping |
|---|---|---|---|---|
| zero request pending | initial confirmation answer + `ANSWERED` + result `NOT_EVALUABLE` | vuota originale | vietate | nessuno |
| zero request pending / successor raggiunto | `EXPIRED` + result `NOT_EVALUABLE` | vuota originale | nessuna answer | nessuno |
| zero pending o terminale / sessione tardiva | `LATE_SESSION_RECONCILIATION` pending | non vuota, canonica | solo membri congelati | nessuno prima dell'answer |
| reconciliation pending / selezione valida | dedicated answer + result `MATCHED` | non vuota, invariata | membro selezionato nella request | uno, `ATHLETE_CONFIRMATION` |
| reconciliation pending / risposta non associativa | dedicated answer + result `NOT_EVALUABLE` | non vuota, invariata | `selected_session_ref=null` | nessuno |
| reconciliation pending / proprio boundary futuro raggiunto | result `NOT_EVALUABLE` + `EXPIRED` | non vuota, invariata | nessuna answer | nessuno |
| qualunque testa / mapping già esistente | no-op verificato | invariata | — | mapping esistente |

La catena conserva sempre warning/evidence zero originari. Un nuovo head cita
il precedente; request, result, attempt e answer restano tutti immutabili.

Per la request zero-sessioni iniziale, ognuna delle sole risposte legali
`NOT_PERFORMED`, `NOT_SYNCHRONIZED` e `DONT_KNOW` chiude la catena. La fase B
usa un'unica `BEGIN IMMEDIATE`, rilegge la request e la testa pending, quindi
precalcola answer/result/event ID e inserisce nell'ordine FK-immediate-safe
**matching confirmation answer → result terminale `NOT_EVALUABLE` distinto →
result/snapshot sidecar → eventuale fan-out terminale → evento `ANSWERED` con origine
`INITIAL_CONFIRMATION`**. Answer, result ed evento sono atomici: nessuno di essi
può essere osservato senza gli altri. L'evento cita esclusivamente
`initial_confirmation_answer_ref`; non può citare una reconciliation answer.
Subito dopo il commit la testa è chiusa. Sweep expiry e avvio reconciliation
rileggono obbligatoriamente quella testa sotto `BEGIN IMMEDIATE` e non possono
più avanzare la precedente request pending. Retry byte-identico rilegge/no-op;
una risposta divergente, un'expiry o una reconciliation concorrente perde il
vincolo one-successor e poi fallisce chiusa (o no-op soltanto se semanticamente
equivalente). Non esiste una finestra in cui l'answer sia committata ma la testa
resti stale.

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

`SELECT_SNAPSHOT` è conferma umana autorevole: crea un nuovo discovery della
**stessa kind e con lo stesso candidate set congelato** dell'origine
(`MULTIPLE` resta `MULTIPLE`; `ZERO` resta `ZERO`), ma **non** reinvoca il
matcher automatico invariato. Nella fase B
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
apre la normale `maintain_plan_confirmations` con `status=REQUIRED`, già
riferita a result e snapshot. Poiché la shape v1–v7 non ha `request_ref` e il
record non può essere mutato append-only, v8 aggiunge
`maintain_plan_matching_confirmation_answers(answer_id PRIMARY KEY,
request_ref NOT NULL UNIQUE REFERENCES maintain_plan_confirmations,
answer_type, selected_session_ref, actor, occurred_at, payload_schema_version,
payload_json)` con CHECK equivalenti alla matrice v7 degli answer. La request
resta `REQUIRED`; l'answer v8 separato ne costituisce la chiusura auditabile.
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

Il validator v8 distingue obbligatoriamente le due shape snapshot-centric:
una request zero-sessioni con tupla dichiarata vuota rifiuta sempre un answer
associativo; una request `LATE_SESSION_RECONCILIATION` lo ammette soltanto con
`selected_session_ref` non-null, membro byte-esatto della propria tupla
congelata non vuota. Il validator rilegge dati canonici persistiti, verifica
ownership, scope/evidence, ordine e digest di **ogni** candidata e non accetta
sessioni fornite soltanto dal client. Le answer non associative richiedono
sempre `selected_session_ref=null`.

Ogni meccanismo di confirmation, incluso quello snapshot-centric senza
sessione e quello existing MatchingResult per `SINGLE`, usa **due transazioni
committate distinte**. La fase A apre `BEGIN IMMEDIATE`, rilegge l'artefatto
irrisolto, crea idempotentemente la sola `REQUEST`, committa, e soltanto dopo il
commit la espone all'atleta. La connessione non conserva una transazione, un
cursor o un lock SQLite durante l'interazione umana.

La fase B inizia soltanto dopo aver ricevuto una risposta. Apre un nuovo
`BEGIN IMMEDIATE`, rilegge dal database request e testa di catena pending già
committate e ne rivalida kind, stato irrisolto, scope, subject, candidate
congelate, ownership e assenza di risposta/mapping concorrente. Precalcola gli
ID. Per `SELECT_SNAPSHOT` l'ordine FK-safe è **answer, mapping, result, sidecar
confirmation-resolution, discovery derivato**; lo stesso vale per una risposta
associativa `SINGLE`. Per risposte non associative è answer, result
`NOT_EVALUABLE` quando il flusso è `SINGLE`, poi discovery derivato; per
`ZERO`/`MULTIPLE` è answer, discovery derivato. Tutti gli artefatti della fase
B sono atomici e il commit precede la loro esposizione. Quando il result
snapshot-level rappresenta più discovery `SINGLE`, “discovery derivato” indica
la **fan-out completa** del §4.1, non la sola discovery selezionata: le righe
non selezionate sono inserite prima del successor event con mapping null.
Rejection e risposta non associativa usano analogamente
`NON_ASSOCIATIVE_CLOSURE` per ogni membro. Una confirmation full-tuple ordinaria
non ha deadline né expiry automatica: resta pending fino a una answer athlete
valida. Gli eventi/sweep di expiry zero-sessioni e reconciliation non sono
riutilizzabili per questo request type. Un errore su una sola riga annulla
answer, mapping, result, sidecar e tutte le resolution.

L'identità deterministica della request rende un retry di fase A equivalente
un no-op verificato. In fase B `UNIQUE(request_ref)` decide la race: il primo
answer valido committato vince; un retry con ID e bytes equivalenti rilegge
l'intera catena e restituisce gli artefatti esistenti, mentre un answer diverso
o artefatti derivati divergenti causano conflitto e rollback. Nessun record
append-only viene aggiornato o cancellato. Payload e colonne duplicate devono
coincidere; trigger `BEFORE UPDATE/DELETE` abortiscono sempre, FK sono attive e
nessun cascade è ammesso.

## 7. Persistenza v8 e atomicità

Inventario normativo request/answer v8: (a) discovery `ZERO/MULTIPLE` usa i
record `REQUEST`/`ANSWER` della propria tabella dedicata; (b) confirmation
`SINGLE` e zero-sessioni basata su `maintain_plan_confirmations` usa
`maintain_plan_matching_confirmation_answers`; (c) late-session reconciliation
usa esclusivamente `maintain_plan_late_session_reconciliation_answers`. Ogni FK
di answer punta alla propria request shape; nessuna request type con risposta
umana può restare priva della corrispondente relazione persistibile e nessuna
answer può attraversare questi tre domini.

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

  La creazione repository di **ogni** nuova `PrescriptionSnapshot` v8 ha un
  contratto atomico obbligatorio, indipendente dal backfill di upgrade. Una sola
  `BEGIN IMMEDIATE` valida ownership e ID, decodifica strict il payload canonico,
  verifica `subject_ref` duplicato e finestra timezone-aware (`start <= end`,
  inclusa `start == end`), calcola `payload_sha256`, inserisce lo snapshot e
  inserisce esattamente una riga indice derivata **dallo stesso payload**; poi
  verifica la coppia 1:1 prima del commit. Qualunque errore di derivazione,
  validazione o insert rollbacka anche lo snapshot. La soluzione normativa è
  questa unit of work repository: non si affida a un trigger SQLite per
  decodificare JSON, salvo futura prova che quel trigger esegua la medesima
  validazione strict e canonica.

  Dopo l'upgrade non può esistere alcuno snapshot v8 ownership-bound committato
  senza esattamente una riga indice corrispondente, né una riga indice senza il
  proprio snapshot; discovery continua a interrogare esclusivamente l'indice
  validato. Un retry con stesso ID, payload canonico, digest, ownership e finestra
  rilegge entrambe le righe e fa no-op. Stesso ID con payload/digest o ownership
  diversi è conflitto fail-closed. Un indice preesistente senza snapshot, uno
  snapshot senza indice o una coppia discordante è corruzione e non viene
  riparata con upsert. Insert concorrenti sullo stesso ID serializzano: il primo
  commit vince, il perdente equivalente rilegge la coppia completa, quello
  divergente rollbacka. Insert concorrenti con ID distinti producono ciascuno la
  propria coppia 1:1. Nessun commit parziale è consentito;
- `maintain_plan_matching_discoveries`, con colonne del §4 e FK a scope,
  sessione, discovery precedente, confirmation discovery, confirmation
  MatchingResult esistente, result e mapping. CHECK implementano esattamente
  la matrice del §4 e rendono mutuamente esclusivi i due confirmation ref.
  In particolare `kind` è vincolato alla cardinalità JSON congelata
  (`ZERO=0`, `SINGLE=1`, `MULTIPLE>=2`) indipendentemente dalla resolution;
  `PENDING` è legale soltanto per `SINGLE` e richiede result, mapping,
  selected snapshot/source e confirmation ref tutti null; `MATCHED` richiede
  result, mapping, selected snapshot e source non-null;
  gli altri stati richiedono selected snapshot/source null. `DIRECT_ID`
  richiede direct evidence valida e permette `MULTIPLE/MATCHED` soltanto se la
  selezione è membro delle candidate; il mapping collegato usa obbligatoriamente
  l'enum v1–v7 `AUTOMATIC`, mai `DIRECT_ID`. `ATHLETE_CONFIRMATION` richiede uno dei
  confirmation ref e applica membership `MULTIPLE` o regola same-scope
  `ZERO`. Trigger applicativi abortiscono se JSON, colonne e righe referenziate
  non soddisfano gli stessi predicati;
- `maintain_plan_matching_discovery_memberships(discovery_result_ref TEXT
  NOT NULL, prescription_snapshot_ref TEXT NOT NULL, actual_session_ref TEXT
  NOT NULL, ordinal INTEGER NOT NULL CHECK(ordinal>=0), PRIMARY KEY
  (discovery_result_ref,prescription_snapshot_ref,actual_session_ref), UNIQUE
  (discovery_result_ref,ordinal), FOREIGN KEY ... ON DELETE NO ACTION)`,
  append-only. Trigger verificano che righe e ordine ricostruiscano esattamente
  `candidate_snapshot_refs` della discovery e la sua sessione. Sono obbligatori
  gli indici `(prescription_snapshot_ref,actual_session_ref,
  discovery_result_ref)` e `(actual_session_ref,prescription_snapshot_ref,
  discovery_result_ref)`;
- `maintain_plan_matching_discovery_resolutions(discovery_resolution_id TEXT
  PRIMARY KEY, discovery_result_ref TEXT NOT NULL REFERENCES
  maintain_plan_matching_discoveries(discovery_result_id), matching_result_ref
  TEXT NOT NULL REFERENCES maintain_plan_matching_results(matching_result_id),
  prescription_snapshot_ref TEXT NOT NULL REFERENCES
  maintain_plan_prescription_snapshots(prescription_snapshot_id),
  decision_snapshot_ref TEXT NOT NULL REFERENCES
  maintain_plan_prescription_snapshots(prescription_snapshot_id),
  actual_session_ref TEXT NOT NULL REFERENCES
  maintain_plan_actual_sessions(session_id), subject_ref TEXT NOT NULL,
  disposition TEXT NOT NULL CHECK
  (disposition IN ('SELECTED_MATCH','INCOMPATIBLE',
  'COMPATIBLE_NOT_SELECTED','CANDIDATE_SNAPSHOT_NOT_SELECTED',
  'NON_ASSOCIATIVE_CLOSURE')),
  prescription_mapping_ref TEXT REFERENCES
  maintain_plan_prescription_mappings(mapping_id), selected_session_ref TEXT,
  frozen_session_refs_json TEXT NOT NULL, compatibility_decision_json TEXT NOT
  NULL, evidence_fingerprint TEXT NOT NULL, previous_chain_head_ref TEXT,
  resolved_at TEXT NOT NULL, payload_json TEXT NOT NULL,
  UNIQUE(discovery_result_ref,prescription_snapshot_ref), FOREIGN KEY ... ON
  DELETE NO ACTION)`, append-only. `UNIQUE(discovery_result_ref,
  prescription_snapshot_ref)` impone una sola resolution terminale per
  relation; per `SINGLE` coincide con una sola riga, per `MULTIPLE` consente la
  chiusura completa di tutte le candidate. CHECK/trigger immediati impongono la
  matrice §4.1: mapping non-null se e solo se `SELECTED_MATCH`, al massimo una
  `SELECTED_MATCH` per `matching_result_ref`, e per ogni altra disposition
  mapping null. Un indice unico parziale
  `(matching_result_ref) WHERE disposition='SELECTED_MATCH'`, più gli indici
  `(matching_result_ref,actual_session_ref)` e
  `(prescription_snapshot_ref,actual_session_ref)`, rendono la fan-out
  verificabile senza JSON. Trigger validano membership della discovery
  `SINGLE` **oppure ogni relation congelata** di una discovery
  `MULTIPLE/MATCHED` con source `DIRECT_ID` o `ATHLETE_CONFIRMATION`; impongono
  `SELECTED_MATCH` soltanto sulla selected relation e
  `CANDIDATE_SNAPSHOT_NOT_SELECTED` su ogni altra. Per tutte le disposition
  ordinarie impongono `prescription_snapshot_ref=decision_snapshot_ref` e
  uguaglianza con il result sidecar. Soltanto per la candidate non selezionata
  accettano P diverso da Q dopo aver provato: origine `MULTIPLE/MATCHED`, source
  autorevole, membership frozen di P e Q, Q selected e uguale a
  `decision_snapshot_ref`/result sidecar, P diverso, sessione e subject identici,
  mapping null. Per la riga selezionata validano inoltre entrambi i ref del
  mapping. Per ogni riga non selezionata vietano il mapping
  anche nel payload. Prima del commit il repository verifica che il numero di
  resolution inserite sia esattamente il numero delle relazioni discovery
  rappresentate (`SINGLE` più tutte le membership congelate di `MULTIPLE`) nel
  result terminale; errore causa rollback della unit of work;
- `maintain_plan_matching_result_snapshot_index(matching_result_ref TEXT
  PRIMARY KEY REFERENCES maintain_plan_matching_results(matching_result_id),
  prescription_snapshot_ref TEXT NOT NULL REFERENCES
  maintain_plan_prescription_snapshots(prescription_snapshot_id), subject_ref
  TEXT NOT NULL, payload_sha256 TEXT NOT NULL, FOREIGN KEY ... ON DELETE NO
  ACTION)`, sidecar append-only 1:1. `subject_ref` e `payload_sha256` sono le
  sole evidence canoniche duplicate necessarie: devono coincidere byte-per-byte
  con snapshot ownership-bound e payload canonico del result. Trigger
  `BEFORE UPDATE/DELETE` abortiscono; CHECK/trigger vietano snapshot/result
  discordanti. L'indice lookup reale è
  `(prescription_snapshot_ref,matching_result_ref)`. Non viene dichiarato alcun
  indice su `maintain_plan_matching_results.prescription_snapshot_ref`, perché
  tale colonna non esiste in v1–v7;
- `maintain_plan_zero_session_terminal_results(terminal_result_ref TEXT PRIMARY
  KEY REFERENCES maintain_plan_matching_results(matching_result_id),
  original_matching_result_ref TEXT NOT NULL REFERENCES
  maintain_plan_matching_results(matching_result_id), previous_chain_head_ref
  TEXT NOT NULL, prescription_snapshot_ref TEXT NOT NULL REFERENCES
  maintain_plan_prescription_snapshots(prescription_snapshot_id), subject_ref
  TEXT NOT NULL, terminal_cause_kind TEXT NOT NULL CHECK(terminal_cause_kind IN
  ('INITIAL_NON_ASSOCIATIVE_ANSWER','RECONCILIATION_NON_ASSOCIATIVE_ANSWER',
  'ZERO_SESSION_EXPIRY','RECONCILIATION_EXPIRY')), terminal_cause_ref TEXT NOT
  NULL, initial_answer_ref TEXT REFERENCES
  maintain_plan_matching_confirmation_answers(answer_id),
  reconciliation_answer_ref TEXT REFERENCES
  maintain_plan_late_session_reconciliation_answers(answer_id),
  zero_expiry_schedule_ref TEXT REFERENCES
  maintain_plan_zero_session_chain_events(event_id),
  reconciliation_expiry_schedule_ref TEXT REFERENCES
  maintain_plan_late_session_reconciliation_expiry_schedules(schedule_id),
  terminal_status TEXT NOT NULL CHECK(terminal_status='NOT_EVALUABLE'),
  matching_policy_version TEXT NOT NULL, payload_json TEXT NOT NULL,
  CHECK(terminal_result_ref<>original_matching_result_ref),
  UNIQUE(original_matching_result_ref,previous_chain_head_ref,
  terminal_cause_kind,terminal_cause_ref), FOREIGN KEY ... ON DELETE NO
  ACTION)`, append-only. Un CHECK richiede esattamente il ref typed coerente con
  `terminal_cause_kind` e gli altri tre null; trigger verificano che
  `terminal_cause_ref` uguagli quel ref, che original result sia
  `CONFIRMATION_REQUIRED`, terminal result sia `NOT_EVALUABLE`, result sidecar e
  snapshot/subject coincidano, e che il previous head sia quello corrente.
  Indici `(original_matching_result_ref,previous_chain_head_ref)` e
  `(prescription_snapshot_ref,terminal_result_ref)` supportano retry e guard;
- indici lookup window-driven sulla sidecar precedente. Sulla tabella v1–v7
  `maintain_plan_confirmations`, che possiede `confirmation_id` e non possiede
  `request_id`, v8 crea esattamente
  `CREATE INDEX idx_mp_confirmations_snapshot_confirmation ON
  maintain_plan_confirmations(prescription_snapshot_ref, confirmation_id)`.
  Gli altri indici sono quelli già definiti su mapping, reconciliation ed eventi.
  Non è lecito scandire o interpretare parzialmente tuple JSON. Le query
  seguono l'ordine §5 e poi PK UTF-8, senza filtro scope;
- la tabella confirmation discovery del §6, indici per ogni FK e trigger
  append-only.
- la tabella append-only `maintain_plan_matching_confirmation_answers` del §6,
  con `UNIQUE(request_ref)`, FK immediate e indici; la request continua a usare
  l'esistente `maintain_plan_confirmations` senza update. Trigger v8 vietano
  inoltre update/delete delle request matching esistenti;
- `maintain_plan_zero_session_chain_events(event_id TEXT PRIMARY KEY,
  origin_request_ref TEXT NOT NULL, previous_chain_head_ref TEXT NOT NULL,
  event_kind TEXT NOT NULL CHECK(event_kind IN ('EXPIRY_SCHEDULED','EXPIRED',
  'RECONCILIATION_EXPIRY_SCHEDULED','RECONCILIATION_EXPIRED',
  'LATE_SESSION_RECONCILIATION','ANSWERED')), expiry_boundary_at TEXT,
  expiry_successor_snapshot_refs_json TEXT NOT NULL,
  reconciliation_request_ref TEXT, answer_source TEXT CHECK(answer_source IN
  ('INITIAL_CONFIRMATION','LATE_RECONCILIATION')),
  initial_confirmation_answer_ref TEXT REFERENCES
  maintain_plan_matching_confirmation_answers(answer_id),
  reconciliation_answer_ref TEXT REFERENCES
  maintain_plan_late_session_reconciliation_answers(answer_id),
  terminal_result_ref TEXT REFERENCES
  maintain_plan_matching_results(matching_result_id), occurred_at TEXT NOT NULL,
  payload_json TEXT NOT NULL, UNIQUE(origin_request_ref,
  previous_chain_head_ref), FOREIGN KEY ... ON DELETE NO ACTION)`. CHECK e
  trigger impongono: scheduling senza terminal result; expiry zero-sessioni o
  reconciliation con result `NOT_EVALUABLE` e senza answer/mapping; gli eventi
  reconciliation-expiry richiedono `reconciliation_request_ref`, ricopiano il
  relativo boundary/gruppo futuro e vietano l'uso del boundary zero originario;
  reconciliation con request e tupla
  candidata non vuota. `ANSWERED` richiede result terminale e distingue
  esplicitamente l'origine: con `answer_source='INITIAL_CONFIRMATION'` richiede
  **esattamente** `initial_confirmation_answer_ref` non-null e
  `reconciliation_answer_ref` null; con
  `answer_source='LATE_RECONCILIATION'` richiede esattamente il contrario e la
  reconciliation request coerente. `EXPIRED`, scheduling e ogni altro evento
  answerless richiedono `answer_source` e **entrambi** gli answer ref null.
  Trigger validano che l'answer iniziale punti alla stessa origin request e che
  la reconciliation answer raggiunga la medesima catena tramite la propria
  request. Le due FK sono immediate e `ON DELETE NO ACTION`. Un indice
  `(origin_request_ref,event_id)` e i link previous formano una sola catena
  append-only, senza fork;

  Matrice normativa delle reference evento (le celle “—” sono obbligatoriamente
  null):

  | `event_kind` | `answer_source` | initial answer ref | reconciliation answer ref | terminal result |
  |---|---|---|---|---|
  | `ANSWERED` iniziale | `INITIAL_CONFIRMATION` | esattamente una | — | `NOT_EVALUABLE`, required |
  | `ANSWERED` reconciliation | `LATE_RECONCILIATION` | — | esattamente una | `MATCHED` o `NOT_EVALUABLE`, required |
  | `EXPIRED` | — | — | — | `NOT_EVALUABLE`, required |
  | `RECONCILIATION_EXPIRED` | — | — | — | `NOT_EVALUABLE`, required |
  | `EXPIRY_SCHEDULED` | — | — | — | — |
  | `RECONCILIATION_EXPIRY_SCHEDULED` | — | — | — | — |
  | `LATE_SESSION_RECONCILIATION` | — | — | — | — |

  Nessun altro incrocio è schema-valid. La riga iniziale richiede inoltre una
  answer con tipo in `NOT_PERFORMED|NOT_SYNCHRONIZED|DONT_KNOW`; quella
  reconciliation applica la propria matrice associativa/non associativa;
- `maintain_plan_late_session_reconciliations(reconciliation_request_id TEXT
  PRIMARY KEY, original_matching_result_ref TEXT NOT NULL,
  original_confirmation_request_ref TEXT NOT NULL, previous_chain_head_ref TEXT
  NOT NULL, subject_ref TEXT NOT NULL, snapshot_ref TEXT NOT NULL,
  sync_scope_ref TEXT NOT NULL, candidate_session_refs_json TEXT NOT NULL,
  declared_session_refs_json TEXT NOT NULL, candidate_evidence_json TEXT NOT
  NULL, status TEXT NOT NULL CHECK(status='REQUIRED'), created_at TEXT NOT NULL,
  reconciliation_expiry_boundary_at TEXT,
  reconciliation_expiry_successor_snapshot_refs_json TEXT NOT NULL,
  payload_json TEXT NOT NULL, UNIQUE(original_confirmation_request_ref,
  previous_chain_head_ref), FOREIGN KEY ... ON DELETE NO ACTION)`. CHECK e
  trigger richiedono tuple uguali, non vuote, ordinate e senza duplicati; ogni
  sessione deve essere same-subject, persisted, scope-eligible e unmapped;
  update/delete sono vietati. La request resta per sempre immutabile con
  `status='REQUIRED'`: la chiusura logica esiste soltanto nella answer e nel
  successivo evento di catena. CHECK impone boundary null se e solo se la tupla
  successor è vuota; se valorizzato, esso deve essere maggiore di `created_at`
  ed essere lo start del primo gruppo futuro same-subject. Indici
  `(subject_ref,reconciliation_expiry_boundary_at,reconciliation_request_id)` e
  sui ref del gruppo supportano scheduling e sweep deterministici;
- `maintain_plan_late_session_reconciliation_expiry_schedules(schedule_id TEXT
  PRIMARY KEY, reconciliation_request_ref TEXT NOT NULL UNIQUE REFERENCES
  maintain_plan_late_session_reconciliations(reconciliation_request_id),
  boundary_at TEXT NOT NULL, successor_snapshot_refs_json TEXT NOT NULL,
  discovered_sync_scope_ref TEXT NOT NULL, payload_json TEXT NOT NULL,
  FOREIGN KEY ... ON DELETE NO ACTION)`, append-only. Esiste solo quando la
  request era nata senza futuro noto; CHECK/trigger impongono gruppo non vuoto,
  primo start strictly-after `created_at`, ownership same-subject, ordine UTF-8
  e uguaglianza payload/colonne. Indici `(boundary_at,
  reconciliation_request_ref)` e sui membership del gruppo rendono lo sweep
  deterministico; retry equivalente rilegge/no-op e un secondo schedule
  divergente fallisce chiuso;
- `maintain_plan_late_session_reconciliation_answers(answer_id TEXT PRIMARY KEY,
  reconciliation_request_ref TEXT NOT NULL UNIQUE REFERENCES
  maintain_plan_late_session_reconciliations(reconciliation_request_id) ON
  DELETE NO ACTION, response_kind TEXT NOT NULL CHECK(response_kind IN
  ('MANUAL_ASSOCIATION','SELECT_CANDIDATE','NOT_PERFORMED',
  'NOT_SYNCHRONIZED','DONT_KNOW')), selected_session_ref TEXT,
  actor TEXT NOT NULL CHECK(length(actor)>0), answered_at TEXT NOT NULL,
  payload_schema_version TEXT NOT NULL CHECK(payload_schema_version='1'),
  payload_json TEXT NOT NULL, audit_evidence_json TEXT NOT NULL,
  FOREIGN KEY(selected_session_ref) REFERENCES maintain_plan_actual_sessions
  (session_id) ON DELETE NO ACTION)`. CHECK e
  trigger impongono `selected_session_ref IS NOT NULL` soltanto per
  `MANUAL_ASSOCIATION|SELECT_CANDIDATE`, e in tal caso membership byte-esatta
  nella `candidate_session_refs_json` congelata della request; per rejection e
  ogni risposta non associativa deve essere null. Payload canonico e colonne
  duplicano request, subject, snapshot, candidate tuple, actor, timestamp,
  response e digest dell'evidence e devono coincidere. Indici su entrambe le FK,
  `UNIQUE(reconciliation_request_ref)` e trigger append-only sono obbligatori;
  questa relazione non può contenere answer di `maintain_plan_confirmations`;
- `maintain_plan_matching_confirmation_resolutions(matching_result_ref TEXT
  PRIMARY KEY, prescription_mapping_ref TEXT NOT NULL UNIQUE,
  discovery_result_ref TEXT NULL REFERENCES
  maintain_plan_matching_discoveries(discovery_result_id),
  discovery_confirmation_ref TEXT UNIQUE, matching_confirmation_ref TEXT UNIQUE,
  reconciliation_answer_ref TEXT UNIQUE REFERENCES
  maintain_plan_late_session_reconciliation_answers(answer_id), actor TEXT NOT
  NULL CHECK(length(actor)>0), confirmed_at TEXT NOT NULL, FOREIGN KEY ... ON
  DELETE NO ACTION)`, sidecar immutabile 1:1. Il CHECK di origine è esattamente:
  `(discovery_confirmation_ref IS NOT NULL) +
  (matching_confirmation_ref IS NOT NULL) +
  (reconciliation_answer_ref IS NOT NULL) = 1`; inoltre
  `reconciliation_answer_ref IS NOT NULL` richiede
  `discovery_result_ref IS NULL`, entrambi gli altri confirmation ref null e la
  FK immediata alla dedicated reconciliation-answer table. Viceversa una
  origine discovery richiede `discovery_result_ref IS NOT NULL`,
  `reconciliation_answer_ref IS NULL` e precisamente uno tra
  `discovery_confirmation_ref` e `matching_confirmation_ref`. Result `MATCHED`,
  mapping `ATHLETE_CONFIRMATION`, actor e timestamp sono obbligatori in ogni
  origine. Per reconciliation, il link alla catena zero-sessioni originaria è
  raggiungibile e validato tramite answer → reconciliation request → original
  result/request; non viene fabbricata una discovery. Payload, subject,
  snapshot, sessione, actor e timestamp devono coincidere tra tutte le righe;
- due indici univoci v8 su `maintain_plan_prescription_mappings`: uno su
  `(actual_session_ref)` e uno, simmetrico, su
  `(prescription_snapshot_ref)`. Rendono fisica la relazione uno-a-uno: una
  sessione non può riferire più snapshot e uno snapshot non può riferire più
  sessioni. Entrambi sono verificati insieme ai trigger append-only.

L'ordine additivo v8 è vincolante: snapshot-window index e backfill;
result-snapshot sidecar e backfill; discovery e membership; confirmation e
answer; `maintain_plan_matching_discovery_resolutions`; terminal-result typed
sidecar; catene zero-sessioni e
reconciliation; validazione mapping legacy; indici univoci mapping; infine
trigger e conteggi di completezza. Nessuna resolution storica viene inventata:
la tabella nasce vuota e ogni result terminale prodotto dopo l'abilitazione v8
deve committare la fan-out completa nella propria unit of work.

Le FK immediate già presenti in `schema.py` sono state auditate: mapping punta
subito a snapshot e sessione, mentre result `MATCHED` punta subito al mapping;
confirmation punta subito a result e snapshot. Poiché non sono deferred e v8
non cambia v1–v7, il mapping deve precedere il result dopo la precomputazione
deterministica di entrambi gli ID.

Ogni write post-upgrade di un `MatchingResult` eleggibile inserisce nella
**stessa** transazione prima il result (dopo l'eventuale mapping richiesto dalla
sua FK immediata) e subito dopo la sua
`maintain_plan_matching_result_snapshot_index`; soltanto allora può inserire
request, resolution sidecar, discovery o chain event dipendenti. Prima del
commit rilegge result, sidecar e snapshot e verifica cardinalità esattamente
1:1, ownership, snapshot ref e digest. Nessun result eleggibile può essere
committato senza sidecar e nessuna sidecar senza result e snapshot. Discovery,
guard e lookup window-driven interrogano questa relazione, mai JSON estratto a
query time.

Un retry con `matching_result_id`, bytes canonici, snapshot, subject e digest
identici rilegge e fa no-op; stesso ID con contenuto, snapshot o digest diverso
è conflitto e rollback. Una sidecar già presente ma divergente, un result senza
sidecar o una sidecar orfana è corruzione fail-closed, non viene riparata con
upsert. Due insert concorrenti sullo stesso ID serializzano sotto
`BEGIN IMMEDIATE`: il perdente equivalente rilegge la coppia, quello divergente
fallisce; ID diversi producono coppie indipendenti complete.

Ogni unit of work apre `BEGIN IMMEDIATE` **prima** delle proprie riletture,
senza mai attraversare l'attesa umana; request e answer appartengono alle due
unit of work distinte del §6. Ciascuna
verifica
payload, metadata, ownership, scope e retry, esegue il matcher puro e inserisce
gli artefatti nell'ordine imposto dalle FK. Result, mapping e discovery
`MATCHED` diventano visibili nello stesso commit. Errore, race divergente,
corruzione o insert parziale eseguono rollback completo. Un retry equivalente
restituisce i record esistenti; nessun upsert distruttivo è ammesso.

La creazione zero-sessioni inserisce result e request e, se il successor è già
noto e il boundary è raggiunto, anche scheduling e terminale expiry nello stesso
commit; se è noto ma non ancora raggiunto inserisce soltanto lo scheduling.
Sweep expiry, answer e reconciliation sono unit of work separate e concorrenti, sempre sotto `BEGIN IMMEDIATE` dopo rilettura della
testa. Lo sweep globale, ordinato deterministicamente, committa prima di
session-driven; session-driven committa prima di window-driven. Le guardie dei
due percorsi precedono ogni matcher, includono request e answer reconciliation
e considerano gestita ogni relazione presente nella catena. Il vincolo unico
sul precedente head assicura un solo successor e, insieme a
`UNIQUE(reconciliation_request_ref)` e agli indici mapping/sessione e mapping/snapshot, una sola
answer vincente e un solo mapping: retry byte-identici rileggono/no-op, answer
divergenti o race perse falliscono chiuso senza record parziali.

In particolare le risposte iniziali `NOT_PERFORMED`, `NOT_SYNCHRONIZED` e
`DONT_KNOW` eseguono **answer → result terminale distinto → result/snapshot
sidecar → fan-out applicabile → evento `ANSWERED` iniziale**
nella stessa unit of work. La reconciliation associativa conserva
**reconciliation answer → mapping → result → sidecar → evento `ANSWERED`
reconciliation**; quella non associativa usa **reconciliation answer → result
terminale distinto → result/snapshot sidecar → fan-out applicabile → evento**. Gli eventi rendono le origini non intercambiabili tramite
i CHECK e le FK dedicate sopra. Dopo il commit di un qualsiasi evento terminale,
ogni sweep o reconciliation concorrente osserva la nuova testa e non può
avanzare la request pending precedente.

L'upgrade v7→v8 è una singola transazione `BEGIN IMMEDIATE`. Dopo aver creato
le strutture, enumera in ordine byte UTF-8 di ID **ogni** snapshot v7 con
`subject_ref IS NOT NULL`, decodifica strict il payload, verifica subject
duplicato, finestra completa timezone-aware con `start <= end`, canonicalizza
i due istanti e calcola il digest del payload canonico; quindi inserisce
esattamente una riga indice per snapshot. Soltanto `start > end` è invalido,
coerentemente con il validator v7; una finestra puntuale valida deve essere
indicizzata. Riga eleggibile indecodificabile o incoerente, conflitto, ID
duplicato o violazione FK abortisce e rollbacka l'intero upgrade.

Nella stessa transazione, dopo la popolazione dell'indice finestre e prima di
creare i lookup result, la migrazione enumera per `matching_result_id` UTF-8
ogni result v7 eleggibile. Decodifica strict e valida interamente payload,
schema/versione, status/mapping coherence e riferimento snapshot; risolve uno e
un solo snapshot ownership-bound già indicizzato, verifica che result, mapping
eventuale, snapshot e `subject_ref` concordino, calcola il digest canonico e
inserisce esattamente una riga
`maintain_plan_matching_result_snapshot_index`. Riferimento assente,
malformato, multiplo o confliggente, dangling, ownership incoerente, digest
discordante o result duplicato abortisce e rollbacka **tutto** l'upgrade. Un
result esistente che non può dimostrare queste condizioni non viene omesso: la
migrazione fallisce.

È eleggibile ogni result v7 il cui payload strict dichiara un
`prescription_snapshot_ref` verso uno snapshot con `subject_ref` non-null. Un
payload che non permette nemmeno di decidere tale eleggibilità è malformato e
fa fallire la migrazione; soltanto un riferimento strict a snapshot legacy con
ownership null è esplicitamente ineleggibile e resta fuori dalla sidecar.

Prima di impostare `user_version=8` e committare, la migrazione verifica:
conteggio indice uguale al conteggio degli snapshot v7 non-null; nessun
eleggibile senza indice; nessun indice senza snapshot eleggibile; uguaglianza
byte-per-byte di subject e finestra decodificata per ogni coppia; e
`foreign_key_check` vuoto. Snapshot legacy con ownership null restano senza
indice e ineleggibili. Il matching non può essere abilitato su un database v8
parzialmente popolato.

La verifica pre-commit comprende inoltre: conteggio sidecar result uguale al
conteggio dei result v7 eleggibili; nessun result eleggibile senza esattamente
una sidecar; nessuna sidecar senza result e snapshot; uguaglianza di snapshot,
subject e digest ricavati strict; e presenza del solo indice schema-valid
`(prescription_snapshot_ref,matching_result_ref)` sulla nuova relazione. Un
retry dell'intera migrazione dopo rollback ripete deterministicamente lo stesso
ordine; una v8 già committata non riesegue né duplica il backfill.

Questo backfill copre soltanto gli snapshot già presenti al passaggio v7→v8.
La completezza continuativa è garantita separatamente dal contratto atomico di
creazione v8 sopra: backfill e write path convergono sulla stessa decodifica,
canonicalizzazione, digest, ownership, vincolo `start <= end` e cardinalità
1:1, ma nessuno dei due sostituisce l'altro.

L'identità canonica della riga indice post-upgrade è lo
`prescription_snapshot_id` (PK/FK 1:1); il contenuto canonico confrontato nei
retry è `(snapshot_ref, subject_ref, scheduled_window_start,
scheduled_window_end, payload_sha256)`. Il digest è SHA-256 dei byte del payload
canonico strict già persistito, non del JSON ricevuto dal client. Duplicate-ID,
digest mismatch e ownership mismatch sono pertanto conflitti distinti e
deterministici, non occasioni per sostituire la riga.

Nella stessa validazione, **prima** di creare gli indici univoci, la migrazione
raggruppa i mapping v7 prima per `actual_session_ref` e poi per
`prescription_snapshot_ref`, in ordine byte UTF-8, e richiede cardinalità al
massimo uno in entrambe le direzioni. Duplicati per sessione, duplicati per
snapshot, coppie discordanti, ownership o resolution metadata contraddittori
abortiscono e rollbackano l'intero upgrade v7→v8; non è ammesso scegliere o
cancellare una riga legacy. Solo dopo questa validazione crea entrambi gli
indici univoci e ripete i conteggi/`foreign_key_check` prima di impostare v8. La sidecar confirmation nasce vuota: popolare l'indice
finestre è struttura obbligatoria, mentre sintetizzare conferme storiche è
vietato.

## 8. Lifecycle degli output

Un `MatchingResult` `MATCHED` richiede un mapping e la fan-out completa delle
resolution per tutte le relazioni discovery rappresentate (`SINGLE` e tutte
le membership congelate di `MULTIPLE`). `CONFIRMATION_REQUIRED` e
`NOT_EVALUABLE` richiedono mapping null. Soltanto una risposta umana valida
produce un nuovo risultato `MATCHED` e mapping con
`resolution_method=ATHLETE_CONFIRMATION`, actor, timestamp e confirmation ref.
Una risoluzione direct-ID produce invece un mapping
`resolution_method=AUTOMATIC`; la provenienza `DIRECT_ID` rimane distinta nella
discovery, nel result e nell'evidence, senza estendere l'enum o i CHECK v1–v7.
Gli indici univoci sui mapping per `actual_session_ref` e per
`prescription_snapshot_ref`, insieme alla rilettura preventiva di entrambi i
lati nella transazione, impediscono un secondo mapping in qualunque direzione. Retry identico restituisce la
coppia esistente; contenuto divergente rollbacka.
«Non svolta», «non sincronizzata» e «non lo so» non producono mapping.

Un result terminale senza mapping richiede comunque una resolution
`NON_ASSOCIATIVE_CLOSURE` per ogni discovery rappresentata; un result pending
non ne richiede alcuna e vieta fan-out parziali. Un result terminale con mapping
richiede esattamente una `SELECTED_MATCH` e zero o più resolution non selezionate
con mapping null. Questi vincoli valgono anche per direct ID e reconciliation. L’expiry ordinaria
full-tuple non esiste; soltanto zero-sessioni e reconciliation possono chiudere
per expiry secondo i rispettivi chain contract.

Gli artefatti precedenti rimangono immutabili. Evaluation e consumer possono
partire soltanto da un mapping persistito univoco. Un direct ID risolto prova
la relazione; differenze di finestra o composizione restano future differenze
di aderenza.

## 9. Identità canoniche e vettori

Ogni preimage usa JSON con `ensure_ascii=False`, `sort_keys=True`, separatori
`(',', ':')`, UTF-8 strict senza BOM e nessuna normalizzazione Unicode. Liste
ordinate usano byte UTF-8 degli ID. SHA-256 è hex lowercase.

L'identità della resolution terminale è
`maintain-plan:matching-discovery-resolution:v1:sha256:<hash>` sulla preimage
canonica composta da discovery, `matching_result_ref` condiviso,
`prescription_snapshot_ref` della relation, `decision_snapshot_ref` del result
sidecar, sessione della riga, disposition, mapping nullable, selected session
nullable, decisione di compatibilità, evidence fingerprint e policy ID/version.
Per `CANDIDATE_SNAPSHOT_NOT_SELECTED`, questi due snapshot sono rispettivamente
P e Q: includerli entrambi impedisce collisioni fra più relation respinte dalla
stessa decisione. `sync_scope_ref` è
sola provenance ed è escluso. Esempio normativo non selezionato:

```text
preimage: {"actual_session_ref":"S1","compatibility_decision":"NOT_SELECTED","decision_snapshot_ref":"Q","discovery_result_ref":"D-S1","disposition":"CANDIDATE_SNAPSHOT_NOT_SELECTED","evidence_fingerprint":"evidence-v1","matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","matching_result_ref":"R-Q-tuple","prescription_mapping_ref":null,"prescription_snapshot_ref":"P","selected_session_ref":"S1"}
sha256: 2798d79162184502f4f3fe6cb26994b79c091ce9d5777096c21cbb1f3090bf6f
```

Cambiare disposition, selected session o mapping cambia l'identità; un retry
byte-identico riusa la riga canonica. La preimage `SELECTED_MATCH` include il
solo mapping canonico, mentre ogni altra preimage deve contenerlo come null.

L'`evidence_fingerprint` deterministico è SHA-256 della seguente preimage
canonica: `artifact_version`, policy ID/version, `subject_ref`,
`actual_session_id`, digest SHA-256 del payload canonico della sessione,
`candidate_mode` (`CONTAINING|ADJACENT|DIRECT_ID`), lista ordinata di oggetti
candidate con `snapshot_id`, payload SHA-256, subject, window start/end, lista
ordinata di direct-evidence ID e relativi payload SHA-256. Campi null sono
espliciti. Sono esclusi `sync_scope_ref`, tempo di discovery/commit e provenance.
Il fingerprint congela quindi esattamente i dati che possono cambiare il giudizio,
non il luogo in cui furono osservati. Per zero-sessioni usa session ID/digest null,
`candidate_mode=ZERO_SESSION` e il solo snapshot indicizzato, sia quando nello
scope non esiste alcuna sessione sia quando `remaining` diventa vuota dopo
l'esclusione autorevole di sessioni gestite da altre relazioni. ID o digest di
queste sessioni estranee non entrano nella preimage e non possono trasformare o
duplicare l'identità snapshot-centric. Ogni identità
iniziale di discovery/result/mapping incorpora questo fingerprint; un tentativo
successivo incorpora anche `previous_terminal_head_ref`.

Discovery iniziale:

```json
{"artifact_version":"1","direct_evidence_ids":[],"matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","prescription_snapshot_ids":["<ordinati>"],"evidence_fingerprint":"<sha256>","session_id":"<id>","subject_ref":"<ref>"}
```

Il discovery derivato aggiunge `confirmation_id`, che identifica l'answer
discovery-specific per `ZERO`/`MULTIPLE` oppure l'answer MatchingResult
esistente per `SINGLE`, e `previous_discovery_result_id`. Namespace
`maintain-plan:matching-discovery:v1:sha256:<hash>`.

Matching result automatico o boundary zero-sessioni:

```json
{"confirmation_id":null,"direct_evidence_ids":[],"matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","evidence_fingerprint":"<sha256>","prescription_snapshot_id":"<id>","session_ids":["<ordinati, anche vuoto>"]}
```

Namespace `maintain-plan:matching-result:v1:sha256:<hash>`. Il mapping mantiene
la preimage esistente con confirmation, snapshot, sessione e resolution method;
non esiste mapping nel caso zero sessioni.

Il result zero-sessioni originario `CONFIRMATION_REQUIRED` usa esclusivamente la
preimage precedente. **Ogni** result terminale derivato `NOT_EVALUABLE` usa
invece il namespace separato
`maintain-plan:zero-session-terminal-result:v1:sha256:<hash>` e questa preimage
versionata, senza campi impliciti:

```json
{"domain":"maintain-plan.zero-session-terminal-result","identity_version":"1","matching_policy_version":"<version>","original_matching_result_ref":"<result CONFIRMATION_REQUIRED>","prescription_snapshot_ref":"<snapshot>","previous_chain_head_ref":"<head riletto>","subject_ref":"<subject>","terminal_cause_kind":"<INITIAL_NON_ASSOCIATIVE_ANSWER|RECONCILIATION_NON_ASSOCIATIVE_ANSWER|ZERO_SESSION_EXPIRY|RECONCILIATION_EXPIRY>","terminal_cause_ref":"<answer o schedule canonico>","terminal_status":"NOT_EVALUABLE"}
```

`terminal_cause_ref` è, senza dipendenze circolari: l'ID canonico dell'answer
iniziale; l'ID canonico della reconciliation answer; l'ID indipendente dello
zero-session expiry schedule/boundary; oppure l'ID indipendente del
reconciliation expiry schedule. Il successor-event ID può includere il result
terminale già calcolato, ma il result non include mai l'evento. Stesso
predecessore e stessa causa riproducono lo stesso ID; answer, schedule o head
diversi producono ID diversi. Il domain tag e namespace rendono impossibile la
collisione con il result originario anche se snapshot, tuple vuota e policy
coincidono.

Sotto `BEGIN IMMEDIATE` si rilegge prima il predecessor head, poi si calcolano
tutti gli ID. L'ordine eseguibile è **answer se applicabile → terminal result →
result/snapshot sidecar → resolution/fan-out terminale applicabile → successor
event**. Il retry equivalente riusa tutte le righe; un'altra causa sullo stesso
head perde `UNIQUE(origin_request_ref,previous_chain_head_ref)` e rollbacka.

Un override direct-ID usa invece una forma distinta che lega esplicitamente
la discovery completa (anche `MULTIPLE`) e non perde il candidate set:

```json
{"direct_evidence_ids":["<ordinati>"],"discovery_result_id":"<discovery completa>","matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","prescription_snapshot_id":"<id selezionato>","resolution_source":"DIRECT_ID","evidence_fingerprint":"<sha256>","session_id":"<id>","subject_ref":"<ref>"}
```

Result e mapping citano `discovery_result_id`, direct evidence e selected
snapshot; la mapping aggiunge il `matching_result_id` e usa il valore
schema-valid `resolution_method="AUTOMATIC"`. `DIRECT_ID` resta esclusivamente
la `resolution_source` della discovery e l'evidence auditabile: non è e non
diventa un valore dell'enum mapping v1–v7. La discovery terminale conserva kind,
candidate refs/evidence e direct evidence originali, imposta
`selected_snapshot_ref`, `resolution_source=DIRECT_ID`, result e mapping.

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

Per un `SINGLE`, `confirmation_id` nella preimage è l'ID della risposta v8
`maintain_plan_matching_confirmation_answers`; `discovery_result_id` è la discovery `SINGLE`
originaria. Questi input impediscono che una conferma sia riciclata su un'altra
discovery e preservano actor, timestamp, snapshot e sessione nell'identità.

Confirmation discovery request:

```json
{"artifact_version":"1","discovery_result_id":"<id>","record_kind":"REQUEST"}
```

Answer: stessa preimage con `record_kind:"ANSWER"`, `request_id`, `answer_type`
e `selected_snapshot_id` (null se non selettiva). Namespace
`maintain-plan:matching-discovery-confirmation:v1:sha256:<hash>`.

La request existing MatchingResult usa l'identità canonica già derivata da
result e snapshot; la nuova answer append-only usa:

```json
{"actor":"<actor>","answer_type":"<type>","occurred_at":"<RFC3339>","request_id":"<confirmation REQUIRED>","selected_session_id":"<id|null>"}
```

Namespace `maintain-plan:matching-confirmation-answer:v1:sha256:<hash>`. Fase A
e fase B usano dunque identità indipendenti; nessuna identità dipende dal tempo
di commit o da un ordine di arrivo non persistito.

La canonical identity di un gruppo prescrizione è la tupla
`(subject_ref, scheduled_window_start, ordered_snapshot_ids)`: la lista contiene
tutti e soli gli exact same-start in ordine byte UTF-8. `scheduled_window_end`
resta evidence per containment/overlap e discovery, ma non entra nell'ordine fra
gruppi né nella scelta del successore. Ogni identity di schedule/expiry duplica
questa tupla e il digest delle righe indice validate.

Gli eventi della catena zero-sessioni usano il namespace
`maintain-plan:zero-session-event:v1:sha256:<hash>`. `EXPIRY_SCHEDULED` ed
`EXPIRED` includono `origin_request_id`, `previous_chain_head_id`,
`expiry_boundary_at`, la tupla ordinata `expiry_successor_snapshot_ids`, event
kind, subject e policy; `EXPIRED` include inoltre
`reason=UNANSWERED_BEFORE_NEXT_PRESCRIPTION`. La reconciliation usa
`maintain-plan:late-session-reconciliation:v1:sha256:<hash>` e include original
result/request, previous head, snapshot, subject, evidence fingerprint e la tupla ordinata
non vuota `candidate_session_ids`. La request di reconciliation deriva a sua
volta dall'ID attempt, dalla stessa tupla, dal `created_at` canonico e dai campi
`reconciliation_expiry_boundary_at` e
`reconciliation_expiry_successor_snapshot_ids` (null/tupla vuota quando non
ancora noti). Lo scheduling successivo identifica request, previous head,
boundary e gruppo futuro; l'expiry aggiunge reason
`UNANSWERED_RECONCILIATION_BEFORE_NEXT_PRESCRIPTION`. La dedicated answer usa namespace
`maintain-plan:late-session-reconciliation-answer:v1:sha256:<hash>` e la
preimage canonica contiene reconciliation request, response kind, selected
session nullable, candidate tuple congelata, subject, actor, `answered_at`,
versione payload e digest SHA-256 dell'audit evidence; result, mapping, sidecar
e evento successor includono il suo `answer_id`. Nessuna identità dipende dallo
stato mutabile della request.

Un evento terminale da answer include sempre `answer_source` e **uno solo** fra
`initial_confirmation_answer_id` e `reconciliation_answer_id`. Per la risposta
zero iniziale include inoltre `origin_request_id`, `previous_chain_head_id`,
`terminal_result_id`, `response_kind`, subject e policy; per la reconciliation
include request e answer reconciliation. Un evento answerless include entrambi
gli ID come null. Questa discriminazione fa parte della preimage e impedisce a
due tipi di answer con lo stesso testo di condividere identità.

Vettore normativo del result terminale zero-sessioni (`é` è U+00E9):

```text
terminal result preimage: {"domain":"maintain-plan.zero-session-terminal-result","identity_version":"1","matching_policy_version":"1.0.0-draft","original_matching_result_ref":"maintain-plan:matching-result:v1:sha256:original-é","prescription_snapshot_ref":"snapshot-é","previous_chain_head_ref":"request-é","subject_ref":"subject-é","terminal_cause_kind":"ZERO_SESSION_EXPIRY","terminal_cause_ref":"expiry-schedule-é","terminal_status":"NOT_EVALUABLE"}
SHA-256: 70a38f858b53ee8f848d8f6f04d4aeebd34b6b3345647f13ad6463a3127ffb6b
```

Vettori normativi aggiuntivi (`é` è U+00E9):

```text
initial answer event preimage: {"answer_source":"INITIAL_CONFIRMATION","event_kind":"ANSWERED","initial_confirmation_answer_id":"initial-answer-é","matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","origin_request_id":"request-é","previous_chain_head_id":"request-é","reconciliation_answer_id":null,"response_kind":"NOT_SYNCHRONIZED","subject_ref":"subject-é","terminal_result_id":"result-terminal-é"}
SHA-256: 8389135c0bcf0ae780d828f3b7a08115c44b6d03ee6fd112855e3c7e6c26321e

expiry preimage: {"event_kind":"EXPIRED","expiry_boundary_at":"2026-09-20T08:00:00Z","expiry_successor_snapshot_ids":["snapshot-next-é"],"matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","origin_request_id":"request-é","previous_chain_head_id":"request-é","reason":"UNANSWERED_BEFORE_NEXT_PRESCRIPTION","subject_ref":"subject-é"}
SHA-256: 6f688b8c61ceac7b3f0ac10e256b1672c25fb77ebd08e8609b83ff0e67788f04

reconciliation preimage: {"candidate_session_ids":["session-late-é"],"created_at":"2026-09-19T12:00:00Z","matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","original_matching_result_id":"result-zero-é","original_request_id":"request-zero-é","previous_chain_head_id":"head-é","reconciliation_expiry_boundary_at":"2026-09-21T08:00:00Z","reconciliation_expiry_successor_snapshot_ids":["snapshot-future-é"],"record_kind":"LATE_SESSION_RECONCILIATION","snapshot_id":"snapshot-é","subject_ref":"subject-é"}
SHA-256: c44aefe14f276682319addbce3db760fd55dde0d506f535e234dae6bdea6af0b

reconciliation answer preimage: {"actor":"athlete-é","answered_at":"2026-09-19T12:00:00Z","audit_evidence_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","candidate_session_ids":["session-late-é"],"payload_schema_version":"1","reconciliation_request_id":"reconciliation-é","response_kind":"MANUAL_ASSOCIATION","selected_session_id":"session-late-é","subject_ref":"subject-é"}
SHA-256: 203dc37fe80846ca2a9a50342f705eb196f279ff95ca308296de875c629599ef

reconciliation expiry preimage: {"event_kind":"RECONCILIATION_EXPIRED","matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","previous_chain_head_id":"reconciliation-request-é","reason":"UNANSWERED_RECONCILIATION_BEFORE_NEXT_PRESCRIPTION","reconciliation_expiry_boundary_at":"2026-09-21T08:00:00Z","reconciliation_expiry_successor_snapshot_ids":["snapshot-future-é"],"reconciliation_request_id":"reconciliation-request-é","subject_ref":"subject-é"}
SHA-256: ae20b0ac63a6aec9f489b9416769e5d65b1cb9d3dbea034c1f75954e1674be2f
```

Vettore normativo per il percorso zero-sessioni (`é` è U+00E9):

```text
preimage: {"confirmation_id":null,"direct_evidence_ids":[],"evidence_fingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","prescription_snapshot_id":"prescrizione-é","session_ids":[]}
SHA-256: 09050d695277f98326b6f2b42bcaebd4f9c42845d7c6d4ce49978dcf65afac45
matching_result_id: maintain-plan:matching-result:v1:sha256:09050d695277f98326b6f2b42bcaebd4f9c42845d7c6d4ce49978dcf65afac45
```

Vettori normativi per `SELECT_SNAPSHOT` (`é` è U+00E9):

```text
result preimage: {"actor":"athlete-é","confirmation_id":"answer-é","confirmed_at":"2026-09-18T10:15:00Z","discovery_result_id":"discovery-é","matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","prescription_snapshot_id":"snapshot-é","session_id":"session-é","subject_ref":"subject-é"}
result SHA-256: 8695891d6cfd60a9fbd12cbd4d8ae7494297f4d2c66cfcc825cce434fca25d09
mapping preimage: {"actor":"athlete-é","confirmation_id":"answer-é","confirmed_at":"2026-09-18T10:15:00Z","discovery_result_id":"discovery-é","matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","matching_result_id":"maintain-plan:matching-result:v1:sha256:8695891d6cfd60a9fbd12cbd4d8ae7494297f4d2c66cfcc825cce434fca25d09","prescription_snapshot_id":"snapshot-é","resolution_method":"ATHLETE_CONFIRMATION","session_id":"session-é","subject_ref":"subject-é"}
mapping SHA-256: 090e65a0386027a4f69fc4bc2327137ed9abc7651165d64070a87c982dc7f2b3
```

Vettore normativo direct-ID `MULTIPLE` (`é` è U+00E9):

```text
preimage: {"direct_evidence_ids":["direct-é"],"discovery_result_id":"discovery-é","evidence_fingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","prescription_snapshot_id":"snapshot-é","resolution_source":"DIRECT_ID","session_id":"session-é","subject_ref":"subject-é"}
SHA-256: f41eceb3545c49b9de086bfff04d97cc4a498e82836e2b53048bd23be5221a85
matching_result_id: maintain-plan:matching-result:v1:sha256:f41eceb3545c49b9de086bfff04d97cc4a498e82836e2b53048bd23be5221a85
mapping preimage: {"direct_evidence_ids":["direct-é"],"discovery_result_id":"discovery-é","evidence_fingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","matching_result_id":"maintain-plan:matching-result:v1:sha256:f41eceb3545c49b9de086bfff04d97cc4a498e82836e2b53048bd23be5221a85","prescription_snapshot_id":"snapshot-é","resolution_method":"AUTOMATIC","resolution_source":"DIRECT_ID","session_id":"session-é","subject_ref":"subject-é"}
mapping SHA-256: d5abc9a74f8af3b6a05a0f7fc482ca4b61c7b2afb12d3f669bed7dc2de53fc98
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
terminata il 18 non ha sessioni coperte. Dopo l'expiry pre-processing globale e
il percorso session-driven, quello window-driven non chiama il matcher:
costruisce il boundary outcome
`CONFIRMATION_REQUIRED` e committa result e request esistente snapshot-centric.
Lo stesso accade per prescrizioni `SINGLE`, `MULTISPORT` e `BRICK`; un retry
dello stesso scope non duplica nulla.

### 10.4 Discovery MULTIPLE

Una sessione e due snapshot rilevanti producono discovery `MULTIPLE` e una
request nella tabella dedicata. La fase A committa la request; dopo la risposta,
nella transazione di fase B vengono verificati ownership e FK e nasce un nuovo
discovery `MULTIPLE/MATCHED` con lo stesso set congelato e uno
`selected_snapshot_ref`. La vecchia discovery e la request non sono aggiornate.
Il result e mapping nuovi citano risposta, actor e timestamp e mantengono
l'evidence incompatibile originale; il matcher non viene rieseguito.

### 10.5 Boundary di sincronizzazione e guard tra percorsi

Uno scope inizia alle 00:00; una finestra termina alle 23:59 del giorno prima e
una sessione coperta inizia alle 00:01. La finestra non interseca lo scope, ma è
il predecessore immediato same-subject e quindi entra nell'evidence: l'esito è
`CONFIRMATION_REQUIRED`, mai `ZERO`. Quel predecessore resta però fuori dal set
synchronization-wide e non genera una falsa conferma zero-sessioni. Se due snapshot vicini producono `MULTIPLE`, il percorso window-driven
considera gestite, prima e dopo la risposta, tutte le coppie congelate **per la
sessione originaria**. Dopo `SELECT_SNAPSHOT` salta la relazione non selezionata
per quella sessione, ma non lo snapshot per sessioni differenti. Il solo
mapping della resolution originaria è
quello confirmation-aware; dopo una risposta non associativa non nasce mapping.

Con un direct ID valido la catena termina `MATCHED` e il mapping usa
`AUTOMATIC`; un retry window-driven rileva la catena completa e non riprocessa
la coppia. Lo stesso lookup impedisce il reprocessing dopo una testa
`NOT_EVALUABLE`. Due run concorrenti serializzano su `BEGIN IMMEDIATE`: il
secondo rilegge la testa committata dal primo e compie lo stesso skip.

### 10.6 Scope multi-day, finestra puntuale e SINGLE

Uno scope di tre giorni contiene una prescrizione lunedì e una mercoledì. La
sessione di lunedì riceve il proprio set del §3.3, non l'unione multi-day: la
finestra di lunedì contiene `S.start`, quindi non vengono neppure caricati i
gruppi adiacenti e la prescrizione mercoledì non la trasforma artificialmente
in `MULTIPLE`. Una
finestra puntuale con `start == end == S.start` è valida, viene indicizzata e
contiene inclusivamente `S.start`.

Se l'unico snapshot candidato è appena fuori finestra, nasce discovery
`SINGLE/CONFIRMATION_REQUIRED` con `matching_result_ref` non-null e mapping
null. La request `maintain_plan_confirmations` riferisce quel result. Una
risposta associativa valida genera, nell'ordine answer, mapping, result,
sidecar e discovery derivato, un `SINGLE/MATCHED`; result e mapping citano
answer, actor e timestamp, mentre l'evidence fuori-finestra resta auditabile.

### 10.7 Direct-ID override e lifecycle a due fasi

Due finestre sovrapposte contengono `S.start`; il candidate set congelato ha
quindi cardinalità due. Un direct ID strict, univoco e same-subject seleziona
la seconda: la discovery resta `MULTIPLE`, diventa `MATCHED`, conserva entrambe
le candidate e registra selected snapshot, source `DIRECT_ID`, result e
mapping con `resolution_method=AUTOMATIC`. Un ID dangling o
ownership-mismatched rollbacka senza richiesta.

Per una discovery `MULTIPLE` senza direct ID, la fase A committa la request e
chiude la transazione prima di mostrarla. Minuti dopo, la fase B rilegge request
e testa pending; una risposta valida inserisce atomicamente answer, mapping,
result, sidecar e discovery `MULTIPLE/MATCHED`. Due risposte concorrenti non
mutano la request: una sola può vincere `UNIQUE(request_ref)`.

### 10.8 Expiry senza risposta e prescrizione successiva

Una request zero-sessioni per lo snapshot A non riceve risposta. Quando lo
scope rende noto B, gruppo same-subject immediatamente seguente con start
strettamente maggiore dello start di A, viene congelato l'intero gruppo di B.
B è successore anche se la sua finestra si sovrappone ad A, è contenuta in A o
inizia esattamente a `A.end`; non deve iniziare dopo `A.end`. Prima di qualunque processing session-driven o
window-driven di B, lo sweep globale rilegge la testa
e appende per A `NOT_EVALUABLE/UNANSWERED_BEFORE_NEXT_PRESCRIPTION`, senza
answer né mapping e conservando warning/evidence. Soltanto il commit successivo
consente il processing di B. Se B non era noto alla fase A di A, A restava
legittimamente pending fino a questa sync. Anche se la sync importa una sessione
per B, expiry A committa prima di discovery/result/mapping per B. Un answer
simultaneo e lo sweep
serializzano: il primo successore committato vince, il secondo rilegge e non
crea una seconda testa.

### 10.9 Sessione tardiva e associazione manuale legale

La request iniziale di A congela `declared_session_refs=[]` e quindi non mostra
associazione manuale. Una sync successiva persiste S; prima del percorso
automatico, la guard trova la catena zero-sessioni (sia pending sia già
expired/risolta), valida ownership e scope e congela `(S)` nella nuova
reconciliation request. Solo questa request mostra `MANUAL_ASSOCIATION(S)`.
L'accettazione crea prima la dedicated reconciliation answer e poi un solo
mapping `ATHLETE_CONFIRMATION`, result, sidecar ed evento successor con link a
result e request originali, request/answer reconciliation, actor e timestamp;
risposta non associativa persistono la answer con sessione null e
chiudono `NOT_EVALUABLE` senza mapping, mentre expiry non crea answer. Due
sessioni tardive visibili nello stesso scope sono
ordinate e congelate insieme; una selezione fuori tupla fallisce chiusa. Le
guardie session-driven e window-driven impediscono entrambe un mapping
automatico concorrente.

### 10.10 Scope sovrapposti e guard autorevole

Lo scope X crea un mapping per S. Lo scope Y sovrapposto rilegge S: la guard
globale trova prima il mapping per `actual_session_ref`, lo restituisce e non
chiama il matcher, anche se `sync_scope_ref` è diverso. Se X aveva lasciato una
request pending, Y espone la stessa request. Se la testa era terminale senza
mapping e fingerprint identico, Y non crea nulla; soltanto una modifica reale a
payload sessione, candidate indicizzate, window o direct evidence cambia il
fingerprint e consente un tentativo collegato alla testa terminale precedente.

### 10.11 Prima run con due finestre già persistite e nessuna sessione

La prima sincronizzazione copre A e B, due finestre consecutive same-subject già
persistite, e non importa sessioni. L'ordine cronologico sceglie A. Poiché B è
già il successore autorevole e il suo boundary è raggiunto, una sola
`BEGIN IMMEDIATE` crea result/request/scheduling di A e ne appende subito
`NOT_EVALUABLE/EXPIRED`; solo dopo quel commit il loop avanza a B e può creare la
sua request. A non è mai osservabile pending mentre B viene processato.

### 10.12 Multi-day con sessioni gestite altrove

Uno scope multi-day contiene lo snapshot A, la cui finestra chiusa non ha
attività, e sessioni già mappate o presenti in discovery per gli snapshot B e
C. Il lookup snapshot-level non trova mapping, discovery, result/request
zero-sessioni, reconciliation o terminale relativo ad A. Il filtro session-level
esclude invece tutte le sessioni B/C, senza ricandidarle per A; `remaining=()`.
Poiché A stesso non è handled, il boundary crea esattamente un `MatchingResult`
zero-sessioni e una request per A. Retry dello stesso scope, scope sovrapposto o
writer concorrente rileggono quell'identità e non ne creano una seconda.

Nel caso complementare A possiede già il proprio result/request zero-sessioni,
oppure una reconciliation o testa terminale raggiungibile dalla stessa catena.
Il primo lookup marca A handled e lo salta, qualunque sia la presenza di
sessioni B/C: non nasce un secondo result/request e nessuna sessione altrui
viene reinterpretata.

### 10.13 Origini della sidecar

Una selezione discovery o una answer `SINGLE` crea una sidecar con
`discovery_result_ref` non-null e il rispettivo unico confirmation ref. Una
manual association tardiva inserisce invece reconciliation answer, mapping,
result, sidecar con `discovery_result_ref=null` e
`reconciliation_answer_ref` non-null, poi l'evento successor. La FK immediata è
soddisfatta in ogni passaggio e la catena zero originaria resta raggiungibile
attraverso request e answer di reconciliation.

### 10.14 Gruppi canonici, overlap e finestre puntuali

A1 e A2 hanno lo stesso start ma end diversi: costituiscono un solo gruppo A,
ordinato internamente per ID UTF-8, e non scadono l'uno per l'altro. B ha start
strettamente maggiore ma precedente ad `A1.end` (overlap/containment): è il
successore immediato di entrambi. Prima di processare qualsiasi membro di B le
request zero-sessioni di A sono chiuse; nello stesso tempo una sessione nel
tratto sovrapposto conserva A e B come candidate e può produrre `MULTIPLE`.
La medesima regola vale se A è puntuale, se B inizia esattamente ad `A.end` o se
B è parzialmente sovrapposto: contano soltanto gruppi/start canonici, mai la
relazione fra gli end.

### 10.15 Deadline propria della reconciliation

La request zero di A è già scaduta quando una sessione tardiva genera R alle
`2026-09-19T12:00:00Z`: R non riusa il vecchio boundary. Il primo gruppo
same-subject con start strettamente successivo al `created_at` committato di R,
per esempio C alle `2026-09-21T08:00:00Z`, diventa il suo boundary e l'intero
gruppo C ne è evidence. Se C non è ancora noto, R resta pending; la sync che lo
scopre schedula e, se già dovuto, committa `RECONCILIATION_EXPIRED` con result
`NOT_EVALUABLE` prima di qualsiasi matching di C. Nessuna answer o mapping è
creata e tutte le evidence zero/reconciliation restano raggiungibili. Answer ed
expiry concorrenti rileggono la stessa testa sotto `BEGIN IMMEDIATE`: un solo
successore vince.

### 10.16 Answer iniziale e testa terminale

Una request zero-sessioni pending riceve `NOT_SYNCHRONIZED`. La fase B rilegge
la testa, inserisce la `maintain_plan_matching_confirmation_answers`, il result
`NOT_EVALUABLE` e l'evento `ANSWERED/INITIAL_CONFIRMATION` che cita soltanto
quella answer, quindi committa. Uno sweep expiry partito subito dopo vede la
testa terminale e fa no-op; se aveva acquisito prima `BEGIN IMMEDIATE`, vince
invece l'expiry e l'answer diventa stale senza insert parziali. La stessa regola
vale per `NOT_PERFORMED` e `DONT_KNOW`. Una answer reconciliation usa
`ANSWERED/LATE_RECONCILIATION` e soltanto la FK reconciliation dedicata.

### 10.17 Snapshot creato dopo l'upgrade

Il repository riceve un nuovo snapshot v8 con finestra puntuale valida. Nella
stessa `BEGIN IMMEDIATE` decodifica e valida il payload, inserisce snapshot e
unica riga `maintain_plan_snapshot_window_index`, verifica subject, finestra e
digest, poi committa. Un errore indice rollbacka anche lo snapshot. Un retry
identico osserva la coppia e fa no-op; stesso ID con digest o ownership diverso
fallisce chiuso. Due writer concorrenti non possono lasciare né uno snapshot
orfano né una riga indice orfana. Il successivo discovery interroga soltanto
l'indice e vede la finestra zero-length perché `start == end` è valido.

### 10.18 MULTISPORT compatible, incompatible, ambiguous e malformed

Snapshot `M` e sessione `S` sono ownership-bound allo stesso subject, entrambi
`MULTISPORT`, in finestra, con due componenti ordinate e discipline esatte:
il branch §4.2 produce `MATCHED` automatico e lo stesso mapping posizionale di
un caso `SINGLE` non ambiguo, senza brick policy. Se `S.start` è fuori finestra
oppure una disciplina/cardinalità/ordine/composition non coincide, produce
`CONFIRMATION_REQUIRED`, mapping nullo e le reason keys esatte dei predicati
falliti. Se la candidate tuple contiene due sessioni entrambe compatibili,
produce ancora `CONFIRMATION_REQUIRED` e conserva entrambe, senza ranking.

Se `M` è valido ma una sessione canonica non porta la struttura necessaria a
calcolare uno dei cinque predicati, il risultato è `NOT_EVALUABLE` con reason
`multisport compatibility input is structurally incomplete`. Se invece `M`
porta una brick policy, un timestamp è naive, una reference è dangling o il
subject non coincide, il validator/ownership boundary fallisce tecnicamente e
rollbacka: non pubblica un falso outcome. Il matcher corrente non soddisfa
ancora questo esempio; il flag resta disabilitato fino alla sua modifica futura.

### 10.19 Backfill e write atomica della sidecar result

Durante v7→v8 un result `R` decodifica univocamente lo snapshot ownership-bound
`P`: la migrazione inserisce `(R,P,subject,payload_sha256)` nella sidecar e solo
dopo crea l'indice `(P,R)`. Un secondo result dangling o con ownership diversa
fa rollbackare anche la riga di `R`; non rimane una v8 parziale. Dopo l'upgrade,
un nuovo result inserisce result e sidecar nello stesso `BEGIN IMMEDIATE` (e,
per `MATCHED`, mapping → result → sidecar). Un retry identico fa no-op; stesso
ID con digest diverso fallisce; due writer concorrenti non possono committare
un result orfano. Guard e discovery trovano `R` mediante la sidecar, senza
estrarre `prescription_snapshot_ref` dal JSON.


### 10.20 Due sessioni compatibili per uno snapshot

Lo snapshot P è candidato per S1 e S2 nello stesso scope; entrambe sono
same-subject, in finestra e compatibili. La worklist contiene P una sola volta e
il matcher riceve `(S1,S2)` in ordine `(start, session_id UTF-8)`. Pubblica un
solo result/request `CONFIRMATION_REQUIRED` con la tupla completa e nessun
mapping. Soltanto una selezione athlete valida può creare un mapping verso S1
o S2; l'altra sessione e P restano protetti dalla catena.

### 10.21 Una sessione compatibile e una incompatibile

Per P la tupla completa è `(S1,S2)`: S1 soddisfa tutti i predicati e S2 no. Il
matcher viene chiamato una volta, non due, e produce il mapping automatico
univoco `P↔S1`; S2 non sopprime il match e non può acquisire P in seguito.

### 10.22 Snapshot già mappato in scope sovrapposti

Lo scope X ha committato `P↔S1`. Lo scope Y sovrapposto include P e S2. La
guardia per `prescription_snapshot_ref` trova il mapping prima della worklist,
lo rilegge anche dal lato sessione e osserva/riusa la relazione: P non viene
valutato né mappato a S2 e non nasce una catena parallela.

### 10.23 Due selezioni concorrenti sullo stesso snapshot

Due transazioni tentano contemporaneamente `P↔S1` e `P↔S2`. Ciascuna apre
`BEGIN IMMEDIATE` e rilegge entrambi i lati. Una sola inserisce; l'indice unico
su `prescription_snapshot_ref` rende l'altra confliggente e questa rollbacka
senza result o sidecar parziali. Non esiste first-session-wins applicativo: il
solo vincitore possibile deriva dalla risposta/autorizzazione già validata.

### 10.24 Retry della stessa mapping canonica

Un retry di `P↔S1` trova lo stesso mapping ID e gli stessi subject, metodo,
evidence e riferimenti sui due lookup. Rilegge e restituisce quel record senza
insert. Una variazione di sessione, snapshot, metodo o digest è conflitto
fail-closed, non un retry.

### 10.25 Upgrade con mapping legacy duplicate per snapshot

In v7 esistono `P↔S1` e `P↔S2`. La validazione raggruppata per
`prescription_snapshot_ref` rileva cardinalità due prima di creare gli indici;
l'intera migrazione v7→v8 rollbacka e `user_version` resta invariato. Nessuna
riga viene scelta, cancellata o riscritta.

### 10.26 Fan-out terminale: compatibile e incompatibile

P ha discovery `D1=SINGLE(P,S1)` e `D2=SINGLE(P,S2)`; S1 è compatibile e S2
incompatibile. Una sola evaluation di `(P,(S1,S2))` crea result `R=MATCHED` e
mapping `M=P↔S1`. Nello stesso commit inserisce
`D1→SELECTED_MATCH(R,M,S1)` e `D2→INCOMPATIBLE(R,null,S1)`. D2 è terminale ma
non cita M: il suo `prescription_mapping_ref` è obbligatoriamente null.

### 10.27 Due compatibili, prima e dopo la scelta

P, S1 e S2 producono `R0=CONFIRMATION_REQUIRED`; D1 e D2 restano entrambe
pending e non esiste mapping né resolution terminale. La selezione valida di
S1 inserisce atomicamente answer, `M=P↔S1`, `R1=MATCHED`, sidecar,
`D1→SELECTED_MATCH(R1,M,S1)` e
`D2→COMPATIBLE_NOT_SELECTED(R1,null,S1)`. La riga di S2 prova quindi una
chiusura terminale senza mapping e non può essere scambiata per P↔S1.

### 10.28 Chiusura non associativa della tupla completa

Una rejection, `DONT_KNOW` o outcome `NOT_EVALUABLE` per
`(P,(S1,S2))` crea/usa un result terminale senza mapping e, nello stesso
commit, due resolution `NON_ASSOCIATIVE_CLOSURE`. Nessuna discovery della
tupla può rimanere pending o prendere un mapping da un'altra catena.

### 10.29 Race fra due selezioni (nessuna expiry ordinaria)

Due selezioni concorrenti aprono `BEGIN IMMEDIATE`, rileggono
request/head e D1/D2. Il primo successore valido inserisce **l'intera** fan-out;
gli altri rileggono e fanno no-op solo se byte-equivalenti, altrimenti falliscono
chiusi. Non può esistere una seconda `SELECTED_MATCH` per R né un secondo
mapping. Non esiste un concorrente expiry per questa confirmation ordinaria: senza answer
la request e D1/D2 rimangono pending. Solo le catene zero-sessioni e
reconciliation dei §§5.1–5.2 hanno sweep ed eventi di expiry.

### 10.30 Retry e rollback della fan-out

Dopo il commit completo, un retry di P/S1/S2 ritrova result, mapping e le due
resolution canoniche e non inserisce nulla. Se durante il primo tentativo D2
non può essere risolta (FK, uniqueness, membership o evidence discordante),
l'insert di D1, result, mapping e sidecar rollbackano insieme: non rimangono né
mapping né result terminale né una discovery orfana pending accanto a una
fan-out parziale.

### 10.31 Vettori normativi dei cinque finding

* Planned indexes `(0,2)` e observed `(0,1)` hanno cardinalità uguale ma index
  mismatch: `CONFIRMATION_REQUIRED`, mai mapping. `(0,2)` e `(0,2)` preservano
  i buchi e possono proseguire ai controlli disciplina/sostituzione. Un duplicato
  o indice non comparabile è `NOT_EVALUABLE` con evidence strutturale.
* Se una sostituzione vincola `environment=OUTDOOR` e observed omette
  environment, la dimensione è unknown ma non rende incompatibile l'intera
  sessione; observed `INDOOR` è invece conflitto incompatibile. Identico vale
  per `mode`.
* La discovery `D0=MULTIPLE(P1,P2)` di S0 risolta via direct ID su P1 e la
  discovery `D1=SINGLE(P1)` di S1 alimentano una sola evaluation di P1. Se S0 è
  selezionata, la fan-out atomica produce `D0→SELECTED_MATCH` e D1
  `INCOMPATIBLE` o `COMPATIBLE_NOT_SELECTED`, con esattamente un mapping; P2
  resta chiuso per la relazione con S0, ma non è globalmente consumato e può
  essere valutato per un'altra sessione. Retry identico riusa la fan-out;
  selezione o
  mapping concorrente divergente rollbacka integralmente.
* Il lookup confirmation schema-valid è
  `maintain_plan_confirmations(prescription_snapshot_ref, confirmation_id)`;
  `request_id` non è una colonna di quella tabella e non compare in alcun DDL.
* Una confirmation ordinaria full-tuple con più compatibili non ha deadline:
  resta pending fino a answer valida. Le expiry zero-sessioni (prima del gruppo
  successore) e reconciliation (al proprio boundary) restano invariate e sono
  gli unici due request type soggetti a sweep automatico.


### 10.32 Release relation-level dopo `MULTIPLE`

S1 congela `MULTIPLE(P,Q)` e l'atleta seleziona Q. La fan-out committa
`(S1,Q)=SELECTED_MATCH` con l'unico mapping e
`(S1,P)=CANDIDATE_SNAPSHOT_NOT_SELECTED` terminale con mapping null. Entrambe le
relazioni sono chiuse per S1, ma soltanto Q è globalmente consumato. P resta
nella worklist per S2; se `(S2,P)` è la sua sola relazione compatibile, la
`SINGLE` di S2 termina `SELECTED_MATCH` e mappa P. Le transazioni S1→Q e S2→P
possono entrambe committare perché entrambi i lati dei mapping sono distinti.
La stessa semantica vale quando Q è scelto da direct ID: frozen evidence P/Q
resta completa, `(S1,P)` è terminale senza mapping e P non è soppresso per S2.

Se invece due sessioni concorrenti S2 e S3 tentano lo stesso P precedentemente
non selezionato per S1, entrambe rileggono relation, session e snapshot guard
sotto `BEGIN IMMEDIATE`. La prima mapping canonica committata occupa P tramite
l'unicità di `prescription_snapshot_ref`; il retry identico la riusa, mentre il
concorrente che seleziona l'altra sessione rilegge il vincitore e fallisce
chiuso senza fan-out parziale. La membership non selezionata `(S1,P)` non decide
la race e non equivale a consumo globale.

### 10.33 Copertura completa per zero-sessioni

Per una finestra overnight `[2026-09-20T22:00Z, 2026-09-21T06:00Z]`, la coverage
half-open `[2026-09-20T00:00Z, 2026-09-22T00:00Z)` soddisfa start inclusivo ed
end strettamente interno: in assenza di sessioni può nascere il result zero.
Una coverage della sola coda `[2026-09-21T00:00Z, 2026-09-22T00:00Z)` enumera
la finestra per intersezione, ma non copre gli start dalle 22:00 a mezzanotte:
non crea result/request zero, expiry o successor event. Una sessione realmente
osservata nella coda può comunque seguire il matching ordinario.

I frammenti `[20T22:00Z,21T01:00Z)` e `[21T02:00Z,21T07:00Z)` hanno un gap e non
provano l'assenza; i frammenti adiacenti
`[20T22:00Z,21T01:00Z)` e `[21T01:00Z,21T07:00Z)` si fondono e coprono l'intera
finestra, autorizzando zero-sessioni. Per una point window a `t`, coverage
`[a,t)` non basta perché `t == coverage_end`; coverage `[t,b)` con `t < b`
la copre. In tutti i casi il test di copertura precede creazione zero,
scheduling expiry e processing del successore.

### 10.34 Identità terminale e validazione eseguibile v8

Il result zero originario Z (`CONFIRMATION_REQUIRED`) e il terminale T
(`NOT_EVALUABLE`) hanno namespace e preimage differenti; il vincolo typed
impone inoltre `T != Z`. Per lo stesso head H, answer A riproduce T(A,H), mentre
answer B, expiry schedule E o head H2 producono ID differenti. Il successor
event cita T soltanto dopo che T e la sidecar sono inseriti; T non cita mai
l'event ID.

Per `MULTIPLE(P,Q)` risolta su Q, il result sidecar indica Q. La resolution
`SELECTED_MATCH` usa relation=decision=Q e porta l'unico mapping; la resolution
`CANDIDATE_SNAPSHOT_NOT_SELECTED` usa relation=P, decision=Q e mapping null.
Un trigger rifiuta P non membro, P=Q, Q non selected, source non autorevole,
subject/session divergenti o qualunque mapping sulla riga P. Dopo il commit P
resta mappabile a S2. Se una riga della fan-out fallisce, l'intera
`BEGIN IMMEDIATE` rollbacka.

Prima del commit documentale è stata eseguita una simulazione SQLite temporanea
non versionata con `PRAGMA foreign_keys=ON`. Il DDL eseguibile ha materializzato
le tabelle correnti coinvolte e tutte le relazioni additive v8 coinvolte in
questi flussi, con gli stessi nomi di tabella/colonna, FK immediate, CHECK,
indici univoci e trigger dichiarati nel §7. Ha eseguito: origine zero seguita da
expiry; origine zero seguita da answer non associativa; reconciliation answer ed
expiry; retry di ogni causa; due cause concorrenti sullo stesso predecessor;
`MULTIPLE(P,Q)`→Q con resolution P→Q; mapping successiva P→S2; membership
respinta invalida; mapping vietato sulla resolution non selezionata; rollback di
fan-out parziale. `PRAGMA foreign_key_check` ha restituito zero righe e
`PRAGMA integrity_check` ha restituito `ok`. Lo script e il database temporanei
non fanno parte del repository.

L'audit DDL ha verificato specificamente che ogni colonna usata dai trigger
esista: `decision_snapshot_ref` e `subject_ref` nella resolution,
`terminal_result_ref` con FK nell'evento, i quattro typed cause ref nella
sidecar terminale, e gli indici sulle sole colonne dichiarate. L'ordine
eseguibile verificato è ID precompute e head re-read → answer eventuale → result
terminale → result/snapshot sidecar → fan-out → event; nessuna FK differita o
identità circolare è richiesta.

## 11. Errori, upgrade e decisioni residue

Sono errori tecnici: scope assente/non riuscito/incoerente; righe nel perimetro
corrotte; ownership discordante; direct evidence malformata; timestamp naive;
direct ID dichiarato ma vuoto, dangling, ambiguo o ownership-mismatched; FK dangling;
payload/colonne discordanti; risposta non appartenente al set o
allo scope; retry divergente. Sono esiti di dominio: zero/più snapshot,
zero/più sessioni, fuori finestra, mismatch e risposta non risolutiva.

DB v1–v7 non abilita questo boundary. La futura v8 è additiva e richiede tutte
le tabelle, indici, trigger e checksum coerenti. “Nessun backfill storico” vale
per discovery, result, confirmation e mapping: non inventa outcome per sync
passati. **Non** vale per la popolazione strutturale obbligatoria dell'indice
finestre durante v7→v8 (§7). Record legacy con ownership nulla restano non
indicizzati e ineleggibili.

### 11.1 Audit interno di coerenza

L'audit normativo completo ha verificato: (1) ordine globale expiry
pre-processing → session-driven → window-driven e guardia sull'intera catena in
ogni stato; (2) transizioni `ZERO`,
`SINGLE`, `MULTIPLE`, `MATCHED`, `CONFIRMATION_REQUIRED` e `NOT_EVALUABLE`;
(3) confirmation snapshot-centric e discovery-specific senza riuso di shape
incompatibili; (4) `SELECT_SNAPSHOT` confirmation-aware senza secondo giudizio
automatico; (5) upgrade v7→v8 tutto-o-niente con popolazione e conteggi esatti;
(6) FK immediate effettive di `schema.py` e ordine answer→mapping→result→
sidecar→discovery; (7) retry equivalenti idempotenti e conflitti divergenti
fail-closed; (8) un solo mapping in entrambe le direzioni — sessione→snapshot e snapshot→sessione — tra entrambi i percorsi; (9) set
per-sessione separati dall'unione synchronization-wide; (10) invariant v7
`start <= end`, incluse finestre zero-length; (11) matrice completa dei ref e
uso della confirmation MatchingResult esistente esclusivamente per `SINGLE`;
(12) request e answer sempre in due transazioni committate senza lock durante
l'attesa; (13) cardinalità congelata distinta dalla resolution e stato
`MULTIPLE/MATCHED` persistibile per direct ID o selezione umana; (14) priorità
del set contenente sugli adiacenti, usati solo quando il primo è vuoto; (15)
early return effettivo di `matching_service.match`, validazione di `SINGLE`,
`MULTISPORT` e `BRICK` e boundary zero-sessioni indipendente dal matcher; (16)
enum/CHECK mapping esistente limitato ad `AUTOMATIC|ATHLETE_CONFIRMATION`, con
`DIRECT_ID` soltanto discovery source; (17) enumerazione synchronization-wide
solo per intersezione e vicini soltanto nel fallback per-sessione; (18) deadline
outcome-contract resa deterministica dal primo gruppo successor e sweep prima
del suo processing, incluso il caso successor non ancora noto; (19) request
zero con tupla vuota priva di opzioni associative e reconciliation append-only
con tupla non vuota e membership strict; (20) arrivo tardivo prima/dopo expiry,
answer stale e race answer/reconciliation/expiry su una sola testa; (21) guard
pre-matcher su entrambi i percorsi e indici one-to-one mapping/sessione e mapping/snapshot; (22) ogni
request v8 ha la propria answer compatibile, con FK immediate eseguibili e senza
riuso cross-type; (23) membership exact/nullability delle answer reconciliation,
request immutabile `REQUIRED`, closure append-only e ordine answer→mapping→
result→sidecar→successor; (24) one-successor/one-winning-answer sotto
`BEGIN IMMEDIATE`, inclusa la race expiry/answer/reconciliation e retry
idempotenti; (25) guard cross-scope prima di ogni matcher, lookup globale e
fingerprint semantico indipendente dalla provenance; (26) creazione+expiry
atomiche del predecessore appena creato prima di avanzare al successor; (27)
sidecar con origini mutuamente esclusive e `discovery_result_ref` nullo soltanto
per reconciliation; (28) tutti i valori confirmation verificati contro
`models.py` e `schema.py`, incluso esclusivamente `NOT_SYNCHRONIZED`;
(29) predicati handled snapshot-level e session-level distinti, con empty tuple
post-filtro che crea il caso zero per uno snapshot mai gestito, lookup
indicizzato deterministico, idempotenza su scope sovrapposti e nessuna
reinterpretazione delle sessioni legate ad altre prescrizioni; (30) ordine
canonico per gruppi di start con same-start indivisibili e successore immediato
a start maggiore, incluse finestre overlapping, contenute, puntuali e adiacenti;
(31) expiry già dovuta atomica prima del gruppo successivo pur preservando
`MULTIPLE`; (32) deadline reconciliation propria, successiva al `created_at`
committato, discovery futura, scheduling e race answer/expiry append-only.

L'estensione di audit richiesta ha inoltre verificato: (33) ogni event kind
zero-sessioni contro entrambe le answer FK e la matrice nullability, inclusa la
distinzione fra answer iniziale e reconciliation; (34) le tre risposte iniziali
chiudono atomicamente la testa prima che expiry o reconciliation possano
osservarla; (35) backfill v7→v8 e creazione snapshot v8 sono percorsi separati
ma applicano la stessa validazione strict e preservano `start <= end`; (36)
completezza bidirezionale snapshot/indice 1:1 dopo ogni commit; (37) rollback,
retry equivalente, duplicate ID, mismatch di digest/ownership e insert
concorrenti non possono produrre coppie parziali; (38) discovery legge ancora
esclusivamente l'indice validato. Nessuna delle verifiche richiede trigger JSON
SQLite o modifica runtime in questa PR.

L'audit aggiuntivo ha confrontato direttamente l'ordine degli early return di
`matching_service.match` e la composizione di `validate_prescription`: (39)
`SINGLE` e `BRICK` mantengono i branch esistenti, mentre `MULTISPORT` richiede
il branch futuro senza brick policy e il feature resta disabilitato; (40) i
casi automatico, incompatibile, ambiguo e strutturalmente incompleto seguono la
matrice del §4.2; (41) l'inventario v8 non dichiara indici su colonne result
inesistenti; (42) backfill result-sidecar, write atomiche post-upgrade,
completezza 1:1, rollback, retry e concorrenza sono eseguibili con FK immediate
nell'ordine mapping → result → sidecar; (43) la worklist snapshot-centric è deduplicata, passa al matcher una sola volta la tupla completa ordinata e non usa chiamate singleton; (44) guardie e lookup mapping sono simmetrici sui due riferimenti; (45) ogni percorso capace di creare mapping — automatico, direct ID, `SELECT_SNAPSHOT`, confirmation `SINGLE` e reconciliation tardiva — rilegge entrambi i lati sotto `BEGIN IMMEDIATE`; (46) i due indici univoci, il controllo duplicati v7→v8 e le sei prove §§10.20–10.25 dimostrano `actual_session_ref →` al massimo uno snapshot e `prescription_snapshot_ref →` al massimo una sessione.

L'audit terminal-discovery ha inoltre enumerato automatico, direct ID,
selection confirmation, confirmation `SINGLE`, reconciliation, rejection,
expiry e `NOT_EVALUABLE`: (47) ogni discovery `SINGLE` rappresentata termina
esattamente una volta per relation tramite
`UNIQUE(discovery_result_ref,prescription_snapshot_ref)`; (48) ogni fan-out
ha zero mapping oppure esattamente una `SELECTED_MATCH`; (49) CHECK, FK e indice
unico parziale rendono impossibile collegare una non selezionata al mapping di
un'altra sessione; (50) conteggio pre-commit e rollback totale impediscono a un
result snapshot-level terminale di lasciare una discovery pending; (51) un
result `CONFIRMATION_REQUIRED` full-tuple lascia invece tutte le discovery
coerentemente pending fino a una sola answer vincente; (52) i casi §§10.26–10.30
coprono fan-out completa, race, retry e failure intermedia.

L'audit finale dei cinque finding ha inoltre verificato: (53) tutti i predicati
MULTISPORT confrontano gli indici esatti prima del pairing e classificano
malformed/non-comparable come `NOT_EVALUABLE`; (54) metadata optional mancanti
sono evidence unknown non eliminatoria, mentre conflitti presenti sono
incompatibili; (55) ogni combinazione terminale `SINGLE` e authoritative
`MULTIPLE` è rappresentabile nella fan-out, conserva frozen candidates e vieta
borrowed mapping; (56) ogni lookup v8 cita colonne esistenti o additive e quello
confirmation usa `confirmation_id`; (57) solo zero-sessioni e reconciliation
hanno expiry, mentre la confirmation full-tuple ordinaria resta pending; (58)
fan-out completa, retry, rollback e conflitti concorrenti sono serializzati e
atomici. (63) result zero originario e terminale usano
namespace/preimage distinti, typed cause ref non circolari e insertion order
verificato; (64) la validazione conditional P→Q è limitata a
`CANDIDATE_SNAPSHOT_NOT_SELECTED`, mentre ogni disposition ordinaria mantiene
snapshot equality; (65) la simulazione SQLite temporanea ha esercitato FK,
CHECK, trigger, retry, race, release e rollback e ha superato
`foreign_key_check`/`integrity_check`. (59) ogni uso di handled distingue guard relation, session e snapshot:
una terminale `MULTIPLE` chiude tutte le relazioni originarie ma consuma
soltanto la selected; (60) direct ID e selezione atleta preservano frozen
evidence senza sopprimere candidate non selezionate per altre sessioni; (61)
zero-sessioni, expiry e successor processing richiedono la union continua di
coverage dell'intera finestra, con start inclusivo, end esclusivo stretto e
point-window non coperta al boundary finale; (62) retry cross-scope e race su
snapshot uguale restano canonici sotto `BEGIN IMMEDIATE` e unicità dei due lati.

**Non resta alcuna decisione normativa bloccante.** Restano lavoro
implementativo: definire modelli/codec, migrazione v8, repository, adapter dello
scope, aggiornare il matcher composition-aware, flag/wiring e test di
race/rollback. Fino ad allora tutto il comportamento
descritto resta non implementato e disabilitato.
