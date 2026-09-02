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
19. **Tolleranze.** Sono definite da policy versionate per disciplina e
    tipologia di seduta. Una regola specifica, esplicita e versionata contenuta
    nella prescrizione può sostituire la policy generale. Nessuna tolleranza è
    nascosta nell'evaluator.
20. **Dose complessiva.** Quantità/durata e intensità sono valutate
    separatamente e soltanto dopo sono combinate nella valutazione della dose
    complessiva mediante una policy esplicita e versionata.
21. **Fasce indipendenti.** I limiti inferiori e superiori sono indipendenti e
    distinguono una fascia principale e una fascia secondaria. Valori e criteri
    appartengono alla policy o alla regola specifica della prescrizione; questo
    draft non introduce soglie numeriche.
22. **Struttura.** La valutazione distingue blocchi obbligatori e facoltativi,
    ordine e `main_set`. Se i blocchi non sono ricostruibili, la gestione è
    prudente e la sola dimensione interessata è `INSUFFICIENT_DATA`.
23. **Intensità per blocco.** Ogni blocco valutabile dichiara metodo, unità,
    obiettivo e copertura richiesta. Non sono ammesse conversioni automatiche
    fra frequenza cardiaca, potenza, passo/velocità e RPE.
24. **Meteo non bloccante.** Per le attività outdoor è contestuale e
    facoltativo; per le attività indoor è `NOT_APPLICABLE`.
