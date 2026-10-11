#!/usr/bin/env bash
cd /workspaces/IronCoach
bash <<'IRONCOACH_RUNTIME_RECOVERY_BASELINE'
set -Eeuo pipefail

report="ironcoach_runtime_recovery_baseline_result.txt"
exec > >(tee "$report") 2>&1

echo '=== BASELINE RECOVERY LEGATA ALLA PRESCRIZIONE ==='
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
  backend/maintain_plan/recovery_baseline_models.py
  backend/maintain_plan/runtime_recovery_baseline_capture.py
  backend/maintain_plan/repository.py
  backend/maintain_plan/schema.py
  backend/maintain_plan/serialization.py
  docs/MAINTAIN_PLAN_RECOVERY_BASELINE_CONTRACT.md
  docs/BETA_0_4_HANDOFF.md
  tests/maintain_plan/test_recovery_baseline_capture.py
  tests/maintain_plan/test_execution_evaluation_hardening.py
  tests/maintain_plan/test_execution_evaluation_review26.py
  tests/maintain_plan/test_persistence.py
  tests/maintain_plan/test_subject_ownership.py
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
  rm -f .ironcoach_runtime_recovery_baseline.patch
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

cat > .ironcoach_runtime_recovery_baseline.patch <<'PATCH_FILE'
--- /dev/null
+++ backend/maintain_plan/recovery_baseline_models.py
@@ -0,0 +1,131 @@
+"""Immutable baseline declaration for the recovery used by one prescription."""
+
+from __future__ import annotations
+
+import json
+from dataclasses import dataclass
+from datetime import datetime
+
+from .models import PrescriptionSnapshot
+from .stability_models import (
+    AnalyzerRef, CategoryMissingness, PrescriptionBaselineBinding,
+    RecoveryAssessment, RecoveryAssessmentRef, RecoveryCategory,
+    STABILITY_CONTRACT_VERSION, VersionedArtifactRef,
+)
+from .stability_validators import (
+    aware, validate_artifact_ref, validate_assessment, validate_provenance,
+)
+from .validators import validate_prescription
+
+
+# Identity of the existing implementation, pinned to its exact source bytes.
+# A changed analyzer requires a new explicit version before comparison.
+RECOVERY_ANALYZER_SOURCE_SHA256 = "b2b2c181857139ca390adbf538e2053d7e2fbbbb40d3ff594721cf9cd4b7bf42"
+RECOVERY_ANALYZER_REF = AnalyzerRef(
+    "ironcoach-recovery-analyzer",
+    "0.4+sha256:" + RECOVERY_ANALYZER_SOURCE_SHA256,
+    "ironcoach-recovery-assessment/0.4",
+)
+RECOVERY_ANALYZER_ARTIFACT = VersionedArtifactRef(
+    "recovery-analyzer", RECOVERY_ANALYZER_REF.analyzer_id,
+    RECOVERY_ANALYZER_REF.analyzer_version,
+)
+
+
+@dataclass(frozen=True)
+class PrescriptionRecoveryBaseline:
+    binding: PrescriptionBaselineBinding
+    assessment: RecoveryAssessment
+    analyzer_output_json: str
+    captured_at: datetime
+
+    @property
+    def baseline_id(self) -> str:
+        return f"{self.binding.prescription_snapshot_ref.artifact_id}:{self.assessment.assessment_id}"
+
+
+def validate_recovery_baseline(
+    value: object, snapshot: object = None,
+) -> tuple[str, ...]:
+    """Validate the declaration and optionally its exact persisted snapshot."""
+    if type(value) is not PrescriptionRecoveryBaseline:
+        return ("baseline must be a PrescriptionRecoveryBaseline",)
+    errors = list(validate_assessment(value.assessment, "baseline_assessment"))
+    binding, assessment = value.binding, value.assessment
+    if type(binding) is not PrescriptionBaselineBinding:
+        return tuple(errors + ["binding must be a PrescriptionBaselineBinding"])
+    for ref, label, kind in (
+        (binding.prescription_snapshot_ref, "snapshot_ref", "prescription-snapshot"),
+        (binding.decision_ref, "decision_ref", "decision"),
+        (binding.baseline_use_attestation_ref, "attestation_ref", "baseline-use-attestation"),
+    ):
+        errors.extend(validate_artifact_ref(ref, label))
+        if type(ref) is VersionedArtifactRef and ref.artifact_type != kind:
+            errors.append(f"{label} must have artifact_type {kind}")
+    errors.extend(validate_provenance(binding.provenance_ref, "binding.provenance_ref"))
+    if type(binding.subject_ref) is not str or not binding.subject_ref.strip():
+        errors.append("binding.subject_ref must be a non-empty string")
+    if not aware(binding.prescription_communicated_at):
+        errors.append("prescription_communicated_at must be timezone-aware")
+    if not aware(value.captured_at):
+        errors.append("captured_at must be timezone-aware")
+    if (aware(value.captured_at) and aware(binding.prescription_communicated_at) and
+            value.captured_at < binding.prescription_communicated_at):
+        errors.append("captured_at must not precede prescription communication")
+    if not validate_provenance(binding.provenance_ref):
+        if binding.provenance_ref.producer != binding.baseline_use_attestation_ref:
+            errors.append("binding provenance must identify the explicit baseline-use attestation")
+    if type(assessment) is RecoveryAssessment:
+        if assessment.contract_version != STABILITY_CONTRACT_VERSION:
+            errors.append("baseline stability contract version is unsupported")
+        if assessment.analyzer_ref != RECOVERY_ANALYZER_REF:
+            errors.append("baseline analyzer version is unsupported")
+        if not assessment.evidence_refs:
+            errors.append("baseline source evidence is required")
+        if assessment.subject_ref != binding.subject_ref:
+            errors.append("baseline ownership must agree with binding")
+        expected_ref = RecoveryAssessmentRef(
+            assessment.assessment_id, assessment.contract_version, assessment.analyzer_ref,
+            assessment.subject_ref, assessment.observed_at, assessment.assessed_at,
+        )
+        if binding.baseline_assessment_ref != expected_ref:
+            errors.append("baseline binding ref must equal its exact assessment")
+        if not validate_provenance(assessment.provenance_ref):
+            if assessment.provenance_ref.producer != RECOVERY_ANALYZER_ARTIFACT:
+                errors.append("assessment provenance must identify the pinned recovery analyzer")
+        if aware(binding.prescription_communicated_at):
+            for timestamp in (assessment.observed_at, assessment.assessed_at):
+                if aware(timestamp) and timestamp > binding.prescription_communicated_at:
+                    errors.append("baseline timestamps must not follow prescription communication")
+        try:
+            output = json.loads(value.analyzer_output_json,
+                                parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)))
+            if type(output) is not dict or type(output.get("level")) is not str:
+                raise ValueError("analyzer output must contain an explicit level")
+            level = output["level"]
+            if level == "UNKNOWN":
+                if (assessment.category is not None or
+                        assessment.category_missingness is not CategoryMissingness.NOT_ASSESSABLE or
+                        assessment.missing_fields != ("baseline_assessment.category",)):
+                    errors.append("UNKNOWN recovery must remain explicitly not assessable")
+            else:
+                if (assessment.category != RecoveryCategory(level) or
+                        assessment.category_missingness is not CategoryMissingness.NOT_MISSING or
+                        assessment.missing_fields):
+                    errors.append("baseline category must equal the explicit analyzer level")
+        except (ValueError, TypeError):
+            errors.append("baseline analyzer_output_json is invalid")
+    if snapshot is not None:
+        errors.extend(validate_prescription(snapshot))
+        if type(snapshot) is PrescriptionSnapshot:
+            if binding.prescription_snapshot_ref != VersionedArtifactRef(
+                    "prescription-snapshot", snapshot.prescription_snapshot_id,
+                    snapshot.contract_version):
+                errors.append("baseline must reference the exact persisted snapshot and version")
+            if binding.decision_ref.artifact_id != snapshot.decision_id:
+                errors.append("baseline decision must equal the persisted snapshot decision")
+            if binding.subject_ref != snapshot.subject_ref:
+                errors.append("baseline snapshot ownership must agree")
+            if binding.prescription_communicated_at != snapshot.communicated_at:
+                errors.append("baseline communication must equal the persisted snapshot timestamp")
+    return tuple(errors)
--- /dev/null
+++ backend/maintain_plan/runtime_recovery_baseline_capture.py
@@ -0,0 +1,104 @@
+"""Opt-in capture of an explicit recovery result used by a prescription.
+
+The caller declares the result already used, its source owner and timestamps.
+No new analysis, latest-record lookup, network call or numeric inference occurs.
+"""
+
+from __future__ import annotations
+
+import json
+
+from .general_stability_service import recovery_assessment_ref
+from .models import PrescriptionSnapshot
+from .recovery_baseline_models import (
+    PrescriptionRecoveryBaseline, RECOVERY_ANALYZER_REF, validate_recovery_baseline,
+)
+from .repository import MaintainPlanRepository
+from .stability_models import (
+    CategoryMissingness, PrescriptionBaselineBinding, RecoveryAssessment,
+    RecoveryCategory, STABILITY_CONTRACT_VERSION, VersionedArtifactRef,
+)
+from .stability_validators import validate_artifact_ref, validate_provenance
+from .validators import validate_prescription
+
+
+class RecoveryBaselineCaptureError(ValueError):
+    def __init__(self, errors, *, code="INPUT_INVALID"):
+        self.code = code
+        self.errors = tuple(errors)
+        super().__init__("; ".join(self.errors))
+
+
+def build_prescription_recovery_baseline(
+    *, snapshot, analyzer_result, source_subject_ref, observation_ref,
+    assessment_id, observed_at, assessed_at, captured_at, decision_ref,
+    baseline_use_attestation_ref, assessment_provenance_ref, binding_provenance_ref,
+) -> PrescriptionRecoveryBaseline:
+    """Freeze the exact analyzer output and explicit evidence used for a decision."""
+    if type(snapshot) is not PrescriptionSnapshot:
+        raise RecoveryBaselineCaptureError(("snapshot must be a PrescriptionSnapshot",))
+    errors = list(validate_prescription(snapshot))
+    errors.extend(validate_artifact_ref(observation_ref, "observation_ref"))
+    errors.extend(validate_provenance(assessment_provenance_ref, "assessment_provenance_ref"))
+    errors.extend(validate_provenance(binding_provenance_ref, "binding_provenance_ref"))
+    errors.extend(validate_artifact_ref(decision_ref, "decision_ref"))
+    errors.extend(validate_artifact_ref(baseline_use_attestation_ref, "baseline_use_attestation_ref"))
+    if source_subject_ref != snapshot.subject_ref:
+        errors.append("source subject must equal snapshot ownership")
+    if errors:
+        raise RecoveryBaselineCaptureError(errors)
+    if type(analyzer_result) is not dict:
+        raise RecoveryBaselineCaptureError(("analyzer_result must be an explicit dictionary",))
+    level = analyzer_result.get("level")
+    if level is None:
+        raise RecoveryBaselineCaptureError(("analyzer_result.level is required",), code="INPUT_MISSING")
+    if type(level) is not str or level not in ("LOW", "MODERATE", "HIGH", "CRITICAL", "UNKNOWN"):
+        raise RecoveryBaselineCaptureError(("analyzer_result.level is unsupported",))
+    if level == "UNKNOWN":
+        category, missingness = None, CategoryMissingness.NOT_ASSESSABLE
+        missing_fields = ("baseline_assessment.category",)
+    else:
+        category, missingness = RecoveryCategory(level), CategoryMissingness.NOT_MISSING
+        missing_fields = ()
+    try:
+        output_json = json.dumps(analyzer_result, allow_nan=False, ensure_ascii=False,
+                                 sort_keys=True, separators=(",", ":"))
+    except (TypeError, ValueError) as error:
+        raise RecoveryBaselineCaptureError(("analyzer_result must be finite JSON data",)) from error
+    assessment = RecoveryAssessment(
+        assessment_id=assessment_id, contract_version=STABILITY_CONTRACT_VERSION,
+        analyzer_ref=RECOVERY_ANALYZER_REF, subject_ref=snapshot.subject_ref,
+        observed_at=observed_at, assessed_at=assessed_at,
+        category=category, category_missingness=missingness,
+        evidence_refs=(observation_ref,), provenance_ref=assessment_provenance_ref,
+        missing_fields=missing_fields,
+    )
+    binding = PrescriptionBaselineBinding(
+        prescription_snapshot_ref=VersionedArtifactRef(
+            "prescription-snapshot", snapshot.prescription_snapshot_id, snapshot.contract_version),
+        decision_ref=decision_ref, subject_ref=snapshot.subject_ref,
+        prescription_communicated_at=snapshot.communicated_at,
+        baseline_assessment_ref=recovery_assessment_ref(assessment),
+        baseline_use_attestation_ref=baseline_use_attestation_ref,
+        provenance_ref=binding_provenance_ref,
+    )
+    value = PrescriptionRecoveryBaseline(binding, assessment, output_json, captured_at)
+    errors = validate_recovery_baseline(value, snapshot)
+    if errors:
+        raise RecoveryBaselineCaptureError(errors)
+    return value
+
+
+class RuntimeRecoveryBaselineCapture:
+    def __init__(self, repository_factory=MaintainPlanRepository):
+        self._repository_factory = repository_factory
+
+    def capture(self, *, enabled=False, database_path=None, **inputs):
+        """Validate before opening SQLite; disabled calls have no side effects."""
+        if enabled is not True:
+            return None
+        value = build_prescription_recovery_baseline(**inputs)
+        if database_path is None:
+            raise RecoveryBaselineCaptureError(("database_path is required",), code="INPUT_MISSING")
+        repository = self._repository_factory(database_path)
+        return repository.acquire_recovery_baseline(value)
--- backend/maintain_plan/repository.py
+++ backend/maintain_plan/repository.py
@@ -14,6 +14,9 @@
                      SourceConflictImpactEvaluation, SourceConflictResolutionEvent,
                      SourceConflictResolutionLog)
 from .stability_models import GeneralStabilityEvaluation
