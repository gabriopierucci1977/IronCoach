# Contratto normativo — runtime matching `PrescriptionSnapshot` / `ActualSession`

**Stato:** normativo contract-first — decisioni R1, R2 e R3 approvate; runtime non implementato

**Perimetro dati corrente:** schema SQLite v7, senza modifiche o nuove migrazioni in questo slice

**Policy di dominio:** `maintain-plan-matching/1.0.0-draft`

## 1. Scopo, autorità e non-obiettivi

Questo documento definisce il futuro boundary runtime che, dopo la persistenza
del binding comune `subject_ref`, collegherà una `ActualSession` persistita a
una `PrescriptionSnapshot` persistita. Integra, senza sostituirli, il
[contratto outcome](MAINTAIN_PLAN_OUTCOME_CONTRACT.md), il
[contratto di cattura ActualSession](MAINTAIN_PLAN_RUNTIME_ACTUAL_SESSION_CONTRACT.md)
e il [contratto ownership](MAINTAIN_PLAN_SUBJECT_OWNERSHIP_CONTRACT.md). In caso
di conflitto prevalgono le invarianti più restrittive di ownership e
append-only.

Lo slice è esclusivamente matching. NON esegue `ExecutionEvaluation`, outcome,
report, confidence adjustment, learning, modifica o ripianificazione del piano
e non chiama il Coach Engine. Un mapping prova soltanto l'associazione: ogni
scostamento di esecuzione resta materia della futura evaluation.

## 2. Boundary, ordine runtime, flag e dry-run

Per ogni attività accettata l'ordine obbligatorio sarà:

1. completare la cattura e il commit dell'`ActualSession`;
2. riaprire dal repository quella sessione e scoprire gli snapshot autorevoli;
3. persistere il discovery result append-only, eseguire il matcher puro e
   persistere atomicamente il solo esito consentito;
4. soltanto dopo il commit consentire la normale Decision Memory e poi il
   Coach Engine.

Il matching non opera sull'oggetto non ancora persistito e non viene eseguito
dopo Decision Memory o Coach Engine. Un errore tecnico blocca entrambi e non
viene degradato a warning. Un esito di dominio irrisolto
(`CONFIRMATION_REQUIRED` o `NOT_EVALUABLE`) non è un errore tecnico, ma non
abilita alcuno degli effetti esclusi al §1.

**R1 è approvata e normativa.** Il solo flag del boundary è
`IRONCOACH_MAINTAIN_PLAN_MATCHING_ENABLED`, separato dagli altri flag, con
default `false` e parsing fail-closed. Se assente, falso, vuoto o invalido, il
repository di matching non viene aperto, discovery e matcher non vengono
eseguiti e non si scrive nulla. In `--dry-run` valgono gli stessi divieti
indipendentemente dal valore del flag. Il flag non abilita evaluation,
reporting, learning o modifica del piano.

## 3. Input autorevoli e trust boundary

Gli unici input sono oggetti riletti e verificati dal repository v7:

- l'`ActualSession` appena persistita, risolta esattamente tramite `session_id`;
- tutte le righe fisiche `PrescriptionSnapshot` selezionate secondo il §4;
- eventuale `DirectIdEvidence` acquisita esplicitamente dalla sorgente e
  riferita alla sessione persistita.

Per entrambi gli artefatti `subject_ref` DEVE essere presente, valido e
identico byte-per-byte. Nessun trim, case folding, normalizzazione Unicode,
coercizione o fallback è ammesso. Una riga legacy con `subject_ref IS NULL` non
è same-subject e non è eleggibile. Un identificatore ricevuto dal caller è
soltanto una chiave di lookup: payload, metadata duplicati nella riga,
riferimenti e ownership devono essere verificati dal repository. Oggetti in
memoria, context runtime, history merged e payload del caller non sostituiscono
la rilettura.

## 4. Candidate discovery fail-closed

### 4.1 Insieme fisico e validazione totale

Per una sessione persistita `S`, la query iniziale recupera **tutte e sole** le
righe fisiche di `maintain_plan_prescription_snapshots` la cui colonna v7
`subject_ref` è esattamente uguale a `S.subject_ref`. Il confronto è quello
esatto del contratto ownership. La query NON usa `scheduled_window`, lifecycle,
discipline, composition o altri campi del payload.

Ogni riga così recuperata deve essere decodificata e verificata: versione del
payload supportata, payload valido, metadata di colonna coerenti col payload e
`snapshot.subject_ref` esattamente coincidente sia con la colonna sia con
`S.subject_ref`. Se anche una sola riga same-subject è corrotta,
indecodificabile, incoerente o non validabile, **l'intera discovery termina con
errore tecnico e rollback**. La riga non può essere esclusa: farlo potrebbe
trasformare un insieme ambiguo in un falso singleton.

Le righe con colonna `subject_ref` diversa o `NULL` non appartengono
all'insieme; non vengono decodificate come candidate e non autorizzano fallback
o backfill. Un indice può ottimizzare la query, ma non cambiarne la semantica.

### 4.2 Finestra e lifecycle

La `scheduled_window` NON è un filtro di discovery. Tutti gli snapshot
persistiti, validi e same-subject vengono forniti al matcher puro, inclusi
quelli fuori finestra. Soltanto
`backend.maintain_plan.matching_service.match` valuta la regola inclusiva:

```text
snapshot.scheduled_window.start <= session.start <= snapshot.scheduled_window.end
```

Il confronto avviene tra istanti timezone-aware. Non esiste una finestra
aggiuntiva. Uno snapshot fuori finestra resta nel discovery result con evidence
temporale negativa e conduce a `CONFIRMATION_REQUIRED`; non viene trasformato
in un caso “zero candidate”.

`PrescriptionSnapshot` non espone uno stato lifecycle. Nello schema/modello v7
eleggibile significa quindi snapshot persistito, immutabile, validato e
same-subject. È vietato inferire `ACTIVE`, `PENDING`, scadenza, supersession o
cancellazione. Un futuro lifecycle potrà filtrare solo dopo una revisione
normativa approvata.

### 4.3 Ordinamento e cardinalità

Gli snapshot validati sono ordinati per
`prescription_snapshot_id` confrontato sui byte UTF-8. Questo ordine totale
serve a identità, audit e serializzazione; non è un ranking e non seleziona il
primo elemento.

In assenza di direct ID valido e risolto, per ciascuno snapshot ordinato il boundary invoca separatamente il matcher puro
con quello snapshot e la tupla singleton `(S,)`. È l'adattamento necessario
all'API esistente, non un secondo algoritmo. Gli esiti per-snapshot vengono
registrati come evidence nel discovery result:

- **zero snapshot:** discovery `ZERO` e `resolution_status` pari a
  `CONFIRMATION_REQUIRED`; nessun `MatchingResult` o mapping riferito a uno
  snapshot inesistente;
- **uno snapshot:** discovery `SINGLE`; il relativo esito puro governa
  `MatchingResult`, mapping ed eventuale confirmation;
- **più snapshot:** discovery `MULTIPLE` e `resolution_status` pari a
  `CONFIRMATION_REQUIRED`; tutti gli esiti puri restano evidence,
  ma nessun mapping incorporato in un esito transitorio viene persistito. È
  necessaria una scelta umana dello snapshot; non esiste tie-break implicito.

La scelta umana di uno snapshot produce un nuovo discovery result append-only
`SINGLE`, che riferisce il discovery `MULTIPLE` e la confirmation; soltanto
allora il matcher viene riacquisito e può produrre il risultato persistibile.
Gli oggetti transitori usati come evidence non sono `MatchingResult` pubblicati
e non sono input downstream.

Un direct ID valido, same-subject e risolto univocamente seleziona invece lo
snapshot esatto dall'insieme completo, anche quando lo stato di discovery è
`MULTIPLE`: viene invocato unicamente il matcher per quello snapshot e il
discovery registra `resolution_status: MATCHED`. Non è un tie-break. Un direct
ID valido ma irrisolto lascia `resolution_status: CONFIRMATION_REQUIRED` come
definito al §6.

## 5. Artefatto discovery approvato (R2)

**R2 è approvata e normativa.** `MatchingDiscoveryResult` è un artefatto di
dominio immutabile e append-only con il seguente payload canonico:

```yaml
matching_discovery_result:
  discovery_result_id: string
  artifact_version: "1"
  status: ZERO | SINGLE | MULTIPLE
  resolution_status: MATCHED | CONFIRMATION_REQUIRED | NOT_EVALUABLE
  actual_session_ref: string
  subject_ref: string
  candidate_snapshot_refs: [string]       # ordine canonico §4.3
  direct_evidence_refs: [string]           # ordine per byte UTF-8
  candidate_evidence:
    - prescription_snapshot_ref: string
      matching_status: MATCHED | CONFIRMATION_REQUIRED | NOT_EVALUABLE
      candidate_session_refs: [string]
      checks: object
      reasons: [string]
      warnings: [string]
  matching_policy_id: maintain-plan-matching
  matching_policy_version: 1.0.0-draft
  previous_discovery_result_ref: string | null
  confirmation_ref: string | null
  discovered_at: datetime
  provenance: object
```

`status` deriva esclusivamente dalla cardinalità di `candidate_snapshot_refs`.
Evidence e riferimenti hanno la stessa cardinalità e lo stesso ordine; con
`ZERO` entrambi sono vuoti. `resolution_status` sintetizza senza inventare un
`MatchingResult` lo stato complessivo: è `CONFIRMATION_REQUIRED` per `ZERO` e
`MULTIPLE`, salvo direct ID valido e risolto; con `SINGLE` coincide con l'esito
del matcher puro. `subject_ref` coincide esattamente con sessione e ogni
snapshot. `previous_discovery_result_ref` e `confirmation_ref` sono
entrambi null per il discovery iniziale e entrambi obbligatori per la
selezione umana da `MULTIPLE`. Il nuovo `SINGLE` contiene soltanto lo snapshot
selezionato; il predecessore conserva per sempre l'insieme completo.

Questo contratto approva forma e semantica dell'artefatto, non una modifica
schema. Lo schema v7 non dispone di una tabella per persisterlo. La scelta tra
una futura migrazione additiva e un event store append-only già autorevole è
ancora indeterminata e richiede una proposta separata con necessità dimostrata.
Fino a quella decisione il wiring produttivo resta vietato; non è ammesso
incorporare l'artefatto in campi generici di altri record.

## 6. Direct ID

`returned_prescription_id` è utilizzabile soltanto quando il dispositivo
restituisce esplicitamente l'identificatore della prescrizione inviata, con
source e provenance conservate. È vietato costruirlo o sostituirlo con
`activity_id`, `source_id`, `file_hash`, Airtable `record_id`, `workout_id`,
`decision_id`, `session_id` o concatenazioni/hash di tali valori. La storica
compatibilità del matcher puro con `workout_id` non autorizza l'adapter runtime
a usarlo come returned prescription ID.

Un valore esplicito, strutturalmente valido e UTF-8 valido che sia dangling,
non risolvibile o non verificabile è **un esito di dominio**:
`CONFIRMATION_REQUIRED`, mapping null, evidence e provenance conservate, senza
fallback al percorso ordinario. Lo stesso vale per un valore valido ma
duplicato o contraddittorio rispetto a un'altra evidence valida.

Sono invece errori tecnici fail-closed un direct ID di tipo/shape malformato,
vuoto o whitespace-only, con Unicode non codificabile UTF-8 strict, una
evidence con `session_id` incoerente rispetto a `S`, oppure una dichiarazione
strutturalmente incoerente o non decodificabile. Distinguere “non risolto” da
“malformato” è obbligatorio.

Un direct ID valido e risolto univocamente a uno snapshot persistito deve
superare la verifica ownership. Se lo snapshot risolto è cross-subject, la
dichiarazione è incoerente e causa errore tecnico; non autorizza mai un
mapping. Se valido, same-subject e univoco, il direct ID ha precedenza su
finestra, composition, cardinalità, ordine e discipline, che restano futuri
scostamenti di evaluation.

Finché Garmin non restituisce un vero ID prescrizione, l'adapter passa
`direct_id_evidence=()` e usa soltanto il percorso senza direct ID.

## 7. Matcher normativo

