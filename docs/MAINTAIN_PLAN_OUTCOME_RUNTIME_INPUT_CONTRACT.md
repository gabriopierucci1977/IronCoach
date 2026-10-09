# DRAFT — Input per la futura orchestrazione dell'outcome MAINTAIN_PLAN

**Stato:** bozza documentale; orchestrazione runtime non implementata.
**Versione del documento:** `maintain-plan-outcome-runtime-inputs/0.1.0-draft`.
**Riferimento del codice esaminato:** `2b0d7ac` — 9 ottobre 2026.

Questo documento descrive le API esistenti e gli input da acquisire prima del
futuro wiring. Non sostituisce il [contratto outcome](MAINTAIN_PLAN_OUTCOME_CONTRACT.md),
il [contratto ownership](MAINTAIN_PLAN_SUBJECT_OWNERSHIP_CONTRACT.md) o il
[contratto matching](MAINTAIN_PLAN_RUNTIME_MATCHING_CONTRACT.md).
La sua aggiunta non approva l'attivazione di outcome, report o learning.

## 1. Stato verificato

ExecutionEvaluationService, GeneralStabilityService e FinalOutcomeService sono
servizi del package; l'audit non ha trovato richiami a outcome o stabilità
fuori da `backend/maintain_plan`. Il matching shadow nella pipeline usa solo
gli artefatti ricevuti nella stessa esecuzione ed è default-off.

Un risultato shadow `MATCHED` descrive quei soli input: non dimostra la
completezza dello scope storico e non produce un PrescriptionMapping.
Il risultato shadow non è un ExecutionEvaluation o una GeneralStabilityEvaluation.

L'audit precedente ha superato 241 test mirati di outcome, stabilità ed
execution, oltre a compilazione e diff check. Questo documento non dichiara
nuovi test, producer canonici o acquisizioni runtime implementate.

## 2. Input diretti del servizio finale

La firma esistente di `evaluate_final_outcome` riceve:

| Input | Tipo | Requisito esistente |
|---|---|---|
| execution | ExecutionEvaluation | Risultato canonico di esecuzione; componenti, aggregati, coverage, dose e policy coerenti |
| stability | GeneralStabilityEvaluation | Risultato canonico di stabilità; binding, selezione, reported problems e policy coerenti |
| evaluation_id | str | Stringa esplicita non vuota |
| evaluated_at | datetime | Timezone-aware; non precedente a stability.evaluated_at |
| provenance_ref | ProvenanceRef | Riferimento strutturale tipizzato al producer e alla provenance |

Il risultato è un MaintainPlanFinalEvaluation draft. Il servizio non acquisisce
artefatti, non apre repository, non produce mapping e non persiste il risultato.
I validator finali controllano anche gli ID di snapshot e sessione condivisi
dalle due evaluation; non risolvono i payload referenziati.

## 3. Artefatti necessari per l'esecuzione

| Input di ExecutionEvaluationService.evaluate | Requisito |
|---|---|
| PrescriptionSnapshot | Prescrizione autorevole effettivamente comunicata; immutabile e appartenente al soggetto |
| ActualSession | Sessione canonica immutabile dello stesso soggetto |
| PrescriptionMapping | Associazione risolta e copertura dei componenti validate sugli esatti snapshot e sessione |
| evaluation_id, evaluated_at | Metadati espliciti per la evaluation |
| conflict_projections, conflict_impacts | Proiezioni e impatti canonici corrispondenti a ogni conflitto sorgente presente |
| provenance | Contesto di audit; non sostituisce target, osservazioni o evidence |

Le tuple dei conflitti possono essere vuote quando la sessione non contiene
conflitti. In presenza di conflitti il servizio richiede copertura esatta,
senza elementi duplicati, riferimenti estranei o impatti ricostruiti arbitrariamente.

L'ownership deve essere validata su snapshot, sessione e mapping prima
dell'execution evaluation. ExecutionEvaluation non contiene subject_ref:
il controllo finale degli ID non sostituisce questa verifica sugli artefatti.
Uno scope di matching incompleto o ambiguo non autorizza a creare un mapping.

## 4. Input della stabilità

GeneralStabilityService.evaluate richiede un GeneralStabilityInput e un
evaluation_id esplicito. GeneralStabilityInput conserva i seguenti campi:

| Campo | Tipo | Autorità richiesta |
|---|---|---|
| contract_version, policy_id, policy_version | str | Versioni esatte previste dal contratto stability |
| prescription_binding | PrescriptionBaselineBinding | Snapshot, decisione, soggetto, comunicazione e attestazione dell'uso della baseline |
| baseline_assessment | RecoveryAssessment oppure None | Assessment realmente usato per formulare la prescrizione; non ricercato a posteriori |
| actual_session_boundary | ActualSessionBoundary | Ref della sessione, soggetto, session_end e provenance disponibili |
| candidate_set | RecoveryAssessmentCandidateSet | Set esplicito frozen degli assessment candidati; una tupla vuota resta rappresentabile |
| next_decision_boundary | NextDecisionBoundary oppure None | Decisione successiva effettiva dello stesso soggetto, quando presente |
| evaluated_at | datetime | Istante timezone-aware della valutazione |
| reported_problems_projection | ReportedProblemsProjectionSnapshot oppure None | Proiezione canonica di feedback e safety, con verifica del canale fino al cutoff |
| provenance_ref | ProvenanceRef | Producer e provenance strutturali versionati |