25. **Prima sorgente meteo.** Open-Meteo è la prima sorgente sostituibile, con
    riferimento alla [Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
    e alle [condizioni di utilizzo e pricing](https://open-meteo.com/en/pricing).
    Devono essere conservate attribuzione e provenienza. La richiesta usa
    coordinate approssimate e non trasmette l'intero tracciato GPS.
26. **Ruolo iniziale del meteo.** Nella prima versione spiega difficoltà e
    scostamenti, ma non applica correzioni matematiche automatiche e non cambia
    da solo lo stato della seduta.
27. **Matching e conferma.** Il matching è deterministico e dà priorità
    all'identificativo diretto. Nei casi ambigui richiede conferma all'atleta;
    prima della conferma l'episodio non entra nel learning.
28. **Tassonomia.** Distingue disciplina, ambiente indoor/outdoor, modalità e
    composizione `single`/`brick`/`multisport`.
29. **Gerarchia delle sorgenti.** L'ordine è: prescrizione IronCoach per quanto
    previsto; Garmin/dispositivo originale per i dati oggettivi eseguiti;
    Strava come integrazione o fallback; feedback dell'atleta per i dati
    soggettivi; Open-Meteo per i dati ambientali.
30. **Discordanze.** Dati discordanti non sono mediati né fusi
    automaticamente. Si conserva l'evidenza distinta secondo provenienza e si
    applica la gerarchia senza nascondere il conflitto.
31. **Missingness per dimensione.** La missingness è isolata alla dimensione
    interessata e il report viene comunque prodotto. Se una dimensione
    obbligatoria non è valutabile, manca un outcome complessivo definitivo. Il
    meteo rimane facoltativo.
32. **Report immediato.** Contiene seduta prevista, seduta eseguita, confronto
    dimensionale, contesto, valutazione della dose e, soltanto se supportate,
    indicazioni per la seduta successiva. Le analisi a 72 ore e 7 giorni
    restano interne.
33. **Questionario facoltativo.** Nessun questionario è obbligatorio. L'assenza
    di segnalazioni significa “nessun problema noto”, non certificazione di
    assenza di problemi.
34. **Feedback soggettivo.** È facoltativo e strutturato per RPE, dolore,
    affaticamento insolito, interruzioni e relative motivazioni.
35. **Perimetro della prima implementazione.** Comprende sedute continue quando
    i dati sono compatibili; intervalli soltanto quando blocchi e segmenti sono
    ricostruibili; Brick come sessione atomica con ordine e consecutività
    verificabili. Non usa proxy per tipologie non supportate.
36. **Linguaggio del report.** I testi mostrati sono comprensibili all'utente;
    codici tecnici, stati di elaborazione e dettagli di policy restano interni.

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
    environment: indoor | outdoor | null
    mode: string | null
    composition: single | brick | multisport
  allowed_substitutions: []
  quantity:
    applicability: REQUIRED | NOT_APPLICABLE
    primary_metric: duration | distance | sets_repetitions | per_segment
    target: object | null
    secondary_metrics: []
    evaluation_policy_id: string | null
    prescription_override: object | null
    bands:
      lower_limit: object | null
      upper_limit: object | null
      primary: object | null
      secondary: object | null
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
    environment: indoor | outdoor | null
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
    interruption: object | null
    interruption_reason: object | null
  weather_context: []
  data_quality:
    source_checked_at: datetime | null
    completeness: string
    missing_fields: []
    warnings: []
  provenance:
    normalized_at: datetime
```

Missingness resta esplicita e non diventa zero. Nessun questionario è
obbligatorio. Ogni elemento di
`source_activities` conserva ID e provenienza. Il matching deve essere
deterministico e privilegia l'identificativo diretto. Se più attività restano
candidate o la relazione è ambigua, nessuna viene scelta arbitrariamente: si
richiede conferma all'atleta, le sole dimensioni non dimostrabili diventano
`INSUFFICIENT_DATA` e l'episodio non entra nel learning prima della conferma.

La gerarchia delle sorgenti è prescrizione IronCoach, Garmin/dispositivo
originale, Strava come integrazione o fallback, feedback atleta per i dati
soggettivi e Open-Meteo per quelli ambientali. Evidenze discordanti conservano
ciascuna la propria provenienza: non sono mediate o fuse automaticamente.

Una interruzione motivata da sicurezza conserva ragione ed evidenza e usa un
testo neutro, non colpevolizzante. Non equivale automaticamente né a errore
dell'atleta né a esecuzione pienamente in linea.

## 5. Valutazione dell'esecuzione

### 5.1 Sport

Il confronto usa separatamente disciplina, ambiente indoor/outdoor, modalità e
composizione `single`/`brick`/`multisport`. La
compatibilità richiede coincidenza oppure un'autorizzazione esplicita nello
snapshot o in una policy versionata da esso richiamata. Questo vale anche per
indoor/outdoor. Somiglianza nominale, comune natura aerobica e attività
osservate a posteriori non autorizzano sostituzioni.

### 5.2 Quantità di lavoro

La quantità, inclusa la durata quando è la metrica primaria, è valutata sulla
metrica dichiarata: durata, distanza,
serie/ripetizioni o metrica per segmento. Metrica, rappresentazione e unità
devono essere compatibili secondo una policy esplicita e versionata per
disciplina e tipologia di seduta. Una regola specifica nella prescrizione può
sostituire la policy generale soltanto se è esplicita, versionata e auditabile.

Limite inferiore e limite superiore sono indipendenti. La policy distingue una
fascia principale e una fascia secondaria e assegna i relativi stati. Nessuna
tolleranza è codificata o nascosta nell'evaluator e nessun valore numerico è
definito in questo documento.

Le metriche secondarie arricchiscono il contesto ma non sostituiscono la
primaria. Non si converte automaticamente distanza in durata, durata in
distanza o una metrica di segmento in una metrica complessiva.

### 5.3 Intensità

La valutazione usa il metodo principale prescritto oppure un metodo secondario
esplicitamente ammesso. Per ogni blocco specifica metodo, unità, obiettivo e
copertura richiesta. Frequenza cardiaca, potenza, passo/velocità e RPE restano
metodi distinti e non vengono convertiti fra loro.

Per una seduta continua la policy valuta la copertura temporale. Per una seduta
a intervalli valuta separatamente i blocchi prescritti. Medie complessive non
dimostrano l'esecuzione dei singoli blocchi. Telemetria insufficiente produce
`INSUFFICIENT_DATA` per l'intensità senza invalidare automaticamente sport,
quantità o struttura.

### 5.4 Struttura

La struttura confronta blocchi obbligatori e facoltativi, ordine, `main_set`,
tipo, quantità applicabile, intensità applicabile, recupero applicabile e
consequenzialità dei segmenti. Il testo libero non viene trasformato a
posteriori in struttura osservabile. Blocchi o segmenti non ricostruibili sono
gestiti prudentemente: la struttura, o il solo blocco da cui dipende una
dimensione, diventa `INSUFFICIENT_DATA` senza inventare l'esecuzione.

### 5.5 Obiettivo della seduta

L'obiettivo è una dimensione valutabile solo con criteri strutturati,
osservabili e associati a una policy versionata. Se è generico o soltanto
testuale, ha `evaluability: CONTEXT_ONLY`: resta visibile come contesto, non
entra nell'aggregazione e non rende l'esecuzione insufficiente.

### 5.6 Quantità, intensità e dose/carico

Quantità/durata e intensità producono risultati separati. Soltanto dopo questa
valutazione sono combinate nella dose complessiva mediante una policy esplicita
e versionata. La combinazione non crea formule implicite: campi, regole,
provenienza e missingness della dose devono essere dichiarati e non possono
sostituire retroattivamente una delle due dimensioni.

## 6. Meteo contestuale

Il meteo è facoltativo e non è una dimensione di aderenza:

- per ogni segmento outdoor può essere registrato con sorgente, timestamp,
  località/provenienza e qualità;
- può spiegare o arricchire il report, ma non determina direttamente `MET` o
  `NOT_MET`;
- se manca, il report procede e non diventa `INSUFFICIENT_DATA`;
- per attività o segmenti indoor è `NOT_APPLICABLE`.

Nella prima versione Open-Meteo è la sorgente sostituibile prioritaria, secondo
la [Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
e le [condizioni di utilizzo e pricing](https://open-meteo.com/en/pricing).
Ogni osservazione conserva sorgente, attribuzione, timestamp, coordinate usate
e provenienza. Le richieste usano coordinate approssimate e non trasmettono
l'intero tracciato GPS.

Il meteo può spiegare difficoltà e scostamenti nel contesto del report, ma non
applica correzioni matematiche automatiche e non cambia da solo lo stato di una
dimensione o della seduta.

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

Nel report i codici tecnici restano interni e sono tradotti nei testi utente
approvati. Anche motivazioni, contesto e indicazioni devono usare un linguaggio
comprensibile, senza esporre identificativi di policy o stati di elaborazione.

## 8. Stabilità generale iniziale

La stabilità è distinta dall'esecuzione. Nella prima versione:

- il recovery è valutato automaticamente tramite analyzer e categorie già
  approvati;
- i problemi riferiti dall'atleta sono considerati come segnali di sicurezza;
- l'assenza di problemi riferiti è `NO_KNOWN_ISSUE`, cioè assenza di problemi
  noti nella sorgente, e non certificazione clinica;
- il feedback soggettivo è facoltativo e, quando fornito, è strutturato per
  RPE, dolore, affaticamento insolito, interruzioni e motivazioni;
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
mantiene la propria identità. Viene prodotto anche quando una dimensione è
`INSUFFICIENT_DATA` e presenta, nell'ordine:

1. seduta prevista;
2. seduta eseguita;
3. confronto dimensionale;
4. contesto;
5. valutazione della dose;
6. indicazioni per la seduta successiva, soltanto quando supportate
   dall'evidenza disponibile.

Il recovery disponibile viene usato prima della
seduta successiva. Le osservazioni a 72 ore e 7 giorni servono esclusivamente
al trend interno e non generano un nuovo report della vecchia seduta.

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

La missingness resta isolata nella dimensione interessata, così le altre parti
del confronto e il report immediato rimangono disponibili. Se una dimensione
obbligatoria non è valutabile, tuttavia, non viene prodotto un outcome
complessivo definitivo e l'aggregazione resta `INSUFFICIENT_DATA`. Il meteo non
è mai una dimensione obbligatoria.

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

La prima implementazione, quando sarà autorizzata, è limitata a:

- sedute continue, quando metrica, unità, metodo e dati sono compatibili;
- intervalli, soltanto quando blocchi e segmenti sono ricostruibili;
- Brick trattate come singole sessioni atomiche, soltanto quando ordine e
  consecutività sono verificabili.

Tipologie non supportate o non ricostruibili restano non valutabili. Non si
usano proxy per estendere artificialmente il perimetro.

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

- valori ammessi nella tassonomia separata di disciplina, ambiente, modalità e
  composizione;
- schema delle sostituzioni esplicite e relativa governance;
- forma canonica di target, osservazioni e unità per ciascuna metrica primaria;
- contenuti numerici delle policy versionate e delle eventuali regole
  specifiche di prescrizione per limiti e fasce;
- metodi d'intensità inizialmente supportati e valori delle policy di copertura
  temporale o per blocco;
- schema canonico dei segmenti, mantenendo le regole approvate su blocchi,
  ordine, `main_set`, matching e Brick;
- policy di aggregazione delle quattro dimensioni di esecuzione nei livelli
  `IN_LINE`, `PARTIALLY_IN_LINE`, `DIFFERENT` e `INSUFFICIENT_DATA`;
- regole operative di freshness, completezza e gestione dei segnali
  contraddittori per la stabilità iniziale;
- schema definitivo e retention dei dati soggettivi, di sicurezza e meteo;
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
- [x] tolleranze, limiti indipendenti, fasce e override della prescrizione hanno
      una governance esplicita senza soglie numeriche inventate;
- [x] matching, gerarchia delle sorgenti, discordanza e conferma dell'atleta
      sono definiti senza fusioni automatiche;
- [x] struttura del report, feedback facoltativo, linguaggio utente e perimetro
      della prima implementazione sono definiti;
- [x] Open-Meteo è indicata come prima sorgente ambientale sostituibile con
      attribuzione, provenienza e minimizzazione delle coordinate;
- [ ] le decisioni residue della sezione 15 sono approvate e versionate;
- [ ] fixture esclusivamente sintetiche coprono tutti gli stati, la missingness,
      l'ambiguità, l'interruzione per sicurezza e i casi Brick;
- [ ] persistenza e audit conservano policy, analyzer, evidenza e provenienza
      senza dipendere dai payload grezzi.

Il completamento futuro della checklist autorizzerà la progettazione
dell'implementazione, ma non modificherà automaticamente lo stato di questo
documento. Fino a un'approvazione esplicita successiva, resta **DRAFT — NON
IMPLEMENTATO**.
