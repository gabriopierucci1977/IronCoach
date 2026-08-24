# Beta 0.3.1 — Integration & Reproducibility Hardening

Status: hardening implementation completed on the reconstructed Beta 0.3 snapshot.

## Pass 1 — Integration contract P0 fixes

### P0.1 — ActivityNormalizer → TrainingAnalyzer

Fixed.

Canonical training descriptors are promoted by `ActivityNormalizer`, and
`TrainingAnalyzer` consumes the canonical schema before falling back to
legacy/raw fields.

### P0.2 — ActivityNormalizer → InjuryAnalyzer

Fixed.

`current_problem` and `pain_score` are canonical normalized fields. Critical
pain information survives normalization and reaches the Decision Engine.

Regression invariant:

```text
raw severe pain
→ normalize
→ InjuryAnalyzer = CRITICAL
→ CoachEngine / DecisionEngine = RECUPERA / RECOVERY
```

### P0.3 — RecoveryHistory → RecoveryTrendAnalyzer

Fixed. Nested sleep score values under `sleep.score` are read correctly.

### P0.4 — missing training load vs zero

Fixed. Missing training load remains `None`; a real observed zero remains
`0.0` and counts as an observed load.

### P0.5 — normalized physical limitations → AdaptationAnalyzer

Fixed. `AdaptationAnalyzer` consumes
`athlete_profile.constraints.physical_limitations` while retaining legacy
compatibility.

## Pass 2 — Duration contract

The magnitude-based duration heuristic has been removed.

A value is no longer treated as seconds merely because it is greater than 300.
Explicit minute/second fields and source conventions determine the unit.

This protects long endurance sessions such as a 360-minute ride from being
silently normalized to 6 minutes.

See `NORMALIZED_ACTIVITY_CONTRACT.md`.

## Pass 2 — Historical load tolerance

`AthleteProfileEngine` no longer returns the placeholder:

```text
DA STIMARE / storico Garmin-Strava non disponibile
```

when valid history is available.

It derives a descriptive baseline from up to eight rolling seven-day windows,
using median weekly training load plus mean, peak, latest-week load, history
coverage, source summary and confidence.

`ContextBuilder` now computes profile intelligence after loading the merged
Airtable/Garmin training history, and `CoachEngine` preserves that enriched
profile in the final decision intelligence.

See `LOAD_TOLERANCE.md`.

## Pass 2 — Decision persistence contract

The previous README overstated Airtable persistence.

The rich Decision Model retains:

- `risk_level`
- `reasoning`
- `intelligence`

but the current Airtable `Decision Log` schema does not expose dedicated
columns for them.

`DecisionWriter` therefore continues to send only supported columns and now
declares that boundary explicitly through `AIRTABLE_FIELDS` and documentation.
This avoids breaking Airtable writes by inventing non-existent columns.

See `DECISION_PERSISTENCE_CONTRACT.md`.

## Pass 2 — Garmin private fixture strategy

The five parser tests that depend on two private Garmin FIT files no longer
fail on a clean public clone.

They are skipped when the files are unavailable and can be enabled by placing
the fixtures under `data/garmin_raw` or setting:

```text
IRONCOACH_GARMIN_FIXTURE_DIR
```

See `GARMIN_TEST_FIXTURES.md`.

## Pass 2 — Reproducible environment and CI

Added:

- `.python-version` → Python 3.11;
- exact runtime dependency versions in `requirements.txt`;
- `requirements-dev.txt` with pytest;
- GitHub Actions workflow `.github/workflows/test.yml`;
- compile step before pytest.

Public CI runs all tests; private FIT-dependent tests are skipped when fixtures
are not present.

## Validation

Current suite:

```text
389 tests collected
384 passed
5 skipped (private Garmin FIT fixtures)
```

The validation environment used temporary import stubs for `pyairtable` and
`fitparse` because those packages are not installed in the reconstruction
sandbox. The stubs are not included in the repository. The five real FIT
parser tests remain skipped because their private binaries are not present.

Python compilation:

```text
python -m compileall -q backend config tests
COMPILE_OK
```

## New/updated regression coverage

- normalized activity contract and safety invariants;
- long-duration unit handling;
- source-specific generic duration;
- explicit duration seconds;
- historical load-tolerance baseline;
- sparse-history confidence behavior;
- ContextBuilder load-tolerance integration;
- CoachEngine propagation of enriched load tolerance.

## Remaining items before Beta 0.4

The P0 contract issues and planned Beta 0.3.1 hardening items are closed.
Recommended next work is product evolution rather than emergency hardening:

1. define the Beta 0.4 coaching-intelligence scope;
2. decide whether to extend Airtable `Decision Log` with structured rich-decision fields;
3. consider replacing the old distance magnitude heuristic with an explicit distance-unit contract;
4. modularize the largest engine/report modules before introducing concurrent/server execution;
5. add private CI coverage for real FIT fixtures if a secure runner becomes available.
