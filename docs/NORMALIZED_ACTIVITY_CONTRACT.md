# Normalized Activity Contract

`ActivityNormalizer` is the schema boundary between external activity sources and the IronCoach coaching pipeline.

Downstream analyzers should prefer the canonical keys below and only inspect `raw` as a backwards-compatible fallback.

## Canonical fields

```python
{
    "source": str,
    "source_id": Any,
    "date": Any,
    "sport": str,
    "workout_name": Any,
    "session_type": Any,
    "duration_minutes": Optional[float],
    "distance_km": float,
    "training_load": Any,
    "intensity": Any,
    "heart_rate": {
        "average": Any,
        "max": Any,
    },
    "power": {
        "average": Any,
        "normalized": Any,
    },
    "rpe": Any,
    "notes": Any,
    "current_problem": Any,
    "pain_score": Any,
    "raw": dict,
}
```

The runtime type contract is declared in `backend/normalization/activity_contract.py` as `NormalizedActivity`.

## Safety invariants

The following fields must not exist only inside `raw`:

- `current_problem`
- `pain_score`

They are promoted by `ActivityNormalizer` because the Injury Analyzer and Decision Engine depend on them for safety decisions.

A severe pain signal must remain equivalent across the boundary:

```text
raw input
→ ActivityNormalizer
→ InjuryAnalyzer
→ DecisionEngine
```

The regression suite verifies that a critical injury remains `CRITICAL` and reaches a `RECUPERA / RECOVERY` decision.

## Missing values

A missing training load is represented as `None`, not `0`.

This distinction is intentional:

```text
None = load not observed / unavailable
0    = observed load equal to zero
```

`TrainingHistory` preserves the same distinction and `LoadAnalyzer` excludes missing loads from `sessions_with_load`.

Missing duration is also preserved as `None` at the activity-normalization boundary.

Duration units are explicit and are **never inferred from numeric magnitude**:

- `duration_minutes`, `Durata minuti`, `duration_min` → minutes;
- `duration_seconds`, `duration_sec`, `moving_time_seconds`, `elapsed_time_seconds` → seconds;
- `moving_time` and `elapsed_time` → seconds;
- generic `duration` → seconds for Garmin/Strava/FIT/TCX/GPX sources, minutes for manual/Airtable-compatible sources.

This removes the old `>300` heuristic, which could turn a valid 360-minute endurance session into 6 minutes. Source adapters should prefer explicit unit-bearing keys whenever possible.

## Analyzer compatibility

`TrainingAnalyzer` reads canonical fields first:

- `rpe`
- `session_type`
- `intensity`
- `duration_minutes`
- `training_load`

It falls back to legacy/raw Airtable keys when needed.

`InjuryAnalyzer` reads canonical fields first:

- `current_problem`
- `pain_score`

and retains legacy/raw fallbacks.

`RecoveryTrendAnalyzer` accepts the canonical `RecoveryHistory` nested sleep structure:

```python
"sleep": {
    "score": ...,
    "hours": ...,
}
```

`AdaptationAnalyzer` reads physical limitations from the normalized athlete profile:

```python
"constraints": {
    "physical_limitations": ...,
}
```

as well as legacy profile shapes.
