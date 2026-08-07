IronCoach

Sistema di coaching intelligente per analisi atleta, valutazione dello stato fisico e adattamento del piano di allenamento.

Versione corrente: Beta 0.3

Architettura

IronCoach utilizza una pipeline modulare:

Airtable / Input atleta
          |
          v
   Context Builder
          |
          v
     Coach Engine
          |
   +------+------+
   |             |
   v             v
Recovery      Performance
Analyzer       Analyzer
   |             |
   v             v
Load        Recovery Trend
Analyzer       Analyzer
   |             |
   +------+------+
          |
          v
 Adaptation Analyzer
          |
          v
 Decision Engine
          |
          v
 Decision Model
          |
   +------+------+
   |             |
   v             v
Report       Decision
Builder       Writer
   |             |
   v             v
Coach Report  Airtable Decision Log

Componenti principali

Context Builder

Costruisce il contesto completo dell'atleta.

Include:

profilo atleta;

recovery corrente;

training corrente;

nutrition corrente;

storico recovery;

storico training load;

storico performance;

ultima decisione registrata;

freschezza strutturata dei dati;

warning di contesto.

La freschezza dei dati distingue tra:

CURRENT;

STALE;

FUTURE;

UNKNOWN.

Output semplificato:

{
  "data_freshness": {
    "level": "HIGH",
    "reasons": [
      "Recovery: dato obsoleto di 12 giorni"
    ],
    "recovery": {
      "status": "STALE",
      "level": "HIGH",
      "age_days": 12,
      "max_age_days": 3
    },
    "training": {
      "status": "CURRENT",
      "level": "LOW",
      "age_days": 2,
      "max_age_days": 7
    }
  }
}

Recovery Analyzer

Valuta:

recovery score;

stato recovery;

qualità del sonno;

segnali di recupero.

Esempio:

{
  "state": "GIALLO",
  "score": 55
}

Load Analyzer

Analizza il carico allenante:

carico recente;

carico cronico;

rapporto acuto/cronico;

distribuzione delle sedute.

Esempio:

{
  "level": "HIGH",
  "acute_chronic_ratio": 1.4
}

Performance Analyzer

Analizza l'evoluzione prestativa dell'atleta.

Supporta il formato verticale:

{
  "date": "2026-01-01",
  "metric": "ftp",
  "value": 280
}

e il formato storico largo:

{
  "date": "2026-01-01",
  "ftp": 280
}

Metriche supportate:

FTP;

CSS;

VO2max corsa;

VO2max bici.

Esempio:

{
  "trend": "DECLINING",
  "metrics": {
    "ftp": -5.4
  }
}

Recovery Trend Analyzer

Analizza l'evoluzione della recovery nel tempo.

Valuta:

miglioramento;

stabilità;

peggioramento.

Adaptation Analyzer

Valuta come l'atleta risponde al carico.

Livelli:

GOOD;

MODERATE;

LIMITED;

UNKNOWN.

Considera:

carico;

performance;

recovery;

trend.

Decision Engine

Il Decision Engine produce la decisione finale.

Decisioni disponibili:

CONFERMA;

ADATTA;

RECUPERA.

Scenario CONFERMA

Quando:

recovery favorevole;

adattamento positivo;

performance stabile o in crescita.

Decisione: CONFERMA
Strategy: KEEP_PLAN

Scenario ADATTA

Quando:

recovery compromessa ma gestibile;

performance in calo;

adattamento moderato.

Decisione: ADATTA
Strategy: ADAPT
Risk: CAUTION

Scenario RECUPERA

Quando:

rischio elevato;

recovery critica;

segnali di sovraccarico.

Decisione: RECUPERA
Strategy: RECOVERY
Risk: HIGH_ALERT

La freschezza dei dati influenza la confidenza della decisione:

dati correnti: confidenza invariata;

training obsoleto: tetto massimo configurabile, default 85;

recovery obsoleta o futura: tetto massimo configurabile, default 75.

Il cap riduce soltanto la confidenza: non può aumentare un valore già inferiore.

Decision Model

La decisione ufficiale mantiene:

{
  "decision": "ADATTA",
  "reason": "...",
  "confidence": 90,
  "strategy": "ADAPT",
  "recommended_action": "...",
  "risk_level": "CAUTION",
  "reasoning": [],
  "intelligence": {}
}

L'intelligence viene mantenuta lungo tutta la pipeline.

Report Builder

Genera il report leggibile del Coach.

Include:

profilo atleta;

recovery;

training;

nutrition;

warning dati;

sintesi coach;

intelligence atleta;

ultima decisione;

nuova decisione;

allenamento modificato.

Sezioni intelligence:

PROFILO ATLETA;

CARICO RECENTE;

ADATTAMENTO AL CARICO;

TREND RECOVERY;

TREND PERFORMANCE;

FRESCHEZZA DATI.

