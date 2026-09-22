# Maintain Plan — contratto ridotto di matching runtime futuro

**Stato:** normativo, non implementato, default-off
**Ambito:** sola decisione di associazione fra artefatti già persistiti

Questo contratto non abilita un matcher. Fino a un'implementazione e a
un'attivazione separate, nessun percorso runtime DEVE eseguirlo o usarne i
risultati. Un flag assente, falso, illeggibile o sconosciuto equivale a
**disabilitato**. Ogni errore di lettura, decodifica, validazione o persistenza
fallisce chiuso, senza mapping parziale.

## 1. Input e scope autorevoli

Gli input sono `PrescriptionSnapshot` e `ActualSession` canonici, immutabili e
**già persistiti**, più la tupla esplicita del tipo esistente
`DirectIdEvidence` definito nel
[contratto outcome §5.7](MAINTAIN_PLAN_OUTCOME_CONTRACT.md). Non sono ammessi
payload della richiesta, history aggregate, record provider, nomi, decisioni
correnti, ricostruzioni o fallback. Uno scope contiene un soggetto opaco,
l'insieme completo degli snapshot eleggibili, la tupla completa delle sessioni
dello stesso soggetto e l'eventuale evidence diretta esplicitamente fornita.

Prima di valutare candidati, il matcher DEVE leggere e validare l'intero scope.
`subject_ref` è confrontato sui byte UTF-8 esatti come definito dal
[contratto ownership](MAINTAIN_PLAN_SUBJECT_OWNERSHIP_CONTRACT.md). Ownership
mancante, corrotta o discordante, inclusa quella incontrata seguendo un ID
diretto, invalida lo scope completo. Un ID diretto non supera mai ownership.

Gli snapshot e le sessioni sono ordinati per la rappresentazione byte UTF-8
dei rispettivi ID, in ordine lessicografico unsigned. L'ordine serve soltanto a
rendere deterministici valutazione e output: tutti i candidati sono valutati e
l'ordine non è mai un tie-break.

### 1.1 Provenienza di ogni predicato

| Decisione o predicato | Dato autorevole permesso |
|---|---|
| ownership e scope | `subject_ref` persistito di snapshot e sessione |
| relazione diretta | `DirectIdEvidence.session_id` e `.returned_prescription_id`, mai campi reinterpretati da `ActualSession` |
| finestra | `PrescriptionSnapshot.scheduled_window` e `ActualSession.start` |
| composition, componenti, ordine e sostituzioni | composition/componenti authored dello snapshot e osservati della sessione |
| `environment` e `mode` | vincolo authored del componente e valore osservato presente dello stesso componente |
| consecutività Brick | componenti, start/end e transizioni osservati, più massimo gap esplicito o default versionato |
| cardinalità globale | insieme completo degli snapshot e tupla completa delle sessioni nello scope |
| assenza autorevole nell'intera finestra | **non disponibile** negli input ridotti correnti |
| insert del mapping | coppia `ONE`, artefatti e due lati del mapping riletti nella transazione |

Nessun esito o predicato può dipendere da un dato diverso da quelli elencati.
In particolare timestamp di sincronizzazione, discovery di predecessori o
successori e assenza nei dati localmente disponibili non costituiscono prova
di copertura.

## 2. Autorità dell'ID diretto

Il matcher legge `returned_prescription_id` soltanto da un
`DirectIdEvidence` esplicito il cui envelope (`evidence_id`, `session_id`,
`source` e `provenance`) è valido e riferisce una sessione canonica dello
scope. `ActualSession.raw_ids`, `original_activity_id`, provenance e metadata
non sono mai reinterpretati come direct-ID evidence. Un valore è autorevole
soltanto se è ben formato, risolve un solo snapshot persistito nello scope e
quello snapshot appartiene allo stesso soggetto della sessione riferita. In tal
caso seleziona quell'associazione anche se esistono alternative strutturali,
lo start è fuori finestra o l'esecuzione devia dalla prescrizione. Le
deviazioni appartengono a una valutazione successiva e non annullano la
relazione.

Evidence cross-subject, un envelope `DirectIdEvidence` persistito corrotto, o
ownership persistita corrotta su uno dei due lati è corruzione: fallimento
chiuso dello scope completo. In un envelope altrimenti valido, un valore ID
restituito pendente, ambiguo o malformato non autorizza fallback strutturale e
produce il boundary non automatico `CONFIRMATION_REQUIRED`. Questo documento
non definisce come una conferma sia richiesta, memorizzata o applicata.

## 3. Dispatch della composition

La composition persistita è decodificata prima del matching:

* dati sconosciuti, incoerenti o indecodificabili sono corruzione e impongono
  rollback dello scope completo; non sono mai “errore oppure `NOT_EVALUABLE`”;
* una composition valida e nota che una futura implementazione dichiara
  deliberatamente fuori dalle proprie capability può produrre
  `NOT_EVALUABLE`;
* le composition core sono `SINGLE`, `BRICK` e `MULTISPORT`.

Senza ID diretto autorevole, per tutte e tre le composition lo start della
sessione DEVE essere incluso nella `scheduled_window` chiusa dello snapshot.
Una finestra puntuale ammette soltanto lo stesso istante. La ricerca di
predecessori o successori può fornire evidenza di composizione, ma non può
creare un match strutturale fuori finestra.

## 4. Compatibilità strutturale

### 4.1 Regole comuni

Composition, cardinalità, ordine e componenti devono essere compatibili. Per
ogni componente pianificato si confronta esclusivamente il componente
osservato corrispondente. `allowed_substitutions` è locale a quel componente:
non si inferisce, eredita, propaga o scambia fra componenti.

La disciplina osservata deve coincidere con quella prescritta oppure con una
sostituzione esplicitamente ammessa per quel componente. I vincoli authored
facoltativi `environment` e `mode`, sulla disciplina originale o sulla
sostituzione, si applicano quando il corrispondente valore osservato è
presente. Metadata osservato mancante non elimina il candidato; un valore
esplicito contraddittorio lo rende incompatibile. Queste regole valgono per
`SINGLE`, `BRICK` e `MULTISPORT`.

### 4.2 SINGLE e MULTISPORT

`SINGLE` richiede esattamente un componente. `MULTISPORT` richiede almeno due
componenti distinti, nell'ordine authored, e conserva i confini osservati; non
viene reinterpretato come `BRICK`. Ogni componente deve soddisfare le regole
comuni e deve disporre dell'evidenza richiesta dal formato persistito.

### 4.3 BRICK

`BRICK` richiede almeno due componenti consecutivi nell'ordine authored,
transizioni valide fra ogni coppia adiacente e timing comparabile sufficiente
per stabilire ordine e gap. Start/end mancanti, non confrontabili o
contraddittori non consentono un match automatico. I componenti non possono
sovrapporsi; nessuna attività estranea può essere interposta; attività non
consecutive non possono formare automaticamente una Brick.

Ogni gap deve essere non negativo e non superiore al massimo esplicito dello
snapshot oppure, se assente, al default versionato di **15 minuti**. Policy
gap mancante, invalida o non determinabile rende il candidato non valutabile,
mai implicitamente illimitato. La transizione deve collegare esattamente i due
componenti adiacenti, essere temporalmente coerente ed essere compresa nel gap.

## 5. Valutazione globale e cardinalità

Per ogni snapshot il matcher DEVE valutare la tupla completa delle sessioni
same-subject; per ogni sessione DEVE inoltre costruire l'insieme, sull'intero
scope, di tutti gli snapshot strutturalmente compatibili. Questi due passaggi
precedono `ONE` e qualunque insert.

Se una sessione è compatibile con più snapshot dalle finestre sovrapposte e
nessun ID diretto autorevole ne seleziona uno, nessuna iterazione può scegliere:
il risultato è ambiguo e non automatico. Analogamente, più sessioni
compatibili con uno snapshot sono ambigue. La cardinalità deterministica è:

* `ZERO`: nessuna sessione strutturalmente compatibile; è cardinalità pura del
  candidate set e non prova l'assenza di una sessione reale;
* `ONE`: esattamente una coppia globale, senza competizione su nessuno dei due
  lati;
* `MULTIPLE`: ogni altra pluralità o competizione.

`ONE` può produrre un mapping automatico. `MULTIPLE` produce
`CONFIRMATION_REQUIRED`. `ZERO`, inclusa una tupla di sessioni vuota, produce
deterministicamente `NOT_EVALUABLE`: non crea mapping, `NO_MATCH`, conferma di
assenza o altra decisione persistita sull'assenza.

### Osservazione zero e copertura

Un futuro outcome autorevole “nessuna sessione” richiederà copertura autorevole
e continua dell'intero intervallo eleggibile chiuso. L'unione degli intervalli
di copertura validi dovrà includere ogni istante dalla frontiera iniziale a
quella finale; un gap, una frontiera aperta, una sorgente non autorevole o un
tratto non verificato impedirà tale outcome. Per una finestra puntuale dovrà
esistere copertura autorevole proprio di quel punto; intervalli adiacenti
saranno continui solo quando le rispettive inclusività copriranno la frontiera
comune.

Nessun input ammesso dal boundary ridotto corrente trasporta questi intervalli.
Di conseguenza l'outcome autorevole di assenza resta **irraggiungibile** finché
un contratto separatamente approvato non fornirà una prova di copertura
autorevole. Non si fabbrica copertura da tupla vuota, timestamp, assenza locale
o discovery di predecessori/successori; questo documento non introduce query
provider/history, tabelle, sidecar, schema, migrazioni, expiry o reconciliation.

## 6. Persistenza atomica minima

Il solo write consentito da questo contratto è il mapping risolto `ONE`. Deve
valere unicità bidirezionale: uno snapshot non può mappare più sessioni e una
sessione non può mappare più snapshot.

L'implementazione futura DEVE aprire `BEGIN IMMEDIATE`, rileggere sotto la
stessa transazione snapshot, sessione, ownership ed entrambi i lati del
mapping, quindi ripetere le invarianti prima dell'insert. Qualunque modifica,
mapping concorrente, mismatch o dato illeggibile causa rollback completo. Il
retry della stessa associazione semanticamente identica restituisce lo stesso
mapping senza duplicarlo; stesso ID con contenuto diverso o uno dei due lati
già associato diversamente è conflitto fail-closed. Commit avviene soltanto
dopo tutte le verifiche.

## 7. Lavoro differito (non normativo)

Sono differiti: UX e memorizzazione delle conferme, evaluation dell'aderenza,
reporting/learning e strategie operative di rollout. Non sono parte di questo
contratto lifecycle di expiry o reconciliation, risoluzione persistita della
discovery, consumo candidati o nuove identità/tabelle accessorie.

## 8. Esempi focalizzati

* Snapshot valido più tupla sessioni vuota e nessuna prova di copertura:
  cardinalità candidati `ZERO`, esito `NOT_EVALUABLE`, nessuna scrittura.
* Una futura prova autorevole di copertura continua sarebbe una precondizione
  per un outcome di assenza, non un meccanismo implementato da questo boundary.
* Un `DirectIdEvidence` valido per la sessione `S`, con ID che risolve
  univocamente lo snapshot same-subject `P`, seleziona `P` anche in presenza di
  alternative strutturali o deviazioni di esecuzione.
* `ActualSession.raw_ids`, `original_activity_id` e provenance, anche se
  contengono una stringa uguale a un workout ID, non sono `DirectIdEvidence` e
  non attivano il percorso diretto.
