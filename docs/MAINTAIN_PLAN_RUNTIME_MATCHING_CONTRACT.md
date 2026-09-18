# Contratto normativo — runtime matching `PrescriptionSnapshot` / `ActualSession`

**Stato:** DRAFT contract-first — nessun runtime wiring implementato

**Perimetro dati:** schema SQLite v7, senza nuove migrazioni

**Policy di dominio:** `maintain-plan-matching/1.0.0-draft`

## 1. Scopo, autorità e non-obiettivi

Questo documento definisce il boundary runtime che, dopo la persistenza del
binding comune `subject_ref`, potrà collegare una `ActualSession` persistita a
una `PrescriptionSnapshot` persistita. Integra, senza sostituirli, il
[contratto outcome](MAINTAIN_PLAN_OUTCOME_CONTRACT.md), il
[contratto di cattura ActualSession](MAINTAIN_PLAN_RUNTIME_ACTUAL_SESSION_CONTRACT.md)
e il [contratto ownership](MAINTAIN_PLAN_SUBJECT_OWNERSHIP_CONTRACT.md).
In caso di conflitto prevalgono le invarianti più restrittive di ownership e
append-only.

Lo slice è esclusivamente matching. NON esegue `ExecutionEvaluation`, outcome,
report, confidence adjustment, learning, modifica o ripianificazione del piano
e non chiama il Coach Engine. Un mapping prova soltanto l'associazione: ogni
scostamento di esecuzione resta materia della futura evaluation.

## 2. Boundary e ordine runtime

Per ogni attività accettata l'ordine obbligatorio sarà:

1. completare la cattura e il commit dell'`ActualSession` secondo il contratto
   dedicato;
2. riaprire dal repository quella sessione e gli snapshot autorevoli;
3. eseguire discovery, matching puro e persistenza atomica del solo esito di
   matching;
4. soltanto dopo il commit consentire la normale Decision Memory e poi il
   Coach Engine.

Il matching non può operare sull'oggetto non ancora persistito né essere
eseguito dopo Decision Memory o Coach Engine. Un errore tecnico blocca entrambi
e non viene degradato a warning. Un esito di dominio irrisolto
(`CONFIRMATION_REQUIRED` o `NOT_EVALUABLE`) non è un errore tecnico, ma non
abilita alcuno degli effetti esclusi al §1.

Il rollout richiede un flag separato, default `false`, con parsing fail-closed.
Il nome non è ancora presente nella configurazione: si raccomanda
`IRONCOACH_MAINTAIN_PLAN_MATCHING_ENABLED` (decisione R1 del §12). Con flag
assente, falso o invalido il repository di matching non viene aperto, non si
esegue discovery e non si scrive nulla. In `--dry-run` valgono gli stessi
divieti indipendentemente dal flag: nessuna lettura o scrittura del repository
di matching e nessuna chiamata al matcher. Il flag non abilita evaluation,
reporting, learning o modifica del piano.

## 3. Input autorevoli e trust boundary

Gli unici input sono oggetti riletti e verificati dal repository v7:

- l'`ActualSession` appena persistita, risolta esattamente tramite `session_id`;
- le `PrescriptionSnapshot` persistite restituite dalla query di discovery;
- eventuale `DirectIdEvidence` acquisita esplicitamente dalla sorgente e
  verificata nuovamente contro snapshot e sessione persistiti.

Per entrambi gli artefatti `subject_ref` DEVE essere presente, valido e
identico byte-per-byte. Nessun trim, case folding, normalizzazione Unicode,
coercizione o fallback è ammesso. Una riga legacy con `subject_ref IS NULL` non
è eleggibile. Un identificatore ricevuto dal caller è soltanto una chiave di
lookup: il payload, i metadata duplicati nella riga, i riferimenti e
`subject_ref` devono essere verificati dal repository prima dell'uso. Oggetti
in memoria, context runtime, history merged e payload forniti dal chiamante non
possono sostituire la rilettura.

## 4. Candidate discovery

### 4.1 Insieme chiuso

In assenza di direct ID autorevole, per una sessione `S` il repository deve
caricare, nella stessa transazione, **tutte e sole** le righe di
`maintain_plan_prescription_snapshots` per cui:

1. payload e metadata sono decodificabili, coerenti e validi;
2. `snapshot.subject_ref == S.subject_ref` con confronto esatto;
3. `snapshot.scheduled_window.start <= S.start <= snapshot.scheduled_window.end`.

