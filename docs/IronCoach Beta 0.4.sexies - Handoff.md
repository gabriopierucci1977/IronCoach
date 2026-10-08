# IronCoach Beta 0.4 — Handoff per nuova chat

**Aggiornato:** 6 ottobre 2026. **Repository:** `gabriopierucci1977/IronCoach`. **Branch usato nell'attuale Codespace:** `feature/beta-0.4-decision-memory`.

> **Priorità attuale:** risolvere il `403` «Azione respinta: origine o autorizzazione non valida» nei moduli della pagina *IronCoach · Le tue sedute*. È il problema che impedisce di incollare e salvare il commento di ChatGPT o Claude su un'attività. L'Handoff del 9 settembre, riportato integralmente in appendice, è una fotografia storica del progetto e **non** certifica lo stato corrente del repository o dei test.

## Come lavorare con l'utente

- L'utente lavora da Chrome su un dispositivo Android, nell'editor web GitHub Codespaces. Ha già dedicato ore a tentativi e riavvii senza risolvere il problema. Fornire istruzioni in italiano, brevi, chiare e passo per passo.
- Per le modifiche al repository vuole **un comando completo da copiare e incollare nel terminale**, non modifiche manuali parziali dei file. Evitare di sottoporgli patch speculative o lunghi cicli di test senza diagnosi.
- Non confondere il prompt del terminale (`... $`) con il prompt di analisi dell'AI. Nel precedente scambio «devo cambiare prompt?» è stato interpretato erroneamente come richiesta di modificare `build_export_prompt`; l'ultimo comando proposto dall'assistente riguardava `session_flow.py` e **non risolveva il 403**. Non sappiamo se l'utente lo abbia eseguito: verificarlo prima di procedere.
- Il filesystem della chat e il Codespace dell'utente sono ambienti diversi. L'assistente può leggere file allegati e copie locali, ma non deve presentare quelle copie come lo stato attuale del Codespace. Non presumere che un comando visibile nella chat sia già stato eseguito nel terminale.

## Scopo funzionale e stato osservato

L'interfaccia locale permette di cercare l'atleta, scegliere una seduta, esportare dati o prompt verso ChatGPT, incollare manualmente il responso anche di Claude e salvarlo come commento associato alla seduta. Il codice mostrato nelle copie locali contiene `backend/maintain_plan/coach_web.py`, `session_flow.py`, `manual_analysis.py` e test specifici. `manual_analysis.py` prevede un database SQLite separato per i commenti e controlla che la seduta appartenga all'atleta. **Non abbiamo prova che un commento sia stato salvato con successo nell'attuale Codespace.**

Nell'interfaccia reale, l'utente ha visualizzato `50 attività disponibile/i.` dopo «Esamina». Ha poi scelto attività già provate e una nuova attività, incollato il commento e premuto il pulsante di salvataggio. Il risultato è rimasto «Azione respinta: origine o autorizzazione non valida». L'errore è apparso anche nella navigazione in incognito e dopo aver fermato e riavviato il Codespace. La pagina GET può quindi funzionare mentre il POST di salvataggio viene respinto. In una diagnosi precedente compariva `origine=NO, cookie=OK, modulo=OK`: è un **indizio** che la verifica di origine falliva in quella prova, non un resoconto completo degli header del POST più recente.

Per il Codespace `probable-space-broccoli-xr99rvppx7xp34wr`, l'indirizzo inoltrato mostrato nella sessione era `https://probable-space-broccoli-xr99rvppx7xp34wr-8765.app.github.dev/`. È un indirizzo temporaneo: se il Codespace o il port forwarding cambiano, recuperarlo dalla scheda **Porte**, riga `8765`. Il `502` nel browser e `Codice HTTP locale: 000` osservati in alcuni tentativi indicavano che il server non rispondeva in quel momento; sono distinti dal `403` a pagina caricata. I terminali si sono chiusi o terminati più volte, a volte dopo comandi con `fuser -k 8765/tcp` e riavvio; non attribuire automaticamente questi guasti a un'unica causa.

