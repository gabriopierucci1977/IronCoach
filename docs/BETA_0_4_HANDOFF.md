IronCoach Beta 0.4 — Handoff

Ultimo aggiornamento: 2026-08-24

Stato repository

Repository:

gabriopierucci1977/IronCoach

Baseline stabile precedente:

tag: v0.3.1

main merge commit: 8d2919a

release: IronCoach v0.3.1 — Integration Hardening

Branch Beta 0.4 attivo:

feature/beta-0.4-decision-memory

Il branch è stato pubblicato su GitHub ed è configurato per tracciare:

origin/feature/beta-0.4-decision-memory

Commit Beta 0.4 già pubblicati:

119e810 feat: add decision rule and intent metadata

a8d7699 feat: add decision memory foundation

Ultima full regression suite:

442 passed, 5 skipped

I 5 skip sono i fixture Garmin privati già noti e attesi.

Working tree al momento dell'handoff:

pulito prima del push finale.

Obiettivo Beta 0.4

IronCoach Beta 0.4 deve imparare dalla risposta dell'atleta alle decisioni precedenti e usare quell'esperienza per migliorare le decisioni future.

Principio architetturale:

contesto corrente
    ↓
analyzers
    ↓
regole di sicurezza deterministiche
    ↓
esperienza storica dell'atleta
    ↓
decision intelligence
    ↓
decisione finale

Il DecisionEngine resta deterministico.

Le regole di sicurezza non vengono delegate liberamente a un LLM.

La Decision Memory deve registrare il ciclo:

contesto
→ decisione
→ attività realmente eseguita
→ aderenza
→ outcome
→ memoria
→ decisioni future

1. Decision metadata completati

File:

backend/decision.py

Il modello Decision è stato esteso in modo retrocompatibile con:

decision_id

rule_id

primary_intent

supporting_intents

Decision.to_dict() espone tutti questi campi.

Nota:

decision_id è supportato dal modello;

la generazione automatica del decision_id nel flusso runtime non è ancora implementata.

2. Rule IDs completati

File:

backend/engines/decision_engine.py

Tutti i 15 rami reali del DecisionEngine espongono ora un rule_id stabile.

INJURY_CRITICAL

RECOVERY_CRITICAL

RECOVERY_MODERATE_HIGH_LOAD_DECLINING

RECOVERY_MODERATE_INJURY_HIGH

RECOVERY_MODERATE_TRAINING_HIGH_NUTRITION_HIGH

RECOVERY_FAVORABLE_TRAINING_HIGH_LOAD_HIGH

RECOVERY_FAVORABLE_NUTRITION_HIGH

ADAPTATION_LIMITED

ADAPTATION_MODERATE

PERFORMANCE_DECLINING_LOAD_HIGH

RECOVERY_UNKNOWN_WITH_STRESS

RECOVERY_UNKNOWN

MULTIPLE_MODERATE_FACTORS

WELLBEING_HIGH_STRESS

DEFAULT_CONFIRM

Concetto:

decision = cosa fare
rule_id  = quale regola ha prodotto la decisione
intent   = quale risultato la decisione vuole ottenere

I rule_id devono essere considerati identificatori storici stabili e non rinominati con leggerezza.

3. Intent vocabulary

Vocabolario ufficiale:

PROTECT_INJURY

RESTORE_RECOVERY

REDUCE_LOAD

RESTORE_FUELING

PROTECT_PERFORMANCE

MAINTAIN_PLAN

MANAGE_UNCERTAINTY

Priorità per i casi aggregati:

PROTECT_INJURY

RESTORE_RECOVERY

RESTORE_FUELING

REDUCE_LOAD

PROTECT_PERFORMANCE

MANAGE_UNCERTAINTY

MAINTAIN_PLAN

Regole esplicite:

intent deterministico.

Regole aggregate:

intent risolto dinamicamente.

Regole con intent dinamico:

ADAPTATION_LIMITED

ADAPTATION_MODERATE

MULTIPLE_MODERATE_FACTORS

RECOVERY_UNKNOWN_WITH_STRESS:

primary intent: MANAGE_UNCERTAINTY

