# IronCoach Beta 0.4 — Handoff

**Data handoff:** 26 agosto 2026  
**Branch:** `feature/beta-0.4-decision-memory`  
**Ultimo commit codice prima dell'handoff:** `e622c56da1d2a47320d4c22221cf8a4d26047ce1`  
**Commit:** `fix: avoid stale training as current load`

---

## 1. Stato generale

IronCoach Beta 0.4 è in sviluppo sul branch:

`feature/beta-0.4-decision-memory`

Prima della creazione di questo handoff:

- working tree pulito;
- branch locale sincronizzato con origin;
- ultimo commit remoto codice: `e622c56`;
- suite completa:
  - **492 passed**
  - **5 skipped**
  - circa 1.58 s.

Non risultano regressioni note nella suite.

---

## 2. Obiettivo Beta 0.4

Obiettivo principale:

> IronCoach deve imparare dalla risposta dell'atleta alle decisioni precedenti e usare quell'esperienza per migliorare le decisioni future.

Principi invarianti:

- `DecisionEngine` deterministico;
- la sicurezza ha sempre priorità;
- Decision Memory può modificare la confidenza entro limiti controllati;
- Decision Memory non cambia arbitrariamente regola o decisione;
- missing data non significa automaticamente esito positivo o negativo;
- attività mancante non significa automaticamente mancata aderenza;
- dati vecchi non devono essere interpretati come stato corrente.

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

Regola importante:

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

Il runtime elabora gli episodi precedenti pendenti prima di creare la nuova decisione.

Il matching attività è conservativo:

- attività successiva alla decisione;
- sport compatibile con quello atteso;
- una sola candidata;
- in caso di ambiguità non viene indovinata un'attività.

---

## 4. Learning layer completato

Componenti principali:

- `learning_analyzer.py`
- `learning_policy.py`
- `learning_service.py`

Repository:

- supporto `list_evaluated_by_athlete`

Orchestrator:

- `learning_service` opzionale;
- `build_learning_evidence`

Factory:

- repository condiviso.

DecisionEngine:

- riceve `assessments["decision_memory"]`;
- inserisce l'evidenza Decision Memory nell'intelligence della regola selezionata.

CoachEngine:

- conserva l'intelligence proveniente dal DecisionEngine.

Main:

- Decision Memory viene collegata prima del CoachEngine.

### Policy learning

- minimo 3 outcome valutabili;
- delta confidenza massimo ±5;
- `INSUFFICIENT_DATA` escluso dal denominatore;
- nessun cambio automatico di decisione/regola;
- `HIGH_ALERT` non viene modificato dalla memoria;
- il cap di freschezza dati viene applicato dopo l'aggiustamento Decision Memory.

---

## 5. Outcome loop end-to-end completato

Commit precedente principale:

`3a015c6 feat: connect decision memory outcome loop end to end`

Implementazioni:

### Activity runtime

Processa soltanto episodi:

`WAITING_FOR_ACTIVITY`

### Lifecycle

Conserva activity ID tramite:

`activity_id or source_id`

### Outcome orchestrator

Supporta:

`process_outcome(athlete_id, recovery_history=None, as_of=None)`

### Outcome evaluator

Adherence:

- stesso sport → `FOLLOWED`
- sport differente → `NOT_FOLLOWED`
- attività assente → `UNKNOWN`

### Outcome runtime

Gestisce:

- adherence pendente;
- recovery outcomes.

### Recovery outcome

Aggiunti:

- `recovery_outcome_evaluator.py`
- `recovery_outcome_processor.py`

### Main runtime

`_attach_decision_memory_learning(..., process_pending=True)`:

1. processa attività Garmin pendenti;
2. processa recovery outcome pendenti;
3. costruisce learning evidence;
4. passa quindi alla nuova decisione.

Nel `run_pipeline`:

`process_pending=(not dry_run)`

---

## 6. Airtable

### Configurazione

`.env` locale configurato.

Variabili necessarie presenti:

- `AIRTABLE_API_KEY`
- `AIRTABLE_BASE_ID`

NON inserire mai credenziali o valori del PAT nel repository o negli handoff.

`.env` è ignorato da Git.

Test reale Airtable riuscito:

`AirtableClient().base.table("Athlete Profile").all(max_records=1)`

Risultato:

`Airtable read: OK`

### Athlete Profile

Conservato come dato reale dell'atleta.

### Dati di sviluppo eliminati

I record presenti nelle altre tabelle erano dati fake/test di sviluppo.

Prima della pulizia:

- Athlete Profile: 1
- Training Log: 5
- Recovery Log: 3
- Nutrition Log: 3
- Performance Log: 3
- Decision Log: 105

Backup creato prima della cancellazione:

`/home/codespace/ironcoach_airtable_backup_20260826_121223.json`

Dopo la pulizia:

- Athlete Profile: 1 — CONSERVATO
- Training Log: 0
- Recovery Log: 0
- Nutrition Log: 0
- Performance Log: 0
- Decision Log: 0

Nota:

> il backup Airtable è locale al Codespace e NON è versionato.

---

## 7. Fix cronologia Airtable

Problema trovato:

due Recovery Log dello stesso giorno venivano ordinati soltanto per data e potevano quindi produrre un trend cronologicamente errato.

Esempio rilevato:

- score 84.5 GREEN;
- poi score 30 RED;
- stessa data;
- `createdTime` differente.

`get_latest_recovery()` era corretto, ma `_get_history()` perdeva `createdTime` prima dell'ordinamento.

Correzione:

`backend/airtable_client.py`

Lo storico viene ora ordinato per:

`(date_field, createdTime)`

oppure solo `createdTime` quando non esiste un campo data.

Commit:

`298aaf5 fix: preserve airtable history chronology`

Suite dopo il fix:

- 491 passed
- 5 skipped.

---

## 8. Archivio storico Garmin ricostruito

L'archivio Garmin Connect ufficiale originale è stato scaricato dall'utente sul PC.

Nel Codespace è stato temporaneamente copiato in:

`data/garmin/Archivio Garmin.zip`

`data/` è ignorato da Git.

Sono stati estratti soltanto i file:

`*_summarizedActivities.json`

in:

`data/garmin/summaries/`

### Attività importate

Totale:

**3858 attività**

Intervallo:

- prima: `2011-07-22T18:44:06Z`
- ultima: `2026-07-30T04:10:16Z`

Sport:

- BIKE: 1285
- INDOOR_CARDIO: 20
- MULTISPORT: 5
- OTHER: 4
- ROW: 1
- RUN: 1603
- STRENGTH: 120
- SWIM: 813
- TRANSITION: 4
- WALK: 3

Ultima attività:

- 30/07/2026
- RUN
- Garmin source id `23784221119`

L'utente si allena regolarmente e l'export Garmin originale è stato scaricato all'inizio dello sviluppo di IronCoach.

Quindi:

> l'archivio storico NON contiene le attività di agosto 2026 e successive.

Questo è intenzionale e noto.

---

## 9. Garmin merged archive

Creato:

`data/garmin/garmin_activities_merged.jsonl.gz`

Manifest:

`data/garmin/garmin_activities_merged.jsonl.gz.manifest.json`

Report:

`data/garmin/garmin_activity_export_report.json`

Raw matches CSV:

`data/garmin/garmin_raw_matches.csv`

Per questa ricostruzione il CSV contiene soltanto gli header richiesti.

Directory raw:

`data/garmin_extracted/`

attualmente vuota.

Tutte le 3858 attività sono state importate come:

`JSON_ONLY`

Conteggio:

- json_only: 3858
- merged: 0
- missing_raw: 0
- parse_errors: 0
- skipped_review: 0

Manifest SHA-256:

`3a806bd09e6fdb97cfa44b8c3f8e9157a1850af960500a77c85e1bc91927b54c`

`GarminActivityArchive().iter_all()` legge e valida correttamente tutte le 3858 attività.

---

## 10. Garmin raw matcher

Durante l'indagine è stato verificato che:

`garmin_raw_matcher.py`

è citato nella documentazione dell'importer ma non risulta mai essere stato versionato nel repository.

`GarminHistoricalImporter` può funzionare anche senza raw matches.

Per la ricostruzione attuale è stato quindi usato un CSV header-only.

Questo non impedisce a IronCoach di usare lo storico riepilogativo Garmin.

---

## 11. Ruolo Garmin vs Airtable

Decisione architetturale attuale:

### Garmin

Fonte canonica per lo storico delle attività.

Non duplicare automaticamente migliaia di attività Garmin in Airtable.

### Airtable

Usato per dati operativi, profilo atleta e altri dati strutturati che hanno senso mantenere nel database Airtable.

Duplicare l'intero archivio Garmin in Airtable non aggiungerebbe valore a IronCoach.

---

## 12. Problema stale training scoperto e risolto

Dopo la pulizia Airtable, un dry-run mostrava:

- archivio Garmin fermo al 30/07;
- carico 28 giorni = 5263.33;
- livello `HIGH`;
- adattamento `LIMITED`;
- decisione `RECUPERA`;
- `HIGH_ALERT`;
- confidenza 96.

Problema:

`LoadAnalyzer` usava come `analysis_date` l'ultima attività disponibile.

Quindi il carico di fine luglio veniva interpretato come “carico recente” anche il 26 agosto.

Inoltre `ContextBuilder` valutava la freschezza training soltanto usando il current training Airtable.

Con Airtable vuoto:

- training freshness risultava `UNKNOWN / LOW`;
- nessun warning;
- lo storico Garmin vecchio influenzava comunque il carico corrente.

Questo violava il principio:

> dato mancante o obsoleto non deve diventare automaticamente una valutazione corrente positiva o negativa.

---

## 13. Semantica corretta stabilita

È stata chiarita una distinzione fondamentale:

### Storico vecchio / fonte non aggiornata

IronCoach può usare lo storico per conoscere l'atleta, ma NON deve assumere che descriva il carico corrente.

### Vero periodo senza allenamenti

In futuro, quando Garmin sarà sincronizzato regolarmente, un periodo senza attività può rappresentare un vero stop, per esempio:

- infortunio;
- malattia;
- pausa;
- detraining.

In quel caso IronCoach dovrà ricalibrare il carico e il rientro.

Principio stabilito:

> “Nessuna attività recente” può significare detraining/stop soltanto se sappiamo che la fonte è aggiornata. Se la fonte non è aggiornata, significa dati insufficienti.

---

## 14. `source_checked_at` — requisito futuro importante

È stato analizzato il manifest Garmin.

Il manifest contiene:

`created_at`

ma NON può essere usato come prova della freschezza Garmin.

Esempio:

- manifest creato il 26/08/2026;
- ultima attività contenuta 30/07/2026.

Quindi:

`created_at` = data di creazione dell'archivio IronCoach

NON:

`source_checked_at` = data in cui Garmin è stato verificato come aggiornato.

Inoltre un aggiornamento incrementale senza nuove attività può restituire:

`ALREADY_CURRENT`

senza modificare necessariamente il manifest delle attività.

Per supportare correttamente il futuro scenario:

**infortunio → 1 mese senza allenamenti → Garmin comunque sincronizzato**

servirà distinguere almeno:

- `last_activity_at`
- `source_checked_at`

Questo requisito NON è ancora implementato.

È da affrontare insieme al futuro aggiornamento automatico/incrementale Garmin.

---

## 15. Fix stale load implementato

Ultimo commit codice:

`e622c56 fix: avoid stale training as current load`

File modificati:

- `backend/analyzers/adaptation_analyzer.py`
- `backend/coach_engine.py`
- `backend/context_builder.py`
- `tests/test_coach_engine_orchestration.py`
- `tests/test_context_builder_garmin.py`

### ContextBuilder

Se esiste un training Airtable corrente:

- quello rimane `context["training"]`.

Se Airtable current training è vuoto ma esiste uno storico merged Garmin/Airtable:

- l'ultima data dello storico viene usata per stabilire la **freschezza del training**;
- la vecchia attività Garmin NON viene trasformata artificialmente nel current training.

Quindi:

- storico Garmin disponibile;
- current training può restare vuoto;
- freshness training può correttamente diventare `STALE`.

### CoachEngine

Se:

`data_freshness.training.status`

è:

- `STALE`
- oppure `FUTURE`

il carico calcolato sullo storico viene degradato per la decisione corrente:

`load.level = UNKNOWN`

Le metriche storiche NON vengono cancellate.

Restano disponibili:

- total load;
- acute load;
- chronic load;
- session count;
- sport distribution;
- acute/chronic ratio;
- analysis date.

La reason diventa:

`Carico corrente non valutabile: freschezza allenamenti insufficiente`

Le vecchie reason come:

`Carico recente elevato`

non vengono mantenute, perché sarebbero fuorvianti.

### AdaptationAnalyzer

L'acute/chronic ratio può produrre un rischio soltanto quando:

`has_load_data == True`

Quindi un ratio proveniente da uno storico stale non può riattivare indirettamente un rischio di carico corrente.

---

## 16. Risultato dry-run dopo il fix

Con archivio Garmin fermo al 30/07 e Airtable operativo vuoto:

### Data freshness

Warning:

`Allenamento: dato obsoleto di 27 giorni (data 2026-07-30, soglia 7 giorni)`

Freshness:

- Level: `MODERATE`
- Training status: `STALE`
- Training age: 27 giorni
- Recovery: `UNKNOWN`

### Load

- Level: `UNKNOWN`
- Total load storico: 5263.33
- Sessions: 37
- Sessions with load: 37
- Analysis date storica: `2026-07-30T04:10:16Z`
- Acute load storico 7d: 1408.5
- Chronic load storico 28d: 5263.33
- Acute/chronic ratio storico: 1.07

Reason corretta:

`Carico corrente non valutabile: freschezza allenamenti insufficiente`

NON compare più:

`Carico recente elevato`

come stato corrente.

### Adaptation

- `MODERATE`
- risk code: `PHYSICAL_LIMITATION`
- nessun `HIGH_LOAD`

Reason:

- limitazione fisica nota;
- adattamento da monitorare.

### Decisione dry-run

- Decisione: `ADATTA`
- Strategia: `ADAPT`
- Confidence: `85`
- Risk level: `CAUTION`
- Rule: `ADAPTATION_MODERATE`
- Primary intent: `PROTECT_INJURY`

Questa prudenza deriva dalla limitazione fisica nota e dalla scarsa freschezza dati, NON da un falso carico attuale elevato.

---

## 17. Test stale-training

Test mirati finali:

`25 passed`

Suite completa finale:

`492 passed, 5 skipped in 1.58s`

Dopo la suite sono stati ripristinati i `.pyc` tracciati accidentalmente modificati.

Prima del commit il working tree conteneva solo i 5 file attesi.

Commit e push riusciti.

HEAD e origin verificati uguali:

`e622c56da1d2a47320d4c22221cf8a4d26047ce1`

---

## 18. Situazione dati locale Codespace

ATTENZIONE:

i seguenti dati sono ignorati da Git e NON sono presenti su GitHub:

- `.env`
- `data/ironcoach_memory.db`
- `data/garmin/Archivio Garmin.zip`
- `data/garmin/summaries/`
- `data/garmin/garmin_raw_matches.csv`
- `data/garmin/garmin_activities_merged.jsonl.gz`
- relativo manifest
- relativo export report
- `data/garmin_extracted/`

Inoltre questo backup è esterno al repository:

`/home/codespace/ironcoach_airtable_backup_20260826_121223.json`

Se il Codespace viene semplicemente fermato, questi file devono essere conservati dal workspace persistente.

Se invece il Codespace venisse cancellato definitivamente, NON possono essere recuperati da Git.

L'archivio Garmin Connect ufficiale originale è comunque disponibile anche sul PC dell'utente.

---

