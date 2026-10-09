# MAINTAIN_PLAN — Runtime Adapter Contract

**Stato: DRAFT — scelta B, definizione del contratto; adapter e wiring non implementati**

## Scopo

Questo documento definisce il confine che dovrà trasformare sorgenti runtime
esplicite in artefatti canonici MAINTAIN_PLAN. Non abilita il runtime e non
introduce una policy di selezione implicita.

L'adapter dovrà fornire alla shadow chain un bundle completo e coerente:

- `subject_ref`;
- `PrescriptionSnapshot`;
- `ActualSession`;
- `PrescriptionMapping`;
- `ExecutionEvaluation`;
- `GeneralStabilityEvaluation`.

Un bundle parziale non è valutabile dalla chain. L'adapter deve restituire un
esito fail-closed con motivo stabile, senza costruire valori sostitutivi.

## Origine degli input

Ogni artefatto deve provenire da un provider esplicito e identificabile. Il
provider può restituire soltanto:

1. un artefatto già canonico e validabile;
2. assenza esplicita con motivo e provenance disponibili.

Payload Garmin, dati grezzi, valori UI o uguaglianze accidentali fra ID planned
e observed non sono input dell'adapter. La normalizzazione resta un confine
precedente e separato.

L'adapter non scopre candidati, non sceglie snapshot o sessioni, non crea
mapping, non calcola evaluation e non interpreta direttamente dati sorgente.
Riceve gli artefatti già scelti da un livello upstream esplicito.

## Ownership e riferimenti

Il bundle è valido soltanto quando:

- `subject_ref` è una stringa non vuota;
- snapshot e sessione hanno lo stesso `subject_ref`, confrontato per uguaglianza
  esatta;
- il mapping riferisce esattamente snapshot e sessione selezionati;
- ogni lato del mapping appartiene agli artefatti riferiti;
- `ExecutionEvaluation` riferisce lo stesso mapping, snapshot e sessione;
- `GeneralStabilityEvaluation` è internamente valida e appartiene allo stesso
  soggetto del bundle;
- provenance, contract version ed evaluation timestamps sono presenti e
  compatibili con i rispettivi contratti.

Il mapping non può essere creato dall'adapter. La prima implementazione del
confine shadow consumerà soltanto mapping già canonici con
`resolution_method=AUTOMATIC`; il percorso `ATHLETE_CONFIRMATION` richiederà un
contratto esplicito separato per l'evento di conferma.

## API concettuale

L'adapter futuro dovrà comportarsi come una funzione pura equivalente a:

```text
adapt_runtime_inputs(
    subject_ref,
    prescription_snapshot,
    actual_session,
    prescription_mapping,
    execution_evaluation,
    stability_evaluation,
) -> RuntimeAdapterResult
```

`RuntimeAdapterResult` deve contenere esclusivamente il bundle canonico o un
fallimento strutturato. Non deve contenere connessioni, repository, sessioni
DB, richieste di rete o callback che eseguono scritture.

## Fallimenti obbligatori

I motivi devono essere deterministici e distinguere almeno:

- `INPUT_MISSING`;
- `INPUT_TYPE_INVALID`;
- `SUBJECT_MISMATCH`;
- `MAPPING_MISMATCH`;
- `EVALUATION_MISMATCH`;
- `PROVENANCE_MISSING`;
- `CONTRACT_VERSION_MISMATCH`;
- `SOURCE_UNAVAILABLE`.

Nessun fallimento può produrre un mapping inferito, un evaluation vuoto o un
outcome parziale. Il chiamante deve poter distinguere input assente, input
malformato e conflitto di ownership.

## Identità, versionamento e idempotenza

Gli artefatti mantengono le identità canoniche esistenti. Una correzione
semantica richiede una nuova identità o versione secondo il contratto
specifico; non si aggiornano righe storiche e non si riutilizza un ID per un
payload diverso.

A parità di identità, versioni, riferimenti, provenance e contenuto canonico,
l'adapter deve produrre lo stesso risultato. L'adapter non persiste e non
implementa `update` o `upsert`.

## Wiring controllato

L'integrazione futura dovrà:

- restare dietro `IRONCOACH_MAINTAIN_PLAN_SHADOW_ENABLED`;
- restare default-off;
- invocare la chain soltanto dopo la disponibilità dell'intero bundle;
- non usare fallback quando un input è mancante o non valutabile;
- lasciare la persistenza in un bridge separato e atomico;
- non modificare `Decision Memory`, `decision_episodes` o il runtime legacy senza
  test di integrazione e regressione dedicati.

## Criteri prima dell'implementazione

Prima di scrivere il codice adapter devono essere identificati e testati:

1. provider concreto di ciascuno dei sei elementi del bundle;
2. identità e provenance per ogni provider;
3. regola di versionamento e idempotenza;
4. comportamento quando un provider è assente, in conflitto o in ritardo;
5. confine tra mapping automatico e conferma atleta;
6. test di integrazione senza rete e senza database reali;
7. piano di rollout mantenendo il flag default-off.

Fino a quel momento questo documento resta una definizione contrattuale
preparatoria: nessun adapter o wiring runtime viene considerato implementato.
