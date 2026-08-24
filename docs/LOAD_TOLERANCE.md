# Historical load tolerance

`AthleteProfileEngine` now derives `load_tolerance` from the normalized training
history available to `ContextBuilder`.

The metric is intentionally **descriptive**, not a physiological safety limit.
It summarizes the load the athlete has demonstrated in the available history
and must not be interpreted as a medical or injury-prevention threshold.

## Window

IronCoach uses up to 56 days of valid dated sessions with an observed
`training_load`.

The history is split into up to eight rolling seven-day buckets ending on the
most recent valid session date.

## Baseline

The primary baseline is the **median weekly load**. The median is used so that
one unusually large week does not dominate the estimate.

The output also exposes:

- `mean_weekly_load`
- `peak_weekly_load`
- `latest_7d_load`
- `sessions_analyzed`
- `weeks_analyzed`
- `data_span_days`
- source summary

## Status and confidence

If fewer than four valid sessions or fewer than seven days of history are
available:

```text
status = DATI INSUFFICIENTI
level = UNKNOWN
confidence = LOW
```

With sufficient history:

```text
status = STIMATA
```

Confidence is:

- `HIGH` with at least 12 valid sessions across at least 28 days;
- `MODERATE` with at least 6 sessions across at least 14 days;
- `LOW` otherwise.

When no valid observed load exists at all, the status remains `DA STIMARE` and
confidence is `NONE`.

## Level

The current descriptive levels are aligned with the weekly equivalent of the
existing `LoadAnalyzer` 28-day bands:

- `LOW`: baseline weekly load < 125
- `NORMAL`: 125 to < 500
- `HIGH`: >= 500

These labels describe **observed historical load volume**, not an automatically
safe amount of training.

## Pipeline

The estimate is computed only after Airtable and Garmin history have been
merged and normalized:

```text
Airtable + Garmin
→ ActivityNormalizer
→ TrainingHistory
→ AthleteProfileEngine.load_tolerance
→ CoachEngine intelligence
→ Coach Report / Decision runtime
```
