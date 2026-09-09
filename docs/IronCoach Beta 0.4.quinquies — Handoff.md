# IronCoach Beta 0.4.quinquies — Handoff

**Data handoff:** 9 settembre 2026
**Repository:** `gabriopierucci1977/IronCoach`
**Branch base:** `feature/beta-0.4-decision-memory`
**HEAD verificato / merge commit PR #26:** `cf911628b62f007a42e93ca3227a1edb84929a87` (`cf91162`)
**Commit:** `feat: add maintain plan execution and conflict evaluation (#26)`
**Predecessore sequenziale:** `docs/IronCoach Beta 0.4.quater — Handoff.md`

---

## 1. Identità e perimetro del checkpoint

Questo documento è il checkpoint sequenziale immediatamente successivo a
`.quater`. Non sostituisce il contratto normativo e non rende operative nel
runtime le componenti MAINTAIN_PLAN descritte qui.

La verifica locale è partita da un working tree pulito. Il nome del branch
locale era `work`, ma il contenuto di `HEAD` coincideva esattamente con il merge
atteso della PR #26, `cf91162`. La materializzazione della PR #26 è quindi stata
verificata per contenuto e commit, senza aggiornare alcun ramo remoto.

La cronologia effettiva `6a7580b..cf91162` contiene una sequenza normativa e
implementativa MAINTAIN_PLAN più ampia dei soli ultimi due commit. L'inventario
verificato con `git log` e con l'ispezione individuale dei commit è:

### Provenienza normativa

- `1b1e7ec` — crea il contratto outcome MAINTAIN_PLAN in stato draft;
- `76a727e` e `2065eb2` — registrano decisioni outcome approvate;
- `e937c0f` — formalizza il contratto della dose;
- `c76ec45` — riconcilia la tassonomia degli sport;
- `a74fb4e` — rappresenta le discipline delle sessioni composte;
- `ee74d6a` — disambigua i riferimenti dei risultati e gli ID canonici della
  dose (`#9` nel subject verificato).

Nel range sono presenti anche i merge commit `7f68156` (PR #5), `53a0070`
(PR #6) e `111eaa0` (PR #8), riconoscibili direttamente dai rispettivi subject.
Non vengono dedotti numeri di PR per commit che non li espongono.

### Provenienza implementativa

- `e15bb98` — introduce modelli, validator, fixture e test dei domain contract;
- `e7faeb2` — rafforza gli invarianti dei contratti (`#19` nel subject);
- `c4ffe73` — preserva target completi di prescrizione, incluse dimensioni e
  policy (`#20` nel subject);
- `62b582d` — introduce e irrobustisce schema, codec e repository SQLite
  append-only (`#21` nel subject);
- `40401e7` — aggiunge l'acquisizione esplicita e persistita del prescription
  snapshot (`#22` nel subject);
- `7ba1fa2` — aggiunge la normalizzazione canonica delle actual session
  (`#23` nel subject);
- `fef3458` — aggiunge lifecycle append-only di feedback e projection dei
  source conflict (`#24` nel subject);
- `835b3c3` — aggiunge matching deterministico, confirmation immutabile,
  ownership del mapping e preservazione della storia delle migrazioni; il
  subject non espone un numero di PR;
- `cf91162` — aggiunge execution evaluation e conflict-impact evaluation
  (`#26` nel subject), inclusi gli hardening per intervalli, recovery e
  aggregazione structure.

Il medesimo range contiene anche commit relativi alla Decision Memory legacy,
alla CI e alla documentazione operativa generale; non sono attribuiti al nuovo
sottosistema MAINTAIN_PLAN soltanto perché compaiono nel range Git.

---

## 2. Stato generale

### Implementato nel package isolato `backend/maintain_plan/`

- contratti immutabili per prescrizione comunicata, sessione osservata,
  mapping, matching, conferma ed execution evaluation;
- normalizzazione delle sessioni effettive senza valutazione implicita;
- matching deterministico con direct-ID prioritario e candidate set esplicito;
- conferme immutabili e versionabili;
- mapping gerarchico di componenti, blocchi, ripetizioni e transizioni;
- valutazione deterministica di identity, quantity, intensity, structure e dose;
- aggregazioni di dimensione, dose e risultato complessivo;
- valutazione dell'impatto dei source conflict e relativi riferimenti di
  proiezione;
- persistenza SQLite insert-only/append-only con migrazioni fino a v6.

### Validato ma ancora isolato

I servizi sopra sono validati da **332 test MAINTAIN_PLAN**, inclusi casi di
intervalli, composizione, sostituzioni, conflitti, recovery conservativo,
persistenza, migrazioni e tampering. Sono componenti utilizzabili tramite API
esplicite del package e database fornito dal chiamante, ma **non sono collegati
al runtime IronCoach**.

### `DRAFT — NON IMPLEMENTATO`

Il documento `docs/MAINTAIN_PLAN_OUTCOME_CONTRACT.md` resta normativo in stato
`DRAFT — NON IMPLEMENTATO`. L'implementazione isolata copre blocchi tecnici del
contratto, ma non equivale all'intero outcome MAINTAIN_PLAN operativo. Restano,
fra l'altro, report finale, learning MAINTAIN_PLAN e attivazione runtime.

### Non collegato al runtime

Non esiste wiring da `backend.main`, `CoachEngine`, `DecisionEngine`, Decision
Memory legacy o Garmin verso `backend.maintain_plan`. Non dichiarare quindi
MAINTAIN_PLAN completamente operativo, end-to-end o attivo in produzione.

---

## 3. Lavoro completato dopo `.quater`

### 3.1 Matching deterministico e direct-ID prioritario

Il matching opera soltanto su `PrescriptionSnapshot` e `ActualSession`
canonici forniti esplicitamente:

- non applica ranking, similarità, euristiche o tie-break/fallback;
- il direct-ID esplicito ha precedenza sul matching per candidate set;
- un direct-ID deve essere unico, coerente e riferire una sessione presente;
- un ID dangling, contraddittorio o ambiguo non viene indovinato;
- l'uguaglianza accidentale fra planned ID e observed ID non costituisce
  evidenza e non produce associazione;
- senza direct-ID valido, ogni candidata riceve controlli ed evidenze
  deterministici; zero o più candidate richiedono conferma, una sola candidata
  produce `MATCHED`.

Il candidate set è persistibile e riproducibile. La conferma conserva il set
originario: non lo ricalcola da dati mutabili e non accetta una selezione fuori
dal set, salvo il distinto percorso esplicito di associazione manuale.

### 3.2 Confirmation immutabile e ownership del mapping

Le conferme modellano gli stati `NOT_REQUIRED`, `REQUIRED`, `ANSWERED`,
`UNKNOWN_ANSWER` e `SUPERSEDED`, con combinazioni stato/risposta/selezione
validate nel dominio e, da v4, anche tramite trigger SQLite.

Una risposta non modifica una conferma già pubblicata: produce nuovi artefatti
versionati. Il `PrescriptionMapping` canonico possiede gerarchicamente i
riferimenti qualificati a:

- componente planned e observed;
- blocco planned e observed;
- ripetizione planned e observed;
- transizione planned e observed.

Ogni livello usa esplicitamente:

- `MATCHED`: entrambi i riferimenti presenti;
- `PLANNED_ONLY`: solo il riferimento pianificato;
- `OBSERVED_ONLY`: solo il riferimento osservato.

I riferimenti sono qualificati dal namespace del relativo snapshot/sessione;
la validazione impedisce riuso, dangling reference e contaminazioni
cross-namespace. Non si inferisce ownership dall'uguaglianza testuale degli ID.

### 3.3 Execution evaluation deterministica

La PR #26 aggiunge la valutazione dell'esecuzione sul mapping canonico. Ogni
`ComponentEvaluation` è validata rispetto all'esatta relazione
snapshot–session–mapping e non può introdurre riferimenti estranei o risultati
incoerenti con lo stato del mapping.

Le dimensioni valutate sono:

- **identity**: disciplina, ambiente e modalità, incluse esclusivamente le
  sostituzioni autorizzate dalla prescrizione e dalla policy dichiarata;
- **quantity**: confronto secondo policy differenziate; la tolleranza/banda
  prevista per quantità continue distance-based non viene riusata
  implicitamente per durata, set/ripetizioni o altre metriche;
- **intensity**: target, unità, metodo, range e finestra di valutazione devono
  essere semanticamente compatibili;
- **structure**: composizione, ordine, blocchi, ripetizioni, recovery e
  transizioni vengono valutati da evidenze esplicite;
- **dose**: deriva dalle dimensioni quantity e intensity referenziate, senza
  inventare una dose quando le evidenze necessarie non sono valutabili.

Sono coperte sessioni single, intervalli e sessioni composte; blocchi e
ripetizioni extra/mancanti restano visibili nel mapping; le transizioni sono
validate rispetto agli endpoint e alle policy di gap. La composition viene
valutata separatamente e partecipa all'esito di sessione.

Le aggregazioni di identity, quantity, intensity, structure e dose sono
deterministiche e conservano coverage ed evidenza. Il risultato complessivo non
nasconde componenti `PLANNED_ONLY` o `OBSERVED_ONLY`.

### 3.4 Regole structure e recovery conservative

Per structure, l'ordine di severità applicato distingue violazione dimostrata,
incertezza e parzialità:

1. `NOT_MET` quando esiste una violazione dimostrata;
2. `INSUFFICIENT_DATA` quando l'evidenza non consente la valutazione;
3. `PARTIALLY_MET` quando la struttura è valutabile ma solo parzialmente
   rispettata;
4. `MET` soltanto con evidenza sufficiente e conforme.

L'unico marker canonico che dichiara incompleta la collezione dei blocchi è:

`structure.blocks`

in `ObservedComponent.missing_fields`. Marker generici o nomi alternativi non
devono produrre la stessa semantica. Le evidenze structure provenienti da
composition, blocchi, ripetizioni, recovery e transizioni sono aggregate in
ordine deterministico.

Per il recovery prescritto con applicabilità `REQUIRED`, l'assenza di un
contratto osservativo tipizzato produce conservativamente
`INSUFFICIENT_DATA`. Le observations generiche non sono interpretabili come
recovery evidence. Il contratto tipizzato per recovery osservato è rinviato e
non va simulato con parsing libero.

### 3.5 Source-conflict impact, projection e persistenza

La valutazione execution può riferire proiezioni dei source conflict e
valutazioni d'impatto versionate. Le proiezioni sono validate con metadati,
cursor dell'evento, serializzazione canonica e SHA-256; il tampering del payload
o dell'hash viene rifiutato.

Un conflitto risolto può produrre un impatto deterministico sulle dimensioni
interessate; un conflitto irrisolto resta esplicito e non richiede un mapping
inventato. La v6 rende pertanto nullable il riferimento al mapping per gli
impact `UNRESOLVED`, preservando byte-for-byte le righe v5 esistenti.

Tutti gli artefatti sono persistiti insert-only. Nuove valutazioni, conferme,
eventi o proiezioni richiedono nuove identità/versioni; non esistono metodi
repository `update_*` o `upsert_*` per riscrivere la storia.

---

## 4. Decisioni normative importanti

Restano vincolanti le seguenti decisioni:

1. nessun ranking, similarità, euristica o fallback nel matching;
2. nessuna inferenza tramite uguaglianza fra ID planned e observed;
3. nessuna interpretazione diretta di dati Garmin non normalizzati;
4. snapshot, sessioni, mapping, conferme, eventi, proiezioni e valutazioni sono
   immutabili e versionati; una correzione aggiunge storia;
5. recovery `REQUIRED` senza evidenza tipizzata è conservativamente
   `INSUFFICIENT_DATA`;
6. observations generiche non sono recovery evidence;
7. il contratto recovery osservato tipizzato è rinviato;
8. per structure la precedenza è `NOT_MET`, `INSUFFICIENT_DATA`,
   `PARTIALLY_MET`, `MET`, rispettivamente per violazione dimostrata,
   incertezza, conformità parziale e conformità dimostrata;
9. `structure.blocks` in `ObservedComponent.missing_fields` è l'unico marker
   canonico di incompletezza della collezione dei blocchi.

---

## 5. Stato della persistenza

`SCHEMA_VERSION = 6`. Non esiste una migrazione v7.

### Scopo delle migrazioni pubblicate

- **v1:** tabelle fondamentali per prescription snapshot, actual session,
  prescription mapping, matching result ed execution evaluation, con indici e
  relazioni esatte;
- **v2:** feedback log/event/projection e source-conflict
  log/event/projection, inclusi indici e vincoli append-only;
- **v3:** tabella delle confirmation e relativi indici;
- **v4:** validazione atomica dello storico v3 e trigger insert/update che
  impongono combinazioni confirmation valide, preservando le righe esistenti;
- **v5:** source-conflict impact evaluation con mapping obbligatorio;
- **v6:** ricostruzione controllata della tabella impact per rendere nullable il
  mapping negli stati irrisolti, con preservazione byte-for-byte della storia.

Le migrazioni pubblicate v1–v6 sono immutabili. Il runner:

- registra versione, checksum e timestamp;
- verifica i checksum già applicati e rileva il tampering;
- usa `BEGIN IMMEDIATE`, commit per successo e rollback completo su errore;
- non modifica tabelle legacy come `decision_episodes`;
- applica ogni migrazione una sola volta.

Il repository MAINTAIN_PLAN è append-only: duplicate identity e incoerenze di
relazione sono rifiutate, la serializzazione viene riletta e validata contro i
metadati canonici, e non esiste backfill implicito.

### Checksum verificati direttamente da `MIGRATIONS`

- v1: `527e9211c82ee7f94791c9feef8c9dbb42220cd88182e1dcb3471319e6966a0c`
- v2: `843592bd9964051fa377912770a953aec3f8a5675133dd603f258883663b26fc`
- v3: `7607d1dd4e9d6a7bf7ebae0668986d9a938572560e52f46d506b22123303ba00`
- v4: `8b2dbd6ff037088309066e82829fa7f708a49cbfdc0447581f2c5b117025c3e1`
- v5: `7a9f07febe192eedc230b927bc582d4b069c6a21b3d5acb64482f1021da058a8`
- v6: `f037b70d3fc8b7638ab0bf4b25dfbc28f05aabfd91a5840f6bd154da867441b8`

---

## 6. Baseline test verificata

Baseline locale al 9 settembre 2026:

- raccolta MAINTAIN_PLAN: **332 test**;
- suite MAINTAIN_PLAN: **332 passed**;
- suite complessiva: **840 passed, 5 skipped**;
- i 5 skipped restano i casi già attesi dalla suite complessiva;
- `compileall` su `backend` e `tests`: completato senza errori;
- `git diff --check`: completato senza errori.

I numeri coincidono con la baseline attesa.

---

## 7. Isolamento confermato

Per il sottosistema MAINTAIN_PLAN introdotto dopo `.quater`:

- nessun runtime wiring;
- nessuna modifica a `DecisionEngine`;
- nessuna modifica alla Decision Memory legacy;
- nessuna modifica alla tabella `decision_episodes`;
- nessun accesso diretto a Garmin;
- nessuna sincronizzazione Garmin;
- nessun report finale MAINTAIN_PLAN;
- nessun learning MAINTAIN_PLAN;
- nessuna rete o servizio esterno.

L'assenza generale di wiring è stata **osservata nel tree corrente** mediante
ricerca repository-wide; non è una garanzia generica attribuibile ai test. I
test automatici hanno uno scope più preciso e cercano, nei file Python sotto
`backend` esterni al package `maintain_plan`, soltanto le rispettive stringhe di
import completamente qualificate:

- `test_actual_session_normalizer.py` controlla
  `backend.maintain_plan.actual_session_normalizer`;
- `test_prescription_snapshot_service.py` controlla
  `backend.maintain_plan.prescription_snapshot_service`;
- `test_persistence.py` controlla `backend.maintain_plan.repository`.

Questi controlli non dimostrano l'assenza di ogni possibile stile di import o
di ogni futura forma di wiring. Database e input dei test sono sintetici e
confinati nelle directory temporanee pytest.

Questo isolamento non contraddice `.quater`: il runtime legacy e le sue
integrazioni descritte lì esistono, ma il nuovo sottosistema MAINTAIN_PLAN non è
stato innestato in esse.

---

## 8. Lavoro rimanente

### Prossimo lavoro immediato

- rileggere il contratto e identificare il prossimo blocco normativo realmente
  approvato; il repository non dimostra un ordine definitivo oltre la PR #26;
- eseguire una revisione READ-ONLY dedicata del blocco scelto prima di scrivere
  codice o prima di proporre il merge;
- arrestarsi se il contratto non determina un comportamento univoco, invece di
  introdurre una policy implicita.

### Lavoro rinviato

- report finale MAINTAIN_PLAN;
- learning basato sugli outcome MAINTAIN_PLAN;
- attivazione e orchestrazione runtime;
- contratto tipizzato futuro per recovery osservato;
- integrazione controllata con Decision Memory, DecisionEngine, CoachEngine e
  le altre componenti legacy;
- ulteriori decisioni normative richieste da casi non coperti in modo univoco.

### Fuori perimetro di questo checkpoint

- modifiche a Garmin, Airtable, sincronizzazioni, rete o servizi esterni;
- modifiche alla Decision Memory legacy o a `decision_episodes`;
- migrazioni o backfill dei database runtime reali;
- interpretazione di payload sorgente non normalizzati;
- ranking probabilistico, fuzzy matching o learning automatico.

### Condizioni prima dell'attivazione runtime

Sono necessari almeno: contratto normativo non ambiguo per il tratto da
attivare, adapter espliciti verso input canonici, configurazione controllata
della persistenza, idempotenza/orchestrazione definite, compatibilità con i
guardrail legacy, test di integrazione e regressione completa, piano di rollout
e revisione READ-ONLY. Nessun dato reale deve essere mutato durante la sola
revisione.

---

## 9. Istruzioni per il prossimo agente

1. partire da `feature/beta-0.4-decision-memory` e verificare che il contenuto
   includa `cf91162` / PR #26;
2. eseguire `git status --short`, `git log -20 --oneline`,
   `git rev-parse HEAD` e controllare che il working tree sia pulito;
3. leggere integralmente:
   - `docs/BETA_0_4_HANDOFF.md`;
   - gli handoff `.bis`, `.ter`, `.quater` e `.quinquies`;
   - `docs/MAINTAIN_PLAN_OUTCOME_CONTRACT.md`;
   - `docs/IRONCOACH_BETA_0_4_START_HERE.md`;
   - tutti i file in `backend/maintain_plan/`;
   - tutti i test in `tests/maintain_plan/`;
4. riprodurre la baseline: 332 test MAINTAIN_PLAN; full suite 840 passed,
   5 skipped; compileall e diff-check puliti;
5. in presenza di ambiguità normativa, **fermarsi** e richiedere una decisione:
   non colmare il vuoto con euristiche o proxy;
6. non modificare mai migrazioni v1–v6 o i loro checksum;
7. un'eventuale v7 deve essere soltanto additiva, transazionale, preservare lo
   storico e avere test di upgrade dalle versioni pubblicate;
8. svolgere una revisione READ-ONLY esplicita prima del merge e verificare che
   non tocchi database, rete o servizi reali.

---

## 10. Comandi di verifica riproducibili

### Git e materializzazione della PR #26

```bash
git status --short
git log -20 --oneline
git rev-parse HEAD
git show --stat --oneline cf91162
```

### Test e compilazione

```bash
python -m pytest --collect-only -q tests/maintain_plan
python -m pytest -q tests/maintain_plan
python -m pytest -q
python -m compileall -q backend tests
git diff --check
```

### Schema e checksum

```bash
python - <<'PY'
from backend.maintain_plan.schema import MIGRATIONS, SCHEMA_VERSION
print("SCHEMA_VERSION", SCHEMA_VERSION)
for migration in MIGRATIONS:
    print(migration.version, migration.checksum)
PY
```

### Assenza di runtime wiring

```bash
rg -n 'backend\.maintain_plan|from backend import maintain_plan|import backend\.maintain_plan' \
  backend --glob '*.py' --glob '!maintain_plan/**'
```

Un output vuoto è l'esito atteso. Se `rg` non è disponibile:

```bash
find backend -path 'backend/maintain_plan' -prune -o -name '*.py' -type f -exec \
  grep -nHE 'backend\.maintain_plan|from backend import maintain_plan|import backend\.maintain_plan' {} +
```

### Append-only e assenza di v7

```bash
rg -n 'def (update_|upsert_)|UPDATE maintain_plan_|SCHEMA_VERSION|Migration\(' \
  backend/maintain_plan
```

Interpretare l'eventuale `UPDATE` dei trigger di validazione v4 come protezione
del vincolo SQLite, non come API di riscrittura: il repository pubblico resta
insert-only. Verificare inoltre che `SCHEMA_VERSION` sia 6 e che `MIGRATIONS`
termini alla versione 6.

---

## 11. Regola di ripartenza

Il checkpoint è sicuro per proseguire soltanto dal contenuto equivalente a
`cf91162`, con suite verde e working tree pulito. Il passo successivo non è
automaticamente report, learning o runtime: deve essere scelto dal contratto e
validato in READ-ONLY. Fino a quel momento MAINTAIN_PLAN resta un sottosistema
deterministico, persistito e ampiamente testato, ma **isolato e non operativo nel
runtime**.
