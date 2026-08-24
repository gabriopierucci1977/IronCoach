# Decision persistence contract

IronCoach distingue tra la **decisione runtime completa** e il sottoinsieme
attualmente persistibile nella tabella Airtable `Decision Log`.

## Decision Model completo

Il runtime mantiene:

```python
{
    "decision": ...,
    "reason": ...,
    "priority": ...,
    "training_priority": ...,
    "confidence": ...,
    "strategy": ...,
    "recommended_action": ...,
    "modified_workout": ...,
    "risk_level": ...,
    "reasoning": [...],
    "intelligence": {...},
}
```

`risk_level`, `reasoning` e `intelligence` sono usati dal Coach Report e restano
accessibili alla pipeline.

## Campi Airtable attuali

`DecisionWriter` invia esclusivamente:

- `Data`
- `Decisione IronCoach`
- `Motivazione`
- `Confidenza`
- `Azione consigliata`
- `Allenamento modificato`
- `Priorità`
- `Priorità allenante`
- `Strategia`

Il contratto è dichiarato anche in `DecisionWriter.AIRTABLE_FIELDS`.

## Perché i campi estesi non vengono inviati

Airtable rifiuta o rende fragile una scrittura quando vengono inviati campi che
non esistono nella tabella. Per questo IronCoach non presume che `Decision Log`
contenga colonne per:

- `risk_level`
- `reasoning`
- `intelligence`

L'estensione futura dello schema Airtable dovrà essere esplicita e accompagnata
da test di compatibilità e aggiornamento dell'anti-duplicato.