I warning strutturati e legacy vengono uniti senza duplicati.

Decision Writer

Gestisce il salvataggio della decisione.

Mantiene:

decisione;

motivazione;

confidenza;

strategia;

rischio;

reasoning;

intelligence;

workout modificato.

Destinazione:

Airtable Decision Log

Il salvataggio evita duplicati quando la decisione corrente è già presente.

Archivio storico Garmin

IronCoach può usare un archivio persistente delle attività Garmin già fuse tra riepiloghi JSON e file grezzi FIT, TCX o GPX.

File principali:

data/garmin/garmin_activities_merged.jsonl.gz
data/garmin/garmin_activities_merged.jsonl.gz.manifest.json
data/garmin/garmin_activity_export_report.json

L'archivio:

contiene una attività per riga;

supporta la compressione gzip;

conserva i segmenti multisport;

valida dimensione e SHA-256 tramite manifest;

non scrive nel database.

Aggiornamento incrementale Garmin

Per aggiornare un archivio già esistente aggiungendo soltanto le nuove attività:

python -m backend.importers.garmin_activity_export_cli --incremental

Il comando:

valida archivio e manifest esistenti;

legge i source_id già presenti;

esclude le attività già archiviate prima del parsing FIT, TCX o GPX;

aggiunge soltanto le attività nuove;

ordina cronologicamente l'archivio risultante;

aggiorna manifest e report;

non riscrive l'archivio quando non ci sono nuove attività;

non scrive nel database.

Esito con nuove attività:

{
  "status": "UPDATED",
  "incremental": true,
  "existing_count": 3858,
  "added_count": 1,
  "activity_count": 3859,
  "excluded_existing": 3858,
  "merge": {
    "total": 1,
    "json_only": 1,
    "merged": 0,
    "parse_errors": 0
  }
}

Seconda esecuzione sugli stessi dati:

{
  "status": "ALREADY_CURRENT",
  "incremental": true,
  "existing_count": 3859,
  "added_count": 0,
  "activity_count": 3859,
  "excluded_existing": 3859
}

Le opzioni --incremental e --force non possono essere usate insieme.

Per visualizzare tutte le opzioni:

python -m backend.importers.garmin_activity_export_cli --help

Configurazione

Copia .env.example in .env e valorizza le variabili richieste.

Variabili principali:

AIRTABLE_API_KEY
AIRTABLE_BASE_ID
OPENAI_API_KEY

Soglie opzionali di freschezza:

IRONCOACH_RECOVERY_MAX_AGE_DAYS=3
IRONCOACH_TRAINING_MAX_AGE_DAYS=7

Cap opzionali della confidenza:

IRONCOACH_FRESHNESS_HIGH_CONFIDENCE_CAP=75
IRONCOACH_FRESHNESS_MODERATE_CONFIDENCE_CAP=85

Comportamento delle soglie temporali:

valori assenti: usa i default;

valori non interi: usa i default;

valori negativi: usa i default;

0: valore valido.

Comportamento dei cap di confidenza:

valori assenti: usa i default;

valori non interi: usa i default;

valori minori di 0 o maggiori di 100: usa i default;

valori compresi tra 0 e 100: validi.

La configurazione viene caricata una sola volta all'avvio tramite RuntimeConfig.

La stessa istanza viene iniettata nel ContextBuilder e nel CoachEngine; il CoachEngine la passa al DecisionEngine.

Le soglie temporali possono anche essere passate direttamente al ContextBuilder; i parametri espliciti hanno priorità sul RuntimeConfig.

Test Coverage

La pipeline è protetta da test su:

Analyzer

Recovery Analyzer;

Load Analyzer;

Performance Analyzer;

Adaptation Analyzer;

Recovery Trend Analyzer.

Orchestrazione

CoachEngine;

flusso applicativo principale;

iniezione condivisa della configurazione runtime;

passaggio end-to-end della freschezza dati;

adattamento workout;

report finale.

Persistenza

Decision Model;

Decision Writer;

anti-duplicato Airtable;

archivio Garmin;

export incrementale Garmin;

filtro incrementale prima del parsing raw;

idempotenza dell'aggiornamento Garmin;

conflitti su activity_id e source_id.

Scenari atleta

Sono coperti:

CONFERMA;

ADATTA;

RECUPERA;

recovery compromessa;

recovery critica;

performance negativa;

adattamento moderato;

rischio elevato;

dati obsoleti;

date future;

soglie configurabili;

confidence cap configurabili;

garanzia che un confidence cap non aumenti la confidenza.

Ultima verifica:

pytest -q

Risultato:

372 passed

Avvio applicazione

python -m backend.main

Filosofia

ANALISI
   |
   v
INTELLIGENCE
   |
   v
DECISIONE
   |
   v
PERSISTENZA

Gli Analyzer analizzano.

Il Decision Engine decide.

Il Report Builder comunica.

Il Decision Writer conserva lo storico.