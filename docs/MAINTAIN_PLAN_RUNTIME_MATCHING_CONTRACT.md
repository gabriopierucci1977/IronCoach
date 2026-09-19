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
set multiplo. Tutti gli altri casi direct-ID falliscono chiusi secondo il
§3.3: non è lecito degradarli a una scelta umana.

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

Candidate ed evidence hanno uguale cardinalità e ordine. `ZERO` richiede
entrambe vuote, `SINGLE` una, `MULTIPLE` almeno due. La matrice normativa
completa è:

| kind | resolution status | `matching_result_ref` | `prescription_mapping_ref` | mapping method | confirmation mechanism |
|---|---|---|---|---|---|
| `ZERO` | `CONFIRMATION_REQUIRED` | null | null | — | discovery-specific §6 |
| `ZERO` | `NOT_EVALUABLE` (risposta non selettiva) | null | null | — | discovery-specific §6 |
| `ZERO` | `MATCHED` | non-null | non-null | `ATHLETE_CONFIRMATION` | `SELECT_SNAPSHOT` same-scope §6 |
| `SINGLE` | `MATCHED` automatico/direct ID | non-null | non-null | `AUTOMATIC` | nessuna |
| `SINGLE` | `MATCHED` derivato | non-null | non-null | `ATHLETE_CONFIRMATION` | existing MatchingResult confirmation |
| `SINGLE` | `CONFIRMATION_REQUIRED` | **non-null** | null | — | existing `maintain_plan_confirmations` sul result |
| `SINGLE` | `NOT_EVALUABLE` | non-null | null | — | risposta existing MatchingResult confirmation |
| `MULTIPLE` | `CONFIRMATION_REQUIRED` | null | null | — | discovery-specific §6 |
| `MULTIPLE` | `NOT_EVALUABLE` (risposta non selettiva) | null | null | — | discovery-specific §6 |
| `MULTIPLE` | `MATCHED` direct ID | non-null | non-null | `AUTOMATIC` | nessuna; `resolution_source=DIRECT_ID` |
| `MULTIPLE` | `MATCHED` selezione umana | non-null | non-null | `ATHLETE_CONFIRMATION` | `SELECT_SNAPSHOT` §6 |

La kind descrive sempre la cardinalità dell'evidence inizialmente congelata,
non il numero di snapshot scelti in seguito. `selected_snapshot_ref` e
`resolution_source` sono non-null esattamente per
`MATCHED`: la source è `AUTOMATIC` solo per `SINGLE`, mentre `DIRECT_ID` e
`ATHLETE_CONFIRMATION` sono lecite per ogni kind. Per `MULTIPLE/MATCHED`, lo
snapshot selezionato DEVE appartenere ai `candidate_snapshot_refs` congelati;
per `ZERO/MATCHED` deve essere lo snapshot same-scope validato ammesso dal §6.
Una source `DIRECT_ID` richiede inoltre
direct evidence strict valida e same-subject che risolva proprio quello
snapshot. Candidate refs/evidence di un `MULTIPLE` restano almeno due e non
sono mai riscritti per simulare `SINGLE`. Ogni altra combinazione è vietata dai
CHECK v8. Un discovery derivato da
risposta ha `previous_discovery_result_ref` e precisamente uno tra
`discovery_confirmation_ref` (solo origine `ZERO`/`MULTIPLE`) e
`matching_confirmation_ref` (solo origine `SINGLE`); quello iniziale ha tutti
e tre null. In particolare il result puro `CONFIRMATION_REQUIRED` di un
`SINGLE` non viene mai scollegato dalla discovery.

Con direct ID validato, una singola `BEGIN IMMEDIATE` rilegge sessione, target
e intero candidate set congelato, precalcola gli ID, inserisce mapping prima del
result per le FK immediate e infine la discovery terminale. Non nasce una
confirmation né una sidecar; result, mapping e discovery citano la stessa
direct evidence e selezione. Retry equivalente restituisce la catena esistente;
una diversa risoluzione dello stesso ID o un mapping concorrente rollbacka.

### 4.1 Guard pre-matcher cross-scope e identità semantica

Prima di invocare il matcher per **ogni** `ActualSession`, una `BEGIN IMMEDIATE`
rilegge artefatti autorevoli senza alcun filtro su `sync_scope_ref`. L'ordine di
lookup è fisso: (1) mapping per `actual_session_ref`; (2) origini e teste di ogni
catena discovery che contiene la sessione; (3) request/answer confirmation
pending; (4) catene zero-sessioni e reconciliation tardive pending o terminali
che contengono la coppia sessione/snapshot. Entro ciascun gruppo l'ordine è per
ID UTF-8; FK, ownership, link, cardinalità e testa unica vengono rivalidati.

