# DRAFT — MAINTAIN_PLAN Outcome Contract — NON IMPLEMENTATO

> **Stato:** DRAFT, NON IMPLEMENTATO.
>
> **Versione di lavoro:** `maintain-plan/1.0.0-draft`.
>
> Le decisioni contrassegnate come **APPROVATA** definiscono il contratto
> concordato, ma non descrivono comportamento attualmente disponibile nel
> runtime. Ogni risultato prodotto con una versione draft è escluso dal
> learning. Fino all'implementazione e a una successiva approvazione esplicita
> dell'attivazione, `MAINTAIN_PLAN` deve restare `INSUFFICIENT_DATA` e non deve
> ricevere esiti tramite fallback o proxy.

## 1. Scopo e confini

Questo documento definisce il contratto dati, semantico e di governance per
valutare se una decisione con primary intent `MAINTAIN_PLAN` ha prodotto
congiuntamente:

1. un'esecuzione coerente con l'ultima prescrizione effettivamente comunicata
   all'atleta; e
2. la stabilità generale dell'atleta.

Il contratto conserva evidenza verificabile per ogni dimensione, senza dedurre
informazioni non osservate. Non implementa evaluator o test, non autorizza
equivalenze implicite, non formula diagnosi cliniche e non usa la mera presenza
di un'attività come prova di successo.

Le soglie riportate in questo documento sono esclusivamente quelle approvate
per l'aderenza alla prescrizione. Non sono soglie cliniche.

Tutte le formulazioni normative nelle sezioni successive descrivono la futura
implementazione: nessuna di esse dichiara un comportamento runtime già
disponibile.

## 2. Registro delle decisioni approvate

Le seguenti decisioni sono **APPROVATE**:

1. **Prescrizione autorevole.** È l'ultima prescrizione effettivamente
   comunicata all'atleta, conservata come snapshot immutabile. La prescrizione
   originaria resta disponibile esclusivamente per audit.
2. **Dimensioni di esecuzione.** Sono identità sportiva, quantità di lavoro,
   intensità e struttura della seduta. `composition` classifica la sessione;
   l'identità sportiva è rappresentata dall'elenco ordinato dei componenti,
   ciascuno descritto da `component_index`, `discipline`, `environment` e
   `mode`.
3. **Separazione semantica.** Quantità, intensità e dose complessiva sono
   concetti distinti. Quantità e intensità sono valutate separatamente e
   combinate senza equivalenze o compensazioni implicite.
4. **Meteo.** È contestuale, facoltativo e non decisionale. Non determina
   direttamente gli stati, non corregge matematicamente la dose e la sua
   assenza non blocca il report. Per indoor è `NOT_APPLICABLE`.
5. **Obiettivo.** È valutabile soltanto con criteri strutturati e osservabili.
   Un obiettivo testuale resta contesto e non blocca l'analisi.
6. **Stati e testi utente.** La corrispondenza della sezione 9 è vincolante.
   Missingness, ambiguità e interruzioni di sicurezza non sono presentate come
   fallimenti dell'atleta.
7. **Stabilità.** Usa la baseline recovery impiegata per formulare la
   prescrizione e il primo follow-up valido dopo la seduta e prima della
   decisione successiva. Considera problemi soggettivi e safety signal; non
   formula diagnosi. Performance non è obbligatoria nella prima versione.
8. **Metriche primarie.** Ogni prescrizione dichiara la metrica primaria. Le
   metriche secondarie sono contestuali e non sostituiscono quella primaria.
9. **Policy della quantità.** Le fasce approvate sono esplicite, indipendenti
   sopra e sotto il target, versionate e sostituibili da una regola esplicita
   della prescrizione.
10. **Metodo d'intensità.** Si usa soltanto il metodo prescritto. HR, power,
    pace/speed e RPE restano distinti e non vengono convertiti automaticamente.
11. **Copertura dell'intensità.** Sedute continue e intervalli usano le soglie
    di copertura approvate nelle sezioni 6.2 e 6.3. Telemetria insufficiente
    rende non valutabile soltanto la dimensione interessata.
12. **Identità sportiva.** `composition` ammette `single`, `brick` e
    `multisport`; i componenti sono canonici e ordinati. Una sessione `single`
    contiene esattamente un componente; `brick` e `multisport` ne contengono
    più di uno. Le sostituzioni sono compatibili automaticamente soltanto se
    dichiarate nella prescrizione.
13. **Tempistiche.** Il report è visibile subito dopo la sincronizzazione; il
    recovery successivo guida internamente la seduta seguente. Le finestre 72h
    e 7d restano trend interni. Nessun aggiornamento tardivo genera un nuovo
    report della vecchia seduta ormai superata.
14. **Deterioramento.** Riusa analyzer e categorie già approvati; i segnali di
    sicurezza hanno priorità e segnali insufficienti o contraddittori non
    producono conclusioni inventate.
15. **Matrice finale.** L'aggregazione execution × stability della sezione 11
    è vincolante.
16. **Brick e multisport.** Sono sessioni composte con componenti distinti da
    blocchi, segmenti e transizioni. Producono una sola sessione, un solo
    outcome e un solo contributo al learning.
17. **Interruzioni.** Un workout interrotto per sicurezza conserva ragione ed
    evidenza e non è descritto come errore dell'atleta.
18. **Applicazione temporale.** Il contratto si applicherà soltanto ai nuovi
    episodi creati dopo la futura attivazione. Nessun episodio storico o draft
    viene reinterpretato o convertito automaticamente.
19. **Tolleranze esplicite.** Nessun evaluator contiene tolleranze nascoste.
20. **Dose complessiva.** È la combinazione versionata di quantità e intensità
    secondo la matrice completa della sezione 7, senza saldo fra scostamenti
    opposti.
21. **Struttura osservabile.** Dichiara requiredness, blocchi obbligatori e
    facoltativi, main set e vincoli d'ordine. Ciò che non è ricostruibile non è
    inferito.
22. **Contratto d'intensità.** Metodo, unità, target, copertura ed evaluation
    window applicabile sono dichiarati per blocco.
23. **Sorgente meteo.** Open-Meteo è la prima sorgente ambientale sostituibile;
    riceve soltanto punti approssimati e orari necessari.
24. **Privacy meteo.** Non sono trasmessi atleta, ID, indirizzo o tracciato
    completo; la persistenza è limitata ai dati effettivamente usati.
25. **Matching deterministico.** Un direct prescription/workout ID valido e
    univoco ha priorità assoluta. Senza direct ID, l'associazione automatica è
    permessa soltanto con esattamente una candidata compatibile secondo la
    sezione 5.
26. **Matching e aderenza separati.** Un direct ID valido prova la relazione
    anche in presenza di scostamenti di esecuzione; tali scostamenti sono
    valutati separatamente e non invalidano il matching.
27. **Conferma.** Quando un'ambiguità può cambiare decisione, valutazione,
    report o learning, IronCoach non sceglie fra interpretazioni plausibili e
    chiede conferma all'atleta secondo la sezione 4.
28. **Zero, una o più candidate.** Zero o più candidate richiedono conferma;
    una sola candidata compatibile consente il matching automatico. Non sono
    ammessi tie-break impliciti.
29. **Candidate window.** Senza direct ID l'inizio dell'attività deve ricadere
    nella `scheduled_window`; una prescrizione con sola data usa l'intero
    giorno nel timezone dell'atleta.
30. **Filtri automatici.** Senza direct ID devono coincidere composition,
    numero, ordine e discipline dei componenti. `environment` e `mode` non
    sono filtri eliminatori.
31. **Consecutività Brick.** Una Brick ha almeno due componenti e almeno due
    discipline differenti. Il gap massimo generale è 15 minuti, definito da
    policy versionata e sostituibile dalla prescrizione.
32. **Brick vs multisport.** La composition autorevole è quella dichiarata
    dalla prescrizione, non quella inferita dalle discipline o dichiarata dal
    dispositivo.
33. **Quantità iniziale.** RUN/BIKE continui usano durata attiva; piscina
    strutturata usa distanza; nuoto continuo/open water usa durata salvo
    prescrizione distance-based; intervalli usano il main set; Brick e
    multisport sono valutati per componente.
34. **STRENGTH.** È rappresentabile con serie e ripetizioni ma resta fuori
    dalla prima valutazione automatica.
35. **Policy quantitative.** Le fasce numeriche approvate sono definite nella
    sezione 6.1.
36. **Policy d'intensità.** Copertura, time-in-target e percentuali di
    ripetizioni approvate sono definite nelle sezioni 6.2 e 6.3.
37. **Policy di struttura.** Gli stati e i criteri approvati sono definiti
    nella sezione 6.4.
38. **Aggregazione dell'esecuzione.** Le quattro dimensioni obbligatorie sono
    aggregate senza compensazioni secondo la sezione 10.
39. **Conflitti di sorgente.** Nessuna media, fusione o sovrascrittura
    silenziosa. I valori discordanti restano con provenance; si chiede conferma
    se il conflitto può cambiare un risultato.
40. **Feedback soggettivo.** È facoltativo, auditabile e privato. L'assenza
    completa di segnalazioni significa `NO_KNOWN_ISSUE`, non certificazione
    medica, e non costituisce di per sé ambiguità.
41. **Rollout.** Tipi/validator/fixture precedono il runtime; feature flag
    separano snapshot, normalization, matching, shadow, report e learning.
42. **Shadow e learning.** Lo shadow non cambia outcome ufficiale, confidence
    o report e non entra nel learning. L'attivazione del learning richiede una
    nuova approvazione esplicita.
43. **Applicability v1.** Per ogni sessione supportata sport/componenti,
    quantità, intensità, struttura e dose sono `REQUIRED`. Un target obbligatorio
    mancante produce `INSUFFICIENT_DATA`, non `NOT_APPLICABLE`.
44. **Risultati per componente.** Identity, quantità, intensità, struttura e
    dose sono valutate per componente e poi aggregate senza compensazioni.
45. **Stabilità tecnica unica.** Gli unici stati sono `STABLE`, `DETERIORATED`
    e `INSUFFICIENT_DATA`, aggregati secondo la sezione 11.
46. **Dettaglio Brick/multisport.** Recovery e stability riguardano l'intera
    sessione; il report dettaglia ciascun componente e la relativa struttura;
    il meteo è separato per componente outdoor e `NOT_APPLICABLE` per ciascun
    componente indoor. Non si sommano unità incompatibili.
47. **Indipendenza dell'attività osservata.** `actual_session` è un input
    canonico immutabile costruibile senza prescrizione o mapping; il risultato
    del matching conserva separatamente il mapping soltanto quando risolto in
    modo automatico univoco o confermato dall'atleta.
48. **Direzione degli intervalli in fascia principale.** Almeno il 90% delle
    ripetizioni obbligatorie rispettate produce sempre `MET + IN_LINE`; la
    direzione degli scostamenti è calcolata soltanto nelle fasce
    `PARTIALLY_MET` e `NOT_MET`.
49. **Aggregazione identity.** L'identità dei componenti usa, senza
    compensazioni, la precedenza `INSUFFICIENT_DATA`, `NOT_MET`,
    `PARTIALLY_MET`, quindi `MET`.
50. **Semantica della dose.** `dose_evaluation.status` esprime soltanto
    `EVALUATED` o `INSUFFICIENT_DATA`; la direzione e la fascia restano campi
    separati.
51. **Direzione d'intensità composta.** Brick e multisport aggregano la
    direzione d'intensità con una precedenza deterministica distinta dallo
    status e senza compensazioni.
52. **Lifecycle append-only.** Correzioni/cancellazioni del feedback e
    risoluzioni dei conflitti sono eventi separati e versionati; non modificano
    l'`actual_session` immutabile.
53. **Copertura dei componenti.** Ogni associazione dichiara `MATCHED`,
    `PLANNED_ONLY` oppure `OBSERVED_ONLY`. Ogni componente pianificato
    obbligatorio produce un risultato riferito dagli aggregati anche se non ha
    una controparte osservata; i componenti soltanto osservati restano evidenza
    visibile, senza target inventati.
54. **Precedenza overall.** Le quattro dimensioni obbligatorie usano, senza
    compensazioni, la precedenza vincolante `INSUFFICIENT_DATA`, `NOT_MET`,
    `PARTIALLY_MET`, quindi `MET`, secondo la sezione 10.