I due confini sono inclusivi. Il confronto avviene tra istanti timezone-aware;
non si confrontano stringhe locali e non si inventa una timezone. Non esiste
un'ulteriore finestra prima o dopo la `scheduled_window`. Il discovery non
filtra per durata, distanza, nome, carico, decisione, workout, somiglianza,
environment o mode.

`PrescriptionSnapshot` non espone oggi uno stato lifecycle. Quindi, nello
schema/modello v7, “eleggibile per lifecycle” significa esclusivamente
snapshot persistito, immutabile e valido; è vietato inferire `ACTIVE`,
`PENDING`, scadenza, supersession o cancellazione da timestamp o da tabelle
esterne. Se sarà introdotto un lifecycle autorevole, una revisione approvata di
questo contratto dovrà definire i suoi stati prima di usarlo come filtro.

Il risultato della query è ordinato mediante chiave totale
`(scheduled_window.start, scheduled_window.end,
prescription_snapshot_id)`, in ordine crescente sugli istanti e poi sui byte
UTF-8 dell'ID. L'ordine serve soltanto ad audit e serializzazione: non è un
ranking e non seleziona il primo elemento.

### 4.2 Cardinalità

- **una candidata:** può essere invocato il matcher puro con quello snapshot e
  la tupla singleton contenente `S`;
- **zero candidate:** nessun mapping; è richiesta conferma secondo il testo e
  le opzioni del contratto outcome §5.5;
- **più candidate snapshot:** nessun matcher per-snapshot, nessun mapping e
  nessun tie-break; è richiesta una scelta umana della prescrizione.

Il modello corrente di `MatchingResult` descrive candidate **sessioni per un
singolo snapshot**, non candidate snapshot per una sessione. Non può quindi
rappresentare fedelmente gli ultimi due esiti del discovery runtime. Il §12 R2
propone la risoluzione; fino alla sua approvazione e implementazione, zero o più
snapshot candidate causano un arresto controllato prima della persistenza di
`MatchingResult`/`Confirmation`, non la fabbricazione di uno stato esistente.

## 5. Direct ID

`returned_prescription_id` è utilizzabile soltanto quando il dispositivo
restituisce esplicitamente l'identificatore della prescrizione che gli era
stato inviato, con source e provenance conservate. Prima del matching il
repository deve risolverlo in modo univoco a uno snapshot persistito, verificare
ownership esatta e verificare che l'evidence riferisca la sessione persistita.
Un direct ID valido ha precedenza sui filtri di finestra, composition,
cardinalità, ordine e discipline: questi diventano eventuali scostamenti della
futura evaluation.

È VIETATO costruire o sostituire `returned_prescription_id` con `activity_id`,
`source_id`, `file_hash`, Airtable `record_id`, `workout_id`, `decision_id`,
`session_id` o qualunque concatenazione/hash di tali valori. Il matcher puro
accetta storicamente anche `workout_id` come target di evidence; il runtime
disciplinato da questo documento DEVE restringere l'adapter al vero ID della
prescrizione e non deve usare quella compatibilità come autorizzazione a
sintetizzarlo.

Finché Garmin non espone un vero ID prescrizione restituito dall'attività,
l'adapter passa `direct_id_evidence=()` e usa soltanto il percorso senza direct
ID. Un valore duplicato, dangling, contraddittorio, malformato o non verificato
richiede conferma e non può ricadere silenziosamente sul matching ordinario.

## 6. Matcher normativo

Il runtime DEVE riusare `backend.maintain_plan.matching_service.match`; sono
vietati un secondo algoritmo, pre-ranking, score, similarità, fuzzy matching o
tie-break impliciti. Dopo discovery singleton, il matcher riceve esattamente lo
snapshot riletto e `(actual_session,)`, oltre a ID, timestamp, evidence e
provenance prodotti secondo questo contratto.

Restano normative le verifiche già implementate dal matcher puro:

- `scheduled_window` inclusiva;
- composition identica;
- stessa cardinalità dei componenti;
- ordine canonico per `component_index`;
- discipline nella stessa posizione, salvo sostituzione esplicitamente
  autorizzata;
- consecutività e policy esplicita per sessioni composte.

Environment e mode non sono filtri eliminatori. Durata, distanza, intensità,
nome e carico non sono criteri. Il runtime non modifica, completa o riordina
semanticamente gli input per farli risultare compatibili.

## 7. Output, confirmation e lifecycle

Con discovery singleton il matcher produce sempre un `MatchingResult`:

| esito puro | `MatchingResult.status` | mapping |
|---|---|---|
| direct ID valido e univoco, oppure unica sessione compatibile | `MATCHED` | obbligatorio |
| zero compatibili, mismatch o direct ID ambiguo/invalido | `CONFIRMATION_REQUIRED` | `null` |
| policy composta obbligatoria mancante o risposta umana non risolutiva | `NOT_EVALUABLE` | `null` |

Il mapping automatico usa `resolution_method=AUTOMATIC`. La confirmation usa
il servizio puro esistente, deve riferire l'esatto risultato immutabile e il
suo candidate set congelato; soltanto una risposta esplicita e valida produce
un **nuovo** `MatchingResult` `MATCHED` e un mapping con
`resolution_method=ATHLETE_CONFIRMATION`, `confirmation_ref`, actor e timestamp.
«Non svolta», «non sincronizzata» e «non lo so» non producono mapping. Risultato,
confirmation e mapping precedenti non vengono aggiornati o cancellati.

Un `PrescriptionMapping` è persistito soltanto insieme a un match unico o alla
risoluzione umana valida. Nei casi irrisolti resta assente. Evaluation e ogni
altro consumer possono partire soltanto da un mapping persistito e univoco, ma
non fanno parte di questo boundary.

## 8. Identità, retry e append-only

I modelli e i contratti esistenti richiedono ID espliciti ma non ne definiscono
la derivazione runtime. La proposta R3 del §12 è quindi **raccomandata, non
approvata**. Fino alla sua approvazione il runtime non deve essere cablato.

La proposta usa JSON canonico UTF-8 (`ensure_ascii=False`, chiavi ordinate,
separatori `(',', ':')`), SHA-256 lowercase e namespace versionati:

- `matching_result_id`: hash di `policy_id`, `policy_version`,
  `prescription_snapshot_id`, `session_id`, insieme ordinato degli ID di tutte
  le sessioni dichiarate al matcher, insieme ordinato delle evidence ID e, per
  un risultato da confirmation, `confirmation_id`;
- `mapping_id`: hash di `prescription_snapshot_id`, `session_id`,
  `resolution_method` e `confirmation_id` (null per automatico).

Timestamp di processo e provenance non entrano nell'identità, ma restano parte
del contenuto persistito. Stessa identità e contenuto semanticamente identico è
un retry: si restituisce il record esistente. Stesso ID con contenuto diverso è
conflitto divergente, con rollback e nessun overwrite.

Il candidate set dichiarato è congelato nel risultato. Se i dati persistiti
cambiano dopo un risultato (per esempio arriva una nuova sessione o un nuovo
snapshot), il risultato storico non viene mutato: una nuova acquisizione usa
un nuovo `matching_result_id`, conserva la relazione causale in provenance e
non invalida implicitamente mapping già risolti. Se la nuova acquisizione rende
ambiguo un caso non ancora risolto, non può riusare la confirmation precedente.
Tutti gli artefatti sono insert-only e append-only.

## 9. Transazioni e concorrenza

Ogni tentativo apre `BEGIN IMMEDIATE` prima di rileggere sessione, direct ID e
candidate. Nella stessa transazione deve:

1. verificare metadata, payload, riferimenti e ownership;
2. materializzare e congelare l'esatto candidate snapshot;
3. eseguire il matcher puro;
4. verificare un eventuale retry/conflitto;
5. inserire prima il mapping, quando presente, e poi il `MatchingResult` che lo
   riferisce;
6. committare soltanto se l'intera operazione riesce.

Nessun lock viene mantenuto durante un'interazione umana. La risposta apre una
nuova `BEGIN IMMEDIATE`, riacquisisce risultato, confirmation, snapshot e
sessione tramite i riferimenti congelati, ne riverifica ownership e contenuto,
quindi persiste atomicamente i nuovi artefatti. Non riesegue discovery usando
lo stato corrente per reinterpretare la domanda storica.

Writer concorrenti con identità equivalente convergono sul record già
persistito; writer divergenti falliscono. Vincoli, race, errore del matcher,
errore di serializzazione o insert parziale causano rollback completo. Dopo un
errore transiente il caller riacquisisce una nuova transazione e ripete tutte
le letture: è vietato riusare oggetti letti prima del rollback. Il repository
attuale non offre ancora questa unit of work composita; aggiungerla è lavoro
successivo, non autorizzato da questo documento.

## 10. Errori e fail-closed

Sono errori tecnici, con rollback e nessun effetto downstream:

- `subject_ref` assente, malformato o discordante;
- sessione/snapshot/evidence riferiti mancanti, duplicati o non risolvibili;
- payload corrotto, versione non supportata o metadata di colonna divergenti;
- timestamp naive/non confrontabili, finestra invalida, input canonico
  malformato o validator non soddisfatto;
- direct ID dichiarato autorevole ma non verificabile;
- conflitto di identità, violazione referenziale o race non equivalente.

Zero o più candidate compatibili, mismatch strutturale, direct ID ambiguo e
policy composta mancante sono esiti di dominio, non errori tecnici; conducono a
confirmation-required/not-evaluable soltanto dove il modello li rappresenta
senza perdita (§4.2 e §7). Nessun errore o esito irrisolto può produrre mapping,
evaluation, report, learning, modifica del piano, Decision Memory o Coach
Engine nel medesimo ciclo.

## 11. Compatibilità database

- **database v1–v6 non migrato:** il runtime matching rifiuta l'avvio; non
  tenta query alternative e non modifica il database;
- **record v1–v6 migrati a v7:** restano leggibili, ma `subject_ref=NULL` li
  rende non eleggibili e non è ammesso backfill euristico;
- **schema v7:** è il solo schema supportato e contiene già gli artefatti
  necessari; payload e colonne ownership devono coincidere;
- **migrazioni:** questo contratto non modifica schema, migrazioni v1–v7 o
  checksum. Una nuova migrazione è vietata salvo necessità dimostrata da una
  decisione successiva approvata (in particolare R2).

## 12. Decisioni nuove che richiedono approvazione

Le seguenti scelte non sono determinate dagli artefatti correnti e non sono
presentate come approvate.

### R1 — nome e semantica del flag

1. **Raccomandata:** `IRONCOACH_MAINTAIN_PLAN_MATCHING_ENABLED`, default false,
   parsing fail-closed e inattivo in dry-run. È coerente con i flag runtime già
   separati e limita il blast radius.
2. Riutilizzare il flag ActualSession: riduce configurazione ma accoppia due
   rollout e può abilitare scritture non intenzionali.
3. Nessun flag: più semplice, ma viola il rollout separato già richiesto.

### R2 — rappresentazione di zero/più snapshot candidate

1. **Raccomandata:** introdurre in un futuro contratto un artefatto discovery
   append-only, con candidate **snapshot** e riferimento alla sessione, quindi
   far nascere `MatchingResult` solo dopo la selezione di uno snapshot. È
   semanticamente esatto, ma richiede modello/persistenza e probabilmente una
   migrazione dimostrata.
2. Produrre un `MatchingResult` per ogni snapshot: non richiede un nuovo tipo,
   ma può creare mapping concorrenti falsi e confirmation frammentate; è
   sconsigliato.
3. Estendere `MatchingResult` per entrambe le direzioni: riduce gli artefatti,
   ma cambia il significato di `candidate_set` e rompe compatibilità di codec e
   consumer.

Fino all'approvazione di R2, il comportamento fail-closed del §4.2 è
vincolante e impedisce il wiring produttivo di quei casi.

### R3 — ID deterministici runtime

1. **Raccomandata:** namespace versionati e SHA-256 sulla preimage canonica del
   §8. Offre retry cross-process deterministici e collision domain separati.
2. UUID casuali più chiave univoca semantica separata: semplice da generare ma
   richiede nuove colonne/indici e migrazione.
3. ID forniti dall'orchestratore: nessuna migrazione, ma idempotenza e
   canonicalizzazione dipendono da un trust boundary oggi non definito.

Prima dell'implementazione R3 deve fissare i nomi esatti dei namespace, lo
shape JSON completo e almeno vettori normativi Unicode; è vietato colmare tali
dettagli nel codice senza approvazione.

## 13. Criteri per l'implementazione successiva

Il futuro slice runtime dovrà aggiungere, senza cambiare questo significato:

- query repository ownership/window e unit of work `BEGIN IMMEDIATE`;
- adapter di direct ID esplicito (vuoto per Garmin finché indisponibile);
- flag separato e wiring nell'ordine del §2;
- persistenza idempotente di mapping/risultato e workflow di confirmation;
- test di confini inclusivi, ownership/legacy, zero/una/più candidate, direct
  ID avversariale, retry/conflitti/race/rollback e dry-run;
- nessuna evaluation, reporting, learning o modifica del piano.

Questo documento non autorizza tali modifiche: definisce il contratto contro
cui dovranno essere proposte e revisionate.