## 19. Cosa NON fare alla ripresa

Non:

- reinserire in Airtable i dati fake eliminati;
- duplicare l'intero archivio Garmin in Airtable;
- interpretare assenza di attività come riposo certo senza conoscere la copertura della fonte;
- usare `manifest.created_at` come `source_checked_at`;
- compromettere il comportamento deterministico del DecisionEngine;
- interpretare missing data come good/bad;
- creare test RED artificiali per modifiche meccaniche;
- creare nuovi test se un test esistente può coprire il contratto.

Quando un file esistente deve essere modificato:

- fornire l'intero file completo;
- oppure un comando automatico completo e sicuro.

Mai chiedere modifiche manuali di singole righe.

---

## 20. Prossimo obiettivo consigliato

Alla ripresa NON è necessario tornare sul fix stale load: è chiuso e testato.

La priorità naturale è progettare il percorso dei **dati reali aggiornati automaticamente**, in particolare Garmin.

Serve arrivare a un meccanismo che possa:

1. aggiornare incrementalmente le attività Garmin;
2. registrare quando la fonte Garmin è stata realmente controllata;
3. distinguere:
   - archivio non aggiornato;
   - vero periodo senza allenamenti;
4. permettere a LoadAnalyzer di valutare correttamente:
   - carico attuale;
   - detraining;
   - stop per infortunio;
   - ritorno progressivo;
5. alimentare Decision Memory con attività realmente successive alle decisioni.

Il codice per l'export Garmin incrementale esiste già:

`GarminActivityExporter.export_incremental(...)`

e la CLI supporta:

`--incremental`

con status:

- `UPDATED`
- `ALREADY_CURRENT`

Ma manca ancora un vero timestamp semantico tipo:

`source_checked_at`

che identifichi l'ultima verifica riuscita della fonte Garmin.

---

## 21. Prima esecuzione reale

Finora le verifiche più recenti sono state eseguite con:

`python -m backend.main --dry-run`

Non conviene ancora iniziare una normale esecuzione operativa quotidiana finché il percorso dei dati correnti non è sufficientemente automatizzato.

Airtable operativo è stato intenzionalmente ripulito.

Garmin storico arriva soltanto al 30/07/2026.

Quindi il sistema oggi conosce bene lo storico, ma NON dispone ancora del flusso completo di dati correnti necessario per un utilizzo regolare reale.

---

## 22. Technical debt noto

Esiste ancora possibile debito tecnico nelle vecchie CLI manuali Decision Memory:

- demo/activity/outcome CLI;
- viewer;
- possibili mismatch model/dict.

Non è stato prioritario durante il completamento del runtime end-to-end.

Affrontarlo soltanto se necessario per il normale flusso Beta 0.4.

---

## 23. Regola di lavoro con ChatGPT

Procedere un passo alla volta.

Per ogni passo:

1. breve spiegazione;
2. un solo comando eseguibile;
3. attendere l'output;
4. decidere il passo successivo sulla base dell'output reale.

Ridurre al minimo la creazione di test.

Creare/estendere test soltanto quando proteggono un contratto non banale o una regressione significativa.

Per modificare file esistenti:

- file completo pronto da sovrascrivere;
- oppure comando automatico completo.

Mai patch manuali da applicare a mano.

---

## 24. Checkpoint finale

Stato noto al momento dell'handoff:

- branch: `feature/beta-0.4-decision-memory`
- codice pushato su GitHub;
- HEAD prima di questo handoff: `e622c56`
- origin sincronizzato;
- suite: `492 passed, 5 skipped`
- Decision Memory learning layer: implementato;
- Outcome loop end-to-end: implementato;
- Airtable fake data: eliminati dopo backup;
- Athlete Profile: conservato;
- cronologia Airtable: corretta;
- Garmin historical archive: ricostruito, 3858 attività;
- Garmin merged archive: validato;
- stale training freshness: corretta;
- stale historical load: non più trattato come carico corrente;
- prossimo grande requisito: aggiornamento automatico Garmin + semantica `source_checked_at`.

