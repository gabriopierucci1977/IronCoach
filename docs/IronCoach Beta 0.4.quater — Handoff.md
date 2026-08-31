# IronCoach Beta 0.4.quater — Handoff

**Data handoff:** 31 agosto 2026
**Branch:** `feature/beta-0.4-decision-memory`
**Ultimo commit codice prima dell'handoff:** `3c180d1`
**Commit:** `feat: show observational Garmin recovery and performance`

---

## 1. Stato generale

IronCoach Beta 0.4 è in sviluppo sul branch:

`feature/beta-0.4-decision-memory`

Stato al momento di questo handoff:

- working tree pulito prima della creazione del presente file;
- branch locale sincronizzato con origin;
- ultimo commit remoto codice: `3c180d1`;
- suite completa:
  - **500 passed**
  - **5 skipped**
  - circa 2.21 s;
- Decision Memory end-to-end operativa;
- Garmin storico ricostruito;
- Garmin live collegato automaticamente al runtime;
- Garmin Recovery acquisito come evidenza osservativa separata;
- Garmin Performance acquisita come evidenza osservativa separata;
- Garmin fueling demand acquisito automaticamente dalle attività;
- Recovery, Performance e fueling Garmin sono visibili nel report
  senza modificare la logica decisionale;
- primo run reale end-to-end completato con successo;
- nessuna regressione nota nella suite.

---

## 2. Obiettivo Beta 0.4

Obiettivo principale:

> IronCoach deve imparare dalla risposta dell'atleta alle decisioni precedenti e usare quell'esperienza per migliorare le decisioni future.

Principi invarianti:

- `DecisionEngine` deterministico;
- la sicurezza ha sempre priorità;
- Decision Memory può modificare la confidenza soltanto entro limiti controllati;
- Decision Memory non cambia arbitrariamente decisione o regola;
- missing data non significa automaticamente esito positivo o negativo;
- attività mancante non significa automaticamente mancata aderenza;
- dati vecchi non devono essere interpretati come stato corrente;
- una fonte aggiornata e un dato fisiologico valutabile sono concetti distinti;
- metriche Garmin differenti non devono essere equiparate soltanto perché usano scale simili.

---

## 3. Decision Memory implementata

### Outcome windows

- 24h
- 72h
- 7d

### Outcome status

- `POSITIVE`
- `NEUTRAL`
- `NEGATIVE`
- `INSUFFICIENT_DATA`

### Intent

- `PROTECT_INJURY`
- `RESTORE_RECOVERY`
- `REDUCE_LOAD`
- `RESTORE_FUELING`
- `PROTECT_PERFORMANCE`
- `MAINTAIN_PLAN`
- `MANAGE_UNCERTAINTY`

### Adherence

- `FOLLOWED`
- `PARTIALLY_FOLLOWED`
- `NOT_FOLLOWED`
- `UNKNOWN`

Regola:

> attività assente ≠ `NOT_FOLLOWED`

### Episode lifecycle

- `OPEN`
- `WAITING_FOR_ACTIVITY`
- `WAITING_FOR_OUTCOME`
- `COMPLETE`
- `INCOMPLETE`

### Persistenza

SQLite:

`data/ironcoach_memory.db`

Identità:

- episode UUID4;
- decision UUID4;
- athlete_id derivato dall'identità Airtable normalizzata;
- activity source/id conservati.

Il runtime elabora episodi precedenti pendenti prima di creare la nuova decisione.

Il matching attività è conservativo e non indovina in caso di ambiguità.

---

## 4. Learning layer

Componenti:

- `learning_analyzer.py`
- `learning_policy.py`
- `learning_service.py`

Repository:

- `list_evaluated_by_athlete`

Orchestrator:

- `learning_service` opzionale;
- `build_learning_evidence`

Factory:

- repository condiviso.

DecisionEngine:

- riceve `assessments["decision_memory"]`;
- espone l'evidenza Decision Memory nell'intelligence della regola selezionata.

CoachEngine:

- conserva l'intelligence proveniente dal DecisionEngine.

Main:

- Decision Memory viene collegata prima del CoachEngine.

### Policy learning

- minimo 3 outcome valutabili;
- delta confidenza massimo ±5;
- `INSUFFICIENT_DATA` escluso dal denominatore;
- nessun cambio automatico di decisione o regola;
- `HIGH_ALERT` non modificato dalla memoria;
- cap di freschezza applicato dopo l'aggiustamento Decision Memory.

---

## 5. Outcome loop end-to-end

Commit storico principale:

`3a015c6 feat: connect decision memory outcome loop end to end`

Il runtime gestisce:

1. episodi `WAITING_FOR_ACTIVITY`;
2. matching dell'attività;
3. adherence;
4. recovery outcomes;
5. learning evidence;
6. nuova decisione.

### Adherence

- stesso sport → `FOLLOWED`
- sport differente → `NOT_FOLLOWED`
- attività assente → `UNKNOWN`

### Recovery outcome

Componenti:

- `recovery_outcome_evaluator.py`
- `recovery_outcome_processor.py`

Finestre con granularità giornaliera:

- 24h → giorno +1;
- 72h → giorni +2 / +3;
- 7d → giorni +4 ... +7.