+from .recovery_baseline_models import (
+    PrescriptionRecoveryBaseline, validate_recovery_baseline,
+)
 from .archive_lock import locked_connect
 from .lifecycle_service import (project_feedback, project_source_conflict,
                                 structurally_equivalent, validate_feedback_payload,
@@ -209,6 +212,95 @@
         if len(rows) > 1:
             raise ValueError("multiple prescription snapshots already exist for decision_id")
         return self.get_prescription_snapshot(rows[0][0])
+
+    @staticmethod
+    def _baseline_retry_equivalent(
+        stored: PrescriptionRecoveryBaseline,
+        candidate: PrescriptionRecoveryBaseline,
+    ) -> bool:
+        from dataclasses import replace
+        return replace(stored, captured_at=candidate.captured_at) == candidate
+
+    def acquire_recovery_baseline(self, value: PrescriptionRecoveryBaseline) -> PrescriptionRecoveryBaseline:
+        """Atomically acquire one immutable baseline for one snapshot."""
+        self._require_valid(validate_recovery_baseline(value))
+        snapshot_ref = value.binding.prescription_snapshot_ref
+        if snapshot_ref.artifact_type != "prescription-snapshot":
+            raise ValueError("baseline must reference a prescription snapshot")
+        snapshot = self.get_prescription_snapshot(snapshot_ref.artifact_id)
+        if snapshot is None:
+            raise ValueError("baseline references a missing prescription snapshot")
+        self._require_valid(validate_recovery_baseline(value, snapshot))
+        with self._connect() as connection:
+            connection.row_factory = sqlite3.Row
+            connection.execute("BEGIN IMMEDIATE")
+            row = connection.execute(
+                "SELECT * FROM maintain_plan_recovery_baselines "
+                "WHERE prescription_snapshot_ref = ?",
+                (snapshot_ref.artifact_id,),
+            ).fetchone()
+            if row is not None:
+                stored = self._decode_recovery_baseline_row(row)
+                if self._baseline_retry_equivalent(stored, value):
+                    return stored
+                raise ValueError("recovery baseline already exists with different content")
+            connection.execute(
+                "INSERT INTO maintain_plan_recovery_baselines "
+                "(baseline_id, subject_ref, prescription_snapshot_ref, assessment_id, "
+                "contract_version, captured_at, payload_schema_version, payload_json) "
+                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
+                (value.baseline_id, value.binding.subject_ref, snapshot_ref.artifact_id,
+                 value.assessment.assessment_id, value.assessment.contract_version,
+                 value.captured_at.isoformat(), PAYLOAD_SCHEMA_VERSION,
+                 serialize_contract(value)),
+            )
+            return value
+
+    def get_recovery_baseline(self, identifier: str) -> PrescriptionRecoveryBaseline | None:
+        stored = self._get("maintain_plan_recovery_baselines", "baseline_id",
+                           identifier, PrescriptionRecoveryBaseline)
+        if stored is None:
+            return None
+        row, value = stored
+        self._validate_recovery_baseline_row(row, value)
+        return value
+
+    def list_recovery_baselines(self, subject_ref: str) -> tuple[PrescriptionRecoveryBaseline, ...]:
+        with self._connect() as connection:
+            connection.row_factory = sqlite3.Row
+            rows = connection.execute(
+                "SELECT * FROM maintain_plan_recovery_baselines "
+                "WHERE subject_ref = ? ORDER BY captured_at, baseline_id",
+                (subject_ref,),
+            ).fetchall()
+        values = []
+        for row in rows:
+            value = deserialize_contract(row["payload_json"], PrescriptionRecoveryBaseline)
+            self._validate_recovery_baseline_row(row, value)
+            values.append(value)
+        return tuple(values)
+
+    def _decode_recovery_baseline_row(self, row: sqlite3.Row) -> PrescriptionRecoveryBaseline:
+        if row["payload_schema_version"] != PAYLOAD_SCHEMA_VERSION:
+            raise ValueError("unsupported stored MAINTAIN_PLAN payload schema version")
+        return deserialize_contract(row["payload_json"], PrescriptionRecoveryBaseline)
+
+    def _validate_recovery_baseline_row(
+        self, row: sqlite3.Row, value: PrescriptionRecoveryBaseline,
+    ) -> None:
+        self._require_valid(validate_recovery_baseline(value))
+        snapshot_ref = value.binding.prescription_snapshot_ref
+        snapshot = self.get_prescription_snapshot(snapshot_ref.artifact_id)
+        self._require_valid(validate_recovery_baseline(value, snapshot))
+        if (
+            row["baseline_id"], row["subject_ref"], row["prescription_snapshot_ref"],
+            row["assessment_id"], row["contract_version"], row["captured_at"],
+        ) != (
+            value.baseline_id, value.binding.subject_ref, snapshot_ref.artifact_id,
+            value.assessment.assessment_id, value.assessment.contract_version,
+            value.captured_at.isoformat(),
+        ):
+            raise ValueError("stored recovery baseline metadata does not match payload")
 
     def create_actual_session(self, value: ActualSession) -> None:
         self._require_valid(validate_actual_session(value))
--- backend/maintain_plan/schema.py
+++ backend/maintain_plan/schema.py
@@ -12,7 +12,7 @@
 from .archive_lock import archive_lock
 
 
-SCHEMA_VERSION = 11
+SCHEMA_VERSION = 12
 
 
 @dataclass(frozen=True)
@@ -532,6 +532,37 @@
 
 MIGRATIONS = MIGRATIONS + (Migration(
     11, hashlib.sha256(_MIGRATION_11_SQL.encode("utf-8")).hexdigest(), _migration_11,
+),)
+
+
+_MIGRATION_12_SQL = """
+CREATE TABLE maintain_plan_recovery_baselines (
+    baseline_id TEXT PRIMARY KEY,
+    subject_ref TEXT NOT NULL,
+    prescription_snapshot_ref TEXT NOT NULL
+        REFERENCES maintain_plan_prescription_snapshots(prescription_snapshot_id),
+    assessment_id TEXT NOT NULL,
+    contract_version TEXT NOT NULL,
+    captured_at TEXT NOT NULL,
+    payload_schema_version TEXT NOT NULL,
+    payload_json TEXT NOT NULL,
+    UNIQUE (prescription_snapshot_ref)
+);
+CREATE INDEX idx_mp_recovery_baselines_subject
+    ON maintain_plan_recovery_baselines(subject_ref);
+CREATE INDEX idx_mp_recovery_baselines_assessment
+    ON maintain_plan_recovery_baselines(assessment_id);
+""".strip()
+
+
+def _migration_12(connection: sqlite3.Connection) -> None:
+    for statement in _MIGRATION_12_SQL.split(";"):
+        if statement.strip():
+            connection.execute(statement)
+
+
+MIGRATIONS = MIGRATIONS + (Migration(
+    12, hashlib.sha256(_MIGRATION_12_SQL.encode("utf-8")).hexdigest(), _migration_12,
 ),)
 
 
--- backend/maintain_plan/serialization.py
+++ backend/maintain_plan/serialization.py
@@ -8,12 +8,12 @@
 from enum import Enum
 from typing import Any
 
-from . import models, stability_models
+from . import models, recovery_baseline_models, stability_models
 
 
 PAYLOAD_SCHEMA_VERSION = "maintain-plan-json/1"
 
-_CONTRACT_MODULES = (models, stability_models)
+_CONTRACT_MODULES = (models, stability_models, recovery_baseline_models)
 _DATACLASSES = {
     name: value
     for module in _CONTRACT_MODULES
--- /dev/null
+++ docs/MAINTAIN_PLAN_RECOVERY_BASELINE_CONTRACT.md
@@ -0,0 +1,29 @@
+# MAINTAIN_PLAN recovery baseline contract
+
+Ultimo aggiornamento: 11 ottobre 2026
+
+`runtime_recovery_baseline_capture.py` conserva il recovery che il chiamante
+dichiara essere stato usato per comunicare una prescrizione. Non cerca il
+record più recente, non ricalcola l'analyzer e non converte numeri Garmin in
+categorie.
+
+La baseline è valida solo quando contiene:
+
+- lo stesso `subject_ref` della `PrescriptionSnapshot` persistita;
+- il riferimento esatto a snapshot, decisione e attestazione di uso;
+- `observed_at`, `assessed_at` e `captured_at` timezone-aware;
+- il riferimento alla sorgente recovery e la provenance dell'analyzer;
+- l'output JSON deterministico dell'analyzer, con `level` esplicito;
+- la versione dell'analyzer vincolata all'hash dei suoi sorgenti.
+
+`LOW`, `MODERATE`, `HIGH` e `CRITICAL` vengono accettati solo se presenti nel
+risultato esplicito dell'analyzer. `UNKNOWN` resta `NOT_ASSESSABLE` con il
+campo mancante canonico `baseline_assessment.category`.
+
+La persistenza è append-only e ammette una sola baseline per snapshot. Un retry
+semanticamente identico restituisce la riga già conservata; un retry con
+contenuto diverso fallisce senza sovrascrivere la baseline.
+
+La cattura è opt-in, non viene importata da `backend/main.py` e non attiva la
+shadow chain. La migration 12 crea solo la tabella isolata
+`maintain_plan_recovery_baselines`.
--- docs/BETA_0_4_HANDOFF.md
+++ docs/BETA_0_4_HANDOFF.md
@@ -1071,3 +1071,23 @@
 Il contratto dettagliato è in
 `docs/MAINTAIN_PLAN_RUNTIME_RECOVERY_ADAPTER_CONTRACT.md`. La chain, il flag
 runtime e la persistenza restano default-off.
+
+## Baseline recovery legata alla prescrizione — 11 ottobre 2026
+
+È stata aggiunta una cattura opt-in per la baseline recovery usata quando una
+prescrizione viene comunicata. La cattura riceve lo snapshot già persistito,
+l'output esplicito del `RecoveryAnalyzer`, il soggetto, la sorgente recovery,
+i timestamp e le provenance; non cerca automaticamente un record nell'archivio
+e non ricalcola la valutazione.
+
+La baseline è vincolata all'hash del sorgente dell'analyzer e al riferimento
+esatto di snapshot e decisione. Una baseline `UNKNOWN` resta non assessable;
+le categorie sono accettate solo dal livello esplicito dell'analyzer.
+
+La migration 12 aggiunge la tabella append-only
+`maintain_plan_recovery_baselines`. Un retry identico è idempotente; un retry
+con contenuto diverso viene rifiutato. La cattura non è importata dal runtime
+legacy e non attiva la shadow chain.
+
+Il contratto è in
+`docs/MAINTAIN_PLAN_RECOVERY_BASELINE_CONTRACT.md`.
--- /dev/null
+++ tests/maintain_plan/test_recovery_baseline_capture.py
@@ -0,0 +1,128 @@
+from dataclasses import replace
+from datetime import timedelta
+
+import pytest
+
+from backend.maintain_plan.recovery_baseline_models import (
+    RECOVERY_ANALYZER_ARTIFACT,
+    RECOVERY_ANALYZER_REF,
+    validate_recovery_baseline,
+)
+from backend.maintain_plan.repository import MaintainPlanRepository
+from backend.maintain_plan.runtime_recovery_baseline_capture import (
+    RecoveryBaselineCaptureError,
+    RuntimeRecoveryBaselineCapture,
+    build_prescription_recovery_baseline,
+)
+from backend.maintain_plan.stability_models import (
+    ProvenanceRef, VersionedArtifactRef,
+)
+from tests.maintain_plan.fixtures import NOW, RUN_PRESCRIPTION
+
+
+OBSERVATION = VersionedArtifactRef("recovery-observation", "garmin:baseline", "1")
+ATTESTATION = VersionedArtifactRef("baseline-use-attestation", "snapshot-1:baseline", "1")
+DECISION = VersionedArtifactRef("decision", "decision-1", "1")
+
+
+def baseline(*, snapshot=RUN_PRESCRIPTION, level="LOW", subject="athlete-1", captured=None):
+    return build_prescription_recovery_baseline(
+        snapshot=snapshot,
+        analyzer_result={
+            "level": level,
+            "state": "VERDE" if level == "LOW" else "",
+            "score": 72 if level == "LOW" else None,
+            "sleep_score": 80,
+            "reasons": (),
+        },
+        source_subject_ref=subject,
+        observation_ref=OBSERVATION,
+        assessment_id="assessment-1",
+        observed_at=NOW - timedelta(minutes=10),
+        assessed_at=NOW - timedelta(minutes=5),
+        captured_at=captured or NOW + timedelta(hours=1),
+        decision_ref=DECISION,
+        baseline_use_attestation_ref=ATTESTATION,
+        assessment_provenance_ref=ProvenanceRef(
+            RECOVERY_ANALYZER_ARTIFACT, "recovery-analysis", "garmin:baseline", "1"),
+        binding_provenance_ref=ProvenanceRef(
+            ATTESTATION, "baseline-capture", "snapshot-1", "1"),
+    )
+
+
+def test_baseline_is_pinned_to_snapshot_and_analyzer_version():
+    value = baseline()
+    assert validate_recovery_baseline(value, RUN_PRESCRIPTION) == ()
+    assert value.assessment.analyzer_ref == RECOVERY_ANALYZER_REF
+    assert value.binding.prescription_snapshot_ref.artifact_id == "snapshot-1"
+
+
+def test_unknown_analyzer_result_remains_not_assessable():
+    value = baseline(level="UNKNOWN")
+    assert value.assessment.category is None
+    assert value.assessment.missing_fields == ("baseline_assessment.category",)
+
+
+def test_capture_is_disabled_without_constructing_repository():
+    class FailRepository:
+        def __init__(self, *_):
+            raise AssertionError("repository must not be constructed")
+
+    assert RuntimeRecoveryBaselineCapture(FailRepository).capture(enabled=False) is None
+
+
+def test_capture_round_trip_retry_and_listing(tmp_path):
+    repository = MaintainPlanRepository(tmp_path / "baseline.db")
+    repository.create_prescription_snapshot(RUN_PRESCRIPTION)
+    value = baseline()
+    capture = RuntimeRecoveryBaselineCapture(lambda _: repository)
+    stored = capture.capture(enabled=True, database_path="ignored", **value_inputs(value))
+    assert repository.get_recovery_baseline(value.baseline_id) == stored
+    retry = capture.capture(
+        enabled=True, database_path="ignored",
+        **value_inputs(value, captured=NOW + timedelta(hours=2)),
+    )
+    assert retry == stored
+    assert repository.list_recovery_baselines("athlete-1") == (stored,)
+
+
+def test_capture_rejects_semantic_retry_for_same_snapshot(tmp_path):
+    repository = MaintainPlanRepository(tmp_path / "baseline.db")
+    repository.create_prescription_snapshot(RUN_PRESCRIPTION)
+    capture = RuntimeRecoveryBaselineCapture(lambda _: repository)
+    capture.capture(enabled=True, database_path="ignored", **value_inputs(baseline()))
+    with pytest.raises(ValueError, match="different content"):
+        capture.capture(enabled=True, database_path="ignored", **value_inputs(baseline(level="HIGH")))
+
+
+def test_capture_rejects_foreign_subject_and_missing_level():
+    with pytest.raises(RecoveryBaselineCaptureError, match="source subject"):
+        baseline(subject="other")
+    with pytest.raises(RecoveryBaselineCaptureError, match="level is required"):
+        build_prescription_recovery_baseline(
+            snapshot=RUN_PRESCRIPTION, analyzer_result={}, source_subject_ref="athlete-1",
+            observation_ref=OBSERVATION, assessment_id="assessment-1",
+            observed_at=NOW - timedelta(minutes=10), assessed_at=NOW - timedelta(minutes=5),
+            captured_at=NOW + timedelta(hours=1), decision_ref=DECISION,
+            baseline_use_attestation_ref=ATTESTATION,
+            assessment_provenance_ref=ProvenanceRef(RECOVERY_ANALYZER_ARTIFACT, "analysis", "x", "1"),
+            binding_provenance_ref=ProvenanceRef(ATTESTATION, "capture", "x", "1"),
+        )
+
+
+def value_inputs(value, *, captured=None):
+    analyzer = __import__("json").loads(value.analyzer_output_json)
+    return {
+        "snapshot": RUN_PRESCRIPTION,
+        "analyzer_result": analyzer,
+        "source_subject_ref": value.binding.subject_ref,
+        "observation_ref": value.assessment.evidence_refs[0],
+        "assessment_id": value.assessment.assessment_id,
+        "observed_at": value.assessment.observed_at,
+        "assessed_at": value.assessment.assessed_at,
+        "captured_at": captured or value.captured_at,
+        "decision_ref": value.binding.decision_ref,
+        "baseline_use_attestation_ref": value.binding.baseline_use_attestation_ref,
+        "assessment_provenance_ref": value.assessment.provenance_ref,
+        "binding_provenance_ref": value.binding.provenance_ref,
+    }
--- tests/maintain_plan/test_execution_evaluation_hardening.py
+++ tests/maintain_plan/test_execution_evaluation_hardening.py
@@ -230,6 +230,6 @@
     run_migrations(path)
     run_migrations(path)
     with sqlite3.connect(path) as connection:
-        assert connection.execute("SELECT count(*) FROM maintain_plan_schema_migrations").fetchone() == (11,)
+        assert connection.execute("SELECT count(*) FROM maintain_plan_schema_migrations").fetchone() == (12,)
         assert connection.execute("SELECT count(*) FROM maintain_plan_source_conflict_impact_evaluations").fetchone() == (0,)
         assert before
--- tests/maintain_plan/test_execution_evaluation_review26.py
+++ tests/maintain_plan/test_execution_evaluation_review26.py
@@ -112,7 +112,7 @@
     run_migrations(path); run_migrations(path)
     with sqlite3.connect(path) as connection:
         assert connection.execute("SELECT * FROM maintain_plan_source_conflict_impact_evaluations").fetchall() == before
-        assert connection.execute("SELECT count(*) FROM maintain_plan_schema_migrations").fetchone() == (11,)
+        assert connection.execute("SELECT count(*) FROM maintain_plan_schema_migrations").fetchone() == (12,)
         info = connection.execute("PRAGMA table_info(maintain_plan_source_conflict_impact_evaluations)").fetchall()
         assert next(row for row in info if row[1] == "prescription_mapping_ref")[3] == 0
-    assert SCHEMA_VERSION == 11
+    assert SCHEMA_VERSION == 12
--- tests/maintain_plan/test_persistence.py
+++ tests/maintain_plan/test_persistence.py
@@ -27,6 +27,7 @@
     "maintain_plan_matching_results",
     "maintain_plan_execution_evaluations",
     "maintain_plan_stability_evaluations",
+    "maintain_plan_recovery_baselines",
 }
 
 
@@ -48,7 +49,7 @@
         versions = connection.execute(
             "SELECT version, checksum FROM maintain_plan_schema_migrations"
         ).fetchall()
-        assert [item[0] for item in versions] == list(range(1, 12))
+        assert [item[0] for item in versions] == list(range(1, 13))
         assert all(len(item[1]) == 64 for item in versions)
         assert {row[1:3] for row in connection.execute(
             "PRAGMA index_list(maintain_plan_prescription_mappings)"
@@ -68,7 +69,7 @@
         assert before == after
         assert connection.execute(
             "SELECT count(*) FROM maintain_plan_schema_migrations"
-                ).fetchone() == (11,)
+                ).fetchone() == (12,)
 
 
 def _seed_confirmation_parents(connection):
@@ -107,7 +108,7 @@
     with sqlite3.connect(path) as connection:
         assert connection.execute("SELECT * FROM maintain_plan_confirmations").fetchall() == before
         assert [row[0] for row in connection.execute(
-            "SELECT version FROM maintain_plan_schema_migrations ORDER BY version")] == list(range(1, 12))
+            "SELECT version FROM maintain_plan_schema_migrations ORDER BY version")] == list(range(1, 13))
         assert {
             "maintain_plan_confirmations_validate_insert",
             "maintain_plan_confirmations_validate_update",
@@ -178,7 +179,7 @@
         assert connection.execute(
             "SELECT count(*) FROM sqlite_master WHERE type='trigger' AND name LIKE 'maintain_plan_confirmations_validate_%'"
         ).fetchone() == (0,)
-    assert SCHEMA_VERSION == 11
+    assert SCHEMA_VERSION == 12
 
 
 def test_migration_preserves_legacy_schema_and_record_exactly(tmp_path):
@@ -272,7 +273,7 @@
         ).fetchall() == mappings
         assert connection.execute(
             "SELECT version FROM maintain_plan_schema_migrations ORDER BY version"
-        ).fetchall() == [(version,) for version in range(1, 12)]
+        ).fetchall() == [(version,) for version in range(1, 13)]
         assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
         assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
 
