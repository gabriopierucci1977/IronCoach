# Nota post-audit

I cinque problemi P0 identificati in questo audit sono stati corretti nel pass di hardening Beta 0.3.1 descritto in `BETA_0_3_1_HARDENING.md`. Il resto del documento conserva lo stato ricostruito dello snapshot Beta 0.3.

---

# IronCoach — Project State Audit

**Snapshot analizzato:** Beta 0.3
**Commit incorporato nello ZIP:** `18960e4f30264ce8234320e715afa719b921e5b7`
**Fonte:** `IronCoach-main.zip`
**Scopo:** ricostruire lo stato reale del progetto dopo la perdita della conversazione di sviluppo e definire un punto di ripartenza affidabile.

---

## 1. Stato generale

IronCoach è già un backend di coaching modulare sostanziale, non un semplice prototipo.

La pipeline implementata è:

```text
Airtable / Input atleta
        ↓
Context Builder
        ↓
Coach Engine
   ┌────┴─────┐
   ↓          ↓
Recovery   Performance
Analyzer    Analyzer
   ↓          ↓
Load       Recovery Trend
Analyzer    Analyzer
   └────┬─────┘
        ↓
Adaptation Analyzer
        ↓
Decision Engine
        ↓
Decision Model
   ┌────┴─────┐
   ↓          ↓
Report      Decision
Builder     Writer
   ↓          ↓
Coach      Airtable
Report     Decision Log
```

Vocabolario decisionale principale:

- `CONFERMA` → `KEEP_PLAN`
- `ADATTA` → `ADAPT`
- `RECUPERA` → `RECOVERY`

Stati freshness:

- `CURRENT`
- `STALE`
- `FUTURE`
- `UNKNOWN`

La configurazione runtime consente di impostare via ambiente le soglie di freschezza e i cap di confidenza.

---

## 2. Inventario del repository

Lo ZIP contiene **125 file reali** più directory.

Struttura principale:

```text
.env.example
.gitignore
README.md
backend/
backups/
config/
docs/
scripts/
tests/
pytest.ini
requirements.txt
```

Distribuzione file:

- `tests/`: 66
- `backend/`: 46
- `config/`: 5
- altri file e README di supporto.

Il codice Python backend è circa **20,9k righe**; i test Python circa **13,3k righe**.

`data/` è esclusa da Git tramite `.gitignore`, quindi gli archivi Garmin e alcuni fixture binari non sono presenti nello snapshot GitHub.

---

## 3. Runtime e orchestrazione

### `backend/main.py`

Implementa la pipeline completa con gestione degli errori per fase.

Supporta `--dry-run`:

- costruisce il contesto;
- esegue il Coach Engine;
- adatta il workout;
- genera il report;
- evita la persistenza della decisione quando richiesto.

La stessa `RuntimeConfig` viene condivisa tra Context Builder e Coach Engine.

### `backend/config.py`

Contiene una `RuntimeConfig` immutabile con configurazione derivata dall'ambiente.

Default principali:

- recovery current max age: 3 giorni;
- training current max age: 7 giorni;
- confidence cap con freshness HIGH: 75;
- confidence cap con freshness MODERATE: 85.

La normalizzazione garantisce un ordine coerente dei cap.

### `config/settings.py`

Carica tramite dotenv:

- `AIRTABLE_API_KEY`
- `AIRTABLE_BASE_ID`
- `OPENAI_API_KEY`

`openai` è presente nelle dipendenze e nelle variabili di configurazione, ma nello snapshot non risulta ancora utilizzato dal backend operativo.

---

## 4. Context Builder

`ContextBuilder v3` costruisce il contesto completo dell'atleta.

Integra:

- profilo atleta;
- recovery corrente;
- training corrente;
- nutrition corrente;
- ultima decisione;
- storico training Airtable;
- archivio Garmin persistente opzionale;
- storico recovery;
- storico performance;
- freshness;
- warning di contesto;
- conteggi delle sorgenti;
- athlete profile intelligence.

L'archivio Garmin di default è:

```text
data/garmin/garmin_activities_merged.jsonl.gz
```

Se non esiste, il sistema degrada in modo controllato e genera un warning invece di interrompere la pipeline.

Il merge training cross-source privilegia Airtable nei duplicati perché Airtable può contenere RPE, note e carico interno soggettivo.

---

## 5. Modelli e normalizzazione

### Modelli core

Sono presenti dataclass per:

- `IronCoachActivity`
- `IronCoachActivitySegment`

con campi per:

- ID e sorgente;
- timing;
- sport/tipo;
- durata;
- distanza;
- dislivello;
- calorie;
- velocità;
- frequenza cardiaca;
- cadenza;
- potenza;
- training load/effect;
- segmenti;
- metadata.

### Normalizzatori

Sono presenti:

- `ActivityNormalizer`
- `AthleteNormalizer`
- `RecoveryNormalizer`

più le astrazioni:

- `TrainingHistory`
- `RecoveryHistory`
- `PerformanceHistory`
- `HistoryBuilder`

---

## 6. Athlete Profile Engine

`AthleteProfileEngine v0.2` deriva:

- tipo atleta;
- punti di forza;
- limitazioni;
- preferenze di allenamento;
- injury patterns;
- goal profile.

Goal supportati:

- `EVENTO`
- `PERFORMANCE`
- `BENESSERE`
- `NON DEFINITO`

### Gap rilevato

`_load_tolerance()` è ancora un placeholder e restituisce sostanzialmente:

```text
DA STIMARE
Storico Garmin/Strava non ancora disponibile
```

Questa assunzione è ormai obsoleta perché l'integrazione Garmin è stata implementata.

---

## 7. Analyzer

### Recovery Analyzer v0.4

Classifica recovery in:

- `VERDE`
- `GIALLO`
- `ROSSO`

con severity interna LOW / MODERATE / CRITICAL.

### Training Analyzer v0.3

Considera:

- RPE;
- tipo seduta;
- zona;
- durata;
- carico interno.

### Injury Analyzer v0.4

Considera:

- dolore/problema corrente;
- pain score;
- storico dell'atleta;
- limitazioni.

Livelli:

- `UNKNOWN`
- `LOW`
- `MODERATE`
- `HIGH`
- `CRITICAL`

### Nutrition Analyzer

Combina lo stato dei dati nutrizionali e produce:

- `LOW`
- `MODERATE`
- `HIGH`
- `UNKNOWN`

### Load Analyzer v0.4

Usa:

- acute window ~7 giorni;
- chronic window ~28 giorni;
- carico complessivo;
- ACWR.

Soglie principali implementate:

- LOW sotto 500;
- HIGH da 2000;
- altrimenti NORMAL.

### Performance Analyzer v0.3

Metriche supportate:

- FTP;
- CSS;
- VO2max run;
- VO2max bike.

Gestisce formati verticali e wide e classifica il trend rispetto a una soglia di circa ±2%.

### Recovery Trend Analyzer v0.1

Confronta finestre recenti e precedenti e produce anche data quality:

- `NONE`
- `LIMITED`
- `GOOD`

### Adaptation Analyzer v0.2

Combina:

- load;
- performance;
- recovery;
- limitazioni.

Output:

- `GOOD`
- `MODERATE`
- `LIMITED`
- `UNKNOWN`

---

## 8. Coach Engine e Decision Engine

### Coach Engine v6.9.5

È l'orchestratore degli analyzer.

Esegue l'analisi e passa gli assessment al Decision Engine; aggiunge inoltre l'intelligence dell'atleta alla decisione finale.

### Decision Engine v6.8

È già un rule engine ampio e strutturato.

Ordine logico principale delle decisioni:

1. injury critica → `RECUPERA`
2. recovery critica → `RECUPERA`
3. recovery moderata + load alto + recovery trend in calo → `RECUPERA`
4. recovery moderata + injury alta → `RECUPERA`
5. recovery moderata + training alto + nutrition alta → `RECUPERA`
6. recovery buona + training alto + load alto → `ADATTA`
7. recovery buona + nutrition alta → `ADATTA`
8. adaptation `LIMITED` → `RECUPERA`
9. adaptation `MODERATE` → `ADATTA`
10. performance in calo + load alto → `ADATTA`
11. recovery `UNKNOWN` con stress → `RECUPERA`, altrimenti `ADATTA`
12. almeno due fattori secondari moderati → `ADATTA`
13. goal `BENESSERE` + training/load HIGH → `RECUPERA`
14. default → `CONFERMA / KEEP_PLAN`

La freshness **non cambia la strategia**, ma riduce la confidenza massima.

La training priority viene derivata da goal e strategia:

- `RIPRISTINO`
- `SPECIFICITA_GARA`
- `SVILUPPO_PRESTAZIONE`
- `CONTINUITA`
- `STANDARD`

Il reason e la recommended action vengono personalizzati anche usando athlete type, goal e training priority.

### Nota architetturale

Il Decision Engine conserva parte dello stato corrente in attributi d'istanza. È adatto all'attuale esecuzione CLI sequenziale, ma andrà reso request-local prima di un futuro uso concorrente/server.