Una finestra maturata senza dati recovery realmente valutabili produce:

`INSUFFICIENT_DATA`

---

## 6. Airtable

Configurazione locale tramite `.env`.

Variabili richieste:

- `AIRTABLE_API_KEY`
- `AIRTABLE_BASE_ID`

Non inserire mai credenziali o token nel repository o negli handoff.

`.env` è ignorato da Git.

### Dati di sviluppo

Le vecchie righe fake presenti nelle tabelle operative sono state eliminate dopo backup.

Backup locale:

`/home/codespace/ironcoach_airtable_backup_20260826_121223.json`

Conservato il profilo atleta reale.

Le tabelle operative erano state azzerate:

- Training Log
- Recovery Log
- Nutrition Log
- Performance Log
- Decision Log

Dopo il primo run reale del 28/08/2026 è stata nuovamente salvata una decisione reale nel `Decision Log`.

---

## 7. Cronologia Airtable

Fix già completato:

`298aaf5 fix: preserve airtable history chronology`

Problema:

record Recovery dello stesso giorno potevano essere ordinati in modo ambiguo.

Correzione:

lo storico Airtable viene ordinato usando:

`(date_field, createdTime)`

oppure `createdTime` quando non esiste il campo data.

---

## 8. Archivio storico Garmin

Archivio Garmin Connect ufficiale originale disponibile localmente.

File nel Codespace:

`data/garmin/Archivio Garmin.zip`

`data/` è ignorato da Git.

Dall'export ufficiale sono state ricostruite inizialmente:

**3858 attività storiche**

Intervallo originale:

- prima: `2011-07-22T18:44:06Z`
- ultima storica: `2026-07-30T04:10:16Z`

Archivio merged:

`data/garmin/garmin_activities_merged.jsonl.gz`

Manifest:

`data/garmin/garmin_activities_merged.jsonl.gz.manifest.json`

SHA-256 dell'archivio storico originale da 3858 attività:

`3a806bd09e6fdb97cfa44b8c3f8e9157a1850af960500a77c85e1bc91927b54c`

L'archivio è locale e ignorato da Git.

---

## 9. Garmin Connect live

Commit principale:

`95759f8 feat: integrate live Garmin sync and personalized load`

Dipendenza:

`garminconnect==0.3.11`

Configurazione:

`.env.example`

contiene:

`GARMINTOKENS=data/garmin/auth`

Il runtime usa token persistenti locali.

Non memorizzare email/password Garmin nel repository.

Il client Garmin è non ufficiale e viene usato soltanto per operazioni read-only.

### Token-only login

Verificato con successo:

`Garmin().login(tokenstore=...)`

Il tokenstore locale è ignorato da Git.

---

## 10. Garmin live activity adapter

File:

`backend/importers/garmin_live_activity_adapter.py`

Converte il formato API live Garmin in:

`IronCoachActivity`

Il formato live differisce materialmente dall'export storico.

Campi verificati:

- activityId
- activityType
- startTimeGMT
- duration
- distance
- elevation
- calories
- speed
- averageHR
- maxHR
- averagePower
- normalizedPower
- activityTrainingLoad
- aerobicTrainingEffect
- anaerobicTrainingEffect

Unità live principali:

- durata: secondi;
- distanza/elevazione: metri;
- calorie: kcal;
- velocità: m/s.

---

## 11. Garmin live sync

File:

`backend/importers/garmin_live_sync.py`

Stato sorgente:

`data/garmin/garmin_live_sync_state.json`

Il sync:

1. valida l'archivio esistente;
2. parte dalla data dell'ultima attività archiviata;
3. effettua login token-only;
4. chiama Garmin Connect;
5. converte le attività;
6. aggiorna incrementalmente l'archivio;
7. valida nuovamente l'archivio;
8. calcola `last_activity_at`;
9. aggiorna `source_checked_at` soltanto dopo successo completo.

### Primo sync reale

Archivio:

- prima: 3858
- fetched: 39
- nuove: 38
- duplicate/skipped: 1
- dopo: **3896**

Ultima attività:

`2026-08-27T09:00:42Z`

### Idempotenza

Secondo sync reale:

- count prima: 3896
- count dopo: 3896
- nuove: 0
- skipped: 1
- `last_activity_at` invariato;
- `source_checked_at` avanzato.

Contratto validato:

> una sorgente Garmin può essere verificata come aggiornata anche senza nuove attività.

---

## 12. `source_checked_at` e `last_activity_at`

Distinzione ora implementata:

### `last_activity_at`

Data dell'ultima attività reale disponibile.

### `source_checked_at`

Data dell'ultima verifica Garmin completata con successo.

Non usare:

`manifest.created_at`

come sostituto di `source_checked_at`.

Questo permette di distinguere:

### Archivio vecchio / sorgente non verificata

Nessuna conclusione sul carico corrente.

### Fonte aggiornata / nessuna attività recente

Possibile vero stop, detraining, infortunio, pausa o assenza di allenamento.

Principio:

> nessuna attività recente è informativa soltanto se sappiamo che la fonte è realmente aggiornata.

---

## 13. Sync Garmin automatico nel runtime

Commit:

`3b772ac feat: sync Garmin automatically before decisions`

Il normale runtime ora tenta automaticamente il Garmin live sync prima di costruire il contesto.

### Run normale

- tenta Garmin live sync;
- aggiorna archivio e source state in caso di successo;
- poi costruisce il `ContextBuilder`.

### Fallimento Garmin

Il sync è:

**best-effort / non bloccante**

Se Garmin è temporaneamente indisponibile:

- la pipeline continua;
- il vecchio archivio valido resta utilizzabile;
- il vecchio `source_checked_at` non viene avanzato;
- viene aggiunto un warning al contesto.

### Dry-run

`--dry-run` NON esegue il sync Garmin.

Motivo:

il sync scrive archivio e state file locali e quindi violerebbe la semantica di dry-run senza persistenza.

---

## 14. ContextBuilder e Garmin source freshness

`ContextBuilder` riceve esplicitamente:

`garmin_source_state_path`

Nel runtime reale viene passato:

`DEFAULT_SYNC_STATE_PATH`

Se esiste `source_checked_at`, la freshness training viene valutata sulla sorgente e non sulla data dell'ultima attività.

`data_freshness["training"]` può contenere:

- `basis = source_checked_at`
- `source_checked_at`
- `last_activity_at`
- `window_complete`

`history_sources` conserva inoltre lo stato Garmin.

Nei test il path non viene passato automaticamente, così i test restano isolati dai file locali reali.

---

## 15. Stale load

Il problema del vecchio handoff è chiuso.

Prima:

uno storico Garmin fermo a luglio poteva produrre un falso carico corrente `HIGH`.

Ora:

se la sorgente training è `STALE` o `FUTURE`, il carico operativo viene degradato a:

`UNKNOWN`

Le metriche storiche restano comunque disponibili.

L'acute/chronic ratio non può riattivare indirettamente un rischio di carico quando il carico corrente non è valutabile.

---

## 16. Finestre 7d / 28d

Durante il primo run reale è emerso un problema:

la finestra 7d dipendeva dall'ora esatta di `source_checked_at`.

Esempio:

due sync nello stesso 28 agosto potevano includere/escludere una seduta al confine delle 168 ore.

Questo rendeva il carico dipendente dall'orario del sync.

Correzione in:

`backend/analyzers/load_analyzer.py`

Le finestre sono ora basate sui:

**giorni di calendario**

e non sulle ore esatte trascorse.

Verifica reale:

due `analysis_date` diverse nello stesso 28/08 producono risultati identici:

- acute load 7d: `1088.67`
- sessions 7d: `9`
- chronic load 28d: `4473.02`
- sessions 28d: `38`
- acute/chronic ratio: `0.974`

---

## 17. Personalizzazione del carico

Il Garmin live sync ha reso evidente che la vecchia soglia assoluta di LoadAnalyzer poteva classificare `HIGH` un carico perfettamente coerente con lo storico personale.

Dati reali rilevati:

- chronic 28d: 4473.02
- chronic weekly average: 1118.26
- baseline weekly personale: 1154.62
- storico analizzato: 74 sessioni / 8 settimane
- confidence baseline: HIGH

La soglia assoluta continuava a produrre:

`HIGH`

e questo propagava un falso rischio `HIGH_LOAD`.

### Nuova logica conservativa

`LoadAnalyzer` conserva:

`absolute_level`

ma aggiunge:

- `classification_basis`
- `personal_baseline_weekly_load`

Un `absolute HIGH` viene trasformato in operativo `NORMAL` soltanto se:

- `load_tolerance.status == STIMATA`
- confidence `MODERATE` o `HIGH`
- baseline positiva;
- acute load 7d <= baseline weekly personale.

Non è stata inventata alcuna nuova soglia percentuale.

Reason:

`Carico assoluto elevato ma coerente con la baseline personale`

Se baseline manca, è poco affidabile o l'acuto supera la baseline:

resta il comportamento assoluto precedente.

---

## 18. TrainingAnalyzer wording

Messaggio aggiornato da:

`Dati sul carico allenante insufficienti`

a:

`Dati sulla seduta corrente insufficienti`

Motivo:

il report dispone già del carico storico Garmin.

Il messaggio riguarda invece la seduta operativa corrente Airtable, che può essere assente.

Questo elimina una contraddizione apparente nel report.

---

## 19. Primo run reale end-to-end

Il 28 agosto 2026 è stato eseguito il primo:

`python -m backend.main`

non dry-run dopo la verifica dei dati Garmin.

### Garmin

Prima:

- archive count: 3896
- `source_checked_at`: `2026-08-28T07:33:25.352858Z`
- `last_activity_at`: `2026-08-27T09:00:42Z`

Dopo:

- archive count: 3896
- nessun duplicato;
- `source_checked_at` avanzato;
- `last_activity_at` invariato.

### Decisione

Decisione reale:

- `ADATTA`
- confidence: `90`
- strategy: `ADAPT`
- risk: `CAUTION`
- rule: `ADAPTATION_MODERATE`
- primary intent: `PROTECT_INJURY`
- training priority: `SPECIFICITA_GARA`

La decisione è stata salvata realmente su Airtable.