Il runtime DEVE riusare `backend.maintain_plan.matching_service.match`. Sono
vietati un secondo algoritmo, pre-ranking, score, similarità, fuzzy matching o
tie-break. Il matcher riceve esclusivamente snapshot e sessione riletti, ID
deterministici, evidence validata e provenance.

Restano normative le verifiche del matcher puro: `scheduled_window` inclusiva,
composition, cardinalità, ordine per `component_index`, discipline e
sostituzioni esplicite, consecutività e policy delle sessioni composte.
Environment e mode non sono filtri eliminatori. Durata, distanza, intensità,
nome e carico non sono criteri.

## 8. Output, confirmation e lifecycle

Per un discovery `SINGLE`, il matcher produce un `MatchingResult`:

| esito puro | `MatchingResult.status` | mapping |
|---|---|---|
| direct ID valido e univoco, oppure sessione compatibile | `MATCHED` | obbligatorio |
| fuori finestra, mismatch o direct ID valido ma irrisolto/ambiguo | `CONFIRMATION_REQUIRED` | `null` |
| policy composta obbligatoria mancante o risposta non risolutiva | `NOT_EVALUABLE` | `null` |

Il mapping automatico usa `resolution_method=AUTOMATIC`. Soltanto una risposta
umana esplicita e valida produce un nuovo risultato `MATCHED` e un mapping
`ATHLETE_CONFIRMATION` con confirmation, actor e timestamp. «Non svolta», «non
sincronizzata» e «non lo so» non producono mapping. Tutti gli artefatti
precedenti restano immutabili.

Con discovery `ZERO` o `MULTIPLE` senza direct ID risolto non si produce un `MatchingResult` canonico,
perché quello esistente è riferito a un singolo snapshot. La confirmation di
discovery approvata da R2 seleziona eventualmente uno snapshot e produce il
nuovo discovery `SINGLE` descritto al §5. Evaluation e altri consumer possono
partire soltanto da un mapping persistito univoco.

## 9. Identità canonica approvata (R3)

**R3 è approvata e normativa.** Tutte le preimage usano JSON canonico con
`ensure_ascii=False`, `sort_keys=True`, separatori `(',', ':')`, encoding UTF-8
strict senza BOM e nessuna normalizzazione Unicode. Le liste sono già ordinate
secondo il rispettivo ordine canonico. Si calcola SHA-256 sui byte e si emette
hex lowercase.

### 9.1 `discovery_result_id`

Preimage con esattamente queste chiavi:

```json
{"artifact_version":"1","direct_evidence_ids":[],"matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","prescription_snapshot_ids":["<id ordinati>"],"session_id":"<session_id>","subject_ref":"<subject_ref>"}
```

Namespace: `maintain-plan:matching-discovery:v1:sha256:<64 hex>`.

Per un discovery derivato da confirmation, la preimage aggiunge esattamente
`"confirmation_id":"<confirmation_id>"` e
`"previous_discovery_result_id":"<discovery_result_id>"`. Non sono presenti
nel discovery iniziale. Questo distingue la selezione dal singleton originario.
`direct_evidence_ids` contiene gli ID ordinati per byte UTF-8; il contenuto
risolto o irrisolto dell'evidence resta nel payload, mentre gli ID rendono
distinti i tentativi con evidence dichiarata diversa.

### 9.2 `matching_result_id`

Preimage con esattamente queste chiavi:

```json
{"confirmation_id":null,"direct_evidence_ids":[],"matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","prescription_snapshot_id":"<snapshot_id>","session_id":"<session_id>"}
```

`direct_evidence_ids` è ordinato per byte UTF-8. `confirmation_id` è null per
il risultato automatico/iniziale e contiene l'ID esatto per un risultato
derivato da risposta umana. Namespace:
`maintain-plan:matching-result:v1:sha256:<64 hex>`.

### 9.3 `mapping_id`

Preimage con esattamente queste chiavi:

```json
{"confirmation_id":null,"prescription_snapshot_id":"<snapshot_id>","resolution_method":"AUTOMATIC","session_id":"<session_id>"}
```

