# IronCoach

Sistema di coaching intelligente per analisi atleta, valutazione stato fisico e adattamento del piano di allenamento.

Versione corrente: **Beta 0.3**

---

# Architettura

IronCoach utilizza una pipeline modulare:
Airtable / Input atleta
|
v
Context Builder
|
v
Coach Engine
|
+----------------+
| |
v v
Recovery Analyzer Performance Analyzer
| |
v v
Load Analyzer Recovery Trend Analyzer
| |
+--------+-------+
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
+--------+--------+
| |
v v
Report Builder Decision Writer
| |
v v
Coach Report Airtable Decision Log

---

# Componenti principali

## Context Builder

Costruisce il contesto completo dell'atleta.

Include:

- profilo atleta;
- recovery corrente;
- storico recovery;
- storico training load;
- storico performance;
- ultima decisione registrata.

---

# Analyzer

## Recovery Analyzer

Valuta:

- recovery score;
- stato recovery;
- qualità sonno;
- segnali di recupero.

Esempio output:

```json
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

Supporta:

Formato verticale
{
  "date": "2026-01-01",
  "metric": "ftp",
  "value": 280
}
Formato storico largo
{
  "date": "2026-01-01",
  "ftp": 280
}
Metriche supportate:

FTP;
CSS;
VO2max corsa;
VO2max bici.

Output esempio:
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
GOOD
MODERATE
LIMITED
UNKNOWN
Considera:

carico;
performance;
recovery;
trend.
Decision Engine

Il Decision Engine produce la decisione finale.

Decisioni disponibili:
CONFERMA
ADATTA
RECUPERA
Scenario CONFERMA

Quando:

recovery favorevole;
adattamento positivo;
performance stabile o in crescita.

Output:
Decisione:
CONFERMA

Strategy:
KEEP_PLAN
Scenario ADATTA

Quando:

recovery compromessa ma gestibile;
performance in calo;
adattamento moderato.

Output:
Decisione:
ADATTA

Strategy:
ADAPT

Risk:
CAUTION
Scenario RECUPERA

Quando:

rischio elevato;
recovery critica;
segnali di sovraccarico.

Output:
Decisione:
RECUPERA

Strategy:
RECOVERY

Risk:
HIGH_ALERT
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
sintesi coach;
intelligence atleta;
ultima decisione;
nuova decisione.

Sezioni intelligence:
PROFILO ATLETA

CARICO RECENTE

ADATTAMENTO AL CARICO

TREND RECOVERY

TREND PERFORMANCE
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
Test Coverage

La pipeline è protetta da test su:

Analyzer
Recovery Analyzer
Load Analyzer
Performance Analyzer
Adaptation Analyzer
Orchestrazione
CoachEngine
Main application flow
Decision flow
Persistenza
Decision Model
Decision Writer
Scenari atleta

Coperti:

ADATTA
Recovery compromessa
Performance negativa
Adattamento moderato
RECUPERA
Recovery critica
Rischio elevato
Stato progetto

Ultima verifica:

pytest -q

169 passed
Avvio applicazione
python -m backend.main
Filosofia

IronCoach separa:

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