Decision Memory è stata eseguita nel normale flusso runtime.

---

## 20. Stato attuale del carico reale

Con Garmin aggiornato:

### Load

- Level: `NORMAL`
- Absolute level: `HIGH`
- Classification basis: `PERSONAL_BASELINE`
- Personal baseline weekly load: `1154.62`
- Total/chronic 28d: `4473.02`
- Acute 7d: `1088.67`
- Chronic weekly average: `1118.26`
- Sessions 7d: `9`
- Sessions 28d: `38`
- Acute/chronic ratio: circa `0.97`

Reason:

`Carico assoluto elevato ma coerente con la baseline personale`

### Adaptation

- `MODERATE`
- risk code: `PHYSICAL_LIMITATION`
- nessun `HIGH_LOAD`

La decisione corrente non viene più distorta da una soglia assoluta non personalizzata.

---

## 21. Garmin Recovery

Commit:

`1cf5ef9 feat: add Garmin recovery observations`

Nuovi componenti:

- `backend/importers/garmin_recovery_adapter.py`
- `backend/importers/garmin_recovery_archive.py`
- `backend/importers/garmin_recovery_sync.py`

Test:

- `tests/test_garmin_recovery_archive.py`
- `tests/test_garmin_recovery_sync.py`

---

## 22. Garmin Recovery — principi semantici

Garmin Recovery è stato deliberatamente introdotto come:

**evidenza fisiologica osservativa separata**

Non sostituisce automaticamente:

`context["recovery"]`

e non entra ancora direttamente in:

- `RecoveryAnalyzer`
- `RecoveryTrendAnalyzer`
- Recovery freshness decisionale
- Decision Memory recovery outcomes

Motivo:

le metriche realmente disponibili sul dispositivo/account non coincidono necessariamente con il Recovery Score già previsto da IronCoach.

---

## 23. Endpoint Garmin Recovery verificati

Nella versione installata di `garminconnect` risultano disponibili:

- `get_sleep_data`
- `get_hrv_data`
- `get_training_readiness`
- `get_morning_training_readiness`
- `get_stress_data`
- `get_body_battery`
- `get_stats_and_body`

Sono stati verificati realmente in sola lettura.

Per il periodo controllato risultavano disponibili soprattutto:

- resting heart rate;
- stress;
- Body Battery.

Non risultavano invece dati validi per:

- sleep score;
- durata sonno valida;
- HRV;
- Training Readiness.

---

## 24. Body Battery ≠ Readiness

Regola architetturale importante:

> Garmin Body Battery NON viene mappata automaticamente a `readiness`.

Motivo:

nell'attuale IronCoach:

`readiness`

viene trattato da `RecoveryAnalyzer` come:

**Recovery Score**

e viene copiato da `RecoveryHistory` in:

`recovery_score`

Usare Body Battery come readiness altererebbe quindi decisioni e trend senza una giustificazione semantica valida.

L'adapter Garmin conserva invece:

- `training_readiness`
- `body_battery`

come campi distinti.

Se Training Readiness non è disponibile:

`training_readiness = None`

---

## 25. Garmin Recovery adapter

L'adapter produce osservazioni del tipo:

- `source = garmin`
- `source_id = garmin-recovery:<date>`
- `date`
- `sleep.score`
- `sleep.hours`
- `sleep.quality`
- `training_readiness`
- `hrv`
- `resting_hr`
- `stress`
- `body_battery`
- `body_battery_charged`
- `body_battery_drained`
- `raw`

Dati mancanti restano:

`None`

Regola specifica:

`sleepTimeSeconds = None` oppure `0`

NON viene interpretato come:

`0 ore di sonno`

ma come dato sonno non disponibile.

---

## 26. Garmin Recovery archive

Archivio locale:

`data/garmin/garmin_recovery_daily.json`

Il record è giornaliero e indicizzato per:

`date`

Il comportamento è:

**upsert**

e non semplice skip duplicate.

Motivo:

i dati dello stesso giorno possono completarsi durante la giornata.

Un secondo sync del 28/08:

- non crea un secondo record;
- sostituisce/aggiorna quello esistente.

Scrittura:

- JSON;
- atomica;
- file temporaneo + `replace`;
- validazione dopo scrittura.

---

## 27. Garmin Recovery sync

State file:

`data/garmin/garmin_recovery_sync_state.json`

Campi principali:

- `source_checked_at`
- `last_observation_date`
- `sync_date`
- conteggi insert/update
- archive path
- state path

`source_checked_at` viene aggiornato soltanto dopo:

1. login Garmin;
2. lettura completa degli endpoint;
3. conversione;
4. upsert archivio;
5. rilettura e validazione dell'archivio.

Un errore non produce un falso aggiornamento dello state file.

---

## 28. Primo sync Recovery reale

Data:

`2026-08-28`

Prima:

- archivio Recovery assente;
- state file assente.

Dopo:

- inserted: 1
- updated: 0
- record count: 1

Osservazione reale normalizzata:

- date: 2026-08-28
- training_readiness: `None`
- HRV: `None`
- sleep hours: `None`
- resting_hr: `43.0`
- stress: `18.0`
- body_battery: `83.0`
- body_battery_charged: `7.0`
- body_battery_drained: `11.0`