55. **Gravità della dose.** Ogni dose valutata, per componente o aggregata,
    usa sempre la fascia peggiore degli input nell'ordine `MAIN < SECONDARY <
    OUT_OF_BAND`, indipendentemente dalla direzione.
56. **Risultato dell'obiettivo.** Un risultato canonico è prodotto soltanto
    per obiettivi `STRUCTURED`, da criteri prescritti osservabili e policy
    versionata. Non è una quinta dimensione e nella v1 non modifica overall,
    dose o learning.
57. **Codice dell'obiettivo strutturato.** Ogni obiettivo `STRUCTURED` ha un
    `code` non null, stabile e utilizzabile nel riferimento canonico; senza
    codice l'input è invalido e non può produrre `objective_result`. Il codice
    non è mai inferito dal testo libero.
58. **Policy della dose valutata.** Ogni dose `EVALUATED`, di componente o
    aggregata, identifica con `policy_id` e `policy_version` non null la matrice
    versionata effettivamente usata. Per `INSUFFICIENT_DATA` entrambi sono null;
    una coppia parziale o assente rende la dose invalida e non pubblicabile né
    utilizzabile per report o learning.
59. **Impatto dei conflitti dopo il matching.** I conflitti sorgente grezzi non
    dipendono dalla prescrizione e non classificano il proprio impatto. Una
    evaluation separata, versionata e auditabile ne determina l'impatto solo
    dopo un mapping risolto e univoco; mapping mancante, ambiguo o non
    confermato impone `UNRESOLVED`.
60. **Direzione della dose composta.** La dose aggregata di Brick e multisport
    applica la precedenza totale della sezione 7 a tutte le dosi dei componenti
    obbligatori, senza compensazioni né selezione arbitraria.
61. **Direzione della quantità in fascia principale.** Qualsiasi risultato
    quantitativo nella fascia `MAIN`, inclusi entrambi i confini, è sempre
    `MET + IN_LINE`; `LOWER` e `HIGHER` descrivono soltanto valori esterni ai
    confini applicabili e non sono derivati da differenze interne alla fascia.
62. **Policy degli obiettivi strutturati.** Ogni obiettivo `STRUCTURED` deve
    prescrivere una coppia completa e non null `policy_id`/`policy_version`,
    oltre al codice stabile; il risultato deve riportare la stessa coppia.
63. **Supporto separato dalla prescrizione.** `requiredness` dichiara se il
    componente è obbligatorio o opzionale, mentre `support_status` dichiara se
    la versione corrente dell'evaluatore può valutarlo. `STRENGTH` è
    esplicitamente `UNSUPPORTED` nella v1, senza diventare `NOT_MET` o
    `INSUFFICIENT_DATA`.
64. **Copertura della valutazione.** La copertura degli obbligatori è
    `FULLY_SUPPORTED`, `PARTIALLY_UNSUPPORTED` o `UNSUPPORTED` ed è distinta
    dall'aderenza. Soltanto `FULLY_SUPPORTED` consente overall e dose aggregata
    definitivi e l'applicazione della precedenza di aderenza.
65. **Requiredness dei componenti soltanto osservati.** `requiredness` proviene
    esclusivamente dalla prescrizione: è quindi `null` per `OBSERVED_ONLY` e
    non può essere inventata a partire dall'attività osservata.
66. **Omissione opzionale.** Un componente pianificato `OPTIONAL`, supportato
    ma non osservato conserva un risultato tracciabile con
    `evaluation_applicability: NOT_APPLICABLE` e senza risultati dimensionali
    o dose; non rappresenta aderenza, insufficienza o esecuzione implicita.
67. **Dimensioni dei conflitti.** L'impatto di un conflitto usa soltanto
    `IDENTITY`, `QUANTITY`, `INTENSITY`, `STRUCTURE`, `DOSE` e `DECISION`,
    elencando tutte le dimensioni realmente interessate senza ricorrere a una
    generica fascia o usare `DECISION` come sostituto.

## 3. Prescrizione autorevole e audit

Lo snapshot autorevole dovrà essere creato quando la prescrizione verrà
effettivamente comunicata all'atleta. Una modifica successiva diventerà
autorevole soltanto dopo una nuova comunicazione e genererà un nuovo snapshot
immutabile.

```yaml
planned_workout:
  contract_version: maintain-plan/1.0.0-draft
  prescription_snapshot_id: string
  workout_id: string
  decision_id: string
  communicated_at: datetime
  scheduled_window:
    start: datetime
    end: datetime
    timezone: string
    derived_from_date_only: boolean
  composition: single | brick | multisport
  matching_policy:
    policy_id: maintain-plan-matching
    policy_version: 1.0.0-draft
  brick_policy:
    policy_id: maintain-plan-brick-consecutivity | null
    policy_version: 1.0.0-draft | null
  components:
    - component_id: string
      component_index: integer
      discipline: RUN | BIKE | SWIM | STRENGTH
      environment: INDOOR | OUTDOOR | null
      mode: ROAD | TRAIL | TRACK | TREADMILL | GRAVEL | MOUNTAIN_BIKE | INDOOR_TRAINER | POOL | OPEN_WATER | null
      requiredness: REQUIRED | OPTIONAL
      support_status: SUPPORTED | UNSUPPORTED
      capability_policy:
        policy_id: maintain-plan-evaluator-capability
        policy_version: 1.0.0-draft
      applicability: REQUIRED
      allowed_substitutions: []
      identity_policy:
        policy_id: maintain-plan-sport-taxonomy
        policy_version: 1.0.0-draft
      quantity:
        applicability: REQUIRED
        primary_metric: active_duration | distance | sets_repetitions | per_segment
        target: object
        unit: string
        secondary_metrics: []
        policy_id: maintain-plan-quantity
        policy_version: 1.0.0-draft
      intensity:
        applicability: REQUIRED
        primary_method: HR | POWER | PACE_SPEED | RPE
        target: object
        unit: string
        allowed_secondary_methods: []
        policy_id: maintain-plan-continuous-intensity | maintain-plan-interval-intensity
        policy_version: 1.0.0-draft
      structure:
        applicability: REQUIRED
        session_type: continuous | intervals | brick | other
        policy_id: maintain-plan-structure
        policy_version: 1.0.0-draft
        blocks:
          - block_id: string
            block_index: integer
            block_type: WARMUP | MAIN_SET | WORK | RECOVERY | COOLDOWN | OTHER
            requiredness: REQUIRED | OPTIONAL
            quantity_target: object | null
            intensity_target: object | null
            method: HR | POWER | PACE_SPEED | RPE | null
            unit: string | null
            target_range: object | null
            evaluation_window: WHOLE_BLOCK | FINAL_PART | AVERAGE | PEAK | TIME_IN_TARGET | null
            coverage_policy:
              policy_id: maintain-plan-continuous-intensity | maintain-plan-interval-intensity | null
              policy_version: 1.0.0-draft | null
            planned_repetitions: integer | null
            recovery:
              applicability: REQUIRED | NOT_APPLICABLE
              target: object | null
            order_constraints: []
            policy_id: maintain-plan-structure
            policy_version: 1.0.0-draft
      dose:
        applicability: REQUIRED
        policy_id: maintain-plan-dose-matrix
        policy_version: 1.0.0-draft
        quantity_dimension_ref: string
        intensity_dimension_ref: string
  transitions:
    - transition_id: string
      from_component_id: string
      to_component_id: string
      policy_id: maintain-plan-brick-consecutivity
      policy_version: 1.0.0-draft
      applicable_limit_minutes: number
  objective:
    evaluability: STRUCTURED | CONTEXT_ONLY | NOT_APPLICABLE
    code: string | null  # obbligatorio e stabile per STRUCTURED
    success_criteria: []
    context_text: string | null
    policy_id: string | null
    policy_version: string | null
  provenance:
    source: string
    captured_at: datetime
  audit:
    original_plan_snapshot_id: string | null
```

Se la prescrizione contiene soltanto la data, `scheduled_window.start` e
`scheduled_window.end` rappresentano quel giorno nel timezone dell'atleta e
`derived_from_date_only` è vero. Target, unità e criteri sono strutturati. Una
metrica primaria `per_segment` dichiara la propria metrica per segmento.

Per ogni coppia `policy_id`/`policy_version`, entrambi i valori devono essere
valorizzati oppure entrambi null. Sono obbligatori per una dimensione
`REQUIRED` e valutabile. La prescrizione seleziona esplicitamente la policy
continuous o intervals in base al `session_type` dichiarato.

Quando `objective.evaluability` è `STRUCTURED`, `objective.code`,
`objective.policy_id` e `objective.policy_version` dovranno essere tutti non
null. Il codice sarà stabile nello snapshot e utilizzabile come chiave nel
riferimento canonico; la coppia completa identificherà la policy versionata che
il futuro `objective_result` dovrà usare. L'obbligo della coppia vale
indipendentemente dalla `requiredness` e dall'applicabilità delle dimensioni:
valorizzare soltanto uno dei due campi non sarà valido. Un obiettivo
`STRUCTURED` senza codice o senza la coppia completa è input invalido e non
potrà produrre un risultato canonico. Per `CONTEXT_ONLY` e `NOT_APPLICABLE`,
`policy_id` e `policy_version` dovranno essere entrambi null e nessun risultato
valutativo sarà prodotto. Non sarà mai inferito un codice, una policy o un
risultato da `context_text` o da altro testo libero.

Per una seduta continua `structure.blocks` può contenere un solo `MAIN_SET`,
oltre a eventuali `WARMUP` e `COOLDOWN`. Per Brick e multisport i blocchi
restano nel proprio componente; le transizioni restano a livello sessione.

Nel sottoschema di ogni blocco pianificato, `recovery.applicability` e
`recovery.target` dovranno rispettare queste invarianti:

- `NOT_APPLICABLE` dichiarerà esplicitamente che il recupero non richiede un
  target d'intensità e imporrà `target: null`;
- `REQUIRED` imporrà un target valorizzato;
- `REQUIRED` con target mancante produrrà `INSUFFICIENT_DATA`, non
  `NOT_APPLICABLE`;
- l'applicability non dovrà mai essere inferita dall'assenza del target.

Lo snapshot immutabile conterrà esclusivamente prescrizione, componenti,
blocchi, transizioni pianificate, policy applicabili, audit e provenance. Non
conterrà aggregati né riferimenti a risultati prodotti dopo l'esecuzione.

La composition dichiarata nello snapshot è autorevole. Non viene inferita dal
numero o dall'ordine delle discipline né sostituita dalla classificazione del
dispositivo.

## 4. Principio generale di conferma

Policy draft: `ironcoach-confirmation-governance/1.0.0-draft`.

Quando un'ambiguità interpretativa potrà modificare una decisione, una
valutazione, un report o il learning, la futura implementazione non dovrà
scegliere autonomamente fra interpretazioni plausibili: dovrà chiedere conferma
all'atleta.

La richiesta dovrà:

- mostrare il dato dubbio;
- presentare interpretazioni comprensibili;
- permettere la risposta «non lo so»;
- conservare domanda, risposta, actor, timestamp e dati coinvolti.

```yaml
confirmation:
  confirmation_id: string
  status: NOT_REQUIRED | REQUIRED | ANSWERED | UNKNOWN_ANSWER | SUPERSEDED
  question: string
  ambiguous_data: []
  interpretations: []
  answer: object | null
  actor: string | null
  asked_at: datetime
  answered_at: datetime | null
  evidence: object
  provenance: object
  policy_id: ironcoach-confirmation-governance
  policy_version: 1.0.0-draft
```

Fino alla risposta, la futura implementazione dovrà garantire che:

- la parte interessata resterà da chiarire;
- non dovrà essere prodotto un esito definitivo basato sul dato ambiguo;
- il caso non dovrà entrare nel learning né modificare la confidence;
- per la decisione successiva dovranno essere usati soltanto dati non
  controversi.
- l'eventuale `prescription_mapping` resterà `null` finché l'associazione non
  sarà confermata in modo esplicito e univoco.

La risposta dovrà chiarire l'interpretazione e dovrà aggiungere una relazione
auditabile, senza riscrivere o cancellare i dati originali, gli ID o la
provenance. «Non lo so» renderà non valutabile la parte interessata. Una
correzione successiva dovrà restare auditabile.

L'assenza completa di segnalazioni soggettive non è di per sé ambigua:
significa «nessun problema noto», non certificazione medica.

## 5. Attività eseguita e matching

### 5.1 Schema canonico

```yaml
actual_session:
  contract_version: maintain-plan/1.0.0-draft
  session_id: string
  source_activities:
    - source: string
      original_activity_id: string
      returned_prescription_id: string | null
      raw_ids: object
      provenance: object
  start: datetime
  end: datetime | null
  timezone: string
  composition: single | brick | multisport | null
  components:
    - component_id: string
      component_index: integer
      discipline: RUN | BIKE | SWIM | STRENGTH | null
      environment: INDOOR | OUTDOOR | null
      mode: ROAD | TRAIL | TRACK | TREADMILL | GRAVEL | MOUNTAIN_BIKE | INDOOR_TRAINER | POOL | OPEN_WATER | null
      source_activity_refs: []
      source_segment_refs: []
      start: datetime | null
      end: datetime | null
      quantity:
        primary_metric: string | null
        observation: object | null
        unit: string | null
        secondary_metrics: []
      intensity:
        methods: []
        observations: object | null
        temporal_coverage: object | null
      structure:
        blocks:
          - block_id: string
            block_index: integer
            block_type: WARMUP | MAIN_SET | WORK | RECOVERY | COOLDOWN | OTHER
            quantity_observation: object | null
            intensity_observation: object | null
            provenance: object
            missing_fields: []
            warnings: []
            repetitions:
              - repetition_id: string
                repetition_index: integer
                block_ref: string
                quantity_observation: object | null
                intensity_observation: object | null
                valid_coverage: object | null
                time_in_target: object | null
                source_segment_refs: []
                provenance: object
                missing_fields: []
                warnings: []
      provenance: object
      missing_fields: []
      warnings: []
      data_quality: object
  transitions:
    - transition_id: string
      from_component_ref: string
      to_component_ref: string
      start: datetime | null
      end: datetime | null
      duration_minutes: number | null
      provenance: object
      missing_fields: []
      warnings: []
  completion:
    status: string | null
    interruption_reason: string | null
    safety_interruption: boolean | null
  athlete_feedback:
    feedback_id: string
    schema_version: maintain-plan-subjective-feedback/1.0.0-draft
    rpe: number | null
    pain: number | null
    unusual_fatigue: NONE | MILD | MODERATE | HIGH | null
    interruption: boolean | null
    reason: HEALTH | WORK_TIME | WEATHER | EQUIPMENT | OTHER | null
    note: string | null
    captured_at: datetime | null
    provenance: object
    missing_fields: []
    warnings: []
  weather_context:
    - component_ref: string
      applicability: OPTIONAL | NOT_APPLICABLE
      rounded_point:
        latitude: number | null
        longitude: number | null
        grid_degrees: 0.05
      relevant_time: datetime | null
      weather:
        temperature: number | null
        apparent_temperature: number | null
        humidity: number | null
        precipitation: number | null
        wind_speed: number | null
        wind_direction: number | null
        wind_gusts: number | null
        weather_code: string | null
        description: string | null
      provider: Open-Meteo | null
      retrieved_at: datetime | null
      schema_version: maintain-plan-weather-context/1.0.0-draft
      policy_id: maintain-plan-weather-privacy
      policy_version: 1.0.0-draft
      provenance: object
      missing_fields: []
      warnings: []
      retention_policy:
        policy_id: maintain-plan-weather-privacy
        policy_version: 1.0.0-draft
  source_conflicts:
    - conflict_id: string
      schema_version: maintain-plan-source-conflict/1.0.0-draft
      field_path: string
      values:
        - value: any
          source: string
          provenance: object
          source_version: string | null
          observed_at: datetime | null
      provenance: object
      captured_at: datetime
      missing_fields: []
      warnings: []
      policy_id: maintain-plan-source-conflicts
      policy_version: 1.0.0-draft
  data_quality:
    source_checked_at: datetime | null
    synchronization_succeeded: boolean | null
    completeness: string
    missing_fields: []
    warnings: []
  provenance:
    normalized_at: datetime
