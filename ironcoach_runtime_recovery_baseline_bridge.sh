#!/usr/bin/env bash
cd /workspaces/IronCoach
bash <<'IRONCOACH_RUNTIME_RECOVERY_BASELINE_BRIDGE'
set -Eeuo pipefail

report="ironcoach_runtime_recovery_baseline_bridge_result.txt"
exec > >(tee "$report") 2>&1

echo '=== BRIDGE BASELINE RECOVERY -> STABILITY ==='
date -u '+RUN_UTC=%Y-%m-%dT%H:%M:%SZ'
if [ "$(git branch --show-current)" != 'feature/beta-0.4-decision-memory' ]; then
  echo 'STOP: branch diversa da quella attesa.'
  exit 1
fi
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo 'STOP: modifiche locali tracciate da preservare; nessun file modificato.'
  git status --short --branch
  exit 1
fi

targets=(
  backend/maintain_plan/runtime_recovery_adapter.py
  docs/MAINTAIN_PLAN_RUNTIME_RECOVERY_ADAPTER_CONTRACT.md
  docs/BETA_0_4_HANDOFF.md
  tests/maintain_plan/test_runtime_recovery_adapter.py
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
  rm -f .ironcoach_runtime_recovery_baseline_bridge.patch
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

cat > .ironcoach_runtime_recovery_baseline_bridge.patch <<'PATCH_FILE'
--- backend/maintain_plan/runtime_recovery_adapter.py
+++ backend/maintain_plan/runtime_recovery_adapter.py
@@ -10,6 +10,10 @@
 from datetime import datetime
 from typing import Any, Iterable
 
+from .recovery_baseline_models import (
+    PrescriptionRecoveryBaseline,
+    validate_recovery_baseline,
+)
 from .runtime_stability_provider import (
     RuntimeStabilityProviderResult,
     provide_runtime_stability,
@@ -113,6 +117,7 @@
     *,
     subject_ref: object,
     missing_category_path: str = "candidate_set.candidates[].category",
+    analyzer_ref: object = None,
 ) -> RecoveryAssessment:
     """Convert one source record using only explicit, typed evidence."""
     if type(record) is not dict:
@@ -134,11 +139,16 @@
     if missingness is CategoryMissingness.MISSING:
         missing = (missing_category_path,)
     evidence, provenance = _assessment_provenance(source_id)
-    analyzer = AnalyzerRef(
-        RECOVERY_ANALYZER_ID,
-        RECOVERY_PROVENANCE_VERSION,
-        RECOVERY_ASSESSMENT_SCHEMA_VERSION,
-    )
+    if analyzer_ref is None:
+        analyzer = AnalyzerRef(
+            RECOVERY_ANALYZER_ID,
+            RECOVERY_PROVENANCE_VERSION,
+            RECOVERY_ASSESSMENT_SCHEMA_VERSION,
+        )
+    elif type(analyzer_ref) is AnalyzerRef:
+        analyzer = analyzer_ref
+    else:
+        raise RuntimeRecoveryAdapterError(("analyzer_ref must be an AnalyzerRef",))
     return RecoveryAssessment(
         assessment_id=f"maintain-plan:recovery-assessment:{source}:{source_id}",
         contract_version=STABILITY_CONTRACT_VERSION,
@@ -163,6 +173,7 @@
     captured_at: object,
     evaluated_cutoff_at: object,
     provenance_ref: object,
+    analyzer_ref: object = None,
 ) -> RecoveryAssessmentCandidateSet:
     """Build the candidate set from an explicit, already scoped record list."""
     if type(records) not in (list, tuple):
@@ -174,7 +185,9 @@
     captured = _parse_timestamp(captured_at, "captured_at")
     cutoff = _parse_timestamp(evaluated_cutoff_at, "evaluated_cutoff_at")
     candidates = tuple(
-        build_recovery_assessment(record, subject_ref=subject_ref)
+        build_recovery_assessment(
+            record, subject_ref=subject_ref, analyzer_ref=analyzer_ref,
+        )
         for record in records
     )
     return RecoveryAssessmentCandidateSet(
@@ -197,6 +210,8 @@
     evaluated_at: object,
     provenance_ref: object,
     baseline_record: object = None,
+    baseline_assessment: object = None,
+    candidate_analyzer_ref: object = None,
 ) -> GeneralStabilityInput:
     """Build a complete typed input without persistence or source discovery."""
     if type(prescription_binding) is not PrescriptionBaselineBinding:
@@ -211,13 +226,28 @@
         captured_at=captured_at,
         evaluated_cutoff_at=evaluated,
         provenance_ref=provenance_ref,
-    )
-    baseline = None
-    if baseline_record is not None:
+        analyzer_ref=candidate_analyzer_ref,
+    )
+    if baseline_record is not None and baseline_assessment is not None:
+        raise RuntimeRecoveryAdapterError((
+            "baseline_record and baseline_assessment are mutually exclusive",
+        ))
+    baseline = baseline_assessment
+    if baseline is not None:
+        if type(baseline) is not RecoveryAssessment:
+            raise RuntimeRecoveryAdapterError((
+                "baseline_assessment must be a RecoveryAssessment",
+            ))
+        if baseline.subject_ref != prescription_binding.subject_ref:
+            raise RuntimeRecoveryAdapterError((
+                "baseline assessment ownership must equal prescription binding",
+            ))
+    elif baseline_record is not None:
         baseline = build_recovery_assessment(
             baseline_record,
             subject_ref=prescription_binding.subject_ref,
             missing_category_path="baseline_assessment.category",
+            analyzer_ref=candidate_analyzer_ref,
         )
     value = GeneralStabilityInput(
         contract_version=STABILITY_CONTRACT_VERSION,
@@ -238,6 +268,43 @@
     return value
 
 
+def build_runtime_stability_input_from_prescription_baseline(
+    *,
+    baseline: object,
+    actual_session_boundary: object,
+    records: object,
+    captured_at: object,
+    evaluated_at: object,
+    provenance_ref: object,
+) -> GeneralStabilityInput:
+    """Use the exact captured baseline and its analyzer identity for follow-ups."""
+    if type(baseline) is not PrescriptionRecoveryBaseline:
+        raise RuntimeRecoveryAdapterError((
+            "baseline must be a PrescriptionRecoveryBaseline",
+        ))
+    errors = validate_recovery_baseline(baseline)
+    if errors:
+        raise RuntimeRecoveryAdapterError(errors)
+    if type(actual_session_boundary) is not ActualSessionBoundary:
+        raise RuntimeRecoveryAdapterError((
+            "actual_session_boundary must be an ActualSessionBoundary",
+        ))
+    if actual_session_boundary.subject_ref != baseline.binding.subject_ref:
+        raise RuntimeRecoveryAdapterError((
+            "baseline and actual session ownership must agree",
+        ))
+    return build_runtime_stability_input(
+        prescription_binding=baseline.binding,
+        actual_session_boundary=actual_session_boundary,
+        records=records,
+        captured_at=captured_at,
+        evaluated_at=evaluated_at,
+        provenance_ref=provenance_ref,
+        baseline_assessment=baseline.assessment,
+        candidate_analyzer_ref=baseline.assessment.analyzer_ref,
+    )
+
+
 def provide_runtime_stability_from_recovery_records(
     *,
     prescription_binding: object,
@@ -265,3 +332,30 @@
         if isinstance(exc, RuntimeRecoveryAdapterError):
             raise
         raise RuntimeRecoveryAdapterError((str(exc),)) from exc
+
+
+def provide_runtime_stability_from_prescription_baseline(
+    *,
+    baseline: object,
+    actual_session_boundary: object,
+    records: object,
+    captured_at: object,
+    evaluated_at: object,
+    provenance_ref: object,
+    evaluation_id: object,
+) -> RuntimeStabilityProviderResult:
+    """Run the provider from a captured baseline without re-analysis or I/O."""
+    value = build_runtime_stability_input_from_prescription_baseline(
+        baseline=baseline,
+        actual_session_boundary=actual_session_boundary,
+        records=records,
+        captured_at=captured_at,
+        evaluated_at=evaluated_at,
+        provenance_ref=provenance_ref,
+    )
+    try:
+        return provide_runtime_stability(value, evaluation_id=evaluation_id)
+    except ValueError as exc:
+        if isinstance(exc, RuntimeRecoveryAdapterError):
+            raise
+        raise RuntimeRecoveryAdapterError((str(exc),)) from exc
--- docs/MAINTAIN_PLAN_RUNTIME_RECOVERY_ADAPTER_CONTRACT.md
+++ docs/MAINTAIN_PLAN_RUNTIME_RECOVERY_ADAPTER_CONTRACT.md
@@ -41,3 +41,16 @@
 questa fase: i record esistenti non soddisfano ancora il requisito dei
 timestamp espliciti e non contengono una categoria canonica. La chain e la
 persistenza restano disattivate per default.
+
+## Bridge con la baseline persistita
+
+`build_runtime_stability_input_from_prescription_baseline` riceve una
+`PrescriptionRecoveryBaseline` già catturata e usa il suo
+`RecoveryAssessment` senza ricrearlo. I record successivi vengono adattati con
+lo stesso `AnalyzerRef` della baseline, così la compatibilità confronta
+assessment prodotti dalla stessa identità dichiarata.
+
+`provide_runtime_stability_from_prescription_baseline` esegue poi il provider
+pure. Il bridge verifica il tipo della baseline, la sua validità e la
+coincidenza del `subject_ref` con la sessione; non legge la persistenza, non
+cerca record recenti e non attiva `backend/main.py`.
--- docs/BETA_0_4_HANDOFF.md
+++ docs/BETA_0_4_HANDOFF.md
@@ -1091,3 +1091,17 @@
 
 Il contratto è in
 `docs/MAINTAIN_PLAN_RECOVERY_BASELINE_CONTRACT.md`.
+
+## Bridge baseline → stability — 11 ottobre 2026
+
+L'adapter recovery ora espone un bridge esplicito per la baseline già catturata:
+`build_runtime_stability_input_from_prescription_baseline` conserva l'assessment
+immutabile della `PrescriptionRecoveryBaseline` e usa il suo `AnalyzerRef` per
+adattare i record follow-up. `provide_runtime_stability_from_prescription_baseline`
+passa quindi l'input typed al provider pure.
+
+Il bridge rifiuta una baseline non tipizzata o non valida e un soggetto della
+sessione diverso da quello della baseline. Non esegue lookup, rianalisi,
+lettura SQLite o wiring del runtime legacy. La proiezione reported-problems
+resta esplicita e assente nel chiamante corrente; la valutazione conserva
+`INSUFFICIENT_DATA` finché quella dimensione non viene fornita.
--- tests/maintain_plan/test_runtime_recovery_adapter.py
+++ tests/maintain_plan/test_runtime_recovery_adapter.py
@@ -1,23 +1,29 @@
 from dataclasses import replace
-from datetime import datetime, timezone
+from datetime import datetime, timedelta, timezone
 
 import pytest
 
 from backend.maintain_plan.runtime_recovery_adapter import (
     RuntimeRecoveryAdapterError,
     build_recovery_assessment,
+    build_runtime_stability_input_from_prescription_baseline,
+    provide_runtime_stability_from_prescription_baseline,
     provide_runtime_stability_from_recovery_records,
 )
 from backend.importers.garmin_recovery_adapter import GarminRecoveryAdapter
+from backend.maintain_plan.recovery_baseline_models import RECOVERY_ANALYZER_REF
 from backend.maintain_plan.stability_models import (
     ActualSessionBoundary,
     CategoryMissingness,
+    CompatibilityStatus,
     GeneralStabilityInput,
     ProvenanceRef,
     RecoveryCategory,
     VersionedArtifactRef,
 )
+from tests.maintain_plan.fixtures import NOW
 from tests.maintain_plan.test_general_stability_service import make_input
+from tests.maintain_plan.test_recovery_baseline_capture import baseline as make_baseline
 
 
 def _record(**overrides):
@@ -127,3 +133,62 @@
             provenance_ref=provenance,
             evaluation_id="runtime-recovery-1",
         )
+
+
+def test_captured_baseline_is_consumed_exactly_and_pins_follow_up_analyzer():
+    captured = make_baseline()
+    context, provenance = _context()
+    boundary = replace(
+        context.actual_session_boundary,
+        subject_ref=captured.binding.subject_ref,
+        session_end=NOW + timedelta(hours=2),
+    )
+    record = _record(
+        source_id="garmin-recovery:2026-01-01-follow-up",
+        observed_at="2026-01-01T12:00:00Z",
+        assessed_at="2026-01-01T12:05:00Z",
+        category="LOW",
+    )
+    result = provide_runtime_stability_from_prescription_baseline(
+        baseline=captured,
+        actual_session_boundary=boundary,
+        records=[record],
+        captured_at=NOW + timedelta(hours=6),
+        evaluated_at=NOW + timedelta(hours=8),
+        provenance_ref=provenance,
+        evaluation_id="runtime-recovery-baseline-1",
+    )
+    evaluation = result.evaluation
+    assert evaluation.baseline_ref is not None
+    assert evaluation.baseline_ref.assessment_id == captured.assessment.assessment_id
+    assert evaluation.compatibility is not None
+    assert evaluation.compatibility.status is CompatibilityStatus.COMPATIBLE
+    assert evaluation.selected_follow_up_ref is not None
+    assert evaluation.selected_follow_up_ref.analyzer_ref == RECOVERY_ANALYZER_REF
+
+
+def test_captured_baseline_bridge_rejects_foreign_session_owner():
+    captured = make_baseline()
+    context, provenance = _context()
+    with pytest.raises(RuntimeRecoveryAdapterError, match="ownership"):
+        build_runtime_stability_input_from_prescription_baseline(
+            baseline=captured,
+            actual_session_boundary=context.actual_session_boundary,
+            records=[],
+            captured_at=NOW + timedelta(hours=6),
+            evaluated_at=NOW + timedelta(hours=8),
+            provenance_ref=provenance,
+        )
+
+
+def test_captured_baseline_bridge_rejects_untyped_baseline():
+    context, provenance = _context()
+    with pytest.raises(RuntimeRecoveryAdapterError, match="PrescriptionRecoveryBaseline"):
+        build_runtime_stability_input_from_prescription_baseline(
+            baseline=object(),
+            actual_session_boundary=context.actual_session_boundary,
+            records=[],
+            captured_at=NOW + timedelta(hours=6),
+            evaluated_at=NOW + timedelta(hours=8),
+            provenance_ref=provenance,
+        )
PATCH_FILE

patch --dry-run --forward --batch -p0 < .ironcoach_runtime_recovery_baseline_bridge.patch
patch --forward --batch -p0 < .ironcoach_runtime_recovery_baseline_bridge.patch
rm -f .ironcoach_runtime_recovery_baseline_bridge.patch

python -m compileall -q backend tests
git diff --check
python -m pytest -q tests/maintain_plan/test_runtime_recovery_adapter.py
python -m pytest -q

git add -- "${targets[@]}"
git diff --cached --check
git commit -m 'feat: bridge persisted recovery baseline to stability'
committed=1
git push origin feature/beta-0.4-decision-memory

echo '=== VERIFICA FINALE ==='
git status --short --branch
git log -1 --oneline
echo '=== FINE REPORT ==='
rm -rf "$backup"
IRONCOACH_RUNTIME_RECOVERY_BASELINE_BRIDGE
