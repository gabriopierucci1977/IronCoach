# MAINTAIN_PLAN — Stability Provider Contract

**Stato: DRAFT — provider stability non implementato e non collegato al runtime**

## Scopo

Il provider stability deve produrre una valutazione canonica per lo stesso
soggetto e la stessa sessione usati dalla shadow chain. Il provider non deve
leggere direttamente payload Garmin, non deve persistere e non deve scegliere
in modo implicito una prescrizione o una sessione.

Il risultato ammesso è:

1. una `GeneralStabilityEvaluation` ottenuta dal servizio canonico;
2. un fallimento strutturato con motivo e provenance sufficienti.

Non sono ammessi valori sintetici, evaluation vuote o fallback a un altro
soggetto/sessione.

## Input tipizzato richiesto

Il provider deve ricevere o risolvere tramite fonti esplicite tutti gli input
di `GeneralStabilityInput`:

- `PrescriptionBaselineBinding`, con snapshot, decisione, soggetto,
  comunicazione, baseline opzionale, attestazione d'uso e provenance;
- `RecoveryAssessment` baseline quando il contratto la dichiara presente;
- `ActualSessionBoundary`, con sessione, soggetto, fine sessione e provenance;
- `RecoveryAssessmentCandidateSet`, con sessione, soggetto, cutoff e candidati
  recovery tipizzati;
- eventuale `NextDecisionBoundary`, soltanto se provvisto da una fonte
  esplicita;
- `evaluated_at` e policy stability canoniche;
- `ReportedProblemsProjectionSnapshot`, oppure assenza esplicita con motivo se
  il canale non è disponibile.

Il provider deve invocare `evaluate_general_stability` con un
`GeneralStabilityInput` completo e lasciare al servizio canonico la selezione,
compatibilità e classificazione dell'evidenza.

## Ownership e coerenza

Prima della valutazione devono essere verificati:

- stesso `subject_ref` in binding, baseline, boundary, candidate set,
  projection e valutazione;
- stesso `actual_session_ref` nel boundary, candidate set e projection;
- stesso snapshot/decisione nel binding;
- cutoff e timestamp coerenti con il contratto stability;
- provenance presente e compatibile per ogni evidenza usata.

La mancanza di una singola evidenza opzionale deve restare rappresentata dai
campi `missing_fields` o dallo stato canonico previsto dal servizio. La
mancanza di un input obbligatorio del provider deve invece produrre un
fallimento `SOURCE_UNAVAILABLE` o `INPUT_MISSING`, senza fabbricare un oggetto
parziale.

## Identità e idempotenza

L'`evaluation_id` viene assegnato dal chiamante in base al contratto di
versionamento e non viene rigenerato dal provider con timestamp casuali. A
parità di input canonici, policy, cutoff, provenance e identità, la valutazione
deve essere deterministica. Una correzione semantica richiede una nuova
identità/versione; non sono ammessi update o upsert.

## Confini operativi

Il provider stability deve essere:

- puro rispetto al bundle ricevuto;
- privo di scritture DB e rete diretta;
- indipendente dal matching discovery;
- indipendente dalla persistenza del mapping;
- compatibile con il flag shadow default-off;
- testabile con fixture sintetici e senza dati reali.

Un adapter runtime potrà chiamarlo soltanto dopo avere verificato snapshot,
sessione e mapping della stessa catena. La persistenza dell'evaluation, se
approvata, resterà un bridge separato e append-only.

## Criteri di accettazione

Prima dell'implementazione devono esistere:

1. provider concreti per baseline, candidate set e projection problemi;
2. regole esplicite per soggetto, sessione, cutoff e provenance;
3. test per input mancante, soggetto estraneo, sessione estranea, cutoff
   incoerente e provenance assente;
4. test di determinismo e retry senza duplicare l'identità;
5. test che dimostrino assenza di DB/rete nel provider;
6. decisione separata sulla persistenza delle `GeneralStabilityEvaluation`.

Fino alla chiusura di questi criteri il provider stability resta un contratto
preparatorio e la runtime adapter chain non viene attivata.