supporting intents derivati dai segnali di stress effettivamente presenti.

4. AdaptationAnalyzer evoluto

File:

backend/analyzers/adaptation_analyzer.py

Output mantenuti:

adaptation_level

risk_factors

positive_factors

reasons

Nuovo output machine-readable:

risk_codes

Risk codes ufficiali:

PHYSICAL_LIMITATION

HIGH_LOAD

HIGH_ACUTE_CHRONIC_RATIO

PERFORMANCE_DECLINING

POOR_RECOVERY

MODERATE_RECOVERY

Mapping verso gli intent dinamici:

PHYSICAL_LIMITATION
→ PROTECT_INJURY

POOR_RECOVERY
MODERATE_RECOVERY
→ RESTORE_RECOVERY

HIGH_LOAD
HIGH_ACUTE_CHRONIC_RATIO
→ REDUCE_LOAD

PERFORMANCE_DECLINING
→ PROTECT_PERFORMANCE

Non viene interpretato testo libero come "Carico recente elevato" per prendere decisioni machine-readable.

Il percorso:

AdaptationAnalyzer
→ CoachEngine
→ assessments["adaptation"]
→ DecisionEngine

mantiene risk_codes senza filtri o ricostruzioni.

5. DecisionEpisode completato

File:

backend/models/decision_episode.py

DecisionEpisode è una dataclass.

Rappresenta il ciclo di vita completo di una decisione IronCoach.

Principi principali:

episode_id: UUID v4 interno

decision_id: identità separata della decisione

schema_version: "1"

stato iniziale: OPEN

timestamp audit: ISO 8601 UTC con suffisso Z

liste e dizionari con default_factory

decisione originale separata dagli outcome successivi

Stati episodio:

OPEN

WAITING_FOR_ACTIVITY

WAITING_FOR_OUTCOME

COMPLETE

INCOMPLETE

INCOMPLETE è destinato a casi tecnici/non finalizzabili, non semplicemente a dati scarsi.

Un episodio può diventare COMPLETE anche con outcome INSUFFICIENT_DATA.

6. Adherence contract progettato

Stati:

FOLLOWED

PARTIALLY_FOLLOWED

NOT_FOLLOWED

UNKNOWN

Prima della valutazione:

NULL

Principio fondamentale:

aderenza alla raccomandazione
≠
qualità dell'outcome

Un outcome negativo non implica automaticamente che la raccomandazione fosse sbagliata.

L'assenza di attività non deve essere interpretata automaticamente come NOT_FOLLOWED.

7. Outcome contract progettato

Finestre:

24h

72h

7d

overall

Stati:

POSITIVE

NEUTRAL

NEGATIVE

INSUFFICIENT_DATA

Prima della valutazione:

NULL

Il significato di outcome deve essere intent-specific.

Esempi:

PROTECT_INJURY
→ dolore, sintomi, limitazioni

RESTORE_RECOVERY
→ recovery, sonno, fatigue, trend

REDUCE_LOAD
→ carico vs tolleranza, recovery, continuità

RESTORE_FUELING
→ stato nutrizionale, fatigue, capacità di allenarsi

PROTECT_PERFORMANCE
→ trend prestativo, completion, carico

MAINTAIN_PLAN
→ workout completato + stabilità generale

MANAGE_UNCERTAINTY
→ nuovi dati, freschezza, riduzione dell'incertezza

8. Decision Memory SQLite

Directory:

backend/decision_memory/

File:

backend/decision_memory/__init__.py

backend/decision_memory/schema.py

backend/decision_memory/repository.py

SQLite è il source of truth della Decision Memory.

Non sono state aggiunte dipendenze:

viene usato sqlite3 della standard library.

Database runtime previsto:

data/ironcoach_memory.db

data/ è già gitignored.

9. Schema SQLite completato

Tabella:

decision_episodes

Lo schema include:

Identità

episode_id

athlete_id

decision_id

decision_timestamp

status

schema_version

Decision metadata

decision_action

strategy

rule_id

primary_intent

decision_confidence

supporting_intents_json

Snapshot

pre_decision_state_json

athlete_state_json

Workout / activity

planned_workout_json

recommended_workout_json

actual_activity_json

actual_activity_id

actual_activity_source

Adherence

adherence_status

adherence_evidence_json

adherence_evaluated_at

Outcome 24h

outcome_24h_status

outcome_24h_evidence_json

outcome_24h_evaluated_at

Outcome 72h

outcome_72h_status

outcome_72h_evidence_json

outcome_72h_evaluated_at

Outcome 7d

outcome_7d_status

outcome_7d_evidence_json

outcome_7d_evaluated_at

Overall

overall_outcome_status

overall_outcome_confidence

overall_outcome_evidence_json

overall_outcome_evaluated_at

Versioni

decision_engine_version

adherence_evaluator_version

outcome_evaluator_version

External references

airtable_decision_record_id

Audit

created_at

updated_at

I campi strutturati flessibili sono serializzati nelle colonne *_json.

10. SQLite constraints

CHECK constraints implementati per:

Episode status

OPEN

WAITING_FOR_ACTIVITY

WAITING_FOR_OUTCOME

COMPLETE

INCOMPLETE

Decision action

CONFERMA

ADATTA

RECUPERA

Primary intent

PROTECT_INJURY

RESTORE_RECOVERY

REDUCE_LOAD

RESTORE_FUELING

PROTECT_PERFORMANCE

MAINTAIN_PLAN

MANAGE_UNCERTAINTY

Adherence

FOLLOWED

PARTIALLY_FOLLOWED

NOT_FOLLOWED

UNKNOWN

oppure NULL

Outcome

POSITIVE

NEUTRAL

NEGATIVE

INSUFFICIENT_DATA

oppure NULL

Applicato a:

24h

72h

7d

overall

decision_id è UNIQUE.

11. SQLite indexes

Indici applicativi implementati:

(athlete_id, decision_timestamp)
(athlete_id, primary_intent)
(athlete_id, overall_outcome_status)
(status)

Nomi:

idx_decision_episodes_athlete_timestamp

idx_decision_episodes_athlete_intent

idx_decision_episodes_athlete_outcome

idx_decision_episodes_status

12. DecisionMemoryRepository completato

File:

backend/decision_memory/repository.py

Metodi implementati:

create(episode)

get_by_episode_id(episode_id)

update(episode)

Il repository:

inizializza automaticamente il database;

serializza/deserializza JSON;

ricostruisce un vero DecisionEpisode;

preserva None per i campi JSON opzionali;

aggiorna updated_at durante update().

update() aggiorna solo i campi evolutivi dell'episodio.

Non deve riscrivere automaticamente:

episode_id

decision_id

decisione originale

rule_id

intenti originali

snapshot pre-decisione

13. Storage architecture

Architettura scelta: ibrida.

Airtable
= stato operativo umano / proiezione

Garmin archive
= cosa l'atleta ha realmente fatto

SQLite Decision Memory
= cosa IronCoach ha deciso e cosa è successo dopo

SQLite è la fonte autorevole per la Decision Memory completa.

Airtable non deve diventare il source of truth della memoria decisionale.

14. Identità e linking progettati

episode_id

UUID v4

interno

immutabile

decision_id

UUID v4

interno

UNIQUE nella Decision Memory

deve essere generato prima della persistenza Airtable

athlete_id

deve essere stabile

non usare il nome atleta

per Beta 0.4.0 riusare il miglior identificatore stabile già disponibile nel flusso corrente, evitando un refactoring identità più ampio

actual_activity

Link previsto tramite:

actual_activity_id

actual_activity_source

Una volta accettato un match, l'identificatore deve essere persistito.

Un match ambiguo non deve essere indovinato:

deve portare ad adherence UNKNOWN.

15. Test aggiunti

Decision intelligence:

tests/test_decision_model_metadata.py

tests/test_decision_engine_rule_metadata.py

tests/test_decision_engine_intents.py

tests/test_decision_engine_dynamic_intents.py

Aggiornato:

tests/test_adaptation_analyzer.py

Decision Memory:

tests/test_decision_episode.py

tests/test_decision_memory_schema.py

tests/test_decision_memory_schema_indexes.py

tests/test_decision_memory_schema_constraints.py

tests/test_decision_memory_repository.py

tests/test_decision_memory_repository_update.py

Ultima full regression suite:

442 passed, 5 skipped

16. Cosa NON è ancora implementato

Non assumere che i seguenti componenti esistano già.

generazione automatica di decision_id nel runtime

creazione automatica di DecisionEpisode dopo una decisione

integrazione del repository dentro CoachEngine

configurazione runtime definitiva per data/ironcoach_memory.db

transizione automatica OPEN -> WAITING_FOR_ACTIVITY

ricerca/lista episodi per atleta

ActivityMatcher

AdherenceEvaluator

OutcomeEvaluator

MemoryUpdater

avanzamento automatico delle finestre 24h/72h/7d

similarità tra episodi

learning score

decision intelligence basata sugli episodi storici

proiezione Airtable della Decision Memory

scheduler/background updater

17. State machine progettata

Flusso previsto:

OPEN
↓
WAITING_FOR_ACTIVITY
↓
WAITING_FOR_OUTCOME
↓
COMPLETE

Stato tecnico alternativo:

INCOMPLETE

Principi:

transizioni monotone;

aggiornamenti idempotenti;

nessuna rivalutazione automatica continua di outcome già finalizzati;

episodio chiudibile entro circa 8 giorni;

dati scarsi → INSUFFICIENT_DATA, non necessariamente INCOMPLETE.

All'avvio futuro di IronCoach:

avanzare gli episodi precedenti ancora aperti;

poi creare la nuova decisione corrente.

Nessuno scheduler iniziale.

18. Prossimo milestone consigliato

Riprendere con una integrazione runtime minima della Decision Memory.

Non iniziare ancora da ActivityMatcher o OutcomeEvaluator.

Prima analizzare:

dove viene prodotto il dizionario decisionale finale nel CoachEngine;

dove DecisionWriter persiste la decisione;

quale identificatore atleta stabile è già disponibile nel ContextBuilder / CoachEngine;

dove è più corretto configurare il path data/ironcoach_memory.db.

Obiettivo del prossimo piccolo milestone:

DecisionEngine
→ decision_id UUID v4
→ DecisionEpisode
→ DecisionMemoryRepository.create()

Senza ancora:

activity matching;

adherence evaluation;

outcome evaluation;

learning.

19. Primo passo esatto quando si riprende

Metodo di lavoro da mantenere:

un passo alla volta;

prima leggere il codice esistente;

test-first quando possibile;

non modificare più componenti contemporaneamente;

full file replacement quando si modifica un file esistente.

Primo comando consigliato alla ripresa:

git status --short

Deve essere pulito.

Poi:

git log --oneline -5

Verificare almeno:

a8d7699 feat: add decision memory foundation
119e810 feat: add decision rule and intent metadata

Dopo questa verifica, analizzare il punto del CoachEngine immediatamente successivo a:

decision = self.decision_engine.decide(
    assessments
)

senza modificare ancora il codice.

20. Regole operative per continuare il lavoro

Durante lo sviluppo:

procedere sempre un passo alla volta;

spiegare brevemente cosa stiamo facendo e perché;

non anticipare cinque o sei passaggi insieme;

dopo ogni comando attendere l'output;

quando un file esistente deve essere modificato, fornire sempre l'intero file completo, non patch manuali o istruzioni del tipo “vai alla riga X”;

evitare comandi con ... o placeholder ambigui;

prima dei commit controllare git status --short;

rimuovere/ripristinare eventuali __pycache__;

prima del commit usare git diff --check o git diff --cached --check;

eseguire i test mirati durante il TDD;

prima di un checkpoint importante eseguire python -m pytest -q.

21. Stato al momento della pausa

Branch remoto disponibile:

origin/feature/beta-0.4-decision-memory

Push completato con successo.

Commit disponibili su GitHub:

119e810 feat: add decision rule and intent metadata
a8d7699 feat: add decision memory foundation

Full suite finale:

442 passed, 5 skipped

La Beta 0.4 è quindi in uno stato sicuro da cui riprendere.