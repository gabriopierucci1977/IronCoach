IronCoach

Sistema di coaching intelligente per analisi atleta, valutazione dello stato fisico e adattamento del piano di allenamento.

Versione corrente: Beta 0.3.1 hardening candidate

## Primo percorso coach MAINTAIN_PLAN (Beta 0.4)

### Scenario ipotetico con attività storiche (Codespace)

Quando l'archivio contiene attività Garmin ma non prescrizioni, avviare il
percorso di prova con:

```bash
./Avvia\ scenario\ coach.sh
```

In **Porte**, mantenere la porta `8765` privata e aprirla nel browser. La pagina
mostra le attività disponibili di nuoto, bici e corsa per
`recO4aHGKSTexpXUC`: selezionare quelle da usare e compilare esplicitamente
durata prevista e RPE. Questi obiettivi non sono ricavati dall'attività svolta.

Il percorso legge l'archivio configurato da
`IRONCOACH_MAINTAIN_PLAN_DATABASE_PATH`, ma scrive piano, copie delle sole
attività scelte, abbinamenti e valutazioni nel database separato
`<nome-base>.coach-trial.<estensione>`. Ogni nuovo scenario sostituisce soltanto quel
database di prova; non scrive nell'archivio reale e non contatta Airtable. Il
piano e ogni esito mostrati sono sempre etichettati come ipotetici. L'assenza
di un'attività non viene trasformata in una seduta saltata.

Dopo aver abilitato la cattura con le variabili `IRONCOACH_MAINTAIN_PLAN_*`
di `.env.example` ed eseguito normalmente IronCoach, le attività Garmin lette
dal `ContextBuilder` vengono trasformate in sessioni MAINTAIN_PLAN. Il runtime
attuale **non importa ancora attività Strava**: la presenza del normalizzatore
Strava non equivale a una sorgente Strava collegata e questa schermata non la
presenta come tale.

Per provarlo senza terminale, fare doppio clic su `Avvia revisione coach.pyw`
in Windows oppure su `Avvia revisione coach.sh` in macOS/Linux (se il sistema
chiede cosa fare, scegliere **Esegui**). Si apre nel browser una pagina locale:
inserire l'ID atleta e premere
**Esamina**. In alternativa resta disponibile il comando:

```bash
python -m backend.main --maintain-plan-review ID_ATLETA
```

Il comando è **di sola consultazione**: non salva abbinamenti né valutazioni.
Per confermare e salvare una proposta usare la pagina browser avviata con
uno dei file `Avvia revisione coach`.

### Preparazione e avvio in GitHub Codespaces

La pagina non inizializza un archivio vuoto: prima deve esistere almeno un
piano `MAINTAIN_PLAN` prodotto dal runtime reale e devono essere state lette le
attività Garmin dell'atleta. Nel file `.env` impostare:

```dotenv
IRONCOACH_MAINTAIN_PLAN_SNAPSHOT_ENABLED=true
IRONCOACH_MAINTAIN_PLAN_ACTUAL_SESSION_ENABLED=true
IRONCOACH_MAINTAIN_PLAN_DATABASE_PATH=data/ironcoach_maintain_plan.db
IRONCOACH_MAINTAIN_PLAN_TIMEZONE=Europe/Rome
```

Poi, nel terminale del Codespace:

1. Verificare che `GARMINTOKENS` punti alla token store Garmin valida (il
   default è `data/garmin/auth`), quindi eseguire `python -m backend.main` con
   le credenziali Airtable e Garmin configurate. Se l'archivio Garmin non
   esiste ancora, `GarminLiveSync` importa da Garmin Connect le attività reali
   degli ultimi 30 giorni e crea archivio e manifest; non crea un archivio
   vuoto quando Garmin non restituisce attività. La normale esecuzione legge i
   dati reali e salva nello stesso archivio isolato sia le attività Garmin
   supportate sia il piano,
   ma salva il piano soltanto se la decisione risultante è
   `MAINTAIN_PLAN` / `KEEP_PLAN`.
2. Verificare che l'esecuzione sia terminata senza errori e che esista
   `data/ironcoach_maintain_plan.db`. Non usare `--dry-run`: per definizione non
   scrive gli artefatti MAINTAIN_PLAN.
3. Eseguire `./Avvia\ revisione\ coach.sh ID_ATLETA`. Il controllo iniziale
   stampa `Revisione pronta` soltanto se, per quello stesso atleta, trova almeno
   una prescrizione MAINTAIN_PLAN e un'attività Garmin acquisita; altrimenti
   indica precisamente quale dei due elementi manca e non avvia la pagina.
   In alternativa, eseguire `./Avvia\ revisione\ coach.sh` senza argomenti
   (anche con doppio clic): si apre la pagina iniziale e il medesimo controllo
   viene eseguito dopo che il coach inserisce l'ID. Finché piano e attività non
   sono entrambi presenti, la pagina indica cosa manca e non dichiara pronta la
   revisione.
4. Aprire **Porte**, lasciare la porta `8765` su **Privata** e scegliere
   **Apri nel browser**. Inserire come ID atleta il `record_id` del profilo
   atleta Airtable (il valore `source_id` mostrato dal runtime).

Se compare un warning di sincronizzazione Garmin, se manca la token store o se
l'importazione termina con errore, **non** considerare riuscita la preparazione:
correggere `GARMINTOKENS`/l'autenticazione Garmin e ripetere
`python -m backend.main`. Anche un'importazione valida con zero attività negli
ultimi 30 giorni interrompe l'inizializzazione; in tal caso sincronizzare dopo
aver registrato un'attività supportata recente, senza creare file vuoti a mano.

La pagina accetta esclusivamente l'indirizzo inoltrato assegnato da GitHub al
Codespace corrente. Non copiare la porta su **Pubblica**. Usa l'archivio già
configurato da `IRONCOACH_MAINTAIN_PLAN_DATABASE_PATH` nel `.env` del progetto;
se il file non esiste, l'avvio si interrompe senza crearne uno nuovo.
I database `ironcoach_memory*.db` sono archivi Decision Memory distinti e non
devono essere indicati come `IRONCOACH_MAINTAIN_PLAN_DATABASE_PATH`.

Una sola corrispondenza globale affidabile viene proposta; viene salvata e
valutata soltanto quando il coach preme il pulsante di conferma. In quel
momento IronCoach rilegge l'intero archivio dell'atleta. La valutazione può
essere `IN_LINE`, `PARTIALLY_IN_LINE`, `DIFFERENT` o `INSUFFICIENT_DATA`.
Più candidati vengono mostrati e sottoposti al coach,
senza scegliere per ordine o somiglianza. Con zero candidati, dati incompleti
o corrotti, il comando non dichiara mai automaticamente saltata la seduta.

### Esempio concreto

Con due corse compatibili vedrai due schede, per esempio:

```text
Quale attività corrisponde all’allenamento previsto?
Previsto: snapshot-10   Attività: garmin-session-42
Previsto: snapshot-10   Attività: garmin-session-43
```

Puoi scegliere **Conferma questa corrispondenza**, oppure **Non lo so: non
salvare nulla**. La conferma viene salvata nel mapping con metodo
`ATHLETE_CONFIRMATION` e attore `coach`; subito dopo la stessa pagina mostra
la conseguenza sul piano. Se non scegli, il database non viene modificato.

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

Il Decision Model e il report mantengono l'intera decisione, inclusi
`risk_level`, `reasoning` e `intelligence`.

Nel Decision Log Airtable corrente il writer persiste soltanto i campi
effettivamente presenti nello schema:

decisione;

motivazione;

confidenza;

strategia;

azione consigliata;

priorità;

priorità allenante;

workout modificato.

`risk_level`, `reasoning` e `intelligence` non vengono inviati come colonne
Airtable finché lo schema Decision Log non dispone di campi dedicati. Restano
comunque disponibili nel runtime e nel Coach Report. Questo evita errori di
scrittura dovuti a colonne inesistenti e rende esplicito il confine tra
Decision Model e persistenza Airtable.

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

Training Analyzer;

Injury Analyzer;

Load Analyzer;

Performance Analyzer;

Adaptation Analyzer;

Recovery Trend Analyzer.

Orchestrazione

CoachEngine;

flusso applicativo principale;

iniezione condivisa della configurazione runtime;

passaggio end-to-end della freschezza dati;

contratto activity normalizzata → analyzer, inclusi segnali di dolore/infortunio;

distinzione tra training load mancante e training load realmente pari a zero;

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

Ultima verifica snapshot hardening Beta 0.3.1:

pytest --collect-only -q

Risultato:

389 test raccolti.

Nell'ambiente di ricostruzione: 384 test passati e 5 test saltati perché richiedono due fixture FIT Garmin private. I test possono usare `IRONCOACH_GARMIN_FIXTURE_DIR` per puntare a un archivio fixture esterno. La CI pubblica esegue la suite completa e tratta correttamente questi test come opzionali.

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