```

Missingness resta esplicita e non diventa zero. Ogni attività sorgente conserva
tutti gli ID originali e la provenienza. Un `returned_prescription_id`
acquisito dalla sorgente sarà soltanto evidence grezza per il matching: non
costituirà un riferimento da `actual_session` a una prescrizione selezionata.

`actual_session` sarà un input canonico immutabile, valido e costruibile anche
senza una prescrizione selezionata e senza alcun mapping. Conterrà esclusivamente attività
sorgente, componenti, blocchi e ripetizioni osservati, transizioni osservate,
feedback, meteo, conflitti, identificatori, provenance, missingness, warning e
qualità dei dati. Componenti, blocchi, ripetizioni e transizioni conterranno
soltanto identità e dati osservati: nessun elemento di `actual_session` punterà
a una prescrizione o a un risultato futuro. Transizioni, componenti sportivi,
recovery blocks e source segments resteranno entità distinte.

Correzioni e cancellazioni del feedback e risoluzioni dei conflitti non
modificheranno `actual_session`: saranno conservate in registri append-only
separati e versionati.

```yaml
feedback_event_log:
  schema_version: maintain-plan-feedback-events/1.0.0-draft
  feedback_ref:
    session_id: string
    feedback_id: string
  events:
    - event_id: string
      event_type: CAPTURED | CORRECTED | DELETED
      occurred_at: datetime
      actor: string
      provenance: object
      schema_version: maintain-plan-feedback-event/1.0.0-draft
      previous_event_ref: string | null
      superseded_event_ref: string | null
      corrected_payload: object | null
      deletion_reason_or_ref: string | null
      audit_metadata: object

source_conflict_resolution_log:
  schema_version: maintain-plan-source-conflict-events/1.0.0-draft
  conflict_ref:
    session_id: string
    conflict_id: string
  events:
    - event_id: string
      event_type: RESOLVED | UNKNOWN_ANSWER | RESOLUTION_WITHDRAWN
      selected_value: any | null
      selected_source: string | null
      unknown_answer: boolean
      actor: string
      occurred_at: datetime
      provenance: object
      schema_version: maintain-plan-source-conflict-event/1.0.0-draft
      previous_event_ref: string | null
      audit_metadata: object
```

Una proiezione deterministica e versionata dovrà ricostruire, esclusivamente
dalla sequenza degli eventi, il feedback e la risoluzione dei conflitti
applicabili al momento della valutazione. Gli eventi non modificheranno la
cattura o il conflitto originale. Il payload soggetto a cancellazione seguirà
la policy privacy; dopo la cancellazione l'audit potrà conservare soltanto i
metadati non sensibili necessari e il feedback non potrà essere usato in
valutazioni future o nel learning. Correzioni e cancellazioni non
reinterpreteranno retroattivamente risultati già pubblicati senza una nuova
`execution_evaluation` esplicitamente versionata.

Per i conflitti, «non lo so» manterrà la dimensione interessata
`INSUFFICIENT_DATA`; una risoluzione ambigua o ritirata non potrà entrare nel
learning. Non saranno ammesse modifiche silenziose o sovrascritture dei valori
originali.

Il matching dovrà produrre un risultato separato dall'attività osservata:

```yaml
matching_result:
  matching_result_id: string
  status: MATCHED | CONFIRMATION_REQUIRED | NOT_EVALUABLE
  candidate_set: []
  candidate_evidence: object
  prescription_mapping: prescription_mapping | null
  confirmation_ref: string | null
  policy_id: maintain-plan-matching
  policy_version: 1.0.0-draft
  provenance: object
  missing_fields: []
  warnings: []

prescription_mapping:
  mapping_id: string
  prescription_snapshot_ref: string
  actual_session_ref: string
  resolution_method: AUTOMATIC | ATHLETE_CONFIRMATION
  component_mappings:
    - planned_component_ref:
        prescription_snapshot_id: string
        component_id: string
      observed_component_ref:
        session_id: string
        component_id: string
      requiredness: REQUIRED | OPTIONAL
      support_status: SUPPORTED | UNSUPPORTED
      capability_policy:
        policy_id: maintain-plan-evaluator-capability
        policy_version: 1.0.0-draft
      evidence: object
      provenance: object
      missing_fields: []
      warnings: []
  block_mappings:
    - planned_block_ref:
        prescription_snapshot_id: string
        component_id: string
        block_id: string
      observed_block_ref:
        session_id: string
        component_id: string
        block_id: string
  repetition_mappings:
    - planned_repetition_ref:
        prescription_snapshot_id: string
        component_id: string
        block_id: string
        repetition_index: integer
      observed_repetition_ref:
        session_id: string
        component_id: string
        block_id: string
        repetition_id: string
  transition_mappings:
    - planned_transition_ref:
        prescription_snapshot_id: string
        transition_id: string
      observed_transition_ref:
        session_id: string
        transition_id: string
  confirmation_audit:
    confirmation_ref: string | null
    actor: string | null
    confirmed_at: datetime | null
  created_at: datetime
  provenance: object
  missing_fields: []
  warnings: []
```

Il conflitto grezzo conserverà soltanto identificatore, campo, valori e
sorgenti discordanti, provenance, versioni, timestamp, missing fields e
warning. Non conterrà `affects_decision` né classificazioni che richiedano la
prescrizione selezionata. La valutazione dell'impatto sarà un oggetto separato:

```yaml
source_conflict_impact_evaluation:
  conflict_impact_evaluation_id: string
  evaluation_version: string
  source_conflict_id: string
  prescription_mapping_ref: string | null
  status: EVALUATED | UNRESOLVED
  affected_dimensions: [IDENTITY | QUANTITY | INTENSITY | STRUCTURE | DOSE | DECISION]
  policy_id: maintain-plan-source-conflict-impact
  policy_version: 1.0.0-draft
  provenance: object
  evaluated_at: datetime
  missing_fields: []
  warnings: []
```

Questa evaluation potrà essere `EVALUATED` soltanto dopo che
`prescription_mapping_ref` risolve un mapping univoco e confermato quando
necessario. Sarà `UNRESOLVED` se il mapping manca, è ambiguo o non confermato;
in tal caso `affected_dimensions` conterrà solo dimensioni accertabili senza
inventare un booleano. Resterà separata sia dagli input immutabili sia dal
registro append-only di risoluzione. Le dimensioni sono vincolanti: una
divergenza su disciplina, ambiente o modalità include `IDENTITY`; una che
modifica una fascia quantitativa include `QUANTITY`; una che modifica una
fascia d'intensità include `INTENSITY`; una che modifica ordine, transizioni o
struttura include `STRUCTURE`. Se cambia la dose risultante si aggiunge
`DOSE`; se cambia una decisione finale si aggiunge `DECISION`. Lo stesso
conflitto può elencare più dimensioni e `DECISION` non sostituisce mai la
dimensione direttamente interessata.

Ogni dimensione obbligatoria direttamente interessata da un conflitto
rilevante `UNRESOLVED` produrrà `INSUFFICIENT_DATA`; il dettaglio del conflitto
resterà nel report e il risultato non contribuirà al learning finché il
conflitto rilevante rimane irrisolto. Una nuova classificazione richiederà una nuova
`evaluation_version`: le evaluation già pubblicate non saranno reinterpretate
retroattivamente.

`prescription_mapping` sarà un risultato immutabile del matching e sarà
presente soltanto dopo un'associazione automatica unica e valida oppure dopo
una conferma esplicita dell'atleta. Con `CONFIRMATION_REQUIRED`,
`NOT_EVALUABLE`, nessuna candidata o candidate ambigue, il mapping dovrà essere
`null`, mentre `actual_session` resterà valido e immutabile. Ogni associazione
nel mapping dovrà essere completamente qualificata e risolversi univocamente;
non saranno ammessi abbinamenti impliciti.

Quando sarà prodotta una valutazione, il mapping dovrà rendere obbligatorio e
univoco il riferimento pianificato pertinente. In particolare,
`planned_block_ref` resterà immutabile e completamente qualificato nel mapping
e nei risultati valutativi e risolverà l'intero contratto pianificato del
blocco: requiredness, target, method, unit, range, evaluation window, coverage
requirement, planned repetitions, recovery target e order constraints. Non
sarà invece richiesto per costruire il blocco osservato prima del matching.

### 5.2 Risultati canonici e ownership della valutazione

`dose_evaluation` sarà un unico tipo canonico riutilizzabile e sarà incorporato
esclusivamente dentro `execution_evaluation`. Non costituirà un risultato
persistito autonomamente né una seconda fonte autorevole.

```yaml
dose_evaluation:
  dose_result_id: string
  status: EVALUATED | INSUFFICIENT_DATA
  direction: LOWER | IN_LINE | HIGHER | MIXED | UNDETERMINED | null
  severity_band: MAIN | SECONDARY | OUT_OF_BAND | null
  quantity_result_ref: string | null
  intensity_result_ref: string | null
  policy_id: maintain-plan-dose-matrix | null
  policy_version: 1.0.0-draft | null
  provenance: object
  computed_at: datetime | null
  missing_fields: []
  warnings: []
```

La coppia `policy_id`/`policy_version` del tipo dovrà essere interamente
valorizzata oppure interamente null. Per ogni dose, di componente o aggregata,
`EVALUATED` imporrà entrambi i campi non null e la coppia identificherà la
matrice versionata effettivamente applicata; `INSUFFICIENT_DATA` imporrà
entrambi null. Valorizzarne uno solo non sarà valido. Una dose `EVALUATED` con
metadati assenti o parziali sarà invalida e non potrà essere pubblicata,
riportata o usata per il learning. `status` rappresenterà esclusivamente la
valutabilità: `EVALUATED` richiederà una `direction` non null, mentre
`INSUFFICIENT_DATA` imporrà `direction: null`. `LOWER`, `IN_LINE`, `HIGHER`,
`MIXED` e `UNDETERMINED` saranno esclusivamente valori di `direction`, mai di
`status`. `UNDETERMINED` sarà una direzione valutata: i dati saranno
sufficienti a riconoscere uno scostamento, ma non a determinarne una direzione
univoca. `severity_band` resterà separata da status e direction; anche
l'applicability resterà separata dalla valutabilità. Per le sessioni supportate
nella v1 la dose resterà `REQUIRED`. Riferimenti mancanti o non risolvibili
produrranno `status: INSUFFICIENT_DATA`, `direction: null` e
`severity_band: null`. Ogni dose `EVALUATED` richiederà invece una
`severity_band` non null, determinata con la regola della sezione 7.

Il seguente `component_evaluation` sarà usato esclusivamente come elemento di
`execution_evaluation.component_results`; non costituirà un oggetto autorevole
separato. Il campo `dose` incorporerà senza variazioni il tipo canonico
`dose_evaluation`.

```yaml
component_evaluation:
  component_result_id: string
  match_status: MATCHED | PLANNED_ONLY | OBSERVED_ONLY
  requiredness: REQUIRED | OPTIONAL | null
  evaluation_applicability: APPLICABLE | NOT_APPLICABLE
  support_status: SUPPORTED | UNSUPPORTED
  capability_policy:
    policy_id: maintain-plan-evaluator-capability
    policy_version: 1.0.0-draft
  planned_component_ref:  # oggetto nullable
    prescription_snapshot_id: string
    component_id: string
  observed_component_ref:  # oggetto nullable
    session_id: string
    component_id: string
  identity:  # object | null; null se UNSUPPORTED o evaluation_applicability: NOT_APPLICABLE
    status: MET | PARTIALLY_MET | NOT_MET | INSUFFICIENT_DATA
    policy_id: maintain-plan-sport-taxonomy
    policy_version: 1.0.0-draft
    evidence: object
  quantity:  # object | null; null se UNSUPPORTED o evaluation_applicability: NOT_APPLICABLE
    result_id: string
    status: MET | PARTIALLY_MET | NOT_MET | INSUFFICIENT_DATA
    direction: LOWER | IN_LINE | HIGHER | null
    band: MAIN | SECONDARY | OUT_OF_BAND | null
    policy_id: maintain-plan-quantity
    policy_version: 1.0.0-draft
    evidence: object
  intensity:  # object | null; null se UNSUPPORTED o evaluation_applicability: NOT_APPLICABLE
    result_id: string
    status: MET | PARTIALLY_MET | NOT_MET | INSUFFICIENT_DATA
    direction: LOWER | IN_LINE | HIGHER | MIXED | UNDETERMINED | null
    band: MAIN | SECONDARY | OUT_OF_BAND | null
    policy_id: maintain-plan-continuous-intensity | maintain-plan-interval-intensity
    policy_version: 1.0.0-draft
    evidence: object
  structure:  # object | null; null se UNSUPPORTED o evaluation_applicability: NOT_APPLICABLE
    result_id: string
    status: MET | PARTIALLY_MET | NOT_MET | INSUFFICIENT_DATA
    policy_id: maintain-plan-structure
    policy_version: 1.0.0-draft
    block_result_refs: []
    repetition_result_refs: []
    transition_result_refs: []
    evidence: object
  dose: dose_evaluation | null  # null se UNSUPPORTED o evaluation_applicability: NOT_APPLICABLE
  provenance: object
  missing_fields: []
  warnings: []
