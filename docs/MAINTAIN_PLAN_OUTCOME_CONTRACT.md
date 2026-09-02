# DRAFT — MAINTAIN_PLAN Outcome Contract — NON IMPLEMENTATO

> **Stato:** DRAFT, NON IMPLEMENTATO.
>
> Le decisioni contrassegnate come **APPROVATA** definiscono il contratto
> concordato, ma non descrivono comportamento attualmente disponibile nel
> runtime. Finché le decisioni residue non saranno approvate e il contratto non
> sarà implementato esplicitamente, `MAINTAIN_PLAN` deve restare
> `INSUFFICIENT_DATA` e non deve ricevere esiti tramite fallback o proxy.

## 1. Scopo e confini

Questo documento definisce il contratto dati e semantico per valutare se una
decisione con primary intent `MAINTAIN_PLAN` ha prodotto congiuntamente:

1. un'esecuzione coerente con l'ultima prescrizione effettivamente comunicata
   all'atleta; e
2. la stabilità generale dell'atleta.

Il contratto deve conservare evidenza verificabile per ogni dimensione, senza
dedurre informazioni non osservate.

Non implementa evaluator o test, non introduce soglie numeriche, non autorizza
equivalenze implicite, non formula diagnosi cliniche e non usa la mera presenza
di un'attività come prova di successo.

## 2. Registro delle decisioni approvate

Le seguenti decisioni sono **APPROVATE**:

1. **Prescrizione autorevole.** È l'ultima prescrizione effettivamente
   comunicata all'atleta, conservata come snapshot immutabile. La prescrizione
   originaria resta disponibile esclusivamente per audit.
2. **Dimensioni di esecuzione.** Sono sport, quantità di lavoro, intensità e
   struttura della seduta.
3. **Separazione semantica.** Quantità di lavoro, intensità e dose/carico
   allenante sono concetti distinti. Quantità e intensità sono valutate
   separatamente e interpretate congiuntamente, senza formule o conversioni
   implicite.
4. **Meteo.** È un dato contestuale facoltativo per le attività outdoor:
   arricchisce l'analisi, non determina direttamente `MET` o `NOT_MET`, e la
   sua assenza non blocca il report né produce `INSUFFICIENT_DATA`. Per le
   attività indoor è `NOT_APPLICABLE`. Sorgente e provenienza devono essere
   conservate.
5. **Obiettivo.** È valutabile soltanto se possiede criteri strutturati e
   osservabili. Un obiettivo testuale o generico resta contesto e non blocca
   l'analisi.
6. **Stati e testi utente.** La corrispondenza definita nella sezione 7 è
   vincolante. La mancanza di dati non deve essere presentata come fallimento
   dell'atleta.
7. **Stabilità iniziale.** Il recovery è valutato automaticamente mediante le
   categorie già approvate. L'assenza di problemi riferiti produce
   `NO_KNOWN_ISSUE`, non una certificazione clinica; i problemi riferiti
   dall'atleta devono essere considerati. La performance non è obbligatoria
   nella prima versione. Recovery mancante o stale non blocca l'analisi
   dell'esecuzione, ma impedisce di inventare la stabilità.
8. **Metrica primaria della quantità.** Ogni prescrizione dichiara `duration`,
   `distance`, `sets_repetitions` oppure una metrica esplicita per segmento. Le
   metriche secondarie sono contestuali e non sono convertite automaticamente.
9. **Policy della quantità.** Gli stati della quantità dipendono da policy
   esplicite e versionate. Questo draft non introduce tolleranze numeriche.
10. **Metodo d'intensità.** Ogni prescrizione dichiara un metodo principale ed
    eventuali metodi secondari ammessi. Sono vietate conversioni automatiche
    fra frequenza cardiaca, potenza, passo/velocità e RPE.
11. **Copertura.** Nelle sedute continue si valuta la copertura temporale;
    negli intervalli si valutano i singoli blocchi. Telemetria insufficiente
    rende non valutabile soltanto la dimensione interessata.
12. **Identità sportiva.** Sport principale, modalità e variante sono campi
    distinti. Indoor e outdoor sono compatibili soltanto se ammessi. Le
    sostituzioni sportive devono essere esplicite e non possono essere inferite
    a posteriori.
13. **Tempistiche.** Il report è visibile subito dopo la sincronizzazione e il
    recovery è usato prima della seduta successiva. Le finestre 72h e 7d sono
    riservate al trend interno. Allenamenti intervenuti impediscono attribuzioni
    causali alla singola seduta. Nessun aggiornamento tardivo può essere
    presentato come un nuovo report della vecchia seduta.
14. **Deterioramento.** Usa analyzer e categorie già approvati. I segnali di
    sicurezza hanno priorità; segnali contraddittori o insufficienti non
    producono conclusioni inventate.
15. **Matrice finale.** L'aggregazione vincolante è definita nella sezione 10.
16. **Brick.** È una sola seduta composta, con segmenti ordinati inclusa la
    transizione e obbligo di consequenzialità. Supporta sia un'attività
    multisport sia file separati, produce dettaglio per segmento ma un solo
    outcome e un solo contributo al learning. Recovery e stabilità riguardano
    l'intera Brick; il meteo è contestuale per ogni segmento outdoor.
17. **Interruzioni e matching.** Un workout interrotto per sicurezza non deve
    essere descritto come errore dell'atleta. Attività multiple o ambigue non
    devono essere collegate arbitrariamente.
18. **Applicazione temporale.** Il nuovo contratto si applica soltanto ai nuovi
    episodi. Nessun episodio storico viene reinterpretato.
19. **Tolleranze esplicite.** Le tolleranze sono definite da policy versionate
    per sport e tipologia di seduta. Una regola specifica conservata nella
    prescrizione può sostituire la policy generale. Limite inferiore e limite
    superiore sono indipendenti e distinguono una fascia principale da una
    secondaria; l'evaluator non contiene tolleranze nascoste.
20. **Dose complessiva.** Quantità o durata e intensità sono valutate
    separatamente; i risultati sono poi combinati in una valutazione della dose
    complessiva soltanto mediante una policy esplicita e versionata.
21. **Struttura osservabile.** La struttura dichiara blocchi obbligatori e
    facoltativi, ordine e main set. I segmenti che non possono essere
    ricostruiti sono gestiti prudentemente e non vengono inferiti.
22. **Contratto d'intensità.** Metodo, unità, obiettivo e copertura sono
    dichiarati per blocco. Non esiste conversione automatica tra frequenza
    cardiaca, potenza, passo/velocità e RPE.
23. **Sorgente meteo iniziale.** Open-Meteo è la prima sorgente ambientale,
    sostituibile, con attribuzione e provenienza conservate. Si usano coordinate
    approssimate e non si trasmette l'intero tracciato GPS.
24. **Ruolo del meteo.** Il meteo outdoor è contestuale e non bloccante, mentre
    per indoor è `NOT_APPLICABLE`. Può spiegare difficoltà e scostamenti ma,
    nella prima versione, non applica formule correttive e non cambia
    autonomamente lo stato della seduta.
25. **Matching e conferma.** Il matching è deterministico e privilegia
    l'identificativo diretto. Nei casi ambigui viene chiesta conferma
    all'atleta; la seduta non entra nel learning prima della conferma.
26. **Tassonomia.** Disciplina, ambiente indoor/outdoor, modalità e composizione
    singola/Brick/multisport sono dimensioni distinte.
27. **Gerarchia e conflitti delle sorgenti.** L'ordine è prescrizione
    IronCoach, Garmin o dispositivo originale, Strava come integrazione o
    fallback, atleta per i dati soggettivi e Open-Meteo per quelli ambientali.
    Dati discordanti non vengono mediati né fusi automaticamente.
28. **Missingness per dimensione.** Il report viene prodotto anche quando una
    dimensione non è valutabile, ma non formula un outcome complessivo
    definitivo se quella dimensione è obbligatoria. Il meteo resta facoltativo.
29. **Report immediato.** Il report comprende seduta prevista, seduta eseguita,
    confronto dimensionale, contesto, valutazione della dose e, quando
    supportate, indicazioni per la seduta successiva. Le analisi a 72 ore e 7
    giorni restano interne.
30. **Feedback soggettivo.** Nessun questionario è obbligatorio. Il feedback
    facoltativo è strutturato per RPE, dolore, affaticamento insolito,
    interruzioni e motivazioni. L'assenza di segnalazioni significa «nessun
    problema noto», non certificazione medica.
31. **Perimetro della prima implementazione.** Sono supportate le sedute
    continue quando i dati sono compatibili, gli intervalli soltanto con
    blocchi e segmenti ricostruibili e le Brick come singole sessioni atomiche
    con ordine e consecutività verificabili. Non si usano proxy per tipologie
    non supportate.
32. **Linguaggio del report.** I testi sono comprensibili all'atleta; i codici
    tecnici rimangono interni.

## 3. Prescrizione autorevole e audit

Lo snapshot autorevole è creato quando la prescrizione viene effettivamente
comunicata all'atleta. Una modifica successiva diventa autorevole soltanto dopo
una nuova comunicazione e genera un nuovo snapshot immutabile. Non si modifica
retroattivamente lo snapshot precedente.

```yaml
planned_workout:
  contract_version: string
  prescription_snapshot_id: string
  workout_id: string
  decision_id: string
  communicated_at: datetime
  scheduled_window:
    start: datetime
    end: datetime
    timezone: string
  sport:
    discipline: string
    environment: indoor | outdoor
    mode: string | null
    composition: single | brick | multisport
  allowed_substitutions: []
  quantity:
    applicability: REQUIRED | NOT_APPLICABLE
    primary_metric: duration | distance | sets_repetitions | per_segment
    target: object | null
    secondary_metrics: []
    evaluation_policy_id: string | null
  intensity:
    applicability: REQUIRED | NOT_APPLICABLE
    primary_method: string | null
    target: object | null
    allowed_secondary_methods: []
    evaluation_policy_id: string | null
  structure:
    applicability: REQUIRED | NOT_APPLICABLE
    session_type: continuous | intervals | brick | other
    segments: []
    evaluation_policy_id: string | null
  objective:
    evaluability: STRUCTURED | CONTEXT_ONLY | NOT_APPLICABLE
    code: string | null
    success_criteria: []
    context_text: string | null
    evaluation_policy_id: string | null
  provenance:
    source: string
    captured_at: datetime
  audit:
    original_plan_snapshot_id: string | null
```

Target, unità e criteri devono essere strutturati. Se la metrica primaria è
`per_segment`, ciascun segmento dichiara esplicitamente la propria metrica.
Le metriche secondarie non sostituiscono quella primaria. L'eventuale piano
originario è consultabile per audit, ma non partecipa al confronto.

## 4. Attività eseguita e matching

```yaml
actual_session:
  contract_version: string
  session_id: string
  source_activities: []
  start: datetime
  end: datetime | null
  timezone: string
  sport:
    discipline: string
    environment: indoor | outdoor
    mode: string | null
    composition: single | brick | multisport
  quantity:
    primary_metric: string | null
    observed: object | null
    secondary_metrics: []
  intensity:
    methods: []
    observations: object | null
    temporal_coverage: object | null
  structure:
    session_type: string | null
    segments: []
  completion:
    status: string | null
    interruption_reason: string | null
    safety_interruption: boolean | null
  athlete_feedback:
    rpe: object | null
    pain: object | null
    unusual_fatigue: object | null
    interruptions: object | null
    reasons: object | null
  weather_context: []
  data_quality:
    source_checked_at: datetime | null
    completeness: string
    missing_fields: []
    warnings: []
  provenance:
    normalized_at: datetime
```

Missingness resta esplicita e non diventa zero. Ogni elemento di
`source_activities` conserva ID e provenienza. Il matching deve essere
deterministico e dà priorità all'identificativo diretto. Se più attività
restano candidate o la relazione è ambigua, nessuna viene scelta
arbitrariamente: viene richiesta conferma all'atleta, le sole dimensioni non
dimostrabili diventano `INSUFFICIENT_DATA` e la seduta non entra nel learning
prima della conferma.

Una interruzione motivata da sicurezza conserva ragione ed evidenza e usa un
testo neutro, non colpevolizzante. Non equivale automaticamente né a errore
dell'atleta né a esecuzione pienamente in linea.

## 5. Valutazione dell'esecuzione

### 5.1 Sport

Il confronto usa separatamente disciplina, ambiente indoor/outdoor, modalità e
composizione singola/Brick/multisport. La
compatibilità richiede coincidenza oppure un'autorizzazione esplicita nello
snapshot o in una policy versionata da esso richiamata. Questo vale anche per
indoor/outdoor. Somiglianza nominale, comune natura aerobica e attività
osservate a posteriori non autorizzano sostituzioni.

### 5.2 Quantità di lavoro

La quantità è valutata sulla metrica primaria dichiarata: durata, distanza,
serie/ripetizioni o metrica per segmento. Metrica, rappresentazione e unità
devono essere compatibili secondo una policy esplicita e versionata per sport e
tipologia di seduta. Una regola specifica della prescrizione sostituisce, quando
presente, la policy generale. Gli stati dipendono da limiti inferiori e
superiori indipendenti, con fascia principale e secondaria esplicitate dalla
policy; nessuna tolleranza è nascosta nell'evaluator e nessun valore numerico è
definito qui.

Le metriche secondarie arricchiscono il contesto ma non sostituiscono la
primaria. Non si converte automaticamente distanza in durata, durata in
distanza o una metrica di segmento in una metrica complessiva.

### 5.3 Intensità

La valutazione usa il metodo principale prescritto oppure un metodo secondario
esplicitamente ammesso. Ogni blocco dichiara metodo, unità, obiettivo e
copertura. Frequenza cardiaca, potenza, passo/velocità e RPE restano metodi
distinti e non vengono convertiti fra loro.

Per una seduta continua la policy valuta la copertura temporale. Per una seduta
a intervalli valuta separatamente i blocchi prescritti. Medie complessive non
dimostrano l'esecuzione dei singoli blocchi. Telemetria insufficiente produce
`INSUFFICIENT_DATA` per l'intensità senza invalidare automaticamente sport,
quantità o struttura.

### 5.4 Struttura

La struttura confronta blocchi obbligatori e facoltativi, ordine, main set,
tipo, quantità applicabile, intensità applicabile, recupero applicabile e
consequenzialità dei segmenti. I segmenti non ricostruibili sono trattati
prudentemente come evidenza insufficiente per le dimensioni che ne dipendono;
non sono inferiti. Il testo libero non viene trasformato a posteriori in
struttura osservabile.

### 5.5 Obiettivo della seduta

L'obiettivo è una dimensione valutabile solo con criteri strutturati,
osservabili e associati a una policy versionata. Se è generico o soltanto
testuale, ha `evaluability: CONTEXT_ONLY`: resta visibile come contesto, non
entra nell'aggregazione e non rende l'esecuzione insufficiente.

### 5.6 Quantità, intensità e dose/carico

Quantità o durata e intensità producono risultati separati. Sono combinati in
una valutazione della dose complessiva esclusivamente da una policy esplicita e
versionata, con campi e provenienza propri. Non esistono formule implicite e la
dose non sostituisce retroattivamente una delle due dimensioni.

## 6. Meteo contestuale

Il meteo è facoltativo e non è una dimensione di aderenza:

- per ogni segmento outdoor può essere registrato con sorgente, timestamp,
  località/provenienza e qualità;
- può spiegare o arricchire il report, ma non determina direttamente `MET` o
  `NOT_MET`;
