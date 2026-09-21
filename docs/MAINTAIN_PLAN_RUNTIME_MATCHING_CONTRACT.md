# Contratto normativo — runtime matching `PrescriptionSnapshot` / `ActualSession`

**Stato:** contract-first; runtime e persistenza non implementati

**Policy:** `maintain-plan-matching/1.0.0-draft`

## 1. Perimetro e feature boundary

Questo documento definisce soltanto il nucleo del futuro matching tra
`PrescriptionSnapshot` e `ActualSession` persistiti. Integra il
[contratto outcome](MAINTAIN_PLAN_OUTCOME_CONTRACT.md), il
[contratto ActualSession](MAINTAIN_PLAN_RUNTIME_ACTUAL_SESSION_CONTRACT.md) e il
[contratto ownership](MAINTAIN_PLAN_SUBJECT_OWNERSHIP_CONTRACT.md).

Il flag futuro `IRONCOACH_MAINTAIN_PLAN_MATCHING_ENABLED` DEVE avere default
`false` e parsing fail-closed. Valore assente, falso o non valido vieta
enumerazione, decisione e scritture di matching. Questo PR è solo
documentazione: non abilita comportamento di produzione e non aggiunge schema,
migrazioni, repository o wiring. Il flag non può essere abilitato finché runtime
e persistenza non implementano integralmente questo contratto. `--dry-run`
proibisce ogni scrittura.

Evaluation, report, learning, ripianificazione, Decision Memory e Coach Engine
restano fuori perimetro. Non si può inferire da questo documento che i flussi
deferiti del §10 siano eseguibili.

## 2. Input autorevoli

Il matcher accetta esclusivamente record persistiti e decodificati strict:

* un `PrescriptionSnapshot` immutabile, con `snapshot_id`, `subject_ref`,
  `scheduled_window`, disciplina e composition;
* zero o più `ActualSession` immutabili, ciascuna con `session_id`,
  `subject_ref`, `start`, sport e segmenti normalizzati;
* una `SynchronizationCoverage` riuscita, immutabile e same-subject, con
  `coverage_start` inclusivo e `coverage_end` esclusivo.

Ogni timestamp DEVE essere timezone-aware e confrontato come istante UTC. Ogni
ID è una stringa non vuota. Tutte le letture verificano coerenza fra indice,
metadata e payload. Record mancanti, duplicati, corrotti, indecodificabili o
cross-subject sono errori tecnici: l'intero scope fallisce senza decisioni
parziali. Non si inventano `now`, lookback, grace period o watermark.

`subject_ref` dello snapshot, di ogni sessione e della coverage deve essere
identico byte-per-byte. Nessun dato di un altro soggetto può partecipare a una
cardinalità, una decisione o un mapping.

## 3. Ordinamento canonico

Gli ID si ordinano per byte UTF-8 ascendenti, senza collation locale. Le sessioni
si ordinano per `(start UTC, session_id UTF-8)`; gli snapshot per
`(scheduled_window.start UTC, snapshot_id UTF-8)`. Deduplicare significa
identità esatta dell'ID dopo aver dimostrato che i payload ripetuti sono
identici; contenuti divergenti per lo stesso ID falliscono chiuso.

L'ordinamento rende replay e lookup deterministici. Non costituisce ranking o
tie-break e non autorizza a scegliere il primo candidato.

## 4. Enumerazione dei candidati

### 4.1 Worklist session-driven

Dopo una sincronizzazione riuscita, ogni sessione coperta è considerata una
volta nell'ordine canonico. Per una sessione `S`, il set temporale same-subject
contiene tutte le finestre con:

```text
window.start <= S.start AND window.end >= S.start
```

Se tale set è vuoto, contiene invece l'intero gruppo predecessore con massimo
`window.end < S.start` e l'intero gruppo successore con minimo
`window.start > S.start`; tutti gli ex aequo sono inclusi. Una point window
`start == end` contiene `S` solo quando coincide con `S.start`.

Un direct ID presente sulla sessione viene validato prima della decisione. Deve
essere sintatticamente valido, risolversi univocamente a uno snapshot persistito
e same-subject. È evidence autorevole e viene unito al set senza eliminare gli
altri candidati. Direct ID dangling, ambiguo, corrotto o cross-subject è errore,
non assenza e non richiesta di conferma sostitutiva.

Per ogni snapshot della worklist, il matcher riceve la tupla completa delle
sessioni autorevolmente catturate ed eleggibili. È vietato decomporre la tupla
in chiamate singleton, fermarsi al primo elemento o omettere un elemento per
creare artificialmente cardinalità zero o uno.

### 4.2 Worklist window-driven

La worklist window-driven contiene le finestre same-subject che intersecano la
coverage riuscita:

```text
window.start < coverage_end AND window.end >= coverage_start
```

L'intersezione permette enumerazione e matching con sessioni realmente
catturate, ma da sola non prova l'assenza di sessioni. Una decisione
zero-sessioni è ammessa soltanto se una componente continua dell'unione
canonica delle coverage riuscite contiene l'intera finestra:

```text
union_start <= window.start AND window.end < union_end
```

Gli intervalli sovrapposti o adiacenti si fondono; un gap interrompe la
copertura. Per una point window a `t` occorre
`union_start <= t AND t < union_end`: `t == union_end` non è coperto. Una
coverage della sola testa, coda o parte centrale non autorizza a inferire
assenza fuori dalla porzione osservata.

Dopo copertura completa, uno snapshot non gestito e senza alcuna sessione
catturata attiva ed eleggibile può produrre la decisione pura zero-sessioni del
§7. Se una sessione è già rappresentata da una decisione non terminale, il
filtro della worklist non prova che la sessione non esista: il caso viene
osservato o differito, mai convertito in zero-sessioni.

### 4.3 Nessun ranking

I candidate set sono completi, immutabili per la singola decisione e ordinati
solo canonicamente. Sono vietati scoring, fuzzy matching, prossimità usata come
ranking, preferenza per import order e implicit tie-breaking.

## 5. Livelli distinti di “gestito”

Le guardie non sono intercambiabili:

* **relazione:** la coppia `(actual_session_ref, prescription_snapshot_ref)` è
  già rappresentata da una decisione autorevole per quella coppia;
* **sessione:** una sessione già mappata o autoritativamente decisa non può
  acquisire un altro snapshot;
* **snapshot:** uno snapshot già mappato o autoritativamente consumato non può
  essere assegnato a un'altra sessione.

La sola appartenenza a un candidate set ambiguo non consuma globalmente lo
snapshot e non equivale a un mapping. Analogamente, il fatto che una relazione
sia già rappresentata non dimostra l'assenza della sessione per il percorso
window-driven. Prima di decidere, l'implementazione futura deve interrogare le
tre guardie nel loro scope esatto e rileggere gli artefatti autorevoli.

Questo PR non definisce la persistenza di decisioni pendenti né come chiuderne
le relazioni: tali lifecycle appartengono al §10 e restano disabilitati.

## 6. Dispatch puro e compatibilità

Il matcher puro applica un dispatch esplicito sulla composition dello snapshot.
Input sconosciuto o malformato produce errore/`NOT_EVALUABLE`, mai fallback a
un altro ramo.

### 6.1 `SINGLE`

Una prescrizione `SINGLE` è compatibile con una sessione solo se:

1. la sessione ha una sola attività/segmento normalizzato utile;
2. sport/discipline canonicali coincidono esattamente;
3. `S.start` appartiene alla finestra inclusiva dello snapshot; oppure un direct
   ID valido costituisce evidence esplicita per quella stessa coppia.

Il direct ID seleziona la coppia indicata ma non rende compatibile una struttura
o ownership invalida e non elimina evidence concorrente dalla decisione.

### 6.2 `BRICK`

Una prescrizione `BRICK` richiede una singola sessione composita normalizzata
con almeno due segmenti utili. Numero, ordine e discipline dei segmenti devono
coincidere esattamente con la prescrizione. Segmenti mancanti, extra,
riordinati o sport non coincidenti sono incompatibili. Non si assemblano
sessioni indipendenti per simulare un brick.

### 6.3 `MULTISPORT`

Una prescrizione `MULTISPORT` richiede una singola sessione multisport
normalizzata. Numero, ordine e discipline delle fasi utili devono coincidere
esattamente. Le transizioni possono essere ignorate solo se il contratto di
normalizzazione le marca esplicitamente come transizioni; non possono essere
reinterpretate come fasi. Non si assemblano attività separate.

`BRICK` e `MULTISPORT` sono rami distinti: nessun fallback reciproco è
consentito. Dove il matcher corrente non può soddisfare questi predicati, il
matching resta disabilitato.

## 7. Decisioni deterministiche

Dopo aver valutato l'intera tupla canonica, il matcher produce una sola
decisione:

| cardinalità compatibile | decisione | mapping automatico |
|---:|---|---|
| 0 | `ZERO` | no |
| 1 | `ONE` | sì, salvo ambiguità direct-ID/evidence |
| >= 2 | `MULTIPLE` | no |

`ZERO` conserva le reason key deterministiche dei predicati falliti. Se la
tupla input è vuota, la decisione è una semplice osservazione zero-sessioni,
ammessa soltanto dal predicato di copertura completa del §4.2.

`ONE` identifica esattamente snapshot e sessione. Un direct ID valido verso
l'unico candidato compatibile è selezione autorevole. Se evidence diretta e
compatibilità strutturale indicano alternative diverse, non è permessa una
scelta implicita: la decisione richiede futura conferma.

`MULTIPLE` conserva l'intera tupla compatibile ordinata. Nessun elemento viene
selezionato per posizione. Le decisioni ambigue o non automatiche richiedono
futura conferma dell'atleta a livello di outcome, ma questo PR non definisce
schema di conferma, answer storage, fan-out o lifecycle e non afferma che la
persistenza corrente possa eseguirli.

## 8. Invarianti minime di persistenza futura

Questo contratto non propone DDL v8. Un'implementazione futura deve essere
compatibile con lo schema esistente e introdurre separatamente, previa
approvazione, soltanto la persistenza necessaria a garantire:

* al massimo un mapping per `ActualSession`;
* al massimo un mapping per `PrescriptionSnapshot`;
* lookup deterministico da entrambi i lati;
* ownership identica fra mapping, sessione e snapshot;
* riferimento a record persistiti e immutabili.

Ogni transazione di mapping usa `BEGIN IMMEDIATE`, rilegge snapshot, sessione,
ownership, decisione/evidence e i due lati di unicità prima della scrittura.
Inserisce mapping e artefatti strettamente necessari in ordine compatibile con
i vincoli, quindi committa atomicamente. Qualunque incongruenza, conflitto,
scrittura parziale o errore causa rollback completo.

Un retry con identici input canonici restituisce l'esito già committato. Stesso
ID con contenuto divergente, sessione già assegnata a un altro snapshot o
snapshot già assegnato a un'altra sessione fallisce chiuso. Due tentativi
concorrenti sullo stesso lato serializzano; dopo il lock il perdente rilegge e
produce retry idempotente oppure conflitto, senza overwrite.

Le identità future devono derivare da input canonici versionati, mai da ordine
di query, clock implicito o stato parziale. Le identità e la migrazione concreta
sono volutamente differite al §10; nessuna nuova relazione di persistenza è
specificata qui.

## 9. Matrice operativa minima

| precondizione | azione consentita |
|---|---|
| flag falso, assente o invalido | nessuna enumerazione o scrittura |
| sync fallita/parziale | nessuna decisione di assenza |
| input corrotto o cross-subject | errore e rollback |
| coverage interseca ma non contiene l'intera finestra | valutare solo sessioni osservate; non inferire zero-sessioni |
| coverage completa, snapshot non gestito, nessuna sessione attiva/eleggibile | decisione pura `ZERO`; lifecycle differito |
| un candidato compatibile senza conflitto | decisione `ONE`; mapping futuro atomico |
| più candidati compatibili | `MULTIPLE`; nessun tie-break o mapping |
| decisione ambigua/non automatica | conferma futura, oggi non persistibile da questo contratto |
| uno dei lati è già mappato diversamente | conflitto fail-closed |
| retry identico | restituzione deterministica dell'esito esistente |

## 10. Deferred follow-up contracts (non normativo)

I seguenti temi **non fanno parte di PR #46** e non devono essere inferiti dal
nucleo normativo precedente:

* persistenza delle conferme e lifecycle delle risposte;
* scadenza automatica delle osservazioni zero-sessioni;
* riconciliazione di sessioni tardive;
* fan-out terminale delle discovery;
* consumo dei candidati fra discovery pendenti sovrapposte;
* migrazione dello schema e identità canoniche di eventi/result.

Tutti questi comportamenti restano disabilitati. Ciascuno richiede un contratto
di follow-up separato e approvato, più schema, migrazione, repository, runtime e
test prima dell'abilitazione. In particolare questo PR non contiene una
transazione eseguibile per conferme, risposte, scadenze o riconciliazioni.

## 11. Criteri di abilitazione futura

Il flag può diventare vero soltanto dopo che test di implementazione dimostrano:

1. validazione strict e ownership byte-equal su ogni input;
2. candidate tuple complete e ordinamento canonico;
3. dispatch e predicati esatti per `SINGLE`, `BRICK` e `MULTISPORT`;
4. copertura completa prima di qualsiasi osservazione zero-sessioni;
5. nessun ranking o tie-break implicito;
6. unicità bidirezionale dei mapping, revalidation `BEGIN IMMEDIATE`, rollback,
   retry idempotente e conflitti fail-closed;
7. assenza di dipendenze dai lifecycle differiti del §10.

Fino ad allora il solo comportamento conforme è mantenere
`IRONCOACH_MAINTAIN_PLAN_MATCHING_ENABLED=false`.