## Evoluzione dei tentativi e test: dati verificabili, non baseline attuale

- Sono stati tentati cambiamenti multipli a `_valid_origin` e alla gestione di `Origin`, `Host`, `X-Forwarded-Host`, `X-Forwarded-Proto`, cookie e token, oltre a test, restart del server, stop/start del Codespace e modalità incognito. Il 403 reale è rimasto.
- Uno screenshot mostra commit/push `af17b4a` (*Fix Codespaces origin validation securely*); un altro `d9c11c1` come versione di diagnosi. **Non sappiamo il commit HEAD odierno, né se i successivi script siano stati committati.** Non chiedere di ripristinare automaticamente a uno di questi commit: potrebbero esserci modifiche importanti successive.
- Una suite intermedia ha restituito `3 failed, 1547 passed, 5 skipped` (test di GET/POST cross origin e proxy Codespaces); una successiva `1 failed, 1549 passed, 5 skipped`, con `test_browser_get_is_read_only_and_cross_origin_post_is_rejected` ancora in errore. Un test che passa con header simulati **non dimostra** il comportamento del proxy reale. Da questi numeri non si può dedurre che la suite attuale sia verde.
- In una copia locale di `coach_web.py`, `do_POST` chiama `_valid_action`, che richiede insieme `_valid_origin`, cookie `ironcoach_action` uguale al token server e campo nascosto `action_token` uguale allo stesso token. Il codice costruisce l'`expected_origin` dalle variabili del processo Codespaces e usa l'header `Host` per scegliere l'origine fidata. Questa è un'osservazione su una **copia locale precedente**, da confrontare con il file corrente.
- Il vecchio file diagnostico `codex_origin_diagnostic.txt` contiene anche una credenziale d'ambiente stampata accidentalmente. **Non riprodurne né condividerne il contenuto; non eseguire dump delle variabili d'ambiente.** Se ancora valida, valutare la revoca o rotazione con le normali impostazioni dell'account.
- L'ultimo comando suggerito dall'assistente sostituiva la funzione `build_export_prompt` in `session_flow.py`. Era fuori tema rispetto alla richiesta di sistemare il blocco del salvataggio e non se ne conosce l'esecuzione o l'esito. Controllare la diff; correggere eventuali danni solo dopo averli verificati.

## Cosa rimane da fare, in ordine

1. **Accertare lo stato attuale, senza mutarlo.** Nel Codespace reale eseguire `git status --short --branch`, `git log -5 --oneline`; ispezionare diff e funzioni attuali in `coach_web.py` e, se modificato, `session_flow.py`. Separare file del repository da log, backup, test output e dati non tracciati. Non perdere lavoro non committato.
2. **Riprodurre una sola richiesta fallita con il server stabilmente attivo.** Verificare che la porta `8765` risponda prima di testare il browser. Rilevare in modo sicuro gli effettivi `Origin`, `Host`, `Referer`, `X-Forwarded-Host`, `X-Forwarded-Proto` del POST e soltanto la presenza/validità booleana del cookie e del campo token. Non stampare cookie, token, contenuto dei commenti o intero ambiente. Se si aggiunge diagnostica al server, rimuoverla dopo la verifica.
3. **Correggere la causa dimostrata dai valori osservati.** Vincolare l'accettazione all'origine pubblica derivata dalla configurazione fidata del processo; non affidarsi a un `Referer` se esiste un `Origin` discordante, non allargare a qualsiasi `localhost` o dominio `*.app.github.dev`, non disabilitare CSRF, né rendere GET capace di salvare. Se l'header atteso non è quello ricevuto, indagare inoltro e autorità esatta prima di cambiare policy.
4. **Verificare il percorso completo.** Test che riproducano gli header reali e respingano origini estranee; poi nel browser reale: «Esamina» → seleziona attività → incolla breve commento → salva → ricarica → controlla che il commento resti associato alla stessa attività. Verificare che una nuova selezione non mostri impropriamente il commento di un'altra seduta. Comunicare risultati reali e test falliti, senza dichiarare successo sulla sola base dei test sintetici.
5. **Solo dopo la verifica**, fornire all'utente il singolo comando completo, idempotente quando possibile, che modifica i file necessari, controlla sintassi e test e non esegue commit/push se questi falliscono. Il commit e il push non sono una prova di funzionamento nell'interfaccia Codespaces.