Il binding contiene un baseline_use_attestation_ref esplicito. Una baseline
assente e il suo ref assente sono missingness ammesse; un ref presente senza
assessment, o discordante dall'assessment fornito, rende invalido l'input.
L'attestazione non può essere sintetizzata dal recovery corrente.

Il candidate set non viene scoperto dal consumer. La selezione considera il
più antico observed_at tra i candidati ammissibili; non usa ranking o tie-break.
Assessment C1 incompatibili non diventano consumabili. Identità qualificate
duplicate con contenuti discordanti invalidano l'intero input.

## 5. Binding, tempi e feedback

Snapshot e sessione delle evaluation devono coincidere. Binding, session
boundary, candidate set, eventuale next decision e projection devono avere
ownership e riferimenti coerenti. Una discordanza strutturale produce errore,
senza evaluation parziale; non viene convertita in missingness.

La baseline ha observed_at e assessed_at non successivi alla comunicazione.
Per i candidati: observed_at <= assessed_at <= candidate_set.captured_at <=
evaluated_at; candidate_set.evaluated_cutoff_at è uguale a evaluated_at.
I candidati selezionabili hanno entrambi i timestamp strettamente successivi
a session_end e, se presente, strettamente precedenti alla decisione successiva.
Non esistono TTL o conversioni da score legacy impliciti.

Il cutoff del feedback è evaluated_at, inclusivo, salvo una next decision
con decision_at <= evaluated_at: in quel caso il cutoff è decision_at,
esclusivo. La finestra inizia dopo session_end, esclusivo.
Una projection consumabile è ACTIVE, completa, VERIFIED, riferita alla
sessione e al soggetto esatti, con finestra corretta e checked_through_at >= cutoff.
L'assenza di record non autorizza NO_KNOWN_ISSUE. Testo libero e payload
Garmin/Airtable non diventano automaticamente evidence di safety.

## 6. Missingness, coverage e risultato draft

Baseline, session_end o projection legittimamente mancanti conservano i path
canonici di missingness. La stabilità aggrega prima un deterioramento affidabile,
poi l'insufficienza delle dimensioni obbligatorie, altrimenti STABLE.
Il risultato finale applica la matrice esistente:

| Condizione | Outcome draft |
|---|---|
| Coverage diversa da FULLY_SUPPORTED, inclusa NO_REQUIRED_COMPONENTS | None; nessun outcome definitivo della sessione |
| Coverage FULLY_SUPPORTED e execution o stability INSUFFICIENT_DATA | INSUFFICIENT_DATA |
| Coverage FULLY_SUPPORTED, execution valutabile e stability DETERIORATED | NEGATIVE |
| Coverage FULLY_SUPPORTED, stability STABLE e execution IN_LINE | POSITIVE |
| Coverage FULLY_SUPPORTED, stability STABLE e execution PARTIALLY_IN_LINE | NEUTRAL |
| Coverage FULLY_SUPPORTED, stability STABLE e execution DIFFERENT | NEGATIVE |

Non si sostituiscono valori mancanti con zeri, proxy o equivalenze. Nessun
risultato draft o shadow diventa outcome ufficiale, report o contributo al learning.

## 7. Dati da acquisire prima del wiring

1. Scope autorevole completo e mapping risolto, con verifica di ownership.
2. Baseline canonica e attestazione del suo uso registrate alla decisione;
   un dato storico non viene ricostruito per prossimità o somiglianza.
3. Producer canonico degli assessment recovery e acquisizione frozen dei
   candidati, con identità, versioni, tempi e provenance espliciti.
4. Producer della projection reported problems e attestazione del controllo
   del canale per la finestra e il cutoff applicabili.
5. Confini di sessione e decisione successiva, ID delle evaluation e policy
   di provenance e lifecycle definite per la futura orchestrazione.

Questi producer e meccanismi di acquisizione non sono forniti dal matching
shadow. La forma P0 è strutturale: non risolve repository, non verifica hash
e non dimostra crittograficamente l'autenticità delle attestazioni.

Questa slice aggiunge soltanto documentazione. Non introduce nuovi flag,
migrazioni, adapter, modifiche ai modelli, attivazioni runtime o learning.
Una futura slice potrà assemblare e validare input canonici espliciti;
l'acquisizione di dati reali e il rollout ufficiale richiedono un perimetro separato.
