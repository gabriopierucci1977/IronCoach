#!/usr/bin/env bash
cd /workspaces/IronCoach
bash <<'IRONCOACH_RUNTIME_RECOVERY_ADAPTER'
set -Eeuo pipefail

report="ironcoach_runtime_recovery_adapter_result.txt"
exec > >(tee "$report") 2>&1

echo '=== ADAPTER RUNTIME RECOVERY TIPIZZATO ==='
date -u '+RUN_UTC=%Y-%m-%dT%H:%M:%SZ'
if [ "$(git branch --show-current)" != 'feature/beta-0.4-decision-memory' ]; then
  echo 'STOP: branch diversa da quella attesa.'
  exit 1
fi
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo 'STOP: modifiche locali da preservare; nessun file modificato.'
  git status --short --branch
  exit 1
fi

targets=(
  backend/maintain_plan/runtime_recovery_adapter.py
  tests/maintain_plan/test_runtime_recovery_adapter.py
  docs/MAINTAIN_PLAN_RUNTIME_RECOVERY_ADAPTER_CONTRACT.md
  docs/BETA_0_4_HANDOFF.md
)
for f in "${targets[@]}"; do
  if [ -e "$f" ] && ! git ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then
    echo "STOP: file non tracciato da preservare: $f"
    exit 1
  fi
done

backup="$(mktemp -d)"
committed=0
for f in "${targets[@]}"; do
  if [ -f "$f" ]; then
    mkdir -p "$backup/$(dirname "$f")"
    cp -p "$f" "$backup/$f"
  fi
done

handle_error() {
  failure_rc="$1"
  failure_line="$2"
  trap - ERR
  set +e
  printf '\nERROR_RC=%s\nERROR_LINE=%s\n' "$failure_rc" "$failure_line"
  rm -f .ironcoach_runtime_recovery_adapter.patch
  if [ "$committed" -eq 0 ]; then
    git restore --staged -- "${targets[@]}" 2>/dev/null
    restore_rc=0
    for f in "${targets[@]}"; do
      if [ -f "$backup/$f" ]; then
        cp -p "$backup/$f" "$f" || restore_rc=1
      else
        rm -f -- "$f" || restore_rc=1
      fi
    done
    if [ "$restore_rc" -eq 0 ]; then
      echo 'ROLLBACK=ESEGUITO'
      rm -rf "$backup"
    else
      echo "ROLLBACK=INCOMPLETO; backup conservato: $backup"
    fi
  else
    echo 'COMMIT_CONSERVATO: il commit locale resta disponibile per riprovare il push.'
    rm -rf "$backup"
  fi
  git status --short --branch
  echo '=== FINE REPORT ==='
  exit "$failure_rc"
}
trap 'handle_error "$?" "$LINENO"' ERR

