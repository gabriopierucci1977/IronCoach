# DRAFT — MAINTAIN_PLAN Outcome Contract — NON IMPLEMENTATO

> **Stato:** DRAFT, NON IMPLEMENTATO.
>
> Questo documento definisce il contratto dati e semantico minimo da approvare
> prima di implementare evaluator o test per l'outcome `MAINTAIN_PLAN`. Non
> descrive comportamento attualmente disponibile nel runtime.

## 1. Obiettivo e non-obiettivi

### Obiettivo

Definire quando IronCoach dispone di evidenza sufficiente per valutare se una
decisione con primary intent `MAINTAIN_PLAN` ha prodotto congiuntamente:

1. il completamento del workout prescritto; e
2. la stabilità generale dell'atleta nella finestra osservativa approvata.

Il contratto deve rendere confrontabili prescrizione ed esecuzione senza
dedurre informazioni non osservate e deve produrre evidenza verificabile per
ogni dimensione valutata.

### Non-obiettivi

Questo contratto non:

- implementa un evaluator, modifica il runtime o definisce nuovi test;
- stabilisce soglie numeriche di aderenza o finestre temporali;
- definisce equivalenze o sostituzioni tra sport;
- converte automaticamente metodi d'intensità differenti;
- introduce criteri clinici o sostituisce una valutazione sanitaria;
- misura il miglioramento di lungo periodo o la correttezza originaria della
  decisione;
- considera la mera presenza di un'attività come prova di successo;
- autorizza l'uso di dati grezzi non contrattualizzati come fallback
  decisionale.

## 2. Prescrizione canonica minima

La prescrizione valutabile deve essere uno snapshot immutabile, riferito alla
decisione, con provenienza e versione del contratto. I campi obbligatori minimi
sono:

```yaml
planned_workout:
  contract_version: string
  workout_id: string
  decision_id: string
  scheduled_window:
    start: datetime
    end: datetime
    timezone: string
  sport:
    code: string
  allowed_substitutions: []
  volume:
    applicability: REQUIRED | NOT_APPLICABLE
    metric: string | null
    target: number | null
    unit: string | null
    tolerance_policy_id: string | null
  intensity:
    applicability: REQUIRED | NOT_APPLICABLE
    method: string | null
    target: object | null
    unit: string | null
    tolerance_policy_id: string | null
  structure:
    applicability: REQUIRED | NOT_APPLICABLE
    segments: []
    evaluation_policy_id: string | null
  objective:
    applicability: REQUIRED | NOT_APPLICABLE
    code: string | null
    success_criteria: []
    evaluation_policy_id: string | null
  provenance:
    source: string
    captured_at: datetime
```

Ogni elemento di `allowed_substitutions` deve essere dichiarato esplicitamente
nella prescrizione o in una policy identificata e versionata. Il contratto non
presume alcuna equivalenza tra sport.

Se `structure.applicability` è `REQUIRED`, ogni segmento deve identificare
almeno ordine, tipo, volume applicabile, metodo d'intensità applicabile,
recupero applicabile e opzionalità. Valori target e unità devono essere campi
strutturati, non estratti da testo libero durante la valutazione.

Le tolerance policy e le evaluation policy sono riferimenti obbligatori quando
la relativa dimensione è richiesta. I loro contenuti e le eventuali soglie
devono essere approvati separatamente: questo draft non ne inventa alcuno.

## 3. Attività eseguita canonica minima

L'attività associata deve essere già normalizzata e deve conservare missingness,
provenienza e qualità dei dati:

```yaml
actual_activity:
  contract_version: string
  activity_id: string
  source: string
  start: datetime
  end: datetime | null
  timezone: string
  sport:
    code: string
  volume:
    metric: string | null
    value: number | null
    unit: string | null
  intensity:
    method: string | null
    observed: object | null
    unit: string | null
    coverage: object | null
  structure:
    segments: []
  completion:
    status: string | null
    interruption_reason: string | null
  safety:
    pain: object | null
    injury_or_adverse_event: object | null
  data_quality:
    source_checked_at: datetime | null
    completeness: string
    missing_fields: []
    warnings: []
  provenance:
    normalized_at: datetime
```

Il valore mancante deve rimanere `null` e non essere trasformato in zero. Le
unità devono essere esplicite. `raw` può essere conservato per audit, ma non può
sostituire i campi canonici richiesti dall'evaluator.

Se la prescrizione richiede struttura, i segmenti reali devono offrire le
stesse dimensioni necessarie al confronto. Una media complessiva dell'attività
non dimostra da sola l'esecuzione dei singoli segmenti.

## 4. Contratto di stabilità generale

La stabilità generale è un outcome composito distinto dall'aderenza. Deve
confrontare una baseline pre-decisione con osservazioni post-decisione entro
finestre esplicite, mature e complete.

```yaml
general_stability:
  contract_version: string
  baseline:
    observed_at: datetime
    dimensions: object
    data_quality: object
  observation_window:
    start: datetime
    end: datetime
    evaluated_at: datetime
    mature: boolean
    complete: boolean
  dimensions:
    recovery: dimension_result
    pain_or_injury: dimension_result
    load_tolerance: dimension_result
    performance: dimension_result
    adverse_events: dimension_result
  overall:
    status: STABLE | DETERIORATED | INSUFFICIENT_DATA
    policy_id: string
    evidence: object
  data_quality:
    freshness: object
    missing_dimensions: []
    warnings: []
```

Per ciascuna dimensione, `dimension_result` deve contenere almeno stato,
baseline, osservazioni, finestra, sorgente, freshness, completezza, policy
versionata ed evidenza. Le dimensioni obbligatorie, le finestre, il significato
di deterioramento e la regola di aggregazione devono essere approvati prima
dell'implementazione.

Il solo recovery non equivale a stabilità generale. L'assenza di un record di
dolore, infortunio o evento avverso non equivale alla prova della loro assenza.
Una finestra non matura o incompleta non può produrre `STABLE`.

## 5. Stati delle dimensioni

Ogni dimensione di completamento (`sport`, `volume`, `intensity`, `structure`,
`objective`) deve restituire esattamente uno dei seguenti stati:

| Stato | Significato |
|---|---|
| `MET` | L'evidenza richiesta, compatibile e completa soddisfa la policy approvata della dimensione. |
| `PARTIALLY_MET` | L'evidenza richiesta è sufficiente per applicare la policy, ma soddisfa solo il criterio di aderenza parziale definito dalla policy. |
| `NOT_MET` | L'evidenza richiesta è sufficiente e compatibile, ma non soddisfa la policy. |
| `NOT_APPLICABLE` | La prescrizione dichiara esplicitamente che la dimensione non si applica. Non è sinonimo di dato mancante. |
| `INSUFFICIENT_DATA` | L'evidenza è mancante, incompleta, ambigua, incompatibile, non fresca o non consente di applicare la policy. |

`PARTIALLY_MET` richiede criteri approvati specifici della dimensione; non può
essere assegnato per intuizione. `NOT_APPLICABLE` è valido solo se dichiarato
nel contratto della prescrizione. In ogni altro caso, l'assenza di dati produce
`INSUFFICIENT_DATA`.

Ogni risultato deve includere:

```yaml
dimension_result:
  status: MET | PARTIALLY_MET | NOT_MET | NOT_APPLICABLE | INSUFFICIENT_DATA
  policy_id: string | null
  planned_evidence: object
  actual_evidence: object
  reasons: []
  data_quality: object
```

## 6. Regole di compatibilità

### Sport

Il confronto è valido solo quando:

- lo sport reale coincide con lo sport canonico prescritto; oppure
- la sostituzione è esplicitamente ammessa da `allowed_substitutions` o da una
  policy versionata richiamata dalla prescrizione.

Una somiglianza nominale, la comune natura aerobica o l'appartenenza implicita
a una famiglia non autorizzano una sostituzione.

### Volume

Il confronto è valido solo quando metrica e unità del volume sono identiche sui
due lati. Conversioni ammesse devono avvenire prima dell'evaluator, in un layer
di normalizzazione con regole esplicite e testate; l'evaluator non deve
indovinare unità o convertire in base alla magnitudine.

### Intensità

Il confronto è valido solo quando il metodo d'intensità è lo stesso nella
prescrizione e nell'attività: per esempio, un target basato su un metodo non può
essere dimostrato mediante un metodo diverso. Qualunque conversione futura fra
metodi richiederà un contratto separato, esplicito e approvato.

### Missingness e incompatibilità

Se una dimensione richiesta presenta dati mancanti, unità incompatibili,
metodi incompatibili, segmentazione insufficiente, sorgente non fresca o
matching ambiguo, il suo stato deve essere `INSUFFICIENT_DATA`.

L'incompatibilità non equivale a `NOT_MET`: quest'ultimo richiede dati
sufficienti per dimostrare che il criterio non è stato soddisfatto.

## 7. Regole contro proxy deboli

È vietato concludere che `MAINTAIN_PLAN` sia positivo usando, da soli o in
combinazioni non contrattualizzate:

- la sola esistenza di un'attività successiva alla decisione;
- la sola coincidenza dello sport;
- nome del workout, tipo seduta o note in testo libero;
- la sola durata, distanza o presenza di movimento;
- medie complessive per inferire l'esecuzione di intervalli o segmenti;
- frequenza cardiaca per dimostrare un target di potenza, potenza per dimostrare
  RPE, o qualsiasi altro metodo d'intensità differente;
- calorie Garmin come prova di fueling;
- VO2max, velocità media o una singola metrica osservazionale come prova di
  performance stabile;
- il solo recovery come prova di stabilità generale;
- assenza di record come prova di assenza di dolore, infortunio o evento
  avverso;
- valori presenti solo in `raw` quando manca il campo canonico richiesto;
- zero sintetici al posto di dati mancanti;
- sport, unità, intensità, criteri clinici o tolleranze inferiti implicitamente.

Il risultato complessivo non deve nascondere gli
`INSUFFICIENT_DATA` delle dimensioni obbligatorie.

## 8. Sorgenti dati necessarie

Prima dell'implementazione devono essere disponibili e contrattualizzate:

1. **Piano/versione della prescrizione**: snapshot immutabile del workout
   effettivamente valido dopo la decisione, inclusi applicabilità, policy e
   finestra programmata.
2. **Attività normalizzata**: sorgente dell'esecuzione con ID stabile, timestamp,
   sport, volume e, quando richiesti, intensità e segmenti.
3. **Telemetria coerente con la prescrizione**: HR, potenza, passo, velocità o
   altro metodo solo quando quello stesso metodo è prescritto e la copertura è
   sufficiente secondo una policy approvata.
4. **Feedback soggettivo strutturato**: RPE, completamento/interruzione, dolore e
   problemi, quando richiesti; il testo libero può accompagnare ma non
   sostituire il dato canonico.
5. **Recovery history**: baseline e osservazioni successive con timestamp,
   freshness e completezza.
6. **Training/load history**: dati coerenti e confrontabili necessari alla
   dimensione di tolleranza al carico.
7. **Injury/adverse-event history**: osservazioni esplicite, incluse quelle
   negative se il contratto della sorgente ne garantisce il significato.
8. **Performance history**, solo se dichiarata obbligatoria dalla policy di
   stabilità e supportata da un vero trend temporale confrontabile.
9. **Stato delle sorgenti**: ultimo controllo riuscito, copertura della finestra,
   freshness, errori e campi mancanti.

Le credenziali, i payload reali e i dati grezzi sensibili non fanno parte di
questo contratto documentale.

## 9. Decisioni ancora aperte prima dell'implementazione

Devono essere risolte e documentate almeno le seguenti decisioni:

- quale oggetto prevale fra workout originariamente pianificato e workout
  raccomandato/modificato;
- tassonomia canonica degli sport e governance delle sostituzioni esplicite;
- metriche di volume ammesse per ciascuno sport;
- policy e tolleranze per `MET`, `PARTIALLY_MET` e `NOT_MET` sul volume;
- metodi d'intensità supportati e forma canonica dei rispettivi target;
- copertura minima della telemetria necessaria per valutare l'intensità;
- schema dei segmenti pianificati e reali, incluso il multisport;
- criteri strutturati per dichiarare raggiunto l'obiettivo della seduta;
- dimensioni obbligatorie della stabilità generale;
- baseline, finestre temporali, maturity, freshness e completezza richieste;
- definizione di deterioramento per ogni dimensione di stabilità;
- regola di aggregazione della stabilità generale;
- regola di aggregazione fra completamento e stabilità nell'outcome finale;
- trattamento di più attività candidate, workout divisi e attività combinate;
- distinzione operativa tra `NOT_MET` e `INSUFFICIENT_DATA` quando l'attività è
  interrotta o la sorgente è incompleta;
- versionamento, audit e migrazione degli episodi già persistiti;
- gestione della privacy e retention dei dati soggettivi o di sicurezza.

Finché queste decisioni non sono chiuse, `MAINTAIN_PLAN` deve rimanere non
implementato e non deve ricevere un esito positivo tramite fallback.

## 10. Criteri di accettazione pre-implementazione

Evaluator e test per `MAINTAIN_PLAN` possono essere scritti solo quando tutti i
seguenti criteri sono soddisfatti:

- [ ] Il contratto di prescrizione canonica è approvato, versionato e distingue
      campi richiesti, opzionali e `NOT_APPLICABLE`.
- [ ] Lo snapshot persistito identifica senza ambiguità il workout valido dopo
      la decisione.
- [ ] Il contratto dell'attività reale è approvato, versionato e conserva
      missingness, unità, provenienza e qualità.
- [ ] Matching temporale, sportivo, multisport e multi-candidato è definito in
      modo deterministico.
- [ ] La tassonomia sportiva e le sole sostituzioni ammesse sono approvate.
- [ ] Le metriche e unità di volume supportate sono esplicite; non esistono
      euristiche basate sulla magnitudine nel percorso dell'evaluator.
- [ ] I metodi d'intensità supportati hanno target e osservazioni nella stessa
      rappresentazione canonica.
- [ ] La struttura prescritta e quella reale sono confrontabili tramite
      segmenti strutturati, senza parsing decisionale di testo libero.
- [ ] L'obiettivo della seduta dispone di criteri osservabili e versionati,
      oppure è dichiarato esplicitamente `NOT_APPLICABLE`.
- [ ] Ogni dimensione ha una policy approvata per tutti e cinque gli stati,
      senza soglie implicite.
- [ ] Il contratto di stabilità generale specifica dimensioni obbligatorie,
      baseline, finestre, maturity, freshness, completezza e aggregazione.
- [ ] Le sorgenti necessarie distinguono esplicitamente dato assente da valore
      zero e assenza di record da osservazione negativa.
- [ ] L'outcome complessivo propaga `INSUFFICIENT_DATA` quando una dimensione
      obbligatoria non è valutabile.
- [ ] Sono approvate le regole che combinano completamento del workout e
      stabilità generale in un outcome finale.
- [ ] Sono disponibili fixture esclusivamente sintetiche e prive di dati reali
      per ciascuno stato, incompatibilità, missingness e caso ambiguo.
- [ ] Versioni delle policy, evidenza per dimensione e motivazioni sono
      persistibili e auditabili senza consultare `raw`.
- [ ] È stata completata una revisione esplicita contro tutti i proxy deboli
      elencati in questo documento.

Il soddisfacimento di questa checklist autorizza la progettazione di evaluator
e test, ma non costituisce di per sé approvazione delle soglie o dei criteri
ancora da definire.