Se esiste un mapping, la sessione è gestita: si restituisce quel mapping e non si
invoca il matcher né si tenta un secondo mapping. Se esiste una catena
irrisolta, si riprende o si espone **quella** request/testa, senza creare una
confirmation parallela. Una reconciliation pending o terminale rende gestita la
relazione anche se nacque in un altro scope. Se la testa terminale non ha
mapping e il fingerprint congelato coincide con quello corrente, il tentativo è
un no-op. `sync_scope_ref` viene conservato come provenienza dell'osservazione,
ma non rende nuova una relazione semanticamente già gestita.

Un nuovo tentativo append-only è lecito soltanto dopo una testa terminale senza
mapping e quando l'evidence autorevole produce un fingerprint diverso. Il nuovo
record deve citare `previous_terminal_head_ref`, il fingerprint precedente e
quello nuovo; non riapre o muta la catena. Un fingerprint uguale con payload
divergente, catene multiple, fork, mapping discordanti o più request pending
falliscono chiusi. Il vincolo univoco su `(actual_session_ref,
previous_terminal_head_ref, evidence_fingerprint)` e quello one-mapping-per-
session decidono le race: sotto `BEGIN IMMEDIATE` il primo commit vince, un
retry equivalente rilegge/no-op e un concorrente divergente rollbacka. Questa
guardia precede sia candidate discovery sia qualunque chiamata al matcher.

## 5. Percorso prescription/window-driven: nessuna sessione catturata

Per ogni snapshot del set synchronization-wide con
`scheduled_window.end < coverage_end`, il boundary apre `BEGIN IMMEDIATE`,
rilegge lo snapshot e le sessioni same-subject dello **stesso scope** già
persistite, ordinate per `(start, session_id UTF-8)`, e distingue due predicati
che non sono intercambiabili:

- **snapshot handled**: esiste già un artefatto autorevole che tratta proprio
  quello snapshot oppure una sua relazione snapshot/sessione: mapping verso lo
  snapshot, discovery originaria/derivata che contiene lo snapshot insieme alla
  sessione, result/request zero-sessioni dello snapshot, reconciliation
  collegata a quel result/request, o relativo artefatto terminale;
- **session handled elsewhere**: la sessione ha mapping, discovery,
  confirmation o reconciliation autorevole, ma nessuna di tali catene contiene
  lo snapshot corrente. Questa sessione è esclusa dalla tupla dello snapshot,
  però **non** rende lo snapshot handled.

Il lookup snapshot-level avviene prima del filtro sessioni e nell'ordine fisso:
(1) mapping per `prescription_snapshot_ref`; (2) discovery complete che
contengono lo snapshot e la sessione; (3) result e request zero-sessioni per lo
snapshot; (4) reconciliation e answer collegate; (5) eventi terminali delle
relative catene. Entro ogni classe ordina per chiave primaria UTF-8 e ricalcola
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
snapshot-level appena definito. Verifica globalmente che non esistano mapping,
discovery, result/request zero-sessioni, reconciliation o artefatti terminali
che trattino lo snapshot o una sua relazione; il fatto che tutte le sessioni
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
stato della testa (`CONFIRMATION_REQUIRED`, `MATCHED` o `NOT_EVALUABLE`). Per
un'origine `MULTIPLE`, ogni snapshot del candidate set congelato è gestito,
inclusi quelli non selezionati dopo una risoluzione autorevole. La coppia viene
quindi saltata deterministicamente: una testa terminale non consente
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
`BEGIN IMMEDIATE`** inserisce result, request, scheduling e terminale
`NOT_EVALUABLE/EXPIRED` di A. Soltanto il commit consente di processare un
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
appende
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
reconciliation request, actor e timestamp. Expiry o risposta non
associativa usa **answer → result `NOT_EVALUABLE` → evento testa**, senza
mapping; l'expiry automatica usa result → evento e non crea answer. Nessuna
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
| zero request pending | answer non associativa | vuota originale | vietate | nessuno |
| zero request pending / successor raggiunto | `EXPIRED` + result `NOT_EVALUABLE` | vuota originale | nessuna answer | nessuno |
| zero pending o terminale / sessione tardiva | `LATE_SESSION_RECONCILIATION` pending | non vuota, canonica | solo membri congelati | nessuno prima dell'answer |
| reconciliation pending / selezione valida | dedicated answer + result `MATCHED` | non vuota, invariata | membro selezionato nella request | uno, `ATHLETE_CONFIRMATION` |
| reconciliation pending / risposta non associativa | dedicated answer + result `NOT_EVALUABLE` | non vuota, invariata | `selected_session_ref=null` | nessuno |
| reconciliation pending / proprio boundary futuro raggiunto | result `NOT_EVALUABLE` + `EXPIRED` | non vuota, invariata | nessuna answer | nessuno |
| qualunque testa / mapping già esistente | no-op verificato | invariata | — | mapping esistente |