Nessun valore mancante è stato inventato.

---

## 29. Idempotenza Recovery reale

Secondo sync dello stesso giorno:

- count prima: 1
- count dopo: 1
- inserted: 0
- updated: 1
- `last_observation_date`: invariato
- `source_checked_at`: avanzato

Quindi l'upsert reale è stato validato.

---

## 30. Garmin Recovery nel ContextBuilder

Nuovo campo:

`garmin_recovery_history`

Contiene le osservazioni Garmin Recovery separate.

Nuovi elementi opzionali in `history_sources`:

- `garmin_recovery_total`
- `garmin_recovery_enabled`
- `garmin_recovery_source_checked_at`
- `garmin_recovery_last_observation_date`

Importante:

se Garmin Recovery non viene esplicitamente configurato nei test, i vecchi contratti `history_sources` restano invariati.

Questo mantiene isolamento e retrocompatibilità dei test.

---

## 31. Recovery decisionale resta separato

Verifica reale dopo il wiring:

### `context["recovery"]`

- source: Airtable
- date: `None`
- readiness: `None`

### `garmin_recovery_history`

1 record Garmin:

- date: 2026-08-28
- resting_hr: 43
- stress: 18
- body_battery: 83
- training_readiness: None
- HRV: None

### Recovery freshness decisionale

Resta:

- status: `UNKNOWN`
- date: `None`

Quindi:

> una fonte Recovery Garmin aggiornata NON rende automaticamente il Recovery decisionale valutabile.

---

## 32. Sync Recovery automatico nel runtime

Il sync Garmin Recovery è ora collegato al run normale con la stessa filosofia del Garmin activity sync.

### Run normale

Tenta:

1. Garmin activity sync;
2. Garmin Recovery sync.

Entrambi sono:

**best-effort**

Se uno fallisce:

- l'altro può comunque essere eseguito;
- IronCoach continua;
- viene prodotto un warning;
- lo state della sorgente fallita non avanza.

### Dry-run

Nessuno dei due sync viene eseguito.

Questo contratto è coperto dai test.

---

## 33. Verifica helper runtime Recovery

L'helper runtime:

`_sync_garmin_recovery_best_effort()`

è stato eseguito realmente senza avviare `run_pipeline()`.

Risultato:

- tipo: `GarminRecoverySyncResult`
- inserted: 0
- updated: 1
- record count: 1
- source_checked_at avanzato;
- nessuna decisione Airtable o Decision Memory salvata.

Quindi il wiring runtime Recovery è validato anche sul servizio Garmin reale.

---

## 34. Dry-run dopo Garmin Recovery

`python -m backend.main --dry-run`

continua a produrre:

- Decisione: `ADATTA`
- Confidence: `90`
- Risk: `CAUTION`
- Rule: `ADAPTATION_MODERATE`
- Primary intent: `PROTECT_INJURY`

Recovery resta:

`UNKNOWN`

Il report NON interpreta Body Battery 83 come Recovery Score.

Questo è il comportamento intenzionale e conservativo.

---

## 35. Nutrition e Garmin fueling demand

Stato decisionale reale:

`Nutrition Log` non contiene dati operativi correnti.

`get_latest_nutrition()` continua quindi a restituire assenza di dato.

IronCoach NON richiede attualmente un diario alimentare con calorie,
macronutrienti o quantità ingerite.

L'assenza di tracking alimentare significa:

`UNKNOWN`

e non viene interpretata come nutrizione adeguata o inadeguata.

### Evidenza automatica Garmin

È stato aggiunto nel `ContextBuilder`:

`garmin_fueling_demand_history`

come storico **osservativo separato** derivato dalle attività Garmin.

Può contenere:

- `calories_burned`
- `estimated_water_ml`
- data
- sport
- `source_id`

Semantica obbligatoria:

> `calories_burned` rappresenta il dispendio energetico della seduta,
> non calorie ingerite e non deficit calorico.

> `estimated_water_ml` rappresenta una stima Garmin della richiesta/perdita
> di liquidi associata alla seduta, non quantità bevuta e non stato di
> idratazione reale.

I dati Garmin non vengono trasformati automaticamente in:

- stato nutrizionale;
- stato di idratazione;
- underfueling;
- disidratazione;
- quantità di calorie da assumere;
- quantità di liquidi effettivamente consumata.

`NutritionAnalyzer` e `DecisionEngine` restano invariati.

Quando non esistono dati nutrizionali reali:

`NutritionAnalyzer -> UNKNOWN`

Il report mostra invece, quando disponibili, i valori osservativi
dell'ultima seduta Garmin, mantenendoli esplicitamente separati dalla
voce `Nutrizione`.

Questa separazione è intenzionale.

---

## 36. Performance

`Performance Log` Airtable non contiene ancora uno storico temporale
reale decisionale.

`get_performance_history()` conserva il fallback esistente costruito
dal profilo atleta con:

- FTP
- VO₂max corsa
- VO₂max bici
- CSS

Quel record:

- non ha una data;
- rappresenta metriche statiche di profilo;
- non costituisce uno storico temporale;
- non è sufficiente per costruire un trend Performance.

