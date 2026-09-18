# Contratto runtime P0 — cattura `ActualSession`

**Stato:** normativo per il primo incremento runtime di `MAINTAIN_PLAN`
**Perimetro storico P0:** schema SQLite `SCHEMA_VERSION = 6`

> Il binding persistente successivo è definito dal
> [contratto subject ownership](MAINTAIN_PLAN_SUBJECT_OWNERSHIP_CONTRACT.md),
> che porta lo schema a v7 senza cambiare le regole di cattura qui definite.
**Flag:** `IRONCOACH_MAINTAIN_PLAN_ACTUAL_SESSION_ENABLED`

## 1. Scopo

Questo documento definisce il primo boundary runtime di `MAINTAIN_PLAN`: la
conversione deterministica di attività Garmin atomiche in `ActualSession` e la
loro persistenza. Il boundary acquisisce **esclusivamente** `ActualSession`.
Tutti i termini **DEVE**, **NON DEVE** e **VIETATO** sono requisiti normativi.

L'incremento implementativo successivo a questo contratto potrà aggiungere il
servizio di cattura, senza cambiare il significato qui definito. Questo
documento non implementa né abilita il runtime e non introduce schema v7.

### 1.1 Non-obiettivi P0

Il boundary NON DEVE eseguire:

- matching, incluso matching diretto per identificatore;
- creazione di `PrescriptionMapping` o di risultati di matching;
- `ExecutionEvaluation`, outcome finale o report;
- adjustment della confidence o learning;
- inferenze su struttura, intensità, completamento o condizioni esterne.

Gli identificatori `activity_id`, `source_id`, `file_hash`, Airtable
`record_id` e `decision_id` NON sono identificatori di una prescription
restituiti da un'attività. Non possono quindi autorizzare alcun matching.

## 2. Trust boundary e sorgente runtime

L'unico input autorevole è ciascun elemento di
`context["garmin_training_history"]`, prodotto dopo
`ContextBuilder.build()`. `context["training"]` e la history merged
`context["training_history"]` NON sono sorgenti di `ActualSession`, nemmeno
come fallback o per completare campi mancanti.

Il boundary tratta i dati Garmin come osservazioni esterne non fidate: valida
tipo, presenza, dominio, identità e timestamp prima di costruire il modello.
Non modifica l'elemento sorgente. Un elemento è accettabile soltanto quando
rappresenta esplicitamente una singola attività atomica e una sola disciplina.
Segmenti o metadata possono documentare la provenienza, ma non possono
trasformare una registrazione ambigua in una sessione supportata.

Sono unsupported e vengono rifiutati, mai suddivisi, uniti o reinterpretati:

- multisport, `multi_sport`, triathlon e brick;
- transizioni (`transition`, `transition_v2`) o attività che contengono una
  transizione;
- discipline multiple nei segmenti;
- classificazioni mancanti, contraddittorie o ambigue;
- discipline diverse da `RUN`, `BIKE` e `SWIM`.

## 3. Classificazione sportiva chiusa

La tabella seguente è esaustiva e **case-sensitive**. I valori sono dimostrati
dalla mappa esplicita dell'importer Garmin summary
(`backend/importers/garmin_summary_importer.py`, `_normalize_sport`) e, per i
valori canonici di `sport`, dall'output di quella stessa mappa. Le fixture
coprono inoltre `running`, `road_biking`, `indoor_cycling` e `lap_swimming` in
`tests/test_garmin_historical_importer.py` e
`tests/test_garmin_summary_importer.py`.

| Campo runtime | Valore esatto | `Discipline` |
|---|---|---|
| `raw.activity_type` | `running` | `RUN` |
| `raw.activity_type` | `track_running` | `RUN` |
| `raw.activity_type` | `street_running` | `RUN` |
| `raw.activity_type` | `trail_running` | `RUN` |
| `raw.activity_type` | `treadmill_running` | `RUN` |
| `raw.activity_type` | `cycling` | `BIKE` |
| `raw.activity_type` | `road_biking` | `BIKE` |
| `raw.activity_type` | `indoor_cycling` | `BIKE` |
| `raw.activity_type` | `virtual_ride` | `BIKE` |
| `raw.activity_type` | `mountain_biking` | `BIKE` |
| `raw.activity_type` | `gravel_cycling` | `BIKE` |
| `raw.activity_type` | `lap_swimming` | `SWIM` |
| `raw.activity_type` | `open_water_swimming` | `SWIM` |
| `raw.activity_type` | `swimming` | `SWIM` |

Il percorso runtime autorevole completo è
`context["garmin_training_history"][i]["raw"]["activity_type"]`. È la copia
letterale di `IronCoachActivity.activity_type`: per il summary importer nasce
da `record["activityType"]`, viene inserita da
`ContextBuilder._garmin_activity_to_session()` nel dizionario passato ad
`ActivityNormalizer.normalize()`, e il normalizer conserva quel dizionario in
`raw`. Il `sport` top-level è invece prodotto da `_normalize_sport()` e può
derivare dalla logica fuzzy dell'importer/normalizer: NON è una fonte
autorevole e NON può sostituire `raw.activity_type`.

`raw.activity_type` DEVE essere una stringa e corrispondere esattamente a una
riga della tabella. Valore assente, tipo non stringa, whitespace aggiuntivo o
valore non enumerato rende l'attività unsupported. Il confronto non applica
trim, case folding, substring matching, whitespace cleanup, traduzione o alias
ulteriori. Se il `sport` top-level è presente, può servire soltanto come
verifica di coerenza: DEVE essere esattamente `RUN`, `BIKE` o `SWIM` e
corrispondere alla disciplina risolta dal raw; una discordanza viene
rifiutata. Il nome è soltanto evidence.

Per ogni attività accettata, `ActualSession.composition` DEVE essere
`Composition.SINGLE`, con esattamente un `ObservedComponent` della disciplina
risolta. P0 non produce mai `BRICK` o `MULTISPORT`.

## 4. Identità deterministica

### 4.1 Identità del soggetto e dell'attività

`subject_ref` è esclusivamente `context["athlete"]["source_id"]`. DEVE essere
una stringa esplicita, non vuota (e non solo whitespace); non viene effettuato
trim e non esiste fallback da nome, profilo o altro identificatore.

`original_activity_id` deriva esclusivamente dal campo Garmin obbligatorio
`activity_id` dell'elemento runtime. `activity_id` DEVE essere una stringa
esplicita, non vuota e non solo whitespace; se è assente o invalido l'attività
viene rifiutata. `source_id` e `file_hash` sono identificatori aggiuntivi
opzionali, conservabili soltanto in `raw_ids`/provenance: `source_id` NON può
sostituire `activity_id`.

### 4.2 Canonicalizzazione di `session_id`

L'input dell'hash è un oggetto JSON versionato che contiene **esattamente**:

```json
{"original_activity_id":"<original_activity_id>","source":"garmin","subject_ref":"<subject_ref>"}
```

“Versionato” significa che questo shape e la costante `source="garmin"` sono
la versione P0 dell'algoritmo d'identità; ogni futura modifica dello shape o
del significato richiede una nuova versione normativa e non può riusare in
silenzio gli ID P0. La serializzazione normativa è esattamente l'equivalente
di:

```python
json.dumps(
    payload,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")
```

L'encoding è UTF-8 senza BOM. Non si applica alcuna normalizzazione Unicode
aggiuntiva: i caratteri non ASCII sono emessi direttamente dal JSON e poi
codificati in UTF-8. Implementazioni equivalenti in altri linguaggi DEVONO
produrre esattamente gli stessi byte.

Si calcola SHA-256 sui byte UTF-8 del JSON canonico, in esadecimale lowercase.
Il risultato è:

```text
maintain-plan:actual-session:sha256:<64 caratteri hex lowercase>
```

Vettore normativo Unicode (la `é` è il code point U+00E9, senza ulteriore
normalizzazione):

```text
payload:  {"original_activity_id":"garmin:123456789","source":"garmin","subject_ref":"atleta-é"}
preimage: {"original_activity_id":"garmin:123456789","source":"garmin","subject_ref":"atleta-é"}
SHA-256:  a7dc959a6b5773ada0993fbae272da4499a66a093d5f30632241cab4925e0559
session_id: maintain-plan:actual-session:sha256:a7dc959a6b5773ada0993fbae272da4499a66a093d5f30632241cab4925e0559
```

Con `ensure_ascii=True` la stessa `subject_ref` diventerebbe letteralmente
`"atleta-\u00e9"` nella preimage: quei byte sono differenti e quindi non sono
conformi.

## 5. Tempo e timezone

`start` proviene esclusivamente dal campo `date` dell'elemento Garmin. DEVE
essere esplicito, sintatticamente valido, rappresentare un istante valido ed
essere timezone-aware tramite `Z` o offset UTC esplicito. Timestamp naive,
date-only, valori invalidi o timezone inventate sono rifiutati; non esiste
timezone di fallback.

Il valore `timezone` di `ActualSession` conserva l'offset esplicito dello
start (`UTC` per `Z`, altrimenti l'offset numerico). La rappresentazione può
essere normalizzata per il modello soltanto preservando lo stesso istante e
offset; non può derivare da metadata come `time_zone_id`.

`end` è valorizzato soltanto se l'elemento autorevole espone un timestamp end
esplicito, valido e timezone-aware, coerente (`end >= start`). La corrente
proiezione di `garmin_training_history` non espone `end`, quindi oggi resta
missing. È VIETATO ricostruirlo da `start + duration_minutes`, elapsed time,
moving time o segmenti.

## 6. Mapping dei campi P0

| Destinazione | Sorgente/regola |
|---|---|
| `session_id` | Algoritmo §4.2 |
| `start`, `timezone` | `date`, secondo §5 |
| `end` | Solo end esplicito secondo §5; altrimenti `None` |
| `composition` | sempre `SINGLE` |
| `components` | una tupla con un componente, indice `0`, disciplina §3 |
| quantità durata | `duration_minutes`, solo se numero finito non negativo già normalizzato; unità `min` |
| quantità distanza | `distance_km`, solo se numero finito non negativo già normalizzato; unità `km` |
| HR osservata | `heart_rate.average` e `.max`, soltanto valori espliciti validi |
| power osservata | `power.average` e `.normalized`, soltanto valori espliciti validi |
| `source_activities` | una voce `source="garmin"`, `original_activity_id=activity_id`; `source_id`/`file_hash` opzionali nei raw IDs/provenance |
| `source_activity_refs` | riferimento alla singola source activity |
| `segments`, `metadata` | soltanto evidence/provenance, mai blocchi o altra struttura canonica |

Durata e distanza vengono conservate soltanto nelle unità già esplicitamente
normalizzate (`duration_minutes`, `distance_km`). Non si leggono unità raw, non
si convertono valori e non si deduce una primary quantity: entrambe sono
osservazioni secondarie/evidence finché tale ruolo non è esplicito.

HR e power sono osservazioni aggregate. Non provano un `intensity_method`, la
copertura temporale, la validità della copertura o il `time_in_target`; tali
campi restano missing.

## 7. Missingness e provenance

Missing è informazione normativa e non diventa mai zero, stringa vuota,
collezione fabbricata o default semantico. In particolare il normalizer
esistente può rappresentare distanza assente come `0`; P0 DEVE verificare la
presenza esplicita nella provenance Garmin prima di conservarla, altrimenti la
distanza resta missing. Uno zero è conservabile solo se esplicitamente
osservato nella sorgente normalizzata e distinguibile dal default.

Restano missing se non sono esplicitamente presenti e validi: environment,
mode, primary quantity, intensity method/unit, blocchi, ripetizioni,
transizioni, completion, feedback e weather. P0 non li deduce da
`activity_type`, nome, segmenti, HR, power o metadata. Le collezioni vuote
richieste dal modello indicano assenza di osservazioni, non un'osservazione
negativa; `missing_fields` DEVE rendere espliciti i campi applicabili non
osservati.

`source_id` e `file_hash`, quando presenti, possono essere copiati senza
reinterpretazione in `SourceActivity.raw_ids`, provenance o data-quality;
`activity_id` può esservi ripetuto, ma resta anche l'unica origine normativa di
`original_activity_id`. Gli identificatori sono evidence tracciabile, non
ownership o collegamento a una prescription. I timestamp di processo
`normalized_at` e
`captured_at`, se aggiunti alla provenance, sono non semantici e non possono
supplire ai timestamp dell'attività.

## 8. Persistenza append-only, retry e concorrenza

La futura operazione di cattura DEVE essere atomica e append-only:

1. aprire una transazione SQLite con `BEGIN IMMEDIATE` **prima** di cercare il
   `session_id`;
2. costruire/validare il candidato e cercare l'ID nella stessa transazione;
3. se assente, inserire il candidato senza update/upsert distruttivo;
4. se presente, confrontare l'intero contenuto semantico canonico;
5. effettuare commit soltanto per inserimento o retry equivalente.

Per lo stesso `session_id`, contenuto semanticamente equivalente restituisce
l'oggetto già persistito (retry idempotente). Contenuto differente produce un
errore di conflitto, rollback completo e nessun overwrite. Nel confronto si
possono ignorare **esclusivamente** `normalized_at` e `captured_at`, dichiarati
timestamp di processo non semantici; nessun altro campo, inclusi provenance,
warnings, missingness e data quality, può essere ignorato. Errori, race e
vincoli SQLite comportano rollback; la transazione `BEGIN IMMEDIATE` serializza
lookup e inserimento concorrenti sul writer.

La persistenza usa lo schema corrente: `SCHEMA_VERSION` DEVE restare `6`.

## 9. Flag, dry-run e wiring

La cattura è protetta esclusivamente dal flag separato
`IRONCOACH_MAINTAIN_PLAN_ACTUAL_SESSION_ENABLED`, con default `false` e parsing
fail-closed: valore assente, vuoto, invalido o non esplicitamente abilitante
disabilita la feature. Il flag non abilita alcuna fase esclusa dal §1.1.

In dry-run il servizio di cattura NON viene chiamato, SQLite NON viene aperto e
non avviene alcuna scrittura, indipendentemente dal flag.

Il wiring futuro è collocato dopo il completamento di
`ContextBuilder.build()` e prima sia della Decision Memory sia del Coach
Engine. Un errore tecnico di validazione/cattura/persistenza è fail-closed:
blocca Decision Memory, Coach Engine e ogni altro effetto downstream; non viene
degradato a warning né recuperato usando altre history. Una singola attività
unsupported genera un esito esplicito unsupported e nessuna `ActualSession`
per quell'elemento; un guasto tecnico genera errore e rollback.

## 10. Divieto di ownership implicita e matching

Nel perimetro storico P0 mancava un ownership binding comune verificabile e il
matching era quindi vietato. Lo slice successivo persiste il binding comune
secondo il
[contratto subject ownership](MAINTAIN_PLAN_SUBJECT_OWNERSHIP_CONTRACT.md).
Questa evoluzione non abilita candidate discovery runtime e non modifica il
matcher puro.

Il database P0 può operare inizialmente per un solo atleta come vincolo
operativo di deployment; questa assunzione NON costituisce prova di ownership
e non attenua il divieto.

Qualunque mapping persistito DEVE ora superare il confronto esatto e
fail-closed previsto dal contratto dedicato; i record legacy senza binding non
sono eleggibili.

Ordine runtime, candidate discovery e transazione del futuro collegamento sono
definiti dal
[contratto runtime matching](MAINTAIN_PLAN_RUNTIME_MATCHING_CONTRACT.md), che
richiede un `SynchronizationCoverage` autorevole e limitato e ordina il
percorso session-driven prima di quello prescription/window-driven, senza
estendere il perimetro di cattura di questo documento. Lo scope aggiunge
soltanto i vicini indicizzati immediati attorno allo start di ogni sessione e
il secondo percorso deve rispettare la guardia delle discovery irrisolte.

## 11. Criteri di accettazione

Il futuro servizio P0 è conforme soltanto se:

1. legge unicamente `garmin_training_history` e produce soltanto
   `ActualSession` atomiche `SINGLE` per RUN/BIKE/SWIM;
2. applica letteralmente tabella chiusa, identità e timestamp di questo
   contratto, senza fallback;
3. preserva missingness, unità normalizzate e provenance senza inventare
   struttura o semantica;
4. non chiama né persiste matching, mapping, evaluation, outcome, report,
   confidence adjustment o learning;
5. è disabilitato per default, fail-closed e totalmente inerte in dry-run;
6. persiste append-only con `BEGIN IMMEDIATE`, retry equivalenti idempotenti e
   conflitti divergenti senza overwrite;
7. blocca gli effetti downstream in caso di errore tecnico;
8. mantiene `SCHEMA_VERSION = 6` e non crea migrazioni o schema v7;
9. deriva `original_activity_id` soltanto dall'`activity_id` Garmin
   obbligatorio e calcola la preimage con la serializzazione esatta del §4.2;
10. assegna lo stesso `session_id` a uguali `subject_ref`, `source="garmin"` e
    `activity_id`, indipendentemente da `source_id`; se a quell'ID corrisponde
    un payload incompatibile, segnala conflitto senza overwrite;
11. legge la classificazione esclusivamente da
    `context["garmin_training_history"][i]["raw"]["activity_type"]`, applica
    il confronto esatto della tabella e usa il `sport` top-level soltanto per
    verificarne la coerenza;
12. dispone di test che provano tutti i casi avversariali del §12.

## 12. Casi avversariali obbligatori

I test del futuro incremento DEVONO includere almeno:

- assenza/non-lista di `garmin_training_history`, senza fallback alle altre
  history;
- athlete mancante, `source_id` non stringa, vuoto o whitespace-only, e prova
  che il nome non è usato;
- `activity_id` Garmin mancante, non stringa, vuoto o whitespace-only e prova
  che `source_id`, `file_hash`, `record_id` o `decision_id` non lo
  sostituiscono;
- stesso `subject_ref`, `source="garmin"` e `activity_id` con `source_id`
  differenti: stesso `session_id`; payload incompatibili per quell'ID:
  conflitto, rollback e nessun overwrite;
- vettore normativo Unicode del §4.2, ordine chiavi e separatori; prova che
  `ensure_ascii=True` produce la diversa preimage con `\u00e9` ed è non
  conforme;
- `raw.activity_type` valido della tabella: accettato; assente, non stringa,
  con whitespace aggiuntivo, fuzzy come `foo_running`, case variant,
  traduzione o sconosciuto: unsupported;
- `sport` top-level valido con `raw.activity_type` invalido o assente:
  unsupported; `raw.activity_type` valido ma `sport` top-level presente e
  discordante: unsupported;
- strength/other, multisport/triathlon/brick, transizione e segmenti
  multi-disciplina: unsupported e mai reinterpretati;
- start naive, date-only, offset invalido, timestamp impossibile e start
  mancante: rifiutati senza timezone fallback;
- end assente con durata presente: end resta missing; end naive o precedente
  allo start: rifiutato;
- durata/distanza mancanti, `None`, non finite, negative, in unità raw e zero
  sintetico del normalizer: mai convertite in zero o conservate; zero sorgente
  esplicito e tracciabile: conservato;
- HR/power presenti senza intensity method, coverage o time-in-target:
  osservazioni preservate e campi inferenziali missing;
- metadata/segmenti che sembrano blocchi, ripetizioni, transition, environment
  o mode: conservati solo come evidence;
- flag assente/falso/invalido e dry-run con flag vero: nessuna chiamata al
  servizio, apertura SQLite o scrittura;
- due retry equivalenti (differenti solo per `normalized_at`/`captured_at`):
  ritorno dell'esistente; differenza in qualunque altro campo: conflitto,
  rollback e nessun overwrite;
- due writer concorrenti sullo stesso ID e su contenuti divergenti, provando
  `BEGIN IMMEDIATE` prima del lookup e un solo risultato persistito;
- errore tecnico di cattura: nessun effetto Decision Memory/Coach Engine;
- tentativi di usare qualunque ID come returned prescription ID o di creare
  matching/`PrescriptionMapping`: vietati;
- deployment single-athlete: prova che non viene trattato come ownership.