La catena conserva sempre warning/evidence zero originari. Un nuovo head cita
il precedente; request, result, attempt e answer restano tutti immutabili.

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
B sono atomici e il commit precede la loro esposizione.

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
- `maintain_plan_matching_discoveries`, con colonne del §4 e FK a scope,
  sessione, discovery precedente, confirmation discovery, confirmation
  MatchingResult esistente, result e mapping. CHECK implementano esattamente
  la matrice del §4 e rendono mutuamente esclusivi i due confirmation ref.
  In particolare `kind` è vincolato alla cardinalità JSON congelata
  (`ZERO=0`, `SINGLE=1`, `MULTIPLE>=2`) indipendentemente dalla resolution;
  `MATCHED` richiede result, mapping, selected snapshot e source non-null;
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
- indici lookup window-driven `(prescription_snapshot_ref,matching_result_id)`
  sui result, `(prescription_snapshot_ref,request_id)` sulle confirmation
  snapshot-centric e quelli già definiti su mapping, reconciliation ed eventi.
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
  reconciliation_request_ref TEXT, reconciliation_answer_ref TEXT,
  terminal_result_ref TEXT, occurred_at TEXT NOT NULL, payload_json TEXT NOT
  NULL, UNIQUE(origin_request_ref,
  previous_chain_head_ref), FOREIGN KEY ... ON DELETE NO ACTION)`. CHECK e
  trigger impongono: scheduling senza terminal result; expiry zero-sessioni o
  reconciliation con result `NOT_EVALUABLE` e senza answer/mapping; gli eventi
  reconciliation-expiry richiedono `reconciliation_request_ref`, ricopiano il
  relativo boundary/gruppo futuro e vietano l'uso del boundary zero originario;
  reconciliation con request e tupla
  candidata non vuota; `ANSWERED` con FK alla dedicated reconciliation answer
  e result terminale; `EXPIRED` senza answer ref. Un indice
  `(origin_request_ref,event_id)` e i link previous formano una sola catena
  append-only, senza fork;
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
- un indice univoco v8 su `maintain_plan_prescription_mappings
  (actual_session_ref)`, oltre ai trigger append-only esistenti, per rendere
  fisica l'invariante di un solo mapping per sessione.

Le FK immediate già presenti in `schema.py` sono state auditate: mapping punta
subito a snapshot e sessione, mentre result `MATCHED` punta subito al mapping;
confirmation punta subito a result e snapshot. Poiché non sono deferred e v8
non cambia v1–v7, il mapping deve precedere il result dopo la precomputazione
deterministica di entrambi gli ID.

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
`UNIQUE(reconciliation_request_ref)` e all'indice mapping/sessione, una sola
answer vincente e un solo mapping: retry byte-identici rileggono/no-op, answer
divergenti o race perse falliscono chiuso senza record parziali.

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
Una risoluzione direct-ID produce invece un mapping
`resolution_method=AUTOMATIC`; la provenienza `DIRECT_ID` rimane distinta nella
discovery, nel result e nell'evidence, senza estendere l'enum o i CHECK v1–v7.
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

Vettori normativi aggiuntivi (`é` è U+00E9):

```text
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
synchronization-wide e non genera una falsa conferma zero-sessioni. Se due
snapshot vicini producono `MULTIPLE`, il percorso window-driven considera il
rapporto gestito sia prima sia dopo la risposta: salta tutte le candidate
congelate, incluse le non selezionate. Dopo `SELECT_SNAPSHOT`, il solo mapping è
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
fail-closed; (8) un solo mapping per sessione tra entrambi i percorsi; (9) set
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
pre-matcher su entrambi i percorsi e indice one-mapping-per-session; (22) ogni
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

**Non resta alcuna decisione normativa bloccante.** Restano lavoro
implementativo: definire modelli/codec, migrazione v8, repository, adapter dello
scope, flag/wiring e test di race/rollback. Fino ad allora tutto il comportamento
descritto resta non implementato e disabilitato.
