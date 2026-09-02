# IronCoach Beta 0.4 — START HERE

Ultimo aggiornamento: 1 settembre 2026.

Questo documento è il punto di ripartenza operativo per una nuova chat.
Supera i vecchi checkpoint quando esiste un'informazione più recente qui.

---

## 1. Repository e branch

Repository:

`https://github.com/gabriopierucci1977/IronCoach`

Branch di sviluppo:

`feature/beta-0.4-decision-memory`

Ultimo commit:

`9e82982 docs: checkpoint injury outcome coverage`

Ultimi commit rilevanti:

- `38a0247 feat: evaluate injury protection outcomes`
- `9e82982 docs: checkpoint injury outcome coverage`
- `3a3c1d7 feat: evaluate uncertainty reduction outcomes`
- `b504db3 docs: checkpoint decision memory outcome coverage`
- `e5502bb fix: complete insufficient recovery outcomes`
- `2c4dbe0 ci: run tests on python 3.12`
- `c27187e fix: resolve ambiguous activity matching safely`
- `8ac51b7 fix: treat unknown workout sport as unspecified`

CI GitHub Actions:

`PASS`

Ultima run verificata:

`33490476693`

Python CI:

`3.12`

Motivo: `garminconnect==0.3.11` richiede Python >= 3.12.

Ultima suite locale completa:

`505 passed, 5 skipped in 1.52s`

---

## 2. Regola di lavoro

Procedere un passo alla volta.

Quando un file esistente deve essere modificato:

- fornire il file completo pronto da sovrascrivere; oppure
- fornire un comando automatico completo e sicuro.

Non chiedere modifiche manuali di singole righe.

Ridurre al minimo i nuovi test.
Aggiungerli solo per contratti o regressioni realmente significativi.

Prima dei commit ripristinare eventuali `.pyc` tracciati sotto:

`config/__pycache__/`

---

## 3. Obiettivo Beta 0.4

La Decision Memory deve imparare dalla risposta dell'atleta alle
decisioni precedenti e calibrare prudentemente decisioni future.

Vincoli:

- `DecisionEngine` resta deterministico;
- la memoria non cambia la regola scelta;
- la memoria non cambia la decisione scelta;
- massimo aggiustamento confidence: ±5;
- minimo 3 outcome valutabili;
- HIGH_ALERT non viene modificato dalla memoria;
- freshness cap applicato dopo la calibrazione memory;
- missing data non significa automaticamente bene o male.

---

## 4. Learning policy

Gli outcome:

- `POSITIVE`
- `NEUTRAL`
- `NEGATIVE`

entrano nel denominatore del learning.

`INSUFFICIENT_DATA` è escluso.

Formula:

`(positive_count - negative_count) / evaluable_count`

moltiplicata per il massimo delta di confidence.

Il learning è raggruppato per:

`rule_id`

---

## 5. Lifecycle Decision Memory

Stati:

- `OPEN`
- `WAITING_FOR_ACTIVITY`
- `WAITING_FOR_OUTCOME`
- `COMPLETE`
- `INCOMPLETE`

`INSUFFICIENT_DATA` è un outcome finale valido.

Alla maturazione del 7d un episodio può quindi diventare:

`COMPLETE + INSUFFICIENT_DATA`

`INCOMPLETE` è riservato a casi tecnici/non finalizzabili.

Commit della correzione:

`e5502bb`

---

## 6. Activity matching

Regole correnti:

- sport `UNKNOWN` o vuoto = sport non specificato;
- 0 candidate -> resta `WAITING_FOR_ACTIVITY`;
- 1 candidata -> viene collegata;
- più candidate -> nessuna scelta arbitraria;
- matching ambiguo -> `WAITING_FOR_OUTCOME`;
- adherence -> `UNKNOWN`.

Non introdurre finestre temporali arbitrarie per forzare il match.

---

## 7. Primo episodio reale

Episode ID:

`1b88bb35-9159-4cff-9010-42b7d5a8ac1b`

Decisione:

- data: 28 agosto 2026;
- action: `ADATTA`;
- rule: `ADAPTATION_MODERATE`;
- primary intent: `PROTECT_INJURY`;
- confidence: `90`.

Matching Garmin reale:

- SWIM;
- BIKE;
- RUN.

Risultato:

- nessuna attività scelta arbitrariamente;
- status: `WAITING_FOR_OUTCOME`;
- actual activity: `None`;
- adherence: `UNKNOWN`.

Backup SQLite prima del processing reale:

`data/ironcoach_memory.db.before_first_real_processing_20260901_061935.bak`

Le finestre già maturate erano:

- 24h: `INSUFFICIENT_DATA`;
- 72h: `INSUFFICIENT_DATA`.

La finestra 7d matura:

`4 settembre 2026`

NON forzarla prima di quella data.

Dopo l'introduzione del nuovo injury outcome, alla prossima valutazione
l'episodio deve essere instradato al processor `PROTECT_INJURY`.

Poiché la baseline reale non dispone di un segnale injury temporale
esplicito sufficiente e il Training Log Airtable reale è vuoto,
l'esito atteso resta:

`INSUFFICIENT_DATA`

Alla maturazione del 7d ci si aspetta:

- outcome 7d: `INSUFFICIENT_DATA`;
- overall: `INSUFFICIENT_DATA`;
- status: `COMPLETE`;
- evaluator: `injury-outcome-v1`.

Verificare realmente questi valori, non forzarli.

---

## 8. Outcome intent-specific implementati

### RESTORE_RECOVERY

Valutabile tramite `recovery_history` Airtable.

Confronto livelli `RecoveryAnalyzer` pre/post:

- miglioramento -> `POSITIVE`;
- invariato -> `NEUTRAL`;
- peggioramento -> `NEGATIVE`;
- dati mancanti -> `INSUFFICIENT_DATA`.

### REDUCE_LOAD

Attualmente usa lo stesso contratto recovery outcome.

### MANAGE_UNCERTAINTY

Commit:

`3a3c1d7`

Usa esclusivamente recovery Airtable già decision-driving.

Contratto:

- baseline recovery deve essere `UNKNOWN`;
- nuovo recovery realmente classificabile -> `POSITIVE`;
- nessun dato nuovo o ancora `UNKNOWN` -> `INSUFFICIENT_DATA`;
- nessun `NEUTRAL` o `NEGATIVE` inventato.

Overall a 7d:

- `POSITIVE` se almeno una finestra ha ridotto realmente l'incertezza;
- altrimenti `INSUFFICIENT_DATA`.

### PROTECT_INJURY

Commit:

`38a0247`

Usa esclusivamente:

`airtable_training_history`

Segnali temporali ammessi:

- `pain_score`;
- `current_problem`.

NON usa:

- Garmin;
- injury history statica;
- limitazioni statiche atleta.

Baseline:

`pre_decision_state["training"]`

Il confronto riusa esclusivamente le categorie di `InjuryAnalyzer`:

- miglioramento -> `POSITIVE`;
- invariato -> `NEUTRAL`;
- peggioramento -> `NEGATIVE`;
- segnale assente -> `INSUFFICIENT_DATA`.

Nessuna nuova soglia numerica introdotta.

Overall:

risultato della finestra 7d.

---

## 9. Intenti non ancora valutabili

Restano intenzionalmente non valutabili senza un contratto più forte:

- `RESTORE_FUELING`;
- `PROTECT_PERFORMANCE`;
- `MAINTAIN_PLAN`.

Devono restare `INSUFFICIENT_DATA` quando manca un segnale
intent-specific affidabile.

Non introdurre proxy deboli per completare artificialmente la copertura.

### RESTORE_FUELING

Airtable dispone solo dello stato Nutrition corrente.
Non esiste ancora un vero `nutrition_history`.

Garmin calories = expenditure, non intake.

Garmin `waterEstimated` = stima domanda/perdita liquidi,
non idratazione realmente assunta.

Quindi Garmin fueling resta osservazionale.

### PROTECT_PERFORMANCE

Il canale Airtable performance temporale esiste nel codice,
ma il Performance Log reale è vuoto.

Il fallback restituisce metriche statiche atleta e non è un trend temporale.

Garmin VO2max resta osservazionale e non deve essere promosso
automaticamente a outcome decision-driving.

### MAINTAIN_PLAN

Il contratto richiede:

- workout completato;
- stabilità generale.

La sola aderenza non dimostra volume, intensità e obiettivo completati.

Il solo recovery non rappresenta stabilità generale.

Quindi non assegnare `POSITIVE` semplicemente perché esiste
un'attività successiva alla decisione.

---

## 10. Garmin

Garmin Connect è usato in sola lettura.

Token-only runtime.

Non salvare o stampare password/token/email.

Archivio storico/live:

`data/garmin/garmin_activities_merged.jsonl.gz`

Ultimo conteggio noto:

`3899 attività`

Ultima attività nota:

30 agosto 2026 RUN.

Garmin Recovery, Performance e Fueling sono osservazionali.

Non devono modificare `DecisionEngine` o Decision Memory outcome
senza un nuovo contratto esplicito.

---

## 11. Airtable reale

Athlete Profile preservato.

I vecchi dati fake sono stati eliminati dai log.

Stato reale noto:

- Training Log: vuoto;
- Recovery Log: vuoto;
- Nutrition Log: vuoto;
- Performance Log: vuoto.

Esiste una decisione reale salvata durante il primo run normale.

Evitare di eseguire casualmente:

`backend.main`

in modalità non-dry-run, perché può persistere nuove decisioni
sia in Airtable sia in SQLite.

---

## 12. SQLite

Source of truth Decision Memory:

`data/ironcoach_memory.db`

`data/` è gitignored.

Non cancellare o ricreare il database reale durante test o analisi.

Usare backup prima di processing manuale reale.

---

## 13. Data freshness

Non interpretare assenza di attività recente come stop reale
se la sorgente Garmin è stale.

`source_checked_at` è distinto da `last_activity_at`.

Manifest `created_at` non deve essere usato come source freshness.

Load stale/future deve diventare `UNKNOWN` nel coaching runtime.

---

## 14. File handoff precedenti

Documentazione storica:

- `docs/IronCoach Beta 0.4.bis — Handoff.md`
- `docs/IronCoach Beta 0.4.ter — Handoff.md`
- `docs/IronCoach Beta 0.4.quater — Handoff.md`

Questo file `START HERE` contiene lo stato operativo più recente.

Consultare gli handoff precedenti solo per dettagli storici.

---

## 15. Prossimo passo esatto

Prima di qualsiasi modifica:

`git status --short`

Il working tree deve essere pulito.

Fino al 4 settembre 2026:

- non forzare il primo episodio reale;
- non promuovere gli intenti ancora unsupported tramite proxy;
- non eseguire casualmente un normale `backend.main`.

Dal 4 settembre 2026 in poi:

processare intenzionalmente SOLO gli episodi già pendenti,
senza creare una nuova decisione.

Comando dedicato:

`python3.12 -m backend.main --process-pending-memory`

Il comando costruisce il contesto dalle sorgenti configurate e riusa i
runtime activity/outcome della Decision Memory. Non esegue la coaching
pipeline, non salva una nuova decisione e non passa un `as_of`, quindi
le finestre non ancora mature non vengono forzate.

Verificare sul primo episodio reale:

- routing verso injury outcome;
- 7d `INSUFFICIENT_DATA`;
- overall `INSUFFICIENT_DATA`;
- status `COMPLETE`;
- `injury-outcome-v1`;
- esclusione dell'episodio dal denominatore del learning.

Dopo questa validazione reale, verificare che il learning evidence
resti invariato in assenza di almeno 3 outcome valutabili.

---

## 16. Istruzione per la nuova chat

Nella nuova chat scrivere semplicemente:

`Riprendiamo IronCoach da docs/IRONCOACH_BETA_0_4_START_HERE.md. Leggilo come fonte operativa principale e procediamo un passo alla volta.`

Non è necessario ricapitolare manualmente il lavoro precedente.