--- tests/maintain_plan/test_subject_ownership.py
+++ tests/maintain_plan/test_subject_ownership.py
@@ -31,8 +31,8 @@
 
 
 def test_v7_is_exactly_append_only_after_v1_through_v6(tmp_path):
-    assert SCHEMA_VERSION == 11
-    assert [migration.version for migration in MIGRATIONS] == list(range(1, 12))
+    assert SCHEMA_VERSION == 12
+    assert [migration.version for migration in MIGRATIONS] == list(range(1, 13))
     path = tmp_path / "upgrade.db"
     run_migrations(path, MIGRATIONS[:6])
     with sqlite3.connect(path) as connection:
@@ -45,7 +45,7 @@
             "SELECT version, checksum FROM maintain_plan_schema_migrations ORDER BY version"
         ).fetchall()
         assert before == after[:6]
-        assert [row[0] for row in after] == list(range(1, 12))
+        assert [row[0] for row in after] == list(range(1, 13))
         assert "subject_ref" in {row[1] for row in connection.execute(
             "PRAGMA table_info(maintain_plan_prescription_snapshots)")}
         assert "subject_ref" in {row[1] for row in connection.execute(
PATCH_FILE

patch --dry-run --forward --batch -p0 < .ironcoach_runtime_recovery_baseline.patch
patch --forward --batch -p0 < .ironcoach_runtime_recovery_baseline.patch
rm -f .ironcoach_runtime_recovery_baseline.patch

python -m compileall -q backend tests
git diff --check
python -m pytest -q

git add -- "${targets[@]}"
git diff --cached --check
git commit -m 'feat: persist prescription recovery baseline'
committed=1
git push origin feature/beta-0.4-decision-memory

echo '=== VERIFICA FINALE ==='
git status --short --branch
git log -1 --oneline
echo '=== FINE REPORT ==='
rm -rf "$backup"
IRONCOACH_RUNTIME_RECOVERY_BASELINE