- se manca, il report procede e non diventa `INSUFFICIENT_DATA`;
- per attività o segmenti indoor è `NOT_APPLICABLE`.

La prima sorgente ambientale è Open-Meteo, sostituibile senza cambiare il
contratto. Ogni dato conserva attribuzione e provenienza. L'integrazione fa
riferimento alla [Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
e alle [condizioni di utilizzo e pricing](https://open-meteo.com/en/pricing).
Per limitare l'esposizione dei dati si usano coordinate approssimate e non si
trasmette l'intero tracciato GPS.

Il meteo può spiegare difficoltà e scostamenti nel testo del report, ma nella
prima versione non applica formule correttive e non cambia autonomamente lo
stato di una dimensione o della seduta.

## 7. Stati interni e testi rivolti all'atleta

| Stato interno | Testo utente obbligatorio |
|---|---|
| `MET` | In linea con quanto previsto |
| `PARTIALLY_MET` | Parzialmente in linea con quanto previsto |
| `NOT_MET` | Diverso da quanto previsto |
| `NOT_APPLICABLE` | Non previsto per questa seduta |
| `INSUFFICIENT_DATA` | Dati non sufficienti per valutarlo |

`PARTIALLY_MET` richiede criteri espliciti della policy. `NOT_APPLICABLE` è
valido solo quando dichiarato dal contratto. `NOT_MET` richiede evidenza
sufficiente e compatibile; dati mancanti, incompatibili o ambigui producono
invece `INSUFFICIENT_DATA` per la dimensione interessata. I testi e le
motivazioni non devono rappresentare missingness, ambiguità o interruzioni di
sicurezza come fallimenti dell'atleta.

Ogni risultato conserva stato, `policy_id`, evidenza pianificata ed effettiva,
ragioni, qualità dei dati e provenienza.

### 7.1 Gerarchia delle sorgenti e conflitti

La provenienza canonica segue questa gerarchia, applicata alla dimensione di
competenza di ciascuna sorgente:

1. prescrizione IronCoach per ciò che era previsto;
2. Garmin o altro dispositivo originale per ciò che è stato registrato;
3. Strava come integrazione o fallback;
4. atleta per RPE, dolore, affaticamento insolito, interruzioni e motivazioni;
5. Open-Meteo per i dati ambientali.

La gerarchia non autorizza a sovrascrivere silenziosamente dati discordanti.
Il conflitto viene conservato come evidenza e gestito dalla policy della
dimensione interessata: non si calcola alcuna media e non si effettua alcuna
fusione automatica.

## 8. Stabilità generale iniziale

La stabilità è distinta dall'esecuzione. Nella prima versione:

- il recovery è valutato automaticamente tramite analyzer e categorie già
  approvati;
- i problemi riferiti dall'atleta sono considerati come segnali di sicurezza;
- l'assenza di problemi riferiti è `NO_KNOWN_ISSUE`, cioè assenza di problemi
  noti nella sorgente, e non certificazione clinica;
- la performance non è obbligatoria;
- recovery mancante o stale non impedisce il report sull'esecuzione, ma rende
  la stabilità `INSUFFICIENT_DATA` anziché consentire una stabilità inventata.

```yaml
general_stability:
  contract_version: string
  recovery:
    analyzer_version: string
    baseline: object | null
    observation: object | null
    freshness: object
    result: STABLE | DETERIORATED | INSUFFICIENT_DATA
  reported_problems:
    result: NO_KNOWN_ISSUE | ISSUE_REPORTED | INSUFFICIENT_DATA
    evidence: object
    provenance: object
  performance:
    applicability: OPTIONAL
    evidence: object | null
  safety_signals: []
  overall:
    status: STABLE | DETERIORATED | INSUFFICIENT_DATA
    policy_id: string
    evidence: object
```

Il deterioramento riusa analyzer e categorie già approvati, senza nuove soglie
implicite. I segnali di sicurezza hanno priorità. Evidenza insufficiente o
contraddittoria non autorizza conclusioni inventate.

## 9. Tempistiche del report e dei trend

Il report della seduta è reso visibile subito dopo la sincronizzazione e
mantiene la propria identità. In un linguaggio comprensibile all'atleta, senza
esporre i codici tecnici interni, presenta:

1. seduta prevista;
2. seduta eseguita;
3. confronto dimensionale;
4. contesto;
5. valutazione della dose;
6. indicazioni per la seduta successiva, soltanto quando supportate.

Il report viene prodotto anche in presenza di missingness isolata. Se una
dimensione obbligatoria non è valutabile, quella dimensione è
`INSUFFICIENT_DATA` e non viene formulato un outcome complessivo definitivo.
Il meteo è facoltativo e la sua assenza non ha questo effetto.

Il recovery disponibile viene usato prima della seduta successiva. Le
osservazioni a 72 ore e 7 giorni servono esclusivamente al trend interno e non
generano un nuovo report della vecchia seduta.

Se fra la seduta e un'osservazione successiva sono intervenuti altri
allenamenti, il sistema non attribuisce causalmente il segnale alla singola
seduta. Un aggiornamento tardivo può aggiornare il trend interno secondo policy
esplicita, ma non viene presentato all'atleta come un nuovo esito di quella
seduta.

## 10. Aggregazione finale approvata

L'esecuzione aggregata assume uno dei livelli `IN_LINE`, `PARTIALLY_IN_LINE`,
`DIFFERENT` o `INSUFFICIENT_DATA`, derivato tramite policy versionate dai
risultati di sport, quantità, intensità e struttura. L'obiettivo
`CONTEXT_ONLY` e il meteo mancante sono esclusi dalle dimensioni essenziali.

| Esecuzione | Stabilità | Outcome `MAINTAIN_PLAN` |
|---|---|---|
| `IN_LINE` | `STABLE` | `POSITIVE` |
| `PARTIALLY_IN_LINE` | `STABLE` | `NEUTRAL` |
| `DIFFERENT` | `STABLE` | `NEGATIVE` |
| qualsiasi stato valutabile | `DETERIORATED` | `NEGATIVE`, con priorità ai segnali di sicurezza |
| dato essenziale non valutabile | qualsiasi | `INSUFFICIENT_DATA` |
| qualsiasi | `INSUFFICIENT_DATA` | `INSUFFICIENT_DATA` |

Per `MAINTAIN_PLAN`, un'esecuzione diversa con stabilità produce dunque
`NEGATIVE`; ciò descrive la differenza dalla prescrizione e non un giudizio
sull'atleta. Meteo mancante e obiettivo descrittivo non producono
`INSUFFICIENT_DATA`.

## 11. Contratto Brick

Una Brick è un'unica seduta composta:

- i segmenti, transizione inclusa, sono ordinati e devono essere consecutivi;
- l'acquisizione può provenire da una singola attività multisport o da file
  separati collegati deterministicamente;
- il report espone il dettaglio di ogni segmento e delle transizioni, ma genera
  un solo outcome complessivo;
- l'episodio fornisce un solo contributo al learning;
- recovery e stabilità sono riferiti all'intera Brick;
- il meteo resta contestuale separatamente per ogni segmento outdoor e
  `NOT_APPLICABLE` per quelli indoor.

File multipli ambigui, sovrapposti o non dimostrabilmente consecutivi non
vengono assemblati arbitrariamente. L'insufficienza di un segmento rende non
valutabili le sole dimensioni essenziali che dipendono da quell'evidenza e si
propaga poi secondo la matrice finale.

## 12. Perimetro della prima implementazione

La prima implementazione è intenzionalmente limitata a:

- sedute continue, quando dati prescritti e osservati sono compatibili;
- intervalli, soltanto quando blocchi e segmenti sono ricostruibili;
- Brick, trattate come singole sessioni atomiche quando ordine e consecutività
  sono verificabili.

Le tipologie non supportate non sono ricostruite mediante proxy. Una
composizione multisport che non soddisfa il contratto Brick resta distinta e
non viene promossa automaticamente a Brick.

## 13. Proxy vietati

Non costituiscono prova sufficiente, da soli o in combinazioni non
contrattualizzate:

- la mera esistenza di un'attività o la sola coincidenza dello sport;
- nomi, note o obiettivi in testo libero;
- una metrica secondaria al posto della quantità primaria;
- medie complessive per dimostrare intervalli o segmenti;
- conversioni fra metodi d'intensità o fra metriche di quantità;
- calorie Garmin come prova di fueling;
- VO2max o una singola metrica osservazionale come prova di stabilità;
- recovery mancante o stale come prova di stabilità;
- assenza di record come certificazione di assenza di problemi;
- valori presenti solo nel payload grezzo quando manca il campo canonico;
- zero sintetici al posto di dati mancanti;
- sport, modalità, variante, indoor/outdoor, sostituzioni o tolleranze inferiti
  a posteriori.

## 14. Versionamento, provenienza e applicazione

Snapshot, attività normalizzata, policy, analyzer, evidenza per dimensione e
risultato devono essere versionati e auditabili. Il payload grezzo può essere
conservato secondo le policy di privacy, ma non sostituisce i dati canonici.

Il presente contratto vale soltanto per episodi creati dopo la futura entrata
in vigore della versione implementata. Episodi già persistiti mantengono
contratto, evidenza e outcome originali: non sono migrati o reinterpretati da
queste regole.

## 15. Decisioni residue prima dell'implementazione

Le decisioni elencate nella sezione 2 sono chiuse. Restano da approvare senza
inventare valori in questo draft:

- schema delle sostituzioni esplicite e relativa governance;
- forma canonica di target, osservazioni e unità per ciascuna metrica primaria;
- valori delle policy versionate per sport e tipologia di seduta, senza
  introdurre qui soglie numeriche;
- metodi d'intensità inizialmente supportati;
- schema canonico dei segmenti e dettaglio operativo del matching dei file
  multipli di una Brick;
- policy di aggregazione delle quattro dimensioni di esecuzione nei livelli
  `IN_LINE`, `PARTIALLY_IN_LINE`, `DIFFERENT` e `INSUFFICIENT_DATA`;
- regole operative di freshness, completezza e gestione dei segnali
  contraddittori per la stabilità iniziale;
- schema di dettaglio e retention dei dati soggettivi, di sicurezza e meteo;
- versione di entrata in vigore per i soli nuovi episodi.

## 16. Criteri di accettazione pre-implementazione

Evaluator e test possono essere progettati soltanto quando:

- [x] la prescrizione autorevole è l'ultimo snapshot immutabile comunicato;
- [x] le quattro dimensioni di esecuzione e la loro separazione sono definite;
- [x] meteo e obiettivo descrittivo sono contestuali e non bloccanti;
- [x] stati interni e testi utente sono definiti;
- [x] il perimetro iniziale della stabilità è definito;
- [x] quantità, intensità, copertura, compatibilità e divieto di conversioni
      implicite sono definiti;
- [x] tempistiche, matrice finale, Brick, sicurezza e applicazione ai soli nuovi
      episodi sono definite;
- [x] gerarchia delle sorgenti, matching con conferma, missingness per
      dimensione, report e perimetro della prima implementazione sono definiti;
- [ ] le decisioni residue della sezione 15 sono approvate e versionate;
- [ ] fixture esclusivamente sintetiche coprono tutti gli stati, la missingness,
      l'ambiguità, l'interruzione per sicurezza e i casi Brick;
- [ ] persistenza e audit conservano policy, analyzer, evidenza e provenienza
      senza dipendere dai payload grezzi.

Il completamento futuro della checklist autorizzerà la progettazione
dell'implementazione, ma non modificherà automaticamente lo stato di questo
documento. Fino a un'approvazione esplicita successiva, resta **DRAFT — NON
IMPLEMENTATO**.