Una prima raccolta **sola lettura** da chiedere o eseguire nel vero terminale, se non si può accedere direttamente al Codespace, è:

```bash
cd /workspaces/IronCoach
git status --short --branch
git log -5 --oneline
git diff -- backend/maintain_plan/coach_web.py backend/maintain_plan/session_flow.py
```

Non richiedere screenshot dell'intero dump d'ambiente o del vecchio `codex_origin_diagnostic.txt`, che può contenere credenziali. Nella nuova chat, chiedere il **file corrente** `backend/maintain_plan/coach_web.py` oppure l'output diagnostico filtrato se non c'è accesso al repository; evitare altri tentativi basati su copie datate.

## Stato storico del sottosistema MAINTAIN_PLAN

L'Handoff originale del 9 settembre riferiva che il package MAINTAIN_PLAN era isolato dal runtime, con contratti, normalizzazione, matching, conferme, valutazioni, repository append-only e schema SQLite v6. Il contratto outcome era ancora `DRAFT — NON IMPLEMENTATO`. Questi vincoli di progetto restano un riferimento, ma le sue statistiche (`332 passed` in MAINTAIN_PLAN e `840 passed, 5 skipped` totali) e il commit `cf91162` sono la **baseline del 9 settembre**, non valori da assumere per ottobre. Le successive funzionalità della UI manuale e i test nuovi spiegano la crescita dei numeri; non affermare che il sistema originale sia stato attivato integralmente nel runtime senza verifica del codice corrente.

---

## Appendice: Handoff originale integrale (9 settembre 2026)

Il testo seguente è conservato come bozza storica. Tutti i riferimenti a «corrente», HEAD e baseline che contiene valgono **alla sua data**.

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

## Chiusura fix origine Codespaces — 7 ottobre 2026

- Causa: il proxy Codespaces riscrive il `POST` con `Origin` HTTP locale, mentre il browser pubblico usa HTTPS.
- Correzione: viene accettato esclusivamente `http://{Host}` quando `Host` è loopback e `X-Forwarded-Host`/`X-Forwarded-Proto` confermano il proxy pubblico HTTPS.
- Il salvataggio reale del commento è stato verificato dalla pagina web e il commento resta associato alla seduta dopo il ricaricamento.
- Verifica: 1550 test passati, 5 saltati; compilazione e `git diff --check` superati.
- Commit applicativo già pubblicato: `db70480`.


## Stato runtime verificato — 8 ottobre 2026

- `SCHEMA_VERSION` corrente: `10`, con migrazioni 1–10 presenti e verificate.
- La cattura `ActualSession` è richiamata da `backend/main.py` dopo la costruzione del contesto e prima della Decision Memory.
- La cattura resta opt-in: il servizio non opera se `IRONCOACH_MAINTAIN_PLAN_ACTUAL_SESSION_ENABLED` è assente o falso.
- Matching runtime, stabilità e outcome finale sono implementati come servizi del package, ma non sono collegati alla pipeline principale.
- Test mirati runtime, stabilità e outcome: `515 passed`; test wiring/outcome: `43 passed`.
- Non è stata eseguita alcuna attivazione runtime né alcuna modifica a dati reali.
- Prima di collegare matching o outcome alla pipeline serve un contratto di wiring e rollout esplicitamente approvato.