```

I riferimenti del componente sono nullable con una matrice di validità
vincolante:

| `match_status` | `planned_component_ref` | `observed_component_ref` | `requiredness` |
|---|---|---|---|
| `MATCHED` | obbligatorio | obbligatorio | non null e coincidente con la prescrizione |
| `PLANNED_ONLY` | obbligatorio | `null` | non null e coincidente con la prescrizione |
| `OBSERVED_ONLY` | `null` | obbligatorio | obbligatoriamente `null` |

Entrambi i riferimenti null sono sempre invalidi. Ogni componente pianificato
`REQUIRED` dovrà avere un proprio `component_result_id` e comparire nei
`component_result_refs` di **tutti** gli aggregati applicabili, anche quando è
`PLANNED_ONLY`. In tale caso i risultati saranno esattamente: identity
`NOT_MET`, structure `NOT_MET`, quantity `INSUFFICIENT_DATA`, intensity
`INSUFFICIENT_DATA` e dose `INSUFFICIENT_DATA` con `direction: null` e
`severity_band: null`. L'assenza non sarà convertita in quantità zero né in
una falsa osservazione. Questo caso usa `evaluation_applicability: APPLICABLE`.

Un componente `OPTIONAL + SUPPORTED + PLANNED_ONLY` avrà invece
`evaluation_applicability: NOT_APPLICABLE`: manterrà `component_result_id` e
un record esplicito per la tracciabilità, ma `identity`, `quantity`,
`intensity`, `structure` e `dose`, inclusi tutti i relativi riferimenti di
risultato, saranno `null`. `NOT_APPLICABLE` appartiene esclusivamente al
wrapper di applicabilità della valutazione: non sarà aggiunto agli enum
canonici di aderenza né a `dose_evaluation.status`. L'omissione non diventerà
`MET`, `NOT_MET`, `PARTIALLY_MET` o `INSUFFICIENT_DATA`, né quantità zero,
falsa osservazione o esecuzione implicita. Il report la mostrerà come
“componente opzionale non eseguito”. Sarà esclusa dagli aggregati delle
dimensioni obbligatorie, dall'overall, dalla dose aggregata, dalla evaluation
coverage e dal learning; la sua omissione non renderà incompleta la copertura
dei componenti obbligatori. Le policy approvate continuano ad applicarsi senza
variazioni ai componenti opzionali effettivamente osservati.

`requiredness` e `support_status` sono ortogonali: il primo conserva la
prescrizione, il secondo la capacità della versione corrente dell'evaluatore.
Un componente `UNSUPPORTED` può quindi restare `REQUIRED` oppure `OPTIONAL`.
Può essere acquisito, conservato, associato dal matching e mostrato nel report;
conserva i riferimenti pianificati e osservati applicabili, evidence,
provenance, `missing_fields` e warning. `capability_policy` deve contenere una
coppia completa policy/versione che determina lo stato `UNSUPPORTED`.

La regola unica per i risultati non supportati è: `identity`, `quantity`,
`intensity`, `structure` e `dose` sono tutti `null`; non si producono quindi
risultati definitivi né relativi riferimenti valutativi. Il componente non sarà
trasformato in una falsa osservazione, quantità zero, `NOT_MET` o
`INSUFFICIENT_DATA`: questi ultimi significano rispettivamente deviazione
accertata e dati necessari mancanti, non incapacità della policy. `STRENGTH`
deve usare `support_status: UNSUPPORTED` nella v1 e non contribuirà al learning.

Un componente `OBSERVED_ONLY` avrà sempre `requiredness: null`: assegnargli
`REQUIRED` o `OPTIONAL` inventerebbe dati prescrittivi. Resterà evidence
esplicita e visibile nel report e conserverà identificatore, osservazioni,
provenance, `missing_fields` e warning, senza target pianificati inventati.
Sarà escluso dai calcoli di completezza dei componenti pianificati,
requiredness, evaluation coverage e aggregazione delle dimensioni
obbligatorie. Potrà influire su identity e composition esclusivamente secondo
le policy già approvate, ma da solo non modificherà l'overall o la dose dei
componenti pianificati obbligatori e non riceverà valutazioni target-based
fabbricate. Entrambi i riferimenti null restano invalidi in ogni caso.

```yaml
execution_evaluation:
  evaluation_id: string
  prescription_mapping_ref: string
  prescription_snapshot_ref: string
  actual_session_ref: string
  feedback_projection_ref:
    projection_id: string | null
    projection_version: string | null
  source_conflict_projection_refs:
    - projection_id: string
      projection_version: string
  source_conflict_impact_evaluation_refs:
    - conflict_impact_evaluation_id: string
      evaluation_version: string
  component_results:
    - component_evaluation: object
  evaluation_coverage:
    status: FULLY_SUPPORTED | PARTIALLY_UNSUPPORTED | UNSUPPORTED
    required_supported_component_refs: []
    required_unsupported_component_refs: []
    optional_unsupported_component_refs: []
    policy_id: maintain-plan-evaluator-capability
    policy_version: 1.0.0-draft
  block_results:
    - result_id: string
      observed_block_ref:
        session_id: string
        component_id: string
        block_id: string
      planned_block_ref:
        prescription_snapshot_id: string
        component_id: string
        block_id: string
      status: MET | PARTIALLY_MET | NOT_MET | INSUFFICIENT_DATA
      policy_id: maintain-plan-structure
      policy_version: 1.0.0-draft
      evidence: object
      provenance: object
  repetition_results:
    - result_id: string
      observed_repetition_ref:
        session_id: string
        component_id: string
        block_id: string
        repetition_id: string
      observed_block_ref:
        session_id: string
        component_id: string
        block_id: string
      planned_context:
        prescription_snapshot_id: string
        component_id: string
        block_id: string
        repetition_index: integer | null
      status: MET | PARTIALLY_MET | NOT_MET | INSUFFICIENT_DATA
      policy_id: maintain-plan-continuous-intensity | maintain-plan-interval-intensity
      policy_version: 1.0.0-draft
      evidence: object
      provenance: object
  transition_results:
    - result_id: string
      observed_transition_ref:
        session_id: string
        transition_id: string
        from_component_ref: string
        to_component_ref: string
      planned_transition_ref:  # l'intero oggetto è null quando non applicabile
        prescription_snapshot_id: string
        transition_id: string
        from_component_id: string
        to_component_id: string
      status: MET | PARTIALLY_MET | NOT_MET | INSUFFICIENT_DATA
      policy_id: maintain-plan-brick-consecutivity | null
      policy_version: 1.0.0-draft | null
      evidence: object
      provenance: object
  identity_aggregate:
    result_id: string
    status: MET | PARTIALLY_MET | NOT_MET | INSUFFICIENT_DATA
    component_result_refs: []
    policy_id: maintain-plan-component-aggregation
    policy_version: 1.0.0-draft
  quantity_aggregate:
    result_id: string
    status: MET | PARTIALLY_MET | NOT_MET | INSUFFICIENT_DATA
    component_result_refs: []
    policy_id: maintain-plan-component-aggregation
    policy_version: 1.0.0-draft
  intensity_aggregate:
    result_id: string
    status: MET | PARTIALLY_MET | NOT_MET | INSUFFICIENT_DATA
    direction: LOWER | IN_LINE | HIGHER | MIXED | UNDETERMINED | null
    component_result_refs: []
    policy_id: maintain-plan-component-aggregation
    policy_version: 1.0.0-draft
  structure_aggregate:
    result_id: string
    status: MET | PARTIALLY_MET | NOT_MET | INSUFFICIENT_DATA
    component_result_refs: []
    block_result_refs: []
    repetition_result_refs: []
    transition_result_refs: []
    policy_id: maintain-plan-component-aggregation
    policy_version: 1.0.0-draft
  dose_aggregate:  # object | null; null se coverage non FULLY_SUPPORTED
    evaluation: dose_evaluation
    component_dose_result_refs: []
  objective_result:  # null salvo objective.evaluability: STRUCTURED
    objective_result_id: string
    status: MET | PARTIALLY_MET | NOT_MET | INSUFFICIENT_DATA
    planned_objective_ref:
      prescription_snapshot_id: string
      objective_code: string
    applied_criteria: []
    planned_evidence_refs: []
    observed_evidence_refs: []
    policy_id: string
    policy_version: string
    provenance: object
    computed_at: datetime
    missing_fields: []
    warnings: []
  overall:  # object | null; null se coverage non FULLY_SUPPORTED
    status: IN_LINE | PARTIALLY_IN_LINE | DIFFERENT | INSUFFICIENT_DATA
  policy_id: maintain-plan-execution-aggregation
  policy_version: 1.0.0-draft
  provenance: object
```

La dose di ogni componente dovrà valorizzare i riferimenti ai risultati
quantity e intensity dello stesso componente. La dose aggregata dovrà
valorizzare i riferimenti agli aggregati quantity e intensity di sessione e
conservare `component_dose_result_refs`. In entrambi i contesti il tipo
incorporato avrà esattamente i campi di `dose_evaluation`, senza forme
alternative o incomplete.

Ogni istanza incorporata di `dose_evaluation`, sia di componente sia
aggregata, dovrà avere un proprio `dose_result_id`, stabile e univoco almeno
nell'intero `execution_evaluation`. `component_dose_result_refs` dovrà
riferire esclusivamente i `dose_result_id` delle dosi dei componenti, mai i
`component_result_id`, e ogni riferimento dovrà risolversi esattamente a una
dose canonica. La dose aggregata non dovrà selezionare implicitamente una
proprietà interna di un risultato di componente. Un riferimento mancante,
duplicato o non risolvibile renderà la dose aggregata
`status: INSUFFICIENT_DATA` con `direction: null` e `severity_band: null`.

Quando `objective.evaluability` è `STRUCTURED`, `objective_result` sarà un
risultato canonico persistibile e verrà prodotto esclusivamente applicando i
criteri osservabili prescritti e la policy versionata riferita dalla
prescrizione. `planned_objective_ref.objective_code` dovrà coincidere
esattamente con il `objective.code` non null e stabile dello snapshot. Un
obiettivo `STRUCTURED` senza codice, con codice non coincidente o senza la
coppia policy/versione completa sarà input invalido e non produrrà
`objective_result`. `objective_result.policy_id` e `policy_version` dovranno
coincidere esattamente con quelli dello snapshot: una coppia parziale o diversa
sarà invalida. Criteri obbligatori mancanti o non
osservabili produrranno
`status: INSUFFICIENT_DATA` e saranno elencati in `missing_fields`; il testo
libero non sarà mai usato per inferire un esito. Per `CONTEXT_ONLY` (e
`NOT_APPLICABLE`) `objective_result` sarà `null`: il contesto resterà visibile
nel report ma non costituirà un risultato valutativo. Nella v1 questo risultato
non è una quinta dimensione obbligatoria e non modifica overall, dose o
learning; qualsiasi influenza futura richiederà una nuova decisione approvata.

`evaluation_coverage.status` è calcolato esclusivamente sui componenti
`REQUIRED`: è `FULLY_SUPPORTED` quando tutti sono `SUPPORTED`,
`PARTIALLY_UNSUPPORTED` quando sono presenti obbligatori sia `SUPPORTED` sia
`UNSUPPORTED`, e `UNSUPPORTED` quando nessun obbligatorio è `SUPPORTED`. Un
componente opzionale `UNSUPPORTED` resta nei risultati e nel report ma, da
solo, non impedisce l'overall degli obbligatori supportati. I componenti
`OBSERVED_ONLY`, la cui `requiredness` è null, e gli
`OPTIONAL + SUPPORTED + PLANNED_ONLY` non partecipano al calcolo; l'omissione
di questi ultimi non rende incompleta la copertura degli obbligatori.

Quando la copertura non è `FULLY_SUPPORTED`, i risultati dei componenti
supportati restano pubblicati nel dettaglio, ma `overall` e `dose_aggregate`
sono entrambi `null` secondo lo schema (non oggetti `INSUFFICIENT_DATA` e non
risultati falliti). La sessione completa non riceve quindi un overall o una
dose definitiva e viene esclusa dal learning. Tutti i componenti non supportati
e la relativa `capability_policy` versionata devono essere elencati nel report.

Gli identificatori osservati avranno questi scope canonici: `block_id` sarà
univoco nel componente osservato, `repetition_id` sarà univoco nel blocco
osservato e `transition_id` sarà univoco nell'intera `actual_session`. I
riferimenti osservati dei risultati saranno completamente qualificati con
`session_id` e con lo scope necessario: componente e blocco per un
blocco; componente, blocco e ripetizione per una ripetizione; transizione e,
quando presenti nel relativo contratto, componenti `from` e `to` per una
transizione. I riferimenti pianificati dei risultati saranno analogamente
qualificati con `prescription_snapshot_id` e gli identificatori canonici
necessari. Ogni riferimento dovrà risolversi esattamente a un elemento; un
riferimento mancante, duplicato, incoerente o non risolvibile produrrà
`INSUFFICIENT_DATA` per il risultato interessato. Non saranno ammessi scope
impliciti o selezioni arbitrarie.

`execution_evaluation` sarà l'unico oggetto autorevole per risultati di blocchi,
ripetizioni e transizioni, risultati per componente, aggregati identity,
quantity, intensity e structure, dose per componente e aggregata e risultato
complessivo dell'esecuzione. Il collegamento sarà realmente unidirezionale:
`execution_evaluation` identificherà lo snapshot pianificato e
l'`actual_session` valutati e riferirà gli identificatori osservati e pianificati
necessari; gli oggetti immutabili di input non conterranno riferimenti ai
risultati futuri.

`execution_evaluation` potrà essere prodotta soltanto quando
`prescription_mapping_ref` risolverà un mapping immutabile, univoco e già
risolto. Dovrà riferire coerentemente quel mapping, lo snapshot e la sessione
osservata. Se il mapping richiesto sarà assente, la valutazione non sarà
pubblicabile oppure produrrà `INSUFFICIENT_DATA`; non potrà contribuire al
learning prima dell'eventuale conferma necessaria.

La valutazione dovrà registrare i riferimenti e le versioni delle proiezioni di
feedback e conflitti effettivamente utilizzate. Un riferimento di proiezione
presente dovrà avere insieme `projection_id` e `projection_version`; entrambi
saranno null quando non esisterà una cattura applicabile. In questo modo una
correzione, cancellazione o risoluzione successiva non modificherà gli input né
la valutazione già pubblicata.

### 5.3 Identificativo diretto

Un ID della prescrizione inviato al dispositivo e restituito dall'attività
dovrà provare l'associazione quando sarà valido e univoco. Dovrà collegare la
seduta anche se
disciplina, durata, intensità o struttura differiscono: queste differenze sono
scostamenti di esecuzione, non errori di matching.

Un ID duplicato, incompleto, contraddittorio o privo di prescrizione
corrispondente dovrà richiedere confirmation. Un ID Garmin o Strava che
identificherà soltanto l'attività non dovrà equivalere automaticamente al
prescription/workout ID.

### 5.4 Matching deterministico senza direct ID

Policy draft: `maintain-plan-matching/1.0.0-draft`.

Questa sezione risolve esplicitamente il rilievo della vecchia PR #7:
**“Define deterministic matching without a direct identifier”.**

Senza direct ID, la futura implementazione dovrà applicare queste regole:

1. l'inizio dell'attività dovrà ricadere nella `scheduled_window`;
2. un'attività fuori finestra dovrà richiedere conferma e non dovrà essere
   scartata definitivamente;
3. `composition` dovrà coincidere;
4. numero, ordine e `discipline` dei componenti dovranno coincidere;
5. una sostituzione sarà compatibile automaticamente soltanto se autorizzata
   esplicitamente nella prescrizione;
6. `environment` e `mode` non saranno filtri eliminatori: se mancanti, non
   impediranno il match ma renderanno non valutabile la relativa parte;
7. un mismatch di composition, discipline o ordine dovrà richiedere conferma;
8. dopo la conferma, ogni scostamento resterà valutato separatamente.

L'associazione automatica sarà ammessa soltanto se resterà esattamente una
candidata compatibile. Zero candidate o più candidate richiederanno conferma.
Non dovranno essere usati spareggi impliciti basati su durata, distanza, nome,
carico o somiglianza. Candidate set, evidence, provenance e stato della
conferma dovranno essere conservati. Nessun learning sarà ammesso prima della
conferma.

Il `matching_result` dovrà mantenere `prescription_mapping: null` quando lo
stato sarà `CONFIRMATION_REQUIRED` o `NOT_EVALUABLE`, oppure quando non vi sarà
alcuna candidata o il candidate set resterà ambiguo. Soltanto un match
automatico unico e valido o una conferma esplicita potranno produrre il mapping
immutabile descritto nella sezione 5.1.

### 5.5 Zero candidate

Dopo la fine della finestra e almeno una sincronizzazione riuscita, il testo
obbligatorio dovrà essere:

> Non ho trovato un'attività associabile alla seduta prevista

La futura implementazione non dovrà presumere che la seduta non sia stata
svolta e dovrà chiedere se sia:

- non svolta;
- svolta ma non sincronizzata;
- da associare manualmente.

Se mancherà una risposta prima della prescrizione successiva, il caso dovrà
essere chiuso internamente come non valutabile, senza outcome definitivo e
senza learning. Una sincronizzazione tardiva potrà aggiornare lo storico dopo
conferma, ma non dovrà generare un nuovo report visibile sulla vecchia seduta
ormai superata.

### 5.6 Sessioni composte e consecutività

Policy draft: `maintain-plan-brick-consecutivity/1.0.0-draft`.

Una Brick:

- può combinare qualsiasi disciplina differente, per esempio `BIKE+RUN` o
  `SWIM+RUN`;
- ha almeno due componenti appartenenti ad almeno due discipline differenti;
- non è formata da due file consecutivi della stessa disciplina;
- ammette al massimo 15 minuti fra la fine di un componente e l'inizio del
  successivo;
- può sostituire il limite generale di 15 minuti con una regola esplicita
  della prescrizione.

L'ordine non determina se la sessione sia una Brick. Se differisce dalla
prescrizione, la sessione resta Brick e lo scostamento è valutato nella
struttura. Oltre 15 minuti la combinazione non è classificata automaticamente
come Brick. La conferma può collegare attività alla stessa prescrizione, ma non
certifica la consecutività e non rende rispettata la struttura.

Un singolo file multisport conserva componenti, ordine e tempi di transizione;
il gap è comunque valutato. File distinti richiedono ordine temporale, nessuna
sovrapposizione, nessuna attività estranea interposta e gap entro la policy;
altrimenti richiedono conferma.

Se la prescrizione dichiara `brick`, componenti compatibili e consecutivi sono
valutati come candidata Brick. Se dichiara `multisport`, questa classificazione
è mantenuta e sono valutati componenti, ordine e transizioni. La classificazione
multisport del dispositivo è evidence utile, ma non sostituisce la
prescrizione. Classificazione mancante o interpretabile in più modi richiede
conferma con provenance conservata.

Recovery e stability riguardano l'intera sessione Brick o multisport, che
produrrà un solo outcome e un solo contributo futuro al learning. Il report
dovrà esporre ciascun componente e la sua struttura interna. Il meteo sarà
separato per ciascun componente outdoor e sarà `NOT_APPLICABLE` per ciascun
componente indoor. Quantità, intensità e dose resteranno separate per
componente e non sommeranno unità incompatibili.

## 6. Applicability e valutazione dell'esecuzione

Per ogni sessione supportata da `MAINTAIN_PLAN` v1, sport/componenti,
quantità, intensità, struttura e dose saranno `REQUIRED`. Se mancherà il target
di una dimensione obbligatoria, la dimensione dovrà risultare
`INSUFFICIENT_DATA`: non dovrà essere usato `NOT_APPLICABLE`.

`NOT_APPLICABLE` significa che un dato è legittimamente irrilevante ed è
ammesso soltanto per meteo indoor, objective testuale/context-only,
performance nella prima stability, recovery intensity target esplicitamente
non richiesto e altri campi dichiarati facoltativi. `INSUFFICIENT_DATA`
significa che un dato necessario non è valutabile; `NOT_MET` richiede invece
evidenza sufficiente di uno scostamento.

`requiredness: REQUIRED | OPTIONAL` descrive esclusivamente la prescrizione;
`support_status: SUPPORTED | UNSUPPORTED` descrive esclusivamente la capacità
della versione corrente dell'evaluatore. `STRENGTH`, pur ammessa come input,
deve essere rappresentata esplicitamente come `UNSUPPORTED` nella v1. Non sarà
usato `NOT_MET` (deviazione accertata) né `INSUFFICIENT_DATA` (dati necessari
mancanti) per rappresentare una disciplina che la policy corrente non valuta.
I componenti non supportati non producono risultati identity, quantity,
intensity, structure o dose, ma restano acquisibili, associabili e visibili
come definito nella sezione 5.2; non entrano nel learning.

### 6.1 Quantità di lavoro

Quantità significa **quanto lavoro è stato svolto**. Policy draft:
`maintain-plan-quantity/1.0.0-draft`.

Metriche primarie approvate:

- RUN/BIKE continui: durata attiva; distanza contestuale salvo prescrizione
  distance-based;
- nuoto strutturato in piscina: distanza; durata complementare;
- nuoto continuo/open water: durata, salvo prescrizione distance-based;
- intervalli: metrica dichiarata per il main set, senza conversioni;
- forza: serie e ripetizioni, con durata contestuale; `STRENGTH` resta fuori
  dalla prima valutazione automatica;
- Brick/multisport: quantità per componente, senza sommare unità incompatibili.

La metrica primaria mancante non dovrà essere sostituita automaticamente.

#### Fasce quantitative approvate

| Ambito | Fascia principale | Secondaria inferiore | Secondaria superiore | Fuori fascia |
|---|---:|---:|---:|---:|
| RUN/BIKE continui duration-based | 90%–105% | 80%–<90% | >105%–115% | <80% o >115% |
| Nuoto strutturato distance-based | 95%–105% | 90%–<95% | >105%–110% | <90% o >110% |
| Nuoto continuo/open water duration-based | 90%–105% | 80%–<90% | >105%–115% | <80% o >115% |
| Main set intervalli | 95%–105% | 80%–<95% | >105%–115% | <80% o >115% |

La fascia principale corrisponde a `MET`, una fascia secondaria a
`PARTIALLY_MET` e fuori fascia a `NOT_MET`; direzione e fascia rimangono
comunque conservate separatamente.

Per ogni risultato quantitativo la regola è vincolante: qualunque valore nella
fascia `MAIN` produce sempre `status: MET` e `direction: IN_LINE`, anche se non
coincide esattamente con il target. Entrambi i confini inclusi della fascia
principale producono `IN_LINE`. Un valore sotto il confine inferiore
applicabile produce `LOWER`; un valore sopra il confine superiore applicabile
produce `HIGHER`. `LOWER` e `HIGHER` non devono mai essere derivati per valori
che restano in `MAIN`. `direction` descrive il verso, mentre `band` descrive la
gravità: i due campi rimangono semanticamente separati.

Esempi normativi, usando soltanto i confini della tabella: per una RUN continua
duration-based con target di 100 minuti, 95 minuti (95% del target) produce
`MET + IN_LINE + MAIN`; anche 90 e 105 minuti, confini inclusi, producono
`MET + IN_LINE + MAIN`; 89 minuti produce `PARTIALLY_MET + LOWER + SECONDARY`;
106 minuti produce `PARTIALLY_MET + HIGHER + SECONDARY`. La differenza di 5
minuti fra 95 e 100 non autorizza a derivare `LOWER` dentro `MAIN`.

Per gli intervalli dovrà essere usata la stessa unità della prescrizione.
Warmup e cooldown aggiuntivi non dovranno compensare un main set incompleto;
struttura e intensità dovranno restare separate. Limiti inferiori e superiori
saranno indipendenti, versionati e sostituibili dalla prescrizione.

### 6.2 Intensità delle sedute continue

Intensità significa **quanto è stato impegnativo**. Policy draft:
`maintain-plan-continuous-intensity/1.0.0-draft`.

- almeno 80% del blocco deve avere dati validi;
- sotto 80% l'intensità è `INSUFFICIENT_DATA`;
- fascia principale: almeno 80% del tempo valutabile nel target;
- fascia secondaria: dal 60% a meno dell'80%;
- fuori fascia: meno del 60%;
- il risultato conserva se lo scostamento è prevalentemente sopra o sotto;
- dovrà essere usato soltanto il metodo prescritto;
- HR, power, pace/speed e RPE non sono convertiti tra loro;
- RPE non sostituisce automaticamente un metodo strumentale.

La direzione usa esclusivamente il tempo valutabile. La fascia principale
produce `IN_LINE`. Nelle fasce secondaria e fuori fascia, tempo sopra maggiore
del tempo sotto produce `HIGHER`, tempo sotto maggiore del tempo sopra produce
`LOWER`, e tempi uguali producono `MIXED`. La sola media, senza distribuzione,
produce `UNDETERMINED`.

### 6.3 Intensità degli intervalli

Policy draft: `maintain-plan-interval-intensity/1.0.0-draft`.

Per ogni ripetizione:

- almeno 80% della evaluation window deve avere dati validi;
- almeno 70% della evaluation window deve essere nel target;
- la prescrizione dichiara metodo ed evaluation window: intero blocco, parte
  finale, media, picco o time-in-target;
- i recuperi dovranno essere valutati soltanto quando
  `recovery.applicability` sarà `REQUIRED` e il target esplicito sarà
  valorizzato; `NOT_APPLICABLE` non sarà interpretato come target mancante.

Per il main set:

- fascia principale: almeno 90% delle ripetizioni obbligatorie rispetta il
  target e produce `status: MET` con `direction: IN_LINE`;
- fascia secondaria: dal 70% a meno del 90%;
- fuori fascia: meno del 70%.

Per HR non dovrà essere presunto che l'intera ripetizione sia valutabile. Se
l'evaluation window mancherà o non sarà ricostruibile, dovrà essere chiesta
conferma quando possibile oppure la dimensione resterà non valutabile. Una
media complessiva corretta non dovrà compensare ripetizioni fuori target.

Quando almeno il 90% delle ripetizioni obbligatorie sarà rispettato, le
eventuali ripetizioni residue non conformi non potranno trasformare la fascia
principale in `HIGHER`, `LOWER` o `MIXED`: il risultato sarà sempre
`MET + IN_LINE`. Soltanto con risultato complessivo `PARTIALLY_MET` o `NOT_MET`
la direzione sarà derivata dalle ripetizioni non conformi valutabili:
prevalentemente sopra produrrà `HIGHER`, prevalentemente sotto produrrà
`LOWER`, entrambe le direzioni senza direzione unica produrranno `MIXED` e dati
insufficienti a determinarla produrranno `UNDETERMINED`. La dose dovrà usare
questa direzione; un'intensità `MET` nella fascia principale contribuirà come
`IN_LINE`. Di conseguenza, nove ripetizioni obbligatorie rispettate su dieci
produrranno `MET + IN_LINE`.

### 6.4 Struttura

Policy draft: `maintain-plan-structure/1.0.0-draft`.

**Rispettata (`MET`):**

- tutti i blocchi obbligatori sono riconoscibili;
- il main set è completato;
- i vincoli d'ordine dichiarati essenziali sono rispettati;
- i componenti Brick sono presenti e il gap è entro 15 minuti o entro la
  regola esplicita della prescrizione.

**Rispettata in parte (`PARTIALLY_MET`):**

- il main set è riconoscibile e sostanzialmente eseguito;
- manca o cambia un blocco obbligatorio secondario; oppure
- l'ordine differisce senza perdere il lavoro principale; oppure
- le discipline Brick sono invertite mantenendo gap valido.

**Non rispettata (`NOT_MET`):**

- main set assente o sostituito;
- componente essenziale mancante;
- vincolo d'ordine essenziale violato;
- Brick con gap superiore a 15 minuti o al limite esplicito applicabile.

**Non valutabile (`INSUFFICIENT_DATA`):**

- blocchi, segmenti, ordine o componenti non sono ricostruibili;
- non si deduce la struttura da durata, media o nome;
- dovrà essere chiesta conferma quando possibile.

Blocchi facoltativi omessi non penalizzano. Blocchi aggiuntivi possono incidere
su quantità o dose, ma non invalidano automaticamente la struttura. La
prescrizione dichiara requiredness e order constraints.

### 6.5 Aggregazione fra componenti

Policy draft: `maintain-plan-component-aggregation/1.0.0-draft`.

Le regole di aderenza seguenti si applicano soltanto con
`evaluation_coverage.status: FULLY_SUPPORTED` e includono i componenti
obbligatori. La copertura non è uno stato di aderenza e non entra in questa
precedenza.

Per identity, quantity, intensity e structure dei componenti obbligatori, la futura
implementazione dovrà applicare in ordine:

1. almeno un componente `INSUFFICIENT_DATA` → aggregato `INSUFFICIENT_DATA`;
2. altrimenti almeno un componente `NOT_MET` → aggregato `NOT_MET`;
3. altrimenti almeno un componente `PARTIALLY_MET` → aggregato `PARTIALLY_MET`;
4. altrimenti → aggregato `MET`.

Ogni aggregato conserverà i riferimenti ai risultati per componente. Non
duplicherà target o osservazioni. In particolare,
`execution_evaluation.identity_aggregate` dovrà applicare lo stesso ordine di
precedenza vincolante:

1. almeno un risultato identity di componente `INSUFFICIENT_DATA` produrrà
   `identity_aggregate: INSUFFICIENT_DATA`;
2. altrimenti almeno un risultato identity `NOT_MET` produrrà
   `identity_aggregate: NOT_MET`;
3. altrimenti almeno un risultato identity `PARTIALLY_MET` produrrà
   `identity_aggregate: PARTIALLY_MET`;
4. altrimenti tutti i risultati identity saranno `MET` e produrranno
   `identity_aggregate: MET`.

Nessun componente potrà compensarne un altro. I componenti
`REQUIRED + PLANNED_ONLY` useranno gli esiti normativi della sezione 5.2 e
saranno inclusi negli aggregati; gli `OPTIONAL + PLANNED_ONLY` saranno esclusi
dagli aggregati con risultati dimensionali null. Gli `OBSERVED_ONLY` resteranno
evidenza esplicita ma non definiranno la completezza dei componenti pianificati
obbligatori e saranno esclusi dalle aggregazioni obbligatorie. Non saranno ammesse
inferenze o aggregazioni alternative. L'overall dell'esecuzione dovrà consumare
l'`identity_aggregate` ottenuto esclusivamente con questa regola.

Lo `status` e la `direction` dell'intensità aggregata resteranno separati. Lo
`status` continuerà a usare la precedenza appena definita. Per
`intensity_aggregate.direction` la futura implementazione dovrà applicare, in
ordine:

1. almeno un componente obbligatorio con intensity `INSUFFICIENT_DATA` →
   `direction: null`;
2. altrimenti `intensity_aggregate.status: MET` → `direction: IN_LINE`;
3. altrimenti, considerando le direzioni dei componenti valutabili:
   - almeno una `UNDETERMINED` → `UNDETERMINED`;
   - altrimenti almeno una `MIXED` → `MIXED`;
   - altrimenti presenza sia di `HIGHER` sia di `LOWER` → `MIXED`;
   - altrimenti presenza di `HIGHER`, con le altre `HIGHER` o `IN_LINE` →
     `HIGHER`;
   - altrimenti presenza di `LOWER`, con le altre `LOWER` o `IN_LINE` →
     `LOWER`;
   - altrimenti tutte `IN_LINE` → `IN_LINE`.

Un componente valutabile dovrà avere direzione non null; `direction: null`
sarà ammesso soltanto per dati obbligatori insufficienti. Nessun componente
potrà compensarne un altro e nessuna direzione sarà scelta usando soltanto il
“componente peggiore”. Il report dovrà mostrare questo aggregato e la dose
dovrà consumarlo secondo le proprie regole, senza compensazioni.

Esempi normativi: `HIGHER + LOWER → MIXED`; `HIGHER + IN_LINE → HIGHER`;
`LOWER + IN_LINE → LOWER`; tutti i componenti `MET → IN_LINE`; almeno un
componente `UNDETERMINED → UNDETERMINED`; almeno un componente obbligatorio
`INSUFFICIENT_DATA → direction: null`.

### 6.6 Esempi normativi di copertura del supporto

- **`REQUIRED + PLANNED_ONLY`:** il componente supportato mantiene
  `evaluation_applicability: APPLICABLE`; identity e structure sono `NOT_MET`,
  quantity e intensity sono `INSUFFICIENT_DATA` e la dose è
  `INSUFFICIENT_DATA` con direction e severity null. Partecipa agli aggregati
  obbligatori.
- **`OPTIONAL + PLANNED_ONLY`:** se supportato, il componente mantiene un
  record e un `component_result_id`, usa
  `evaluation_applicability: NOT_APPLICABLE` e ha identity, quantity,
  intensity, structure, dose e relativi riferimenti null. È riportato come
  “componente opzionale non eseguito” ed è escluso da aggregati, overall, dose
  aggregata, evaluation coverage e learning.
- **`OPTIONAL + MATCHED`:** conserva `requiredness: OPTIONAL`, riferimenti
  planned e observed e viene valutato secondo le policy già approvate per i
  componenti opzionali effettivamente osservati, senza che la sua requiredness
  sia promossa a `REQUIRED`.
- **`OBSERVED_ONLY`:** conserva il riferimento osservato, evidence,
  provenance, missing fields e warning, ma usa `planned_component_ref: null` e
  `requiredness: null`; non riceve target inventati ed è escluso dai calcoli
  obbligatori, salvo l'influenza su identity/composition già approvata.

- **Sessione solo STRENGTH:** il componente resta `REQUIRED` e matched o
  planned-only secondo l'evidence, ma è `support_status: UNSUPPORTED` con
  capability policy versionata; `evaluation_coverage.status: UNSUPPORTED`,
  `overall: null`, `dose_aggregate: null`, nessun risultato dimensionale e
  nessun learning.
- **Brick RUN + STRENGTH obbligatoria:** RUN è `SUPPORTED`, STRENGTH resta
  `REQUIRED + UNSUPPORTED`; la copertura è `PARTIALLY_UNSUPPORTED`. I risultati
  RUN sono conservati e pubblicati, mentre overall e dose aggregata sono null;
  la sessione non è classificata fallita o insufficientemente osservata e non
  entra nel learning.
- **STRENGTH opzionale:** RUN obbligatoria supportata e STRENGTH
  `OPTIONAL + UNSUPPORTED` producono `FULLY_SUPPORTED`; STRENGTH resta visibile
  con capability policy e risultati valutativi null, ma non impedisce overall
  e dose degli obbligatori supportati.
- **Tutti gli obbligatori supportati:** una sessione RUN, BIKE o SWIM i cui
  componenti `REQUIRED` sono tutti `SUPPORTED` produce `FULLY_SUPPORTED`; si
  applicano normalmente aggregati, dose e precedenza overall. Eventuali dati
  mancanti sono poi trattati come `INSUFFICIENT_DATA`, non come supporto
  mancante.

### 6.7 Identità sportiva e obiettivo

Il confronto valuta composition e componenti in ordine. Per ciascun componente
confronta discipline, environment e mode. Una compatibilità automatica richiede
coincidenza o sostituzione esplicitamente autorizzata.

Environment o mode mancanti rendono non valutabile la parte corrispondente, ma
non impediscono il matching. Dopo direct ID o conferma, mismatch e sostituzioni
non autorizzate restano scostamenti di esecuzione.

L'obiettivo è valutabile solo con criteri strutturati, osservabili e associati
a policy versionata prescritta mediante coppia completa e non null, producendo
il risultato canonico della sezione 5.2 con la medesima coppia. L'obbligo vale
per ogni `STRUCTURED` indipendentemente da requiredness e applicabilità delle
dimensioni; una coppia parziale invalida l'input. Se
generico o testuale è `CONTEXT_ONLY`, resta visibile nel report, non produce un
risultato valutativo, ha coppia policy null e non entra nell'aggregazione. Lo
stesso vale per `NOT_APPLICABLE`. Criteri strutturati
obbligatori mancanti o non osservabili producono `INSUFFICIENT_DATA`; non si
inferisce mai un esito dal testo libero.

Ogni risultato di quantità conserva:

```yaml
direction: LOWER | IN_LINE | HIGHER
band: MAIN | SECONDARY | OUT_OF_BAND | null
```

Ogni risultato d'intensità conserva invece `LOWER`, `IN_LINE`, `HIGHER`,
`MIXED` o `UNDETERMINED`, oltre alla fascia applicabile.

## 7. Dose complessiva

Dose complessiva significa **combinazione di quantità e intensità**. Policy
approvata in versione draft: `maintain-plan-dose-matrix/1.0.0-draft`.

La forma canonica è definita una sola volta nella sezione 5.2 ed è
incorporata esclusivamente in `execution_evaluation`, sia per ogni componente
sia per la dose aggregata di sessione.

Matrice approvata:

- con quantità e intensità valutabili → `status: EVALUATED`;
- entrambe in linea → `direction: IN_LINE`;
- nessuna superiore e almeno una inferiore → `direction: LOWER`;
- nessuna inferiore e almeno una superiore → `direction: HIGHER`;
- una inferiore e l'altra superiore → `direction: MIXED`, senza compensazione;
- per ogni dose `EVALUATED`, `severity_band` usa sempre la fascia peggiore
  degli input nell'ordine `MAIN < SECONDARY < OUT_OF_BAND`;
- nella dose mista non si calcola un saldo;
- una direzione d'intensità `MIXED` produce `direction: MIXED`;
- una direzione d'intensità `UNDETERMINED` impedisce una direzione definitiva
  della dose e produce `direction: UNDETERMINED` con `status: EVALUATED`;
- se una dimensione obbligatoria non è valutabile →
  `status: INSUFFICIENT_DATA`, `direction: null` e `severity_band: null`;
- i riferimenti ai risultati quantity/intensity sono sempre conservati.

La dose deve consumare ogni quantità `MET/MAIN` come `direction: IN_LINE`,
senza ricalcolare il verso dalla differenza puntuale dal target. La direction
della quantità e la `severity_band` della dose restano campi semanticamente
distinti.

Per gli intervalli, un'intensità nella fascia principale con `status: MET`
dovrà avere `direction: IN_LINE` e contribuirà alla matrice della dose come
`IN_LINE`; le ripetizioni residue non conformi entro quella fascia non
potranno modificarne la direzione.

La fascia peggiore è vincolante anche con direzioni opposte e `MIXED`, quando
un input è `IN_LINE` e l'altro deviante, e con direction `UNDETERMINED` purché
gli input necessari siano valutabili. `MIXED` descrive soltanto la direzione e
non compensa la gravità. Se una fascia obbligatoria non può essere determinata,
la dose è `INSUFFICIENT_DATA` con direction e severity entrambe null. Esempi
normativi: `MAIN + SECONDARY → SECONDARY`; `OUT_OF_BAND + MAIN → OUT_OF_BAND`;
`LOWER/SECONDARY + HIGHER/OUT_OF_BAND → MIXED/OUT_OF_BAND`;
`IN_LINE/MAIN + HIGHER/SECONDARY → HIGHER/SECONDARY`. La medesima regola vale
senza variazioni per dosi di componente e dose aggregata; non introduce nuove
soglie.

Una durata più breve e intensità maggiore, o viceversa, non sono equivalenti.
Il meteo non corregge matematicamente la dose. La dose non è una quinta
dimensione dell'aggregazione dell'esecuzione.

Per Brick e multisport la futura implementazione dovrà calcolare una dose per
ogni componente supportato. La dose aggregata dell'intera sessione sarà
prodotta soltanto con copertura `FULLY_SUPPORTED` e aggregherà tutte le dosi
dei componenti obbligatori; altrimenti sarà `null`, pur conservando le dosi di
dettaglio supportate. La prima
condizione applicabile della seguente precedenza ordinata, totale e
deterministica prevarrà:

1. almeno una dose `INSUFFICIENT_DATA` → dose aggregata
   `INSUFFICIENT_DATA`, con `direction: null` e `severity_band: null`;
2. altrimenti almeno una direction `UNDETERMINED` → `UNDETERMINED`;
3. altrimenti almeno una direction `MIXED` → `MIXED`;
4. altrimenti presenza sia di `HIGHER` sia di `LOWER` → `MIXED`;
5. altrimenti almeno una `HIGHER` → `HIGHER`;
6. altrimenti almeno una `LOWER` → `LOWER`;
7. altrimenti, quando tutte sono `IN_LINE` → `IN_LINE`.

`IN_LINE` sarà neutro. Esempi normativi: `IN_LINE + LOWER → LOWER`;
`IN_LINE + HIGHER → HIGHER`; `LOWER + HIGHER → MIXED`;
`MIXED + IN_LINE → MIXED`; `UNDETERMINED + HIGHER → UNDETERMINED`; tutte
`IN_LINE → IN_LINE`; almeno un componente obbligatorio insufficiente → dose
aggregata `INSUFFICIENT_DATA` con direction e severity null.

Per ogni dose aggregata `EVALUATED`, `severity_band` sarà la fascia peggiore
fra tutti gli input valutati secondo `MAIN < SECONDARY < OUT_OF_BAND`, anche
con direction `MIXED` o `UNDETERMINED`. Non saranno ammessi compensazione,
saldo tra componenti o selezione arbitraria di un solo componente. Il report
dovrà mostrare sempre separatamente valutabilità (`status`),
esito direzionale (`direction`) e fascia (`severity_band`), oltre al dettaglio
per componente. Il futuro learning dovrà consumare gli stessi tre campi senza
confonderne le semantiche. Un dubbio capace di cambiare la decisione richiederà
confirmation.

## 8. Meteo contestuale e privacy

Policy draft: `maintain-plan-weather-privacy/1.0.0-draft`.

Per ogni componente outdoor la futura implementazione dovrà calcolare
localmente al massimo tre punti: inizio, metà e fine. I punti saranno
arrotondati a una griglia di 0,05° e deduplicati dopo l'arrotondamento. A
Open-Meteo saranno inviati soltanto coordinate
approssimate e orari necessari; mai atleta, prescription/activity ID,
indirizzo o intero tracciato GPS.

Senza GPS dovrà essere usata soltanto una località approssimativa fornita
dall'atleta; altrimenti il meteo resterà missing. Per indoor non dovrà essere
effettuata alcuna richiesta.

Campi iniziali:

- temperatura e temperatura percepita;
- umidità e precipitazioni;
- velocità, direzione e raffiche del vento;
- weather code e descrizione.

Saranno persistiti soltanto valori usati, punti approssimati, orari, provider,
`retrieved_at` e schema version. Non si conserva una copia aggiuntiva del
tracciato né il payload provider completo. La retention coincide con quella
dell'episodio.

Il meteo dovrà restare facoltativo, contestuale e non decisionale. Potrà
spiegare difficoltà nel report, ma non cambierà autonomamente uno stato.

L'integrazione prevista usa la
[Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
nel rispetto delle
[condizioni di utilizzo e pricing](https://open-meteo.com/en/pricing).

## 9. Stati interni, testi e conflitti

| Stato interno dimensionale | Testo utente obbligatorio |
|---|---|
| `MET` | In linea con quanto previsto |
| `PARTIALLY_MET` | Parzialmente in linea con quanto previsto |
| `NOT_MET` | Diverso da quanto previsto |
| `NOT_APPLICABLE` | Non previsto per questa seduta |
| `INSUFFICIENT_DATA` | Dati non sufficienti per valutarlo |

`NOT_MET` richiede evidenza sufficiente. Missingness, incompatibilità o
ambiguità producono `INSUFFICIENT_DATA` per la parte interessata. Ogni risultato
conserva policy/versione, planned/actual evidence, ragioni, qualità e
provenance.

### 9.1 Gerarchia e conflitti delle sorgenti

Policy draft: `maintain-plan-source-conflicts/1.0.0-draft`.

Ogni conflitto userà lo `schema_version`
`maintain-plan-source-conflict/1.0.0-draft`; tale versione dello schema resterà
distinta dalla coppia `policy_id`/`policy_version` che ne governerà la
risoluzione.

1. prescrizione IronCoach per ciò che era previsto;
2. Garmin o dispositivo originale per dati oggettivi registrati;
3. Strava per integrare campi assenti o come fallback;
4. atleta come fonte autorevole per dati soggettivi;
5. Open-Meteo per dati ambientali.

La gerarchia non autorizza sovrascritture silenziose. Moving time ed elapsed
time restano distinti; valori comparabili discordanti sono entrambi conservati
con provenance. Non si calcolano medie o fusioni automatiche.

Solo dopo un `prescription_mapping` risolto e univoco, la evaluation separata
dell'impatto stabilirà in modo versionato e auditabile quali fra `IDENTITY`,
`QUANTITY`, `INTENSITY`, `STRUCTURE`, `DOSE` e `DECISION` siano interessate.
Se l'impatto resta `UNRESOLVED` su una dimensione obbligatoria direttamente
interessata, quella dimensione sarà `INSUFFICIENT_DATA`, non
sarà pubblicata come valutata e non contribuirà al learning. Se l'impatto
valutato potrà cambiare il risultato, la futura implementazione dovrà chiedere
conferma; altrimenti userà la sorgente prioritaria conservando il conflitto.
La selezione e «non lo so» saranno registrati soltanto nel registro
append-only di risoluzione: la proiezione versionata selezionerà il dato per la
valutazione senza modificare gli originali, mentre «non lo so» renderà la
dimensione non valutabile. `execution_evaluation` conserverà la versione della
proiezione usata; una risoluzione ambigua o ritirata resterà esclusa dal
learning.

### 9.2 Feedback soggettivo

Policy draft: `maintain-plan-subjective-feedback/1.0.0-draft`.

Campi facoltativi:

- RPE 1–10;
- dolore 0–10;
- affaticamento insolito: `NONE`, `MILD`, `MODERATE`, `HIGH`;
- interruzione sì/no;
- motivo: `HEALTH`, `WORK_TIME`, `WEATHER`, `EQUIPMENT`, `OTHER`;
- nota libera.

Nessun questionario è obbligatorio. L'assenza completa significa «nessun
problema noto» e non certificazione medica. Non si convertono automaticamente
i segnali e non si formulano diagnosi o nuove soglie cliniche. Ambiguità o
contraddizioni rilevanti richiedono conferma; correzioni successive saranno
eventi auditabili nel registro append-only separato.

La cattura iniziale immutabile del feedback sarà collegata soltanto all'episodio
e all'atleta proprietario e conserverà timestamp, provenance e schema version.
Avrà la stessa retention dell'episodio. Correzione e cancellazione saranno
possibili su richiesta esclusivamente mediante eventi append-only; la
proiezione deterministica ricostruirà la versione applicabile. Un dato
cancellato sarà escluso da uso futuro e learning e il contenuto soggetto a
cancellazione seguirà la policy privacy, lasciando nell'audit soltanto i
metadati non sensibili necessari. Le note non saranno inviate a provider
esterni.

## 10. Aggregazione dell'esecuzione

Policy approvata in versione draft:
`maintain-plan-execution-aggregation/1.0.0-draft`.

Prima dell'aderenza si calcola `evaluation_coverage.status`. La precedenza
`INSUFFICIENT_DATA → DIFFERENT → PARTIALLY_IN_LINE → IN_LINE` qui definita è
applicabile soltanto quando la copertura è `FULLY_SUPPORTED`. Con copertura
`PARTIALLY_UNSUPPORTED` o `UNSUPPORTED`, `overall` è `null`/non prodotto: non
sarà sintetizzato come fallimento né come osservazione insufficiente. Gli
aggregati di dettaglio eventualmente calcolabili sui componenti supportati
restano pubblicabili, ma non rappresentano l'intera sessione.

Le dimensioni obbligatorie sono:

- sport/componenti;
- quantità;
- intensità;
- struttura.

| Condizione | Codice interno | Testo atleta |
|---|---|---|
| Almeno una obbligatoria non valutabile | `INSUFFICIENT_DATA` | Non ci sono abbastanza dati per una valutazione completa |
| Altrimenti, almeno una obbligatoria non rispettata | `DIFFERENT` | Seduta diversa da quella programmata |
| Altrimenti, almeno una obbligatoria parziale | `PARTIALLY_IN_LINE` | Seduta eseguita con alcune variazioni |
| Altrimenti, tutte rispettate | `IN_LINE` | Seduta eseguita come previsto |

La tabella è una precedenza vincolante: si applica la prima condizione vera e
non sono consentite compensazioni o interpretazioni alternative. Se una
deviazione è accertata ma un'altra dimensione obbligatoria è
`INSUFFICIENT_DATA`, la deviazione resta nel dettaglio e nel report, mentre
l'overall resta `INSUFFICIENT_DATA`. Outcome finale, report e futuro learning
consumeranno la stessa precedenza. Il meteo e l'obiettivo non entrano
nell'aggregazione. La dose riassume quantità e intensità e non è contata come
quinta dimensione. I codici tecnici restano interni.

## 11. Stabilità e outcome finale

Policy draft: `maintain-plan-stability/1.0.0-draft`.

Baseline e follow-up devono essere compatibili e versionati:

- baseline: recovery assessment usato per formulare la prescrizione;
- follow-up: prima valutazione valida dopo la seduta e prima della decisione
  successiva.

```yaml
general_stability:
  contract_version: maintain-plan/1.0.0-draft
  recovery:
    analyzer_version: string
    baseline: object | null
    follow_up: object | null
    freshness: object
    compatibility: object
    result: STABLE | DETERIORATED | INSUFFICIENT_DATA
  reported_problems:
    result: NO_KNOWN_ISSUE | ISSUE_REPORTED | INSUFFICIENT_DATA
    evidence: object
    provenance: object
  performance:
    applicability: OPTIONAL | NOT_APPLICABLE
    evidence: object | null
  safety_signals: []
  confirmation_ref: string | null
  overall:
    status: STABLE | DETERIORATED | INSUFFICIENT_DATA
    policy_id: maintain-plan-stability
    policy_version: 1.0.0-draft
    evidence: object
```

Nella prima versione della stability, `performance.applicability` dovrà essere
`NOT_APPLICABLE`. Una versione futura potrà renderla `OPTIONAL` soltanto
attraverso policy e schema versionati. `OPTIONAL` e `NOT_APPLICABLE` non sono
sinonimi.

Gli unici stati tecnici sono `STABLE`, `DETERIORATED` e
`INSUFFICIENT_DATA`:

- recovery nella stessa categoria o migliore → `STABLE`;
- recovery peggiore → `DETERIORATED`;
- recovery missing, stale, incompatibile o ambiguo → `INSUFFICIENT_DATA`;
- dolore, problema, affaticamento insolito o interruzione per salute
  chiaramente segnalati → safety `DETERIORATED`;
- assenza di segnalazioni → `NO_KNOWN_ISSUE`, non certificazione medica;
- segnale ambiguo → confirmation e `INSUFFICIENT_DATA` fino alla risposta.

La futura implementazione dovrà aggregare in ordine:

1. almeno una dimensione con deterioramento affidabile → `DETERIORATED`;
2. altrimenti una dimensione obbligatoria non valutabile →
   `INSUFFICIENT_DATA`;
3. altrimenti → `STABLE`.

Testi utente obbligatori:

- `STABLE`: «Non risultano segnali di peggioramento»;
- `DETERIORATED`: «Sono emersi segnali da considerare prima della prossima
  seduta»;
- `INSUFFICIENT_DATA`: «Non ci sono abbastanza informazioni per valutare il
  recupero».

Questi stati non formulano diagnosi e non introducono soglie cliniche.

Il report visibile dovrà restare immediato. Il controllo recovery successivo
dovrà restare interno, guidare la prossima seduta e non produrre un nuovo
report tardivo della vecchia seduta. Il learning sarà ammesso soltanto dopo una
verifica interna valida.

### 11.1 Matrice finale approvata

| Esecuzione | Stabilità | Outcome `MAINTAIN_PLAN` |
|---|---|---|
| `IN_LINE` | `STABLE` | `POSITIVE` |
| `PARTIALLY_IN_LINE` | `STABLE` | `NEUTRAL` |
| `DIFFERENT` | `STABLE` | `NEGATIVE` |
| qualsiasi stato valutabile | `DETERIORATED` | `NEGATIVE`, con priorità ai safety signal |
| dato essenziale non valutabile | qualsiasi | `INSUFFICIENT_DATA` |
| qualsiasi | `INSUFFICIENT_DATA` | `INSUFFICIENT_DATA` |

Un'esecuzione diversa con stabilità descrive una differenza dalla prescrizione,
non un giudizio sull'atleta. Meteo missing e obiettivo descrittivo non producono
`INSUFFICIENT_DATA`.

La matrice finale presuppone `evaluation_coverage.status: FULLY_SUPPORTED`.
Quando la copertura non è completa, l'overall d'esecuzione e la dose aggregata
sono null e non viene pubblicato un outcome definitivo dell'intera sessione;
la sessione non è classificata `NEGATIVE` né `INSUFFICIENT_DATA` per il solo
mancato supporto e resta esclusa dal learning.

## 12. Report e tempistiche

Il report dovrà essere prodotto subito dopo la sincronizzazione e presentare
in linguaggio comprensibile:

1. seduta prevista;
2. seduta eseguita;
3. confronto delle quattro dimensioni;
4. contesto e conflitti rilevanti;
5. componenti `PLANNED_ONLY` e `OBSERVED_ONLY`, senza osservazioni o target
   inventati, distinguendo esplicitamente l'opzionale omesso come “componente
   opzionale non eseguito” e mostrando evidence, provenance, missing fields e
   warning dei componenti soltanto osservati;
6. `evaluation_coverage.status`, tutti i componenti `UNSUPPORTED` e la
   capability policy/versione che determina ciascun mancato supporto;
7. obiettivo `CONTEXT_ONLY` come solo contesto oppure risultato strutturato con
   lo stesso codice e la stessa coppia policy/versione non null della
   prescrizione, quando validamente prodotto;
8. dose complessiva, pubblicabile solo con coppia policy/version valida se
   `EVALUATED`;
9. indicazioni per la seduta successiva soltanto quando supportate.

Per la dose, il report e il futuro learning dovranno consumare `status` per la
valutabilità, `direction` per l'esito direzionale e `severity_band` per la
fascia, senza usare uno di questi campi come sostituto degli altri.

Il report dovrà procedere con missingness isolata, ma non formulare un outcome
definitivo se una dimensione obbligatoria è non valutabile. Dovrà indicare se
uno scostamento di intensità è prevalentemente sopra o sotto il target. Una
interruzione di sicurezza dovrà usare testo neutro.

Con copertura non completa il report conserverà tutti i dettagli valutativi dei
componenti supportati e mostrerà esplicitamente `overall: null` e
`dose_aggregate: null`; non descriverà la sessione completa come fallita o
insufficientemente osservata. Un solo componente opzionale non supportato non
bloccherà invece overall e dose degli obbligatori supportati.

Il recovery successivo e i trend a 72h/7d dovranno restare interni. Allenamenti
intervenuti impediranno attribuzioni causali alla singola seduta. Aggiornamenti
tardivi potranno aggiornare lo storico secondo il contratto, ma non saranno
presentati come un nuovo report della vecchia seduta.

## 13. Tassonomia iniziale

Policy draft: `maintain-plan-sport-taxonomy/1.0.0-draft`.

Discipline iniziali: `RUN`, `BIKE`, `SWIM`. `STRENGTH` resta rappresentabile ma
fuori dalla prima valutazione automatica.

Environment: `INDOOR`, `OUTDOOR`, oppure null/missing se non determinabile. Non
dovrà essere usato `UNKNOWN` come osservazione sintetica.

Mode iniziali:

- RUN: `ROAD`, `TRAIL`, `TRACK`, `TREADMILL`;
- BIKE: `ROAD`, `GRAVEL`, `MOUNTAIN_BIKE`, `INDOOR_TRAINER`;
- SWIM: `POOL`, `OPEN_WATER`.

Mode può essere missing e non è inferito dal nome libero. Mapping di sorgente
sono ammessi soltanto se documentati; nuovi valori richiedono tassonomia
versionata. Non esistono equivalenze fra discipline. Le sostituzioni sono
dichiarate nella prescrizione per componente. Una sostituzione non autorizzata
può essere collegata tramite direct ID o conferma, ma resta uno scostamento. Il
valore raw è preservato.

## 14. Perimetro iniziale e proxy vietati

La futura prima implementazione automatica dovrà essere limitata a:

- sedute continue con dati compatibili;
- intervalli con blocchi e segmenti ricostruibili;
- Brick atomiche con componenti e consecutività verificabili.

`STRENGTH` e tipologie non supportate restano rappresentabili ma non sono
ricostruite mediante proxy. Una composition multisport non è promossa a Brick.

Non costituiscono prova sufficiente:

- mera esistenza di un'attività o sola coincidenza di discipline;
- nomi, note o obiettivi in testo libero;
- metrica secondaria al posto della primaria;
- medie complessive per dimostrare intervalli;
- conversioni fra quantità o metodi d'intensità;
- calorie Garmin come prova di fueling;
- VO2max come prova di stabilità;
- recovery missing/stale come prova di stabilità;
- assenza di record come certificazione medica;
- campi presenti soltanto nel raw;
- zero sintetici al posto di missingness;
- tassonomia, substitutions o tolleranze inferite a posteriori;
- valori aggregati al posto dei componenti;
- blocchi o segmenti usati come proxy dei componenti;
- tie-break basati su durata, distanza, nome, carico o somiglianza.

## 15. Versionamento, rollout e learning gates

Durante lo sviluppo dovrà essere usato `maintain-plan/1.0.0-draft`. Snapshot,
attività normalizzata, policy, analyzer, conferme, evidence e risultati
dovranno essere versionati e auditabili. Il raw non dovrà sostituire i campi
canonici.

La prima unità implementativa comprenderà soltanto tipi, validator e fixture
sintetiche, senza runtime wiring. Feature flag separati dovranno governare:

- snapshot;
- normalization;
- matching;
- shadow evaluation;
- report;
- learning.

In shadow evaluation il risultato:

- non dovrà modificare l'outcome ufficiale;
- non dovrà modificare la confidence;
- non dovrà pubblicare report;
- non dovrà entrare nel learning.

Il report potrà essere attivato successivamente mantenendo il learning
disabilitato. L'attivazione del learning richiederà una nuova approvazione
esplicita dell'utente e dovrà conservare le protezioni esistenti, aggiungendo
gate per:

- versione draft;
- shadow;
- ambiguità aperta;
- mapping non confermato;
- conflitto rilevante con impatto `UNRESOLVED`;
- confirmation mancante o risposta «non lo so»;
- dato cancellato;
- proiezione di feedback o conflitto ambigua, ritirata o non risolvibile;
- outcome `INSUFFICIENT_DATA`;
- dati essenziali insufficienti o dose valutata con metadati policy invalidi;
- omissione di un componente opzionale, il cui record resta escluso dal
  learning anche quando la copertura degli obbligatori è completa;
- copertura non completamente supportata (`PARTIALLY_UNSUPPORTED` o
  `UNSUPPORTED`);
- episodio precedente all'effective date.

Versione definitiva ed effective date saranno assegnate soltanto dopo
validazione. L'accesso futuro a dati reali richiede autorizzazione separata.

## 16. Decisioni residue prima dell'implementazione

Le policy di prodotto descritte in questo documento sono approvate. Restano
aperte, senza autorizzare comportamenti impliciti:

- progettazione tecnica dei tipi, validator, storage, migrazioni additive,
  servizi di confirmation e interfacce fra moduli;
- progettazione tecnica dei registri append-only, delle proiezioni versionate e
  della minimizzazione dei metadati audit dopo cancellazione, nel rispetto
  delle invarianti approvate;
- mapping documentato dei payload delle singole sorgenti verso tassonomia,
  target, unità, evaluation window, componenti e provenance;
- formato tecnico definitivo degli identificativi, candidate set, evidence e
  riferimenti audit, nel rispetto degli schemi semantici approvati;
- comportamento operativo delle feature flag e osservabilità dello shadow;
- fixture sintetiche e verifiche end-to-end non ancora realizzate;
- verifiche future, separatamente autorizzate, sulla qualità dei direct ID,
  timestamp, timezone, multisport, telemetria, recovery e conflitti nei dati
  reali;
- criteri finali di uscita dalla shadow evaluation;
- versione definitiva ed effective date;
- attivazione del report runtime;
- attivazione del learning, che richiede nuova approvazione esplicita.

Queste decisioni residue non riaprono candidate window, filtri, fasce,
consecutività, aggregazioni, dose, tassonomia iniziale, meteo/privacy, conflitti
o feedback approvati nel presente draft.

## 17. Checklist pre-implementazione

### Definizione documentale

- [x] prescrizione autorevole e schema snapshot definiti;
- [x] quattro dimensioni e loro separazione definite;
- [x] tassonomia iniziale e componenti canonici definiti;
- [x] target e osservazioni per componente senza duplicazioni di sessione
      definiti;
- [x] ownership separata di snapshot, attività osservata ed evaluation
      definita documentalmente;
- [x] `actual_session` indipendente dalla prescrizione e costruibile prima del
      matching definita documentalmente;
- [x] `prescription_mapping` separato, immutabile e assente per matching non
      risolti definito;
- [x] riferimenti ai risultati confinati a `execution_evaluation` e
      correlazione unidirezionale definita;
- [x] scope e forma completamente qualificata dei riferimenti osservati e
      pianificati definiti;
- [x] blocchi, ripetizioni e transizioni canonici definiti;
- [x] recovery target con applicability e invarianti definito;
- [x] principio generale di confirmation definito;
- [x] candidate window, filtri e casi zero/una/più candidate definiti;
- [x] direct ID e separazione matching/aderenza definiti;
- [x] Brick/multisport e policy dei 15 minuti definiti;
- [x] metriche e fasce quantitative iniziali definite;
- [x] ogni quantità in fascia `MAIN`, inclusi i confini, definita come
      `MET + IN_LINE` e consumo coerente nella dose definito;
- [x] intensità continuous/intervals e coverage definite;
- [x] struttura e aggregazione dell'esecuzione definite;
- [x] precedenza completa dell'aggregazione identity, senza compensazioni,
      definita;
- [x] matrice `MATCHED`/`PLANNED_ONLY`/`OBSERVED_ONLY`, riferimenti nullable e
      copertura dei componenti pianificati obbligatori definite;
- [x] `requiredness: null` vincolante per `OBSERVED_ONLY` ed esclusioni da
      completezza, copertura e aggregati obbligatori definite;
- [x] wrapper `evaluation_applicability: NOT_APPLICABLE` per
      `OPTIONAL + SUPPORTED + PLANNED_ONLY`, risultati null ed esclusioni da
      aggregati, overall, dose, coverage e learning definiti;
- [x] precedenza unica dell'overall definita e condivisa da outcome, report e
      futuro learning;
- [x] matrice completa della dose definita;
- [x] unico tipo canonico `dose_evaluation` incorporato nella evaluation
      definito;
- [x] `dose_result_id` e destinazione di `component_dose_result_refs` definiti;
- [x] valutabilità, direzione, fascia e applicability della dose mantenute
      semanticamente separate;
- [x] fascia peggiore obbligatoria per ogni dose valutata, incluse direzioni
      `MIXED` e `UNDETERMINED`, definita;
- [x] risultato canonico dell'obiettivo `STRUCTURED` ed esclusione valutativa
      degli obiettivi `CONTEXT_ONLY` definiti;
- [x] codice non null e stabile obbligatorio per gli obiettivi `STRUCTURED` e
      coerenza del riferimento canonico definiti;
- [x] coppia policy/versione completa obbligatoria per ogni obiettivo
      `STRUCTURED`, coincidenza nel risultato e null per gli altri obiettivi
      definite;
- [x] `requiredness` e `support_status` separati, `STRENGTH` esplicitamente
      non supportata e riferimenti valutativi null definiti;
- [x] copertura del supporto, blocco di overall/dose aggregata e casi normativi
      per componenti obbligatori e opzionali definiti;
- [x] metadati della matrice obbligatori per ogni dose `EVALUATED`, di
      componente e aggregata, definiti;
- [x] impatto dei conflitti separato dagli input grezzi e valutato dopo il
      mapping con stato `UNRESOLVED` definito;
- [x] dimensioni canoniche complete dell'impatto dei conflitti e propagazione
      di `INSUFFICIENT_DATA` sulle dimensioni obbligatorie interessate definite;
- [x] aggregazione totale della direction della dose composta ed esempi
      normativi definiti;
- [x] direzione aggregata dell'intensità per sessioni composte definita con
      precedenza deterministica ed esempi normativi;
- [x] applicability delle dimensioni obbligatorie definita;
- [x] direzioni `MIXED` e `UNDETERMINED` definite;
- [x] stabilità iniziale definita semanticamente;
- [x] meteo/privacy, conflitti e feedback definiti;
- [x] registri append-only e proiezioni versionate per feedback e conflitti
      definiti senza mutare `actual_session`;
- [x] report, rollout e learning gates definiti;
- [x] applicazione ai soli nuovi episodi definita.

### Evidenza implementativa ancora mancante

- [ ] tipi e validator implementati con fixture sintetiche;
- [ ] propagazione di `INSUFFICIENT_DATA` verificata per ogni dimensione e dose;
- [ ] riferimenti, versioni, audit e provenance verificabili end-to-end;
- [ ] unicità e risoluzione dei riferimenti qualificati e dei `dose_result_id`
      verificate end-to-end;
- [ ] ownership unidirezionale, indipendenza di `actual_session` e produzione
      condizionata a un mapping univoco verificate end-to-end;
- [ ] risoluzione immutabile di `planned_block_ref` nel mapping e nei risultati
      valutativi verificata end-to-end;
- [ ] invarianti di `recovery.applicability` e `recovery.target` validate con
      fixture sintetiche;
- [ ] matching e confirmation coperti per zero/una/più candidate e direct ID;
- [ ] casi Brick/multisport coperti, inclusi componenti mancanti, fuori ordine,
      sovrapposti, interposti e oltre 15 minuti;
- [ ] fixture coprono `REQUIRED + PLANNED_ONLY`, `OPTIONAL + PLANNED_ONLY`,
      `OPTIONAL + MATCHED` e `OBSERVED_ONLY`, inclusi requiredness e riferimenti
      null validi e invalidi;
- [ ] fixture coprono la precedenza overall con deviazioni accertate insieme a
      dimensioni insufficienti;
- [ ] fixture coprono la fascia peggiore di dose per componente e aggregata;
- [ ] fixture rifiutano obiettivi `STRUCTURED` senza codice o con riferimento
      incoerente e non inferiscono codice o risultato dal testo libero;
- [ ] fixture rifiutano dosi `EVALUATED` senza la coppia policy/version e dosi
      `INSUFFICIENT_DATA` che la valorizzano;
- [ ] fixture coprono l'intera precedenza della direction aggregata della dose,
      inclusi neutralità di `IN_LINE`, `MIXED`, `UNDETERMINED` e insufficienza;
- [ ] fixture coprono obiettivi `STRUCTURED` e `CONTEXT_ONLY` senza inferenze
      dal testo libero;
- [ ] fixture rifiutano ogni obiettivo `STRUCTURED` con coppia policy/versione
      assente o parziale e risultati con coppia diversa dalla prescrizione;
- [ ] fixture coprono tutte le fasce quantitative e d'intensità;
- [ ] fixture coprono `MET + IN_LINE` per ogni valore quantitativo in `MAIN`,
      inclusi entrambi i confini e il caso RUN al 95%, e `LOWER`/`HIGHER` solo
      fuori dai confini applicabili;
- [ ] fixture coprono STRENGTH-only, Brick RUN+STRENGTH obbligatoria,
      STRENGTH opzionale e tutti gli obbligatori supportati, inclusi null di
      overall, dose e risultati dei componenti non supportati;
- [ ] fixture confermano `MET + IN_LINE` con almeno il 90% delle ripetizioni
      obbligatorie rispettate e l'aggregazione identity completa;
- [ ] persistenza conserva originali, conflitti, correzioni e cancellazioni;
- [ ] proiezioni di feedback e conflitti ricostruite deterministicamente e
      riferite dall'evaluation con la versione effettivamente usata;
- [ ] evaluation dell'impatto dei conflitti versionate dopo mapping univoco,
      separate dagli input, con tutte le dimensioni canoniche interessate e
      bloccanti per report e learning se irrisolte;
- [ ] feature flag e shadow provati senza modificare outcome, report, confidence
      o learning;
- [ ] verifiche con dati reali autorizzate e completate;
- [ ] criteri di uscita dalla shadow approvati;
- [ ] versione definitiva ed effective date approvate;
- [ ] attivazione del learning approvata esplicitamente.

Il completamento della checklist implementativa non cambia automaticamente lo
stato del documento. Fino a una successiva approvazione esplicita resta
**DRAFT — NON IMPLEMENTATO**.