cat > .ironcoach_runtime_recovery_adapter.patch <<'PATCH_FILE'
--- /dev/null
+++ backend/maintain_plan/runtime_recovery_adapter.py
@@ -0,0 +1,267 @@
+"""Pure adapter from explicit runtime recovery records to stability contracts.
+
+This module deliberately does not read the Garmin archive, perform I/O, or
+derive a recovery category from a numeric readiness/body-battery value.  The
+caller must provide the runtime timestamps and the subject-scoped context.
+"""
+
+from __future__ import annotations
+
+from datetime import datetime
+from typing import Any, Iterable
+
+from .runtime_stability_provider import (
+    RuntimeStabilityProviderResult,
+    provide_runtime_stability,
+)
+from .stability_models import (
+    ActualSessionBoundary,
+    AnalyzerRef,
+    CategoryMissingness,
+    GeneralStabilityInput,
+    PrescriptionBaselineBinding,
+    ProvenanceRef,
+    RecoveryAssessment,
+    RecoveryAssessmentCandidateSet,
+    RecoveryCategory,
+    STABILITY_CONTRACT_VERSION,
+    STABILITY_POLICY_ID,
+    STABILITY_POLICY_VERSION,
+    VersionedArtifactRef,
+)
+from .stability_validators import validate_general_stability_input
+
+
+RECOVERY_ASSESSMENT_SCHEMA_VERSION = "runtime-recovery-assessment/1.0.0"
+RECOVERY_PROVENANCE_VERSION = "1"
+RECOVERY_ARTIFACT_TYPE = "recovery-observation"
+RECOVERY_PROVENANCE_TYPE = "runtime-recovery-record"
+RECOVERY_ANALYZER_ID = "runtime-recovery-source"
+
+
+class RuntimeRecoveryAdapterError(ValueError):
+    """Fail-closed error at the runtime recovery trust boundary."""
+
+    def __init__(self, errors: Iterable[str], *, code: str = "INPUT_INVALID"):
+        self.code = code
+        self.errors = tuple(errors)
+        super().__init__("; ".join(self.errors))
+
+
+def _is_aware(value: object) -> bool:
+    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
+
+
+def _parse_timestamp(value: object, field: str) -> datetime:
+    if isinstance(value, datetime):
+        if not _is_aware(value):
+            raise RuntimeRecoveryAdapterError((f"{field} must be timezone-aware",))
+        return value
+    if type(value) is not str or not value.strip():
+        raise RuntimeRecoveryAdapterError((f"{field} is required as an explicit timezone-aware timestamp",),
+                                          code="INPUT_MISSING")
+    text = value.strip()
+    try:
+        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
+    except ValueError as exc:
+        raise RuntimeRecoveryAdapterError((f"{field} is not a valid ISO-8601 timestamp",)) from exc
+    if not _is_aware(parsed):
+        raise RuntimeRecoveryAdapterError((f"{field} must be timezone-aware",))
+    return parsed
+
+
+def _required_text(record: dict[str, Any], field: str) -> str:
+    value = record.get(field)
+    if type(value) is not str or not value.strip():
+        raise RuntimeRecoveryAdapterError((f"record.{field} is required",), code="INPUT_MISSING")
+    return value.strip()
+
+
+def _category(record: dict[str, Any]) -> tuple[RecoveryCategory | None, CategoryMissingness, tuple[str, ...]]:
+    values = []
+    for field in ("recovery_category", "category"):
+        if field in record and record[field] is not None:
+            values.append((field, record[field]))
+    if not values:
+        return None, CategoryMissingness.MISSING, ("candidate_set.candidates[].category",)
+    first = values[0][1]
+    if len(values) > 1 and values[1][1] != first:
+        raise RuntimeRecoveryAdapterError(("record.recovery_category and record.category disagree",))
+    if isinstance(first, RecoveryCategory):
+        return first, CategoryMissingness.NOT_MISSING, ()
+    if type(first) is not str:
+        raise RuntimeRecoveryAdapterError(("record category must be one of LOW, MODERATE, HIGH, CRITICAL",))
+    try:
+        return RecoveryCategory(first), CategoryMissingness.NOT_MISSING, ()
+    except ValueError as exc:
+        raise RuntimeRecoveryAdapterError(("record category must be one of LOW, MODERATE, HIGH, CRITICAL",)) from exc
+
+
+def _assessment_provenance(source_id: str) -> tuple[VersionedArtifactRef, ProvenanceRef]:
+    evidence = VersionedArtifactRef(RECOVERY_ARTIFACT_TYPE, source_id, RECOVERY_PROVENANCE_VERSION)
+    provenance = ProvenanceRef(
+        producer=evidence,
+        provenance_type=RECOVERY_PROVENANCE_TYPE,
+        provenance_id=source_id,
+        provenance_version=RECOVERY_PROVENANCE_VERSION,
+    )
+    return evidence, provenance
+
+
+def build_recovery_assessment(
+    record: object,
+    *,
+    subject_ref: object,
+    missing_category_path: str = "candidate_set.candidates[].category",
+) -> RecoveryAssessment:
+    """Convert one source record using only explicit, typed evidence."""
+    if type(record) is not dict:
+        raise RuntimeRecoveryAdapterError(("record must be a dictionary",))
+    if type(subject_ref) is not str or not subject_ref.strip():
+        raise RuntimeRecoveryAdapterError(("subject_ref must be a non-empty string",))
+    subject = subject_ref.strip()
+    source = _required_text(record, "source")
+    source_id = _required_text(record, "source_id")
+    _required_text(record, "date")
+    claimed_subject = record.get("subject_ref")
+    if claimed_subject is not None and claimed_subject != subject:
+        raise RuntimeRecoveryAdapterError(("record subject_ref does not match runtime subject",))
+    observed_at = _parse_timestamp(record.get("observed_at"), "record.observed_at")
+    assessed_at = _parse_timestamp(record.get("assessed_at"), "record.assessed_at")
+    if observed_at > assessed_at:
+        raise RuntimeRecoveryAdapterError(("record.observed_at must not follow record.assessed_at",))
+    category, missingness, missing = _category(record)
+    if missingness is CategoryMissingness.MISSING:
+        missing = (missing_category_path,)
+    evidence, provenance = _assessment_provenance(source_id)
+    analyzer = AnalyzerRef(
+        RECOVERY_ANALYZER_ID,
+        RECOVERY_PROVENANCE_VERSION,
+        RECOVERY_ASSESSMENT_SCHEMA_VERSION,
+    )
+    return RecoveryAssessment(
+        assessment_id=f"maintain-plan:recovery-assessment:{source}:{source_id}",
+        contract_version=STABILITY_CONTRACT_VERSION,
+        analyzer_ref=analyzer,
+        subject_ref=subject,
+        observed_at=observed_at,
+        assessed_at=assessed_at,
+        category=category,
+        category_missingness=missingness,
+        evidence_refs=(evidence,),
+        provenance_ref=provenance,
+        missing_fields=missing,
+        warnings=(),
+    )
+
+
+def build_recovery_candidate_set(
+    records: object,
+    *,
+    actual_session_ref: object,
+    subject_ref: object,
+    captured_at: object,
+    evaluated_cutoff_at: object,
+    provenance_ref: object,
+) -> RecoveryAssessmentCandidateSet:
+    """Build the candidate set from an explicit, already scoped record list."""
+    if type(records) not in (list, tuple):
+        raise RuntimeRecoveryAdapterError(("records must be a list or tuple",))
+    if type(actual_session_ref) is not VersionedArtifactRef:
+        raise RuntimeRecoveryAdapterError(("actual_session_ref must be a VersionedArtifactRef",))
+    if type(provenance_ref) is not ProvenanceRef:
+        raise RuntimeRecoveryAdapterError(("provenance_ref must be a ProvenanceRef",))
+    captured = _parse_timestamp(captured_at, "captured_at")
+    cutoff = _parse_timestamp(evaluated_cutoff_at, "evaluated_cutoff_at")
+    candidates = tuple(
+        build_recovery_assessment(record, subject_ref=subject_ref)
+        for record in records
+    )
+    return RecoveryAssessmentCandidateSet(
+        contract_version=STABILITY_CONTRACT_VERSION,
+        actual_session_ref=actual_session_ref,
+        subject_ref=subject_ref,
+        captured_at=captured,
+        evaluated_cutoff_at=cutoff,
+        candidates=candidates,
+        provenance_ref=provenance_ref,
+    )
+
+
+def build_runtime_stability_input(
+    *,
+    prescription_binding: object,
+    actual_session_boundary: object,
+    records: object,
+    captured_at: object,
+    evaluated_at: object,
+    provenance_ref: object,
+    baseline_record: object = None,
+) -> GeneralStabilityInput:
+    """Build a complete typed input without persistence or source discovery."""
+    if type(prescription_binding) is not PrescriptionBaselineBinding:
+        raise RuntimeRecoveryAdapterError(("prescription_binding must be a PrescriptionBaselineBinding",))
+    if type(actual_session_boundary) is not ActualSessionBoundary:
+        raise RuntimeRecoveryAdapterError(("actual_session_boundary must be an ActualSessionBoundary",))
+    evaluated = _parse_timestamp(evaluated_at, "evaluated_at")
+    candidate_set = build_recovery_candidate_set(
+        records,
+        actual_session_ref=actual_session_boundary.actual_session_ref,
+        subject_ref=prescription_binding.subject_ref,
+        captured_at=captured_at,
+        evaluated_cutoff_at=evaluated,
+        provenance_ref=provenance_ref,
+    )
+    baseline = None
+    if baseline_record is not None:
+        baseline = build_recovery_assessment(
+            baseline_record,
+            subject_ref=prescription_binding.subject_ref,
+            missing_category_path="baseline_assessment.category",
+        )
+    value = GeneralStabilityInput(
+        contract_version=STABILITY_CONTRACT_VERSION,
+        policy_id=STABILITY_POLICY_ID,
+        policy_version=STABILITY_POLICY_VERSION,
+        prescription_binding=prescription_binding,
+        baseline_assessment=baseline,
+        actual_session_boundary=actual_session_boundary,
+        candidate_set=candidate_set,
+        next_decision_boundary=None,
+        evaluated_at=evaluated,
+        reported_problems_projection=None,
+        provenance_ref=provenance_ref,
+    )
+    errors = validate_general_stability_input(value)
+    if errors:
+        raise RuntimeRecoveryAdapterError(errors)
+    return value
+
+
+def provide_runtime_stability_from_recovery_records(
+    *,
+    prescription_binding: object,
+    actual_session_boundary: object,
+    records: object,
+    captured_at: object,
+    evaluated_at: object,
+    provenance_ref: object,
+    evaluation_id: object,
+    baseline_record: object = None,
+) -> RuntimeStabilityProviderResult:
+    """Adapt explicit records and run the existing pure stability provider."""
+    value = build_runtime_stability_input(
+        prescription_binding=prescription_binding,
+        actual_session_boundary=actual_session_boundary,
+        records=records,
+        captured_at=captured_at,
+        evaluated_at=evaluated_at,
+        provenance_ref=provenance_ref,
+        baseline_record=baseline_record,
+    )
+    try:
+        return provide_runtime_stability(value, evaluation_id=evaluation_id)
+    except ValueError as exc:
+        if isinstance(exc, RuntimeRecoveryAdapterError):
+            raise
+        raise RuntimeRecoveryAdapterError((str(exc),)) from exc
--- /dev/null
+++ tests/maintain_plan/test_runtime_recovery_adapter.py
@@ -0,0 +1,129 @@
+from dataclasses import replace
+from datetime import datetime, timezone
+
+import pytest
+
+from backend.maintain_plan.runtime_recovery_adapter import (
+    RuntimeRecoveryAdapterError,
+    build_recovery_assessment,
+    provide_runtime_stability_from_recovery_records,
+)
+from backend.importers.garmin_recovery_adapter import GarminRecoveryAdapter
+from backend.maintain_plan.stability_models import (
+    ActualSessionBoundary,
+    CategoryMissingness,
+    GeneralStabilityInput,
+    ProvenanceRef,
+    RecoveryCategory,
+    VersionedArtifactRef,
+)
+from tests.maintain_plan.test_general_stability_service import make_input
+
+
+def _record(**overrides):
+    value = {
+        "source": "garmin",
+        "source_id": "garmin-recovery:2026-01-01",
+        "date": "2026-01-01",
+        "observed_at": "2026-01-01T06:00:00Z",
+        "assessed_at": "2026-01-01T06:05:00Z",
+        "training_readiness": 72,
+    }
+    value.update(overrides)
+    return value
+
+
+def _context():
+    value = make_input()
+    value = replace(
+        value,
+        prescription_binding=replace(value.prescription_binding, baseline_assessment_ref=None),
+        baseline_assessment=None,
+    )
+    provenance = value.provenance_ref
+    return value, provenance
+
+
+def test_adapter_keeps_numeric_training_readiness_out_of_category():
+    assessment = build_recovery_assessment(_record(), subject_ref="athlete")
+    assert assessment.category is None
+    assert assessment.category_missingness is CategoryMissingness.MISSING
+    assert assessment.missing_fields == ("candidate_set.candidates[].category",)
+
+
+def test_adapter_accepts_only_explicit_category():
+    assessment = build_recovery_assessment(
+        _record(category="LOW"),
+        subject_ref="athlete",
+    )
+    assert assessment.category is RecoveryCategory.LOW
+    assert assessment.category_missingness is CategoryMissingness.NOT_MISSING
+
+
+def test_adapter_rejects_unknown_category():
+    with pytest.raises(RuntimeRecoveryAdapterError, match="one of LOW"):
+        build_recovery_assessment(_record(category="GOOD"), subject_ref="athlete")
+
+
+def test_adapter_rejects_missing_explicit_timestamp():
+    with pytest.raises(RuntimeRecoveryAdapterError) as error:
+        build_recovery_assessment(_record(observed_at=None), subject_ref="athlete")
+    assert error.value.code == "INPUT_MISSING"
+
+
+def test_current_garmin_daily_shape_is_rejected_until_timestamp_is_explicit():
+    daily = GarminRecoveryAdapter.convert(date="2026-01-01", training_readiness={"score": 72})
+    with pytest.raises(RuntimeRecoveryAdapterError) as error:
+        build_recovery_assessment(daily, subject_ref="athlete")
+    assert error.value.code == "INPUT_MISSING"
+
+
+def test_adapter_rejects_foreign_subject_claim():
+    with pytest.raises(RuntimeRecoveryAdapterError, match="subject_ref"):
+        build_recovery_assessment(_record(subject_ref="other-athlete"), subject_ref="athlete")
+
+
+def test_adapter_runs_pure_provider_and_reports_missing_dimensions():
+    value, provenance = _context()
+    result = provide_runtime_stability_from_recovery_records(
+        prescription_binding=value.prescription_binding,
+        actual_session_boundary=value.actual_session_boundary,
+        records=[_record()],
+        captured_at=value.evaluated_at,
+        evaluated_at=value.evaluated_at,
+        provenance_ref=provenance,
+        evaluation_id="runtime-recovery-1",
+    )
+    assert result.evaluation.evaluation_id == "runtime-recovery-1"
+    assert result.evaluation.recovery_result.value == "INSUFFICIENT_DATA"
+    assert "baseline_assessment" in result.evaluation.missing_fields
+    assert "reported_problems_projection" in result.evaluation.missing_fields
+    assert "candidate_set.candidates" not in result.evaluation.missing_fields
+
+
+def test_adapter_is_deterministic_for_same_input():
+    value, provenance = _context()
+    kwargs = dict(
+        prescription_binding=value.prescription_binding,
+        actual_session_boundary=value.actual_session_boundary,
+        records=[_record()],
+        captured_at=value.evaluated_at,
+        evaluated_at=value.evaluated_at,
+        provenance_ref=provenance,
+        evaluation_id="runtime-recovery-1",
+    )
+    assert provide_runtime_stability_from_recovery_records(**kwargs).evaluation == provide_runtime_stability_from_recovery_records(**kwargs).evaluation
+
+
+def test_adapter_rejects_naive_runtime_context_timestamp():
+    value, provenance = _context()
+    with pytest.raises(RuntimeRecoveryAdapterError, match="timezone-aware"):
+        provide_runtime_stability_from_recovery_records(
+            prescription_binding=value.prescription_binding,
+            actual_session_boundary=value.actual_session_boundary,
+            records=[_record()],
+            captured_at=datetime(2026, 10, 10, 7, 0),
+            evaluated_at=value.evaluated_at,
+            provenance_ref=provenance,
+            evaluation_id="runtime-recovery-1",
+        )
--- /dev/null
+++ docs/MAINTAIN_PLAN_RUNTIME_RECOVERY_ADAPTER_CONTRACT.md
@@ -0,0 +1,43 @@
+# MAINTAIN_PLAN runtime recovery adapter contract
+
+Ultimo aggiornamento: 10 ottobre 2026
+
+`backend/maintain_plan/runtime_recovery_adapter.py` è un confine puro tra
+record recovery già disponibili al runtime e i contratti typed di
+MAINTAIN_PLAN. Non legge l'archivio, non usa rete o database e non viene
+importato dal percorso runtime attivo.
+
+## Input obbligatori
+
+Ogni record deve fornire `source`, `source_id`, `date`, `observed_at` e
+`assessed_at`. I due timestamp devono essere espliciti, ISO-8601 e timezone
+aware. Il contesto chiamante fornisce inoltre `subject_ref`, la sessione
+reale, il binding della prescrizione, `captured_at`, `evaluated_at` e la
+provenance.
+
+Un `subject_ref` presente nel record deve coincidere esattamente con quello del
+contesto. Un mismatch interrompe l'adattamento.
+
+## Categoria recovery
+
+La categoria è accettata solo quando il record contiene esplicitamente uno dei
+valori `LOW`, `MODERATE`, `HIGH` o `CRITICAL` nel campo `category` o
+`recovery_category`. `training_readiness`, Body Battery, stress e altri numeri
+Garmin non vengono convertiti in una categoria.
+
+Quando la categoria manca, l'assessment viene creato con
+`CategoryMissingness.MISSING` e il campo canonico
+`candidate_set.candidates[].category`; la valutazione stability resta quindi
+`INSUFFICIENT_DATA` finché non esiste evidenza sufficiente.
+
+Un timestamp mancante, naive o non interpretabile e una categoria esplicita
+non riconosciuta producono un errore fail-closed. L'adapter non inventa la
+mezzanotte UTC a partire da `date`.
+
+## Stato di integrazione
+
+L'archivio `GarminRecoveryArchive` attuale conserva solo record giornalieri con
+`date` e valori descrittivi. Non viene modificato né collegato alla chain in
+questa fase: i record esistenti non soddisfano ancora il requisito dei
+timestamp espliciti e non contengono una categoria canonica. La chain e la
+persistenza restano disattivate per default.
--- docs/BETA_0_4_HANDOFF.md
+++ docs/BETA_0_4_HANDOFF.md
@@ -1048,3 +1048,26 @@
 Questo checkpoint persiste soltanto una valutazione completa ricevuta dal
 provider; non crea baseline, candidate set o reported-problems dal runtime e
 non attiva la shadow chain.