### Garmin Performance osservativo

È stato aggiunto nel `ContextBuilder`:

`garmin_performance_history`

come storico temporale **osservativo separato**.

La forma dei record è verticale:

- `date`
- `metric`
- `value`
- `source`
- `source_id`

Metriche oggi supportate:

- `vo2max_run`
- `vo2max_bike`

La sorgente è l'archivio attività Garmin già normalizzato.

Per le attività live il relativo metadata Garmin può contenere il
VO₂max restituito dalla sorgente.

Gli aggiornamenti live possono arricchire il metadata delle attività
già presenti senza modificare identità o metriche canoniche della
seduta.

Principio:

> Garmin Performance osservativo non viene copiato automaticamente
> dentro `performance_history` decisionale.

Di conseguenza:

`PerformanceTrendAnalyzer`

continua correttamente a produrre:

`UNKNOWN`

quando manca uno storico Performance decisionale confrontabile.

Il report può mostrare l'ultimo VO₂max osservato per corsa e bici,
ma non costruisce da questi dati un trend e non modifica la decisione.

---

## 36-bis. Delta implementativo successivo al `.ter`

Il presente handoff include quattro commit di codice
successivi a:

`d0aa2ef docs: add beta 0.4 ter handoff`

Commit implementativi:

1. `01a9188 feat: add observational Garmin performance`
2. `ea164ed feat: add observational Garmin fueling demand`
3. `4258a31 feat: show observational Garmin fueling in report`
4. `3c180d1 feat: show observational Garmin recovery and performance`

### Garmin Performance — dettagli reali

L'archivio storico Garmin conteneva già VO₂max nei metadata
normalizzati storici.

Il live adapter è stato esteso per conservare:

`metadata.garmin_live.vo2_max`

dal campo Garmin:

`vO2MaxValue`

Il live sync può inoltre arricchire il metadata Garmin delle
attività già archiviate quando incontra nuovamente la stessa
attività.

L'arricchimento:

- richiede identità coerente;
- modifica soltanto `metadata["garmin_live"]`;
- non modifica `activity_id`;
- non modifica `source_id`;
- non modifica le metriche canoniche della seduta.

È stato eseguito un backfill locale controllato dopo backup.

Backup:

`data/garmin/garmin_activities_merged.jsonl.gz.before_performance_backfill_20260831_070220.bak`

`data/garmin/garmin_activities_merged.jsonl.gz.manifest.json.before_performance_backfill_20260831_070220.bak`

Dopo il backfill:

- archivio attività invariato: **3896 attività**;
- osservazioni VO₂max Garmin totali: **1320**;
- `vo2max_run`: **1142**;
- `vo2max_bike`: **178**.

Ultime osservazioni reali note:

- corsa:
  - data: `2026-08-26`;
  - VO₂max: `57.0`;
  - `source_id`: `24126326294`;
- bici:
  - data: `2026-08-27`;
  - VO₂max: `55.0`;
  - `source_id`: `24134063811`.

Questi dati alimentano:

`garmin_performance_history`

ma NON:

`performance_history`

e quindi non modificano automaticamente
`PerformanceTrendAnalyzer`.

### Garmin fueling demand — dettagli reali

Il live activity adapter è stato esteso per conservare:

`metadata.garmin_live.water_estimated_ml`

dal campo Garmin:

`waterEstimated`

Semantica:

> `waterEstimated` è una stima Garmin associata alla seduta.
> Non rappresenta acqua realmente bevuta e non dimostra
> disidratazione.

Il `ContextBuilder` preserva inoltre il valore:

`calories`

dell'attività normalizzata e costruisce:

`garmin_fueling_demand_history`

con:

- `date`;
- `source`;
- `source_id`;
- `sport`;
- `calories_burned`;
- `estimated_water_ml`.

Semantica:

> `calories_burned` è dispendio energetico dell'attività,
> non calorie ingerite e non deficit energetico.

È stato eseguito un backfill locale controllato dei valori
`waterEstimated` dopo backup.

Backup:

`data/garmin/garmin_activities_merged.jsonl.gz.before_fueling_backfill_20260831_072016.bak`

`data/garmin/garmin_activities_merged.jsonl.gz.manifest.json.before_fueling_backfill_20260831_072016.bak`

Il controllo live sul periodo 1-27 agosto 2026 aveva rilevato:

- **37 attività** Garmin lette;
- **37 attività** abbinate all'archivio;
- **27 attività** con `waterEstimated`.

Dopo il backfill:

- archivio attività invariato: **3896 attività**;
- osservazioni fueling demand: **3829**;
- osservazioni con `calories_burned`: **3829**;
- osservazioni con `estimated_water_ml`: **27**.

Esempi reali più recenti verificati:

- `2026-08-25` BIKE:
  - `1280 kcal`;
  - `1834 ml` Garmin stimati;
- `2026-08-26` RUN:
  - `672 kcal`;
  - `824 ml` Garmin stimati;
- `2026-08-27` BIKE:
  - `523 kcal`;
  - `739 ml` Garmin stimati.

`nutrition` resta separato.

Con Nutrition reale assente:

`nutrition == {}`

e:

`NutritionAnalyzer -> UNKNOWN`