Per conferma, `confirmation_id` contiene l'ID esatto e `resolution_method` è
`ATHLETE_CONFIRMATION`. Namespace:
`maintain-plan:prescription-mapping:v1:sha256:<64 hex>`.

### 9.4 Vettori normativi Unicode

Nei vettori seguenti `é` è U+00E9 e non viene normalizzata.

```text
discovery preimage: {"artifact_version":"1","direct_evidence_ids":[],"matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","prescription_snapshot_ids":["prescrizione-é"],"session_id":"sessione-é","subject_ref":"atleta-é"}
SHA-256: 46d49c83ef61f2804df1b1bf969bb35fa07c15248022909a225a01afa7bbf1a1
discovery_result_id: maintain-plan:matching-discovery:v1:sha256:46d49c83ef61f2804df1b1bf969bb35fa07c15248022909a225a01afa7bbf1a1

matching preimage: {"confirmation_id":null,"direct_evidence_ids":[],"matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","prescription_snapshot_id":"prescrizione-é","session_id":"sessione-é"}
SHA-256: a08b15f0f101bcd9421968ca6b017bae6b5cc81d39f343fc243a469b4938b332
matching_result_id: maintain-plan:matching-result:v1:sha256:a08b15f0f101bcd9421968ca6b017bae6b5cc81d39f343fc243a469b4938b332

mapping preimage: {"confirmation_id":null,"prescription_snapshot_id":"prescrizione-é","resolution_method":"AUTOMATIC","session_id":"sessione-é"}
SHA-256: 165f6834f063bc6a0f3aa2714be874c388e2d3e3d6f16f1645926079a5fdeee5
mapping_id: maintain-plan:prescription-mapping:v1:sha256:165f6834f063bc6a0f3aa2714be874c388e2d3e3d6f16f1645926079a5fdeee5
```

Vettori della variante derivata da confirmation:

```text
confirmed discovery preimage: {"artifact_version":"1","confirmation_id":"conferma-é","direct_evidence_ids":[],"matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","prescription_snapshot_ids":["prescrizione-é"],"previous_discovery_result_id":"precedente-é","session_id":"sessione-é","subject_ref":"atleta-é"}
SHA-256: efffbf8d3cff161f8ee97d662b63c1ee0bf2c9d4b5c6e66c196e79e30a0af8d1
discovery_result_id: maintain-plan:matching-discovery:v1:sha256:efffbf8d3cff161f8ee97d662b63c1ee0bf2c9d4b5c6e66c196e79e30a0af8d1

confirmed matching preimage: {"confirmation_id":"conferma-é","direct_evidence_ids":[],"matching_policy_id":"maintain-plan-matching","matching_policy_version":"1.0.0-draft","prescription_snapshot_id":"prescrizione-é","session_id":"sessione-é"}
SHA-256: df7edc0afc2192c299d416091a4653a45f64ff9d205994a3d93f994182adc66e
matching_result_id: maintain-plan:matching-result:v1:sha256:df7edc0afc2192c299d416091a4653a45f64ff9d205994a3d93f994182adc66e

confirmed mapping preimage: {"confirmation_id":"conferma-é","prescription_snapshot_id":"prescrizione-é","resolution_method":"ATHLETE_CONFIRMATION","session_id":"sessione-é"}
SHA-256: f703c37757364b6dc0199af4630d6931fc13b7b9ab3e28964d5f9c11d20a38e8
mapping_id: maintain-plan:prescription-mapping:v1:sha256:f703c37757364b6dc0199af4630d6931fc13b7b9ab3e28964d5f9c11d20a38e8
```

Con `ensure_ascii=True`, normalizzazione NFD/NFC differente, chiavi o liste in
ordine diverso, spazi JSON o BOM si ottengono byte non conformi.

### 9.5 Retry, cambiamenti e conflitti

Timestamp e provenance non entrano nell'identità, ma restano contenuto
persistito. Stesso ID e contenuto semanticamente equivalente è un retry e
restituisce il record esistente. Stesso ID con contenuto diverso è conflitto
divergente: rollback, nessun overwrite.

Il candidate set è congelato. Se l'insieme cambia, si produce un nuovo
`discovery_result_id`; il risultato storico e gli eventuali mapping risolti non
vengono mutati. Un discovery nuovo e ambiguo non riusa una confirmation
precedente. Discovery, risultati, confirmation e mapping sono append-only.