+
+## Adapter runtime recovery tipizzato — 10 ottobre 2026
+
+È stato aggiunto `backend/maintain_plan/runtime_recovery_adapter.py` come
+confine pure per record recovery già disponibili al runtime. L'adapter non
+legge Garmin, non usa rete o database e non viene importato da
+`backend/main.py`.
+
+Il record deve fornire `source`, `source_id`, `date`, `observed_at` e
+`assessed_at`; i timestamp devono essere espliciti e timezone-aware. Un
+`subject_ref` eventualmente presente deve coincidere con quello del contesto.
+Il campo `training_readiness` non viene convertito in una categoria recovery.
+Solo `LOW`, `MODERATE`, `HIGH` e `CRITICAL` espliciti sono categorie valide.
+
+L'archivio `GarminRecoveryArchive` attuale non possiede ancora tutti questi
+campi: per questo l'adapter rifiuta i record incompleti invece di inventare la
+mezzanotte UTC o una classificazione. Con categoria assente ma timestamp
+validi, l'assessment conserva `CategoryMissingness.MISSING` e la valutazione
+resta `INSUFFICIENT_DATA`.
+
+Il contratto dettagliato è in
+`docs/MAINTAIN_PLAN_RUNTIME_RECOVERY_ADAPTER_CONTRACT.md`. La chain, il flag
+runtime e la persistenza restano default-off.
PATCH_FILE

patch --dry-run --forward --batch -p0 < .ironcoach_runtime_recovery_adapter.patch
patch --forward --batch -p0 < .ironcoach_runtime_recovery_adapter.patch
rm -f .ironcoach_runtime_recovery_adapter.patch

python -m compileall -q backend tests
git diff --check
python -m pytest -q

git add -- "${targets[@]}"
git diff --cached --check
git commit -m 'feat: add typed runtime recovery adapter'
committed=1
git push origin feature/beta-0.4-decision-memory

echo '=== VERIFICA FINALE ==='
git status --short --branch
git log -1 --oneline
echo '=== FINE REPORT ==='
rm -rf "$backup"
IRONCOACH_RUNTIME_RECOVERY_ADAPTER