---

## 9. Workout Adapter

`WorkoutAdapter` è già un componente avanzato e non una semplice riduzione percentuale.

Gestisce:

- RUN;
- BIKE;
- SWIM;
- fallback generico.

Strategie operative:

- `KEEP_PLAN`
- `ADAPT`
- `REDUCE_LOAD`
- `RECOVERY`

Tiene conto della training priority e del goal.

Esempi:

- `SPECIFICITA_GARA` → blocchi specifici controllati;
- `SVILUPPO_PRESTAZIONE` → qualità controllata;
- `CONTINUITA` → prevalenza Z1-Z2, eliminazione degli stimoli troppo intensi;
- `RIPRISTINO` → recupero attivo e rimozione della qualità.

---

## 10. Report e persistenza decisione

### Report Builder v0.3.1

Include sezioni per:

- atleta;
- recovery;
- training;
- nutrition;
- context warnings;
- coach summary;
- profilo atleta;
- carico recente;
- adattamento al carico;
- recovery trend;
- performance trend;
- freschezza dati;
- ultima decisione;
- decisione corrente;
- workout modificato.

### Decision Writer

Persistenza Airtable dei campi:

- Data
- Decisione IronCoach
- Motivazione
- Confidenza
- Azione consigliata
- Allenamento modificato
- Priorità
- Priorità allenante
- Strategia

È presente protezione anti-duplicato per decisioni equivalenti nello stesso giorno.

### Disallineamento documentazione/codice

Il README lascia intendere che vengano mantenuti anche:

- risk level;
- reasoning;
- intelligence.

Il writer attuale non persiste questi tre elementi. Va deciso se estendere lo schema Airtable o correggere la documentazione.

---

## 11. Integrazione Airtable

Il client gestisce le tabelle:

- Athlete Profile
- Recovery Log
- Training Log
- Nutrition Log
- Decision Log
- Performance Log

La performance history supporta sia un log dedicato sia un fallback sul profilo atleta.

---

## 12. Sottosistema Garmin

Questa è una delle parti più sviluppate della Beta 0.3.

Sono presenti:

- import delle attività Garmin riassunte in JSON;
- historical importer;
- matching summary/raw;
- classificazione `SAFE / REVIEW / JSON_ONLY`;
- secure extraction FIT/TCX/GPX da ZIP;
- protezione path traversal;
- hash e manifest;
- import FIT;
- supporto multisport;
- merge summary + raw;
- mantenimento dei segmenti multisport;
- export JSONL/gzip atomico;
- SHA256/manifest;
- archivio persistente indicizzato in memoria;
- query latest/between/sport/stats;
- export incrementale;
- filtering degli ID già archiviati prima del parsing raw;
- idempotenza;
- nessuna riscrittura se non ci sono nuove attività;
- incompatibilità controllata tra `--incremental` e `--force`.

---

## 13. Audit test

La documentazione dichiara **372 test passed**.

Lo snapshot attuale raccoglie invece:

**373 test**

Nel sandbox mancavano inizialmente `pyairtable` e `fitparse`, quindi la raccolta non poteva partire.

Per verificare il codice senza modificare il progetto sono stati usati **stub temporanei esclusivamente per gli import**.

Risultato:

```text
373 test raccolti
368 passed
5 failed
```

I 5 failure appartengono esclusivamente a:

- `tests/test_garmin_importer.py`
- `tests/test_garmin_multisport.py`

e falliscono perché nello ZIP GitHub non sono presenti i fixture binari gitignored:

```text
data/garmin_raw/4872731416_ACTIVITY.fit
data/garmin_raw/14891176843_ACTIVITY.fit
```

Escludendo questi test dipendenti dai file esterni:

```text
368 passed
```

È stata inoltre eseguita la compilazione Python di backend/config/tests:

```text
COMPILE_OK
```

Questo non sostituisce un test con le vere dipendenze installate e i fixture Garmin, ma non sono emersi failure logici nei 368 test eseguibili nello snapshot.

---

## 14. Copertura indicativa

Sui 368 test eseguibili nell'ambiente di audit la copertura complessiva è risultata circa **91%** considerando progetto e test nel calcolo.

Moduli core con copertura molto alta includono:

- config;
- context builder;
- decision model;
- decision writer;
- decision engine;
- report builder;
- main;
- workout adapter;
- performance analyzer;
- Garmin archive/exporter/historical importer.

Aree meno coperte:

- Injury Analyzer;
- Nutrition Analyzer;
- Recovery Analyzer;
- Training Analyzer;
- Airtable client;
- FIT importer.

Parte della bassa copertura FIT è spiegata dall'assenza dei file Garmin raw nello ZIP.

---

# 15. Problemi di integrazione critici scoperti

Questa è la parte più importante dell'audit.

I singoli componenti sono ben testati, ma alcuni test utilizzano direttamente il formato atteso dal singolo analyzer. Quando invece i dati percorrono la pipeline reale `Normalizer → Analyzer`, emergono contratti non allineati.

## P0.1 — ActivityNormalizer → TrainingAnalyzer

Il normalizzatore produce principalmente:

```text
rpe
intensity
duration_minutes
training_load
raw
```

Il Training Analyzer cerca invece molte informazioni nei campi legacy:

```text
Tipo seduta / tipo_seduta
Zona prevista / zona_prevista
Durata minuti / durata_minuti
Carico interno / carico_interno
```

e non usa `raw`.

Riproduzione dell'audit:

- stessa seduta raw, analizzata direttamente → `HIGH`
- seduta passata prima da ActivityNormalizer → `MODERATE`

Vengono perse informazioni su tipo, zona, durata e carico.

**Impatto:** possibile sottostima dello stress allenante nella pipeline reale.

---

## P0.2 — ActivityNormalizer → InjuryAnalyzer

ActivityNormalizer non promuove i dati di dolore/problema corrente nel contratto normalizzato; restano nel blocco `raw`.

InjuryAnalyzer cerca invece i campi top-level.

Riproduzione:

- dolore severo + pain score 9 direttamente all'Injury Analyzer → `CRITICAL`
- stesso input normalizzato prima con ActivityNormalizer → `UNKNOWN` in assenza di storico utile.

**Impatto:** safety-critical. Un dolore corrente può scomparire dalla valutazione prima del Decision Engine.

**Questo è il primo bug da correggere.**

---

## P0.3 — RecoveryHistory → RecoveryTrendAnalyzer

RecoveryHistory struttura il sonno come:

```python
sleep = {
    "score": ...,
    "hours": ...
}
```

RecoveryTrendAnalyzer non discende correttamente nel campo `score`.

Riproduzione:

- sleep score 50 → 70
- trend recovery generale: `IMPROVING`
- `sleep_trend`: `UNKNOWN`

**Impatto:** perdita di intelligence specifica sul trend del sonno.

---

## P0.4 — Missing training load trasformato in zero reale

ActivityNormalizer usa `0` come default quando il training load manca.

LoadAnalyzer contiene logica per ignorare carichi mancanti, ma dopo la normalizzazione non può più distinguere:

```text
carico realmente 0
```

da

```text
carico non disponibile
```

Riproduzione:

- seduta senza load → viene contata come sessione con load zero;
- il risultato può diventare `LOW` invece di `UNKNOWN / dati insufficienti`.

**Impatto:** può far apparire basso un carico che in realtà è semplicemente sconosciuto e alterare ACWR/load assessment.

---

## P0.5 — AdaptationAnalyzer non vede correttamente le limitazioni normalizzate

AthleteNormalizer conserva le limitazioni in:

```text
constraints.physical_limitations
```

AdaptationAnalyzer cerca invece:

```text
profile["limitations"]
```

Riproduzione:

- profilo flat con limitazione Achille → adaptation `MODERATE`
- stesso profilo nella forma normalizzata → adaptation `GOOD`

**Impatto:** le limitazioni fisiche possono essere sottopesate nell'analisi dell'adattamento.

---

## 16. Perché i test esistenti non hanno intercettato i P0

La suite ha una buona copertura dei componenti, ma molti analyzer testano input costruiti direttamente nel formato atteso dall'analyzer.

I test di integrazione usano in diversi casi context/fake già preparati, anziché percorrere sempre:

```text
raw Airtable
→ normalizer
→ history
→ CoachEngine
→ analyzer
→ DecisionEngine
```

Quindi i componenti possono essere corretti singolarmente ma incompatibili ai confini.

La priorità di sviluppo deve diventare **contract testing end-to-end**.

---

## 17. Altri gap e debito tecnico

### Durata attività

ActivityNormalizer usa una euristica:

- valore numerico > 300 → assume secondi e divide per 60.

Questo rende ambigua una reale durata endurance superiore a 300 minuti.

Esempio:

```text
360 minuti
```

potrebbero essere interpretati come:

```text
6 minuti
```

Per un sistema dedicato anche a endurance/Ironman è un rischio concreto.

### Dedupe cross-source

Il dedupe può considerare duplicate due attività dello stesso sport distanti fino a circa un giorno se durata/distanza sono molto simili.

È utile, ma potrebbe produrre falsi positivi su sessioni ripetute in giorni consecutivi.

### Packaging e riproducibilità

Nello snapshot non risultano:

- CI workflow;
- `pyproject.toml`;
- pin delle versioni delle dipendenze;
- dichiarazione esplicita della versione Python;
- LICENSE.

`requirements.txt` contiene dipendenze non pinnate.

### Cartelle documentali

I README interni di varie cartelle sono ancora quasi placeholder.

### Moduli molto grandi

Alcuni file sono diventati molto estesi, in particolare:

- Decision Engine;
- Workout Adapter;
- Report Builder;
- Coach Engine.

Non è un blocco immediato, ma prima di trasformare IronCoach in un servizio concorrente converrà modularizzarli.

---

## 18. Ricostruzione probabile della sequenza di sviluppo

Dalla struttura del codice e dalla suite emerge questa evoluzione:

1. fondazione Airtable + analyzer + decision/report;
2. normalizzazione e history abstraction;
3. athlete profile intelligence e goal profile;
4. Garmin historical import/export/archive;
5. raw Garmin merge + multisport;
6. export incrementale/idempotente;
7. freshness e confidence cap configurabili;
8. evoluzione Workout Adapter goal-aware;
9. propagazione end-to-end della `training_priority`;
10. dry-run e hardening Beta 0.3.

L'area più recente appare fortemente concentrata sulla propagazione della training priority attraverso:

```text
DecisionEngine
→ CoachEngine
→ WorkoutAdapter
→ Report
→ DecisionWriter
→ main
```

---

# 19. Stato reale della Beta 0.3

## Parti solide

- architettura modulare;
- rule-based Decision Engine;
- Workout Adapter sport-aware e goal-aware;
- Context Builder;
- freshness/confidence;
- Garmin historical subsystem;
- decision/report pipeline;
- ampia suite di test;
- dry-run;
- persistenza Airtable;
- athlete intelligence;
- training priority end-to-end.

## Parti da considerare incomplete prima della Beta 0.4

- contratto canonico Normalizer ↔ Analyzer;
- conservazione dei segnali injury correnti;
- semantica missing-vs-zero del training load;
- sleep trend;
- limitations nel Adaptation Analyzer;
- load tolerance reale;
- persistenza completa di reasoning/risk/intelligence;
- strategia esplicita per unità di durata;
- riproducibilità CI/dependency pinning.

---

# 20. Piano di ripartenza raccomandato

## Fase 0 — Hardening immediato

Ordine consigliato:

1. **correggere la perdita di current injury/pain**
2. definire il contratto canonico di `NormalizedActivity`
3. allineare TrainingAnalyzer al contratto normalizzato
4. preservare `None` quando training load è sconosciuto
5. correggere sleep score nel RecoveryTrendAnalyzer
6. passare correttamente le physical limitations all'AdaptationAnalyzer
7. aggiungere regression test reali `raw → normalizer → analyzer`
8. aggiungere almeno un test `ContextBuilder → CoachEngine → DecisionEngine` per ciascun P0

## Fase 1 — Beta 0.3.1 hardening

- eliminare l'euristica ambigua della durata;
- implementare load tolerance da storico reale Garmin/Airtable;
- allineare DecisionWriter e README;
- definire una strategia per i fixture Garmin;
- pin dipendenze e Python version;
- aggiungere CI;
- aggiornare conteggio test/documentazione.

## Fase 2 — Beta 0.4

Solo dopo il completamento della Fase 0 conviene riaprire lo sviluppo funzionale e decidere le nuove capacità di coaching/intelligence.

---

# 21. Decisione di progetto

**IronCoach Beta 0.3 non deve essere riscritto.**

La base è ampia, coerente e già ben sviluppata.

Il prossimo lavoro non dovrebbe essere l'aggiunta immediata di nuove feature, ma un breve ciclo di **integration-contract hardening**.

La priorità assoluta è la pipeline injury:

```text
Airtable/Input
→ ActivityNormalizer
→ InjuryAnalyzer
→ DecisionEngine
```

perché al momento un segnale di dolore corrente può essere perso durante la normalizzazione.

Una volta chiusi i cinque P0 e aggiunti i regression test end-to-end, il progetto avrà una base molto più sicura per evolvere verso Beta 0.4.

---

*Questo documento rappresenta il nuovo stato di riferimento ricostruito del progetto IronCoach a partire dallo snapshot Beta 0.3.*