## 10. Transazioni e concorrenza

Ogni tentativo apre `BEGIN IMMEDIATE` prima di rileggere sessione, righe
same-subject e direct evidence. Nella stessa transazione deve:

1. verificare sessione e ogni riga same-subject secondo il §4.1;
2. congelare l'insieme completo e costruire il discovery result;
3. eseguire il matcher puro per ogni snapshot;
4. verificare retry o conflitti;
5. persistere atomicamente discovery e, solo quando ammessi, mapping e
   `MatchingResult`;
6. committare soltanto se l'intera operazione riesce.

Nessun lock resta aperto durante un'interazione umana. La risposta apre una
nuova `BEGIN IMMEDIATE`, riacquisisce gli artefatti tramite i riferimenti
congelati e ne riverifica ownership e contenuto. Non usa lo stato corrente per
reinterpretare la domanda storica.

Writer concorrenti equivalenti convergono sul record esistente; writer
divergenti falliscono. Vincoli, race, errore del matcher, serializzazione o
insert parziale causano rollback completo. Dopo un errore transiente il caller
apre una nuova transazione e ripete tutte le letture; non riusa oggetti letti
prima del rollback.

## 11. Errori e fail-closed

Sono errori tecnici, con rollback e nessun effetto downstream:

- ownership della sessione assente o malformata;
- qualsiasi riga same-subject corrotta, indecodificabile, incoerente o non
  validabile;
- riferimenti obbligatori mancanti o incoerenti, payload/versione non
  supportati, timestamp naive/non confrontabili o finestra invalida;
- direct evidence malformata, Unicode non valido, session ref discordante,
  dichiarazione strutturalmente incoerente o snapshot risolto cross-subject;
- conflitto divergente, violazione referenziale o race non equivalente.

Sono esiti di dominio, non errori tecnici: zero snapshot; più snapshot; fuori
finestra o mismatch; policy composta mancante; direct ID esplicito e ben
formato ma dangling, non risolvibile, non verificabile, duplicato o
contraddittorio. Questi esiti seguono §§4–8 e non producono mapping finché non
sono risolti. Nessun errore o esito irrisolto produce evaluation, report,
learning, modifica del piano, Decision Memory o Coach Engine nello stesso
ciclo.

## 12. Compatibilità database e decisione ancora aperta

- **database v1–v6 non migrato:** il runtime matching rifiuta l'avvio;
- **record v1–v6 migrati a v7:** restano leggibili, ma `subject_ref=NULL` li
  rende non eleggibili e non è ammesso backfill;
- **schema v7:** è il solo schema supportato dagli input correnti; payload e
  colonne ownership devono coincidere;
- **questo slice:** non modifica schema, migrazioni v1–v7 o checksum.

R1, R2 e R3 non sono più decisioni aperte. Resta indeterminata esclusivamente
la destinazione persistente di `MatchingDiscoveryResult`: il requisito
append-only è normativo, ma schema v7 non offre una tabella adeguata. Non si
inventa storage implicito. Una futura proposta dovrà dimostrare se serve una
migrazione additiva oppure se esiste un event store autorevole compatibile,
prima di qualunque wiring produttivo.

## 13. Criteri per l'implementazione successiva

Il futuro slice runtime dovrà aggiungere, senza cambiare questo significato:

- query fisica same-subject fail-closed e unit of work `BEGIN IMMEDIATE`;
- modello e persistenza append-only del discovery dopo la decisione storage;
- adapter direct-ID esplicito, vuoto per Garmin finché indisponibile;
- flag R1 e wiring nell'ordine del §2;
- generatori ID R3, persistenza idempotente e confirmation R2;
- test su righe corrotte, finestre inclusive/fuori finestra, ownership/legacy,
  zero/una/più candidate, vettori Unicode, direct ID, retry, race, rollback e
  dry-run;
- nessuna evaluation, reporting, learning o modifica del piano.

Questo documento non implementa né autorizza automaticamente tali modifiche:
è il contratto contro cui dovranno essere proposte e revisionate.