### Report osservativo

Il report è stato esteso senza modificare
`DecisionEngine`.

Esempio reale verificato in `--dry-run`:

- `Nutrizione: N/D`;
- `Osservazioni Garmin recovery (2026-08-28): FC riposo 43 bpm; Stress 18; Body Battery 83`;
- `Garmin VO₂max osservato: corsa 57; bici 55`;
- `Costo energetico seduta Garmin: 523 kcal`;
- `Liquidi stimati dalla seduta Garmin: 739 ml`.

Nello stesso dry-run:

- `TREND RECOVERY -> UNKNOWN`;
- `TREND PERFORMANCE -> UNKNOWN`;
- Nutrition decisionale -> dati insufficienti;
- la decisione non è stata modificata dai nuovi dati
  osservativi.

Questo comportamento è intenzionale.

---

## 37. Distinzione dati statici vs trend

Principio da mantenere:

### Metriche statiche profilo

Esempi:

- FTP
- CSS
- VO₂max

possono descrivere il profilo atleta.

### Storico Performance

Per costruire un trend devono esistere:

- date reali;
- metriche confrontabili;
- più osservazioni nel tempo.

Non trasformare automaticamente metriche statiche senza data in un trend.

---

## 38. Stato sorgenti reale

### Athlete Profile

Disponibile da Airtable.

### Training history

Disponibile e aggiornato da Garmin.

### Current training Airtable

Può essere assente.

### Recovery Airtable

Assente.

### Garmin Recovery osservativo

Disponibile separatamente dal Recovery decisionale.

Può contenere osservazioni come:

- frequenza cardiaca a riposo;
- stress Garmin;
- Body Battery;
- eventuale Training Readiness quando disponibile.

Body Battery resta distinta dalla readiness IronCoach.

### Nutrition decisionale

Assente.

L'assenza di tracking alimentare resta `UNKNOWN`.

### Garmin fueling demand osservativo

Disponibile dalle attività Garmin.

Può esporre:

- costo energetico della seduta;
- stima Garmin dei liquidi associati alla seduta.

Non rappresenta cibo o liquidi effettivamente assunti.

### Performance decisionale temporale

Assente.

### Garmin Performance osservativo

Disponibile come serie temporale separata di VO₂max corsa/bici.

Non alimenta ancora `PerformanceTrendAnalyzer`.

### Decision Log

Contiene almeno la prima decisione reale salvata il 28/08/2026.

---

## 39. Dati locali non versionati

I seguenti dati sono ignorati da Git e NON sono presenti su GitHub:

- `.env`
- `data/ironcoach_memory.db`
- `data/garmin/Archivio Garmin.zip`
- `data/garmin/summaries/`
- `data/garmin/garmin_raw_matches.csv`
- `data/garmin/garmin_activities_merged.jsonl.gz`
- relativo manifest
- export report
- `data/garmin/garmin_live_sync_state.json`
- `data/garmin/auth/`
- `data/garmin/garmin_recovery_daily.json`
- `data/garmin/garmin_recovery_sync_state.json`
- `data/garmin_extracted/`

Backup Airtable esterno al repository:

`/home/codespace/ironcoach_airtable_backup_20260826_121223.json`

Se il Codespace viene eliminato definitivamente, questi file non sono recuperabili da Git.

L'archivio Garmin Connect ufficiale originale resta disponibile anche esternamente al repository.

---

## 40. Commit principali recenti

### `298aaf5`

`fix: preserve airtable history chronology`

### `e622c56`

`fix: avoid stale training as current load`

### `9a36d01`

`docs: add beta 0.4 handoff`

### `674095d`

`docs: rename beta 0.4 handoff`

### `95759f8`

`feat: integrate live Garmin sync and personalized load`

### `3b772ac`

`feat: sync Garmin automatically before decisions`

Include anche la correzione delle finestre temporali 7d/28d basate sui giorni di calendario.

### `1cf5ef9`

`feat: add Garmin recovery observations`

---

## 41. Suite finale

Ultima suite completa prima del presente handoff:

**500 passed, 5 skipped in 1.82 s**

La suite è stata eseguita dopo:

- Garmin Recovery adapter;
- archive;
- sync;
- ContextBuilder wiring;
- runtime best-effort wiring;
- dry-run protection.

Dopo i test sono stati ripristinati i `.pyc` tracciati accidentalmente modificati.

---

## 42. Sicurezza

Prima del commit Garmin Recovery è stato eseguito uno scan sui file intenzionali.

Risultato:

`Security scan: OK`

Nessuna:

- credenziale;
- password;
- access token;
- refresh token;
- email letterale

rilevata nei file da versionare.

Non inserire mai nei commit:

- credenziali Garmin;
- tokenstore;
- `.env`;
- dati sensibili locali.

---

## 43. Regole architetturali da mantenere

1. Missing data ≠ good.
2. Missing data ≠ bad.
3. Attività assente ≠ mancata aderenza.
4. Fonte vecchia ≠ stop reale.
5. Fonte aggiornata + nessuna attività può essere informativo.
6. `manifest.created_at` ≠ `source_checked_at`.
7. Body Battery ≠ Training Readiness.
8. Training Readiness ≠ automaticamente qualsiasi recovery score.
9. Recovery source freshness ≠ Recovery evaluability.
10. Metriche statiche Performance ≠ trend Performance.
11. Garmin activity archive resta canonico per lo storico attività.
12. Non duplicare migliaia di attività Garmin in Airtable.
13. DecisionEngine resta deterministico.
14. Decision Memory può regolare confidenza, non sovvertire sicurezza e regole.
15. Gli errori temporanei Garmin non devono bloccare completamente IronCoach.

---

## 44. Cosa NON fare alla ripresa

Non:

- reinserire i dati fake Airtable eliminati;
- duplicare l'archivio Garmin in Airtable;
- usare Body Battery come `readiness`;
- trasformare stress/resting HR in un Recovery Score inventato;
- marcare Recovery `CURRENT` soltanto perché Garmin è stato interrogato;
- considerare il fallback FTP/VO₂max/CSS come vero storico Performance;
- introdurre soglie fisiologiche arbitrarie senza un contratto esplicito;
- eseguire il Garmin sync durante `--dry-run`;
- trasformare un errore Garmin in un aggiornamento falso di `source_checked_at`;
- creare test RED artificiali per wiring meccanico;
- creare nuovi test quando un test esistente può coprire il contratto.

---

## 45. Prossimo obiettivo consigliato

I tre blocchi Garmin principali sono ora disponibili come evidenze
osservative:

1. Recovery;
2. Performance;
3. fueling demand.

Non trasformarli automaticamente in segnali decisionali.

Il prossimo obiettivo è definire, una semantica alla volta, se e in
quali condizioni una di queste evidenze possa diventare realmente
decision-driving.

Prima di ogni eventuale integrazione devono essere espliciti:

- significato fisiologico del dato;
- qualità minima richiesta;
- freschezza;
- gestione dei missing data;
- soglie, soltanto se motivate e contrattualizzate;
- comportamento in caso di conflitto con Airtable;
- comportamento in caso di dato vecchio;
- effetto massimo consentito sulla decisione.

Principio:

> osservazione automatica ≠ interpretazione automatica.

Nel frattempo il Decision Memory loop deve continuare a raccogliere
naturalmente episodi reali e outcome reali.

Non creare outcome artificiali soltanto per far crescere lo storico
di apprendimento.

---

## 46. Technical debt noto

Possibile debito tecnico nelle vecchie CLI manuali Decision Memory:

- demo/activity/outcome CLI;
- viewer;
- possibili mismatch model/dict.

Non è prioritario rispetto al normale flusso Beta 0.4.

Affrontarlo soltanto se interferisce con il runtime operativo.

---

## 47. Regola di lavoro con ChatGPT

Procedere un passo alla volta.

Per ogni passo:

1. breve spiegazione;
2. un solo comando eseguibile;
3. attendere l'output;
4. decidere il passo successivo sulla base dell'output reale.

Ridurre al minimo la creazione di test.

Creare o estendere test soltanto per:

- contratti non banali;
- regressioni significative;
- sicurezza semantica.

Quando un file esistente deve essere modificato:

- fornire l'intero file completo;
- oppure un comando automatico completo e sicuro.

Mai chiedere patch manuali di singole righe.

---

## 48. Checkpoint finale

Stato noto al momento dell'handoff:

- branch: `feature/beta-0.4-decision-memory`;
- HEAD codice: `3c180d1`;
- origin sincronizzato;
- suite completa: **500 passed, 5 skipped** in circa **2.21 s**;
- Decision Memory learning layer: implementato;
- Outcome loop end-to-end: implementato;
- Airtable fake data: eliminati dopo backup;
- Athlete Profile: conservato;
- cronologia Airtable: corretta;
- Garmin historical archive: ricostruito;
- Garmin archive locale: **3896 attività**;
- Garmin token-only sync: funzionante;
- `last_activity_at`: implementato;
- `source_checked_at`: implementato;
- Garmin automatic sync pre-decisione: implementato;
- sync Garmin failure: non bloccante;
- dry-run senza sync: implementato;
- stale historical load: corretto;
- finestre 7d/28d: stabili per giorno di calendario;
- load personale: baseline integrata conservativamente;
- primo run reale: completato;
- decisione reale salvata;
- Garmin Recovery adapter/archive/sync: implementati;
- Garmin Recovery automatic best-effort: implementato;
- Body Battery separata da readiness;
- Recovery Garmin osservativo non altera le decisioni;
- Garmin Performance osservativo: implementato;
- Garmin VO₂max corsa/bici: disponibile come storico separato;
- Garmin fueling demand osservativo: implementato;
- costo energetico Garmin: distinto dall'assunzione calorica;
- stima liquidi Garmin: distinta dall'idratazione reale;
- Nutrition decisionale reale: ancora assente e quindi `UNKNOWN`;
- Performance decisionale temporale reale: ancora assente;
- report: mostra Recovery, VO₂max e fueling Garmin come osservazioni;
- report osservativo Garmin: non modifica `DecisionEngine`;
- prossimo step: definire eventuali contratti decisionali per i dati
  osservativi senza introdurre interpretazioni automatiche arbitrarie.
