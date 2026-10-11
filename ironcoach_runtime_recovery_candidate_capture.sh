#!/usr/bin/env bash
cd /workspaces/IronCoach
bash <<'IRONCOACH_RUNTIME_RECOVERY_CANDIDATE_CAPTURE'
set -Eeuo pipefail

report="ironcoach_runtime_recovery_candidate_capture_result.txt"
exec > >(tee "$report") 2>&1

echo '=== PERSISTENZA CANDIDATE SET RECOVERY ==='
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
  backend/maintain_plan/stability_validators.py
  backend/maintain_plan/schema.py
  backend/maintain_plan/repository.py
  backend/maintain_plan/runtime_recovery_candidate_capture.py
  tests/maintain_plan/test_recovery_candidate_capture.py
  tests/maintain_plan/test_persistence.py
  tests/maintain_plan/test_subject_ownership.py
  tests/maintain_plan/test_execution_evaluation_hardening.py
  tests/maintain_plan/test_execution_evaluation_review26.py
  docs/MAINTAIN_PLAN_RECOVERY_CANDIDATE_SET_CONTRACT.md
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
  rm -f .ironcoach_runtime_recovery_candidate_capture.patch
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

cat > .ironcoach_runtime_recovery_candidate_capture.patch <<'PATCH_FILE'
--- backend/maintain_plan/stability_validators.py
+++ backend/maintain_plan/stability_validators.py
@@ -175,6 +175,44 @@
         for field in ("analyzer_id", "analyzer_version", "assessment_schema_version"):
             _text(getattr(value.analyzer_ref, field), f"{name}.analyzer_ref.{field}",
                   errors, nullable=True)
+    return tuple(errors)
+
+
+def validate_recovery_candidate_set(
+    value: object, name: str = "candidate_set",
+) -> tuple[str, ...]:
+    """Validate a candidate set independently of a complete stability input."""
+    errors: list[str] = []
+    if type(value) is not RecoveryAssessmentCandidateSet:
+        return (f"{name} must be a RecoveryAssessmentCandidateSet",)
+    errors.extend(validate_artifact_ref(value.actual_session_ref,
+                                        f"{name}.actual_session_ref"))
+    errors.extend(validate_provenance(value.provenance_ref, f"{name}.provenance_ref"))
+    _text(value.subject_ref, f"{name}.subject_ref", errors)
+    _text(value.contract_version, f"{name}.contract_version", errors)
+    if value.contract_version != STABILITY_CONTRACT_VERSION:
+        errors.append(f"{name}.contract_version is unsupported")
+    _datetime(value.captured_at, f"{name}.captured_at", errors)
+    _datetime(value.evaluated_cutoff_at, f"{name}.evaluated_cutoff_at", errors)
+    if (aware(value.captured_at) and aware(value.evaluated_cutoff_at) and
+            value.captured_at > value.evaluated_cutoff_at):
+        errors.append(f"{name}.captured_at must not follow evaluated_cutoff_at")
+    if type(value.candidates) is not tuple:
+        errors.append(f"{name}.candidates must be a tuple")
+        return tuple(errors)
+    for candidate in value.candidates:
+        errors.extend(validate_assessment(candidate, f"{name}.candidates[]"))
+        if type(candidate) is not RecoveryAssessment:
+            continue
+        if (aware(candidate.assessed_at) and aware(value.captured_at) and
+                candidate.assessed_at > value.captured_at):
+            errors.append(f"{name}.candidate assessed_at must not follow captured_at")
+        if (aware(candidate.observed_at) and aware(value.evaluated_cutoff_at) and
+                candidate.observed_at > value.evaluated_cutoff_at):
+            errors.append(f"{name}.candidate observed_at must not follow evaluated_cutoff_at")
+        if (aware(candidate.assessed_at) and aware(value.evaluated_cutoff_at) and
+                candidate.assessed_at > value.evaluated_cutoff_at):
+            errors.append(f"{name}.candidate assessed_at must not follow evaluated_cutoff_at")
     return tuple(errors)
 
 
--- backend/maintain_plan/schema.py
+++ backend/maintain_plan/schema.py
@@ -12,7 +12,7 @@
 from .archive_lock import archive_lock
 
 
-SCHEMA_VERSION = 12
+SCHEMA_VERSION = 13
 
 
 @dataclass(frozen=True)
@@ -563,6 +563,38 @@
 
 MIGRATIONS = MIGRATIONS + (Migration(
     12, hashlib.sha256(_MIGRATION_12_SQL.encode("utf-8")).hexdigest(), _migration_12,
+),)
+
+
+_MIGRATION_13_SQL = """
+CREATE TABLE maintain_plan_recovery_candidate_sets (
+    candidate_set_id TEXT PRIMARY KEY,
+    subject_ref TEXT NOT NULL,
+    actual_session_ref TEXT NOT NULL
+        REFERENCES maintain_plan_actual_sessions(session_id),
+    contract_version TEXT NOT NULL,
+    captured_at TEXT NOT NULL,
+    evaluated_cutoff_at TEXT NOT NULL,
+    payload_schema_version TEXT NOT NULL,
+    payload_json TEXT NOT NULL
+);
+CREATE INDEX idx_mp_recovery_candidate_sets_subject
+    ON maintain_plan_recovery_candidate_sets(subject_ref);
+CREATE INDEX idx_mp_recovery_candidate_sets_session
+    ON maintain_plan_recovery_candidate_sets(actual_session_ref);
+CREATE INDEX idx_mp_recovery_candidate_sets_cutoff
+    ON maintain_plan_recovery_candidate_sets(evaluated_cutoff_at);
+""".strip()
+
+
+def _migration_13(connection: sqlite3.Connection) -> None:
+    for statement in _MIGRATION_13_SQL.split(";"):
+        if statement.strip():
+            connection.execute(statement)
+
+
+MIGRATIONS = MIGRATIONS + (Migration(
+    13, hashlib.sha256(_MIGRATION_13_SQL.encode("utf-8")).hexdigest(), _migration_13,
 ),)
 
 
--- backend/maintain_plan/repository.py
+++ backend/maintain_plan/repository.py
@@ -13,7 +13,7 @@
                      PrescriptionSnapshot, SourceConflictProjection,
                      SourceConflictImpactEvaluation, SourceConflictResolutionEvent,
                      SourceConflictResolutionLog)
-from .stability_models import GeneralStabilityEvaluation
+from .stability_models import GeneralStabilityEvaluation, RecoveryAssessmentCandidateSet
 from .recovery_baseline_models import (
     PrescriptionRecoveryBaseline, validate_recovery_baseline,
 )
@@ -29,7 +29,9 @@
                          validate_confirmation, validate_mapping, validate_matching_result,
                          validate_mapping_ownership, validate_prescription,
                          validate_source_conflict_impact)
-from .stability_validators import validate_general_stability_evaluation
+from .stability_validators import (
+    validate_general_stability_evaluation, validate_recovery_candidate_set,
+)
 
 if TYPE_CHECKING:
     from .runtime_matching_decision import MatchingDecision
@@ -301,6 +303,107 @@
             value.captured_at.isoformat(),
         ):
             raise ValueError("stored recovery baseline metadata does not match payload")
+
+    def acquire_recovery_candidate_set(
+        self, candidate_set_id: str, value: RecoveryAssessmentCandidateSet,
+    ) -> RecoveryAssessmentCandidateSet:
+        """Atomically acquire one immutable candidate set for an actual session."""
+        if type(candidate_set_id) is not str or not candidate_set_id.strip():
+            raise ValueError("candidate_set_id must be a non-empty string")
+        self._require_valid(validate_recovery_candidate_set(value))
+        session_ref = value.actual_session_ref
+        if session_ref.artifact_type != "actual-session":
+            raise ValueError("candidate set must reference an actual session")
+        session = self.get_actual_session(session_ref.artifact_id)
+        if session is None:
+            raise ValueError("candidate set references a missing actual session")
+        if session.subject_ref != value.subject_ref:
+            raise ValueError("candidate set session ownership is incoherent")
+        stored_row = None
+        stored = None
+        with self._connect() as connection:
+            connection.row_factory = sqlite3.Row
+            connection.execute("BEGIN IMMEDIATE")
+            stored_row = connection.execute(
+                "SELECT * FROM maintain_plan_recovery_candidate_sets "
+                "WHERE candidate_set_id = ?",
+                (candidate_set_id,),
+            ).fetchone()
+            if stored_row is None:
+                connection.execute(
+                    "INSERT INTO maintain_plan_recovery_candidate_sets "
+                    "(candidate_set_id, subject_ref, actual_session_ref, contract_version, "
+                    "captured_at, evaluated_cutoff_at, payload_schema_version, payload_json) "
+                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
+                    (candidate_set_id, value.subject_ref, session_ref.artifact_id,
+                     value.contract_version, value.captured_at.isoformat(),
+                     value.evaluated_cutoff_at.isoformat(), PAYLOAD_SCHEMA_VERSION,
+                     serialize_contract(value)),
+                )
+                return value
+            stored = self._decode_recovery_candidate_set_row(stored_row)
+        # Validate the existing row after releasing the write transaction.  The
+        # validator follows the foreign key to the immutable session row.
+        self._validate_recovery_candidate_set_row(stored_row, candidate_set_id, stored)
+        if stored == value:
+            return stored
+        raise ValueError("recovery candidate set already exists with different content")
+
+    def get_recovery_candidate_set(
+        self, candidate_set_id: str,
+    ) -> RecoveryAssessmentCandidateSet | None:
+        stored = self._get("maintain_plan_recovery_candidate_sets", "candidate_set_id",
+                           candidate_set_id, RecoveryAssessmentCandidateSet)
+        if stored is None:
+            return None
+        row, value = stored
+        self._validate_recovery_candidate_set_row(row, candidate_set_id, value)
+        return value
+
+    def list_recovery_candidate_sets(
+        self, subject_ref: str,
+    ) -> tuple[RecoveryAssessmentCandidateSet, ...]:
+        with self._connect() as connection:
+            connection.row_factory = sqlite3.Row
+            rows = connection.execute(
+                "SELECT * FROM maintain_plan_recovery_candidate_sets "
+                "WHERE subject_ref = ? ORDER BY evaluated_cutoff_at, captured_at, candidate_set_id",
+                (subject_ref,),
+            ).fetchall()
+        values = []
+        for row in rows:
+            value = self._decode_recovery_candidate_set_row(row)
+            self._validate_recovery_candidate_set_row(row, row["candidate_set_id"], value)
+            values.append(value)
+        return tuple(values)
+
+    def _decode_recovery_candidate_set_row(
+        self, row: sqlite3.Row,
+    ) -> RecoveryAssessmentCandidateSet:
+        if row["payload_schema_version"] != PAYLOAD_SCHEMA_VERSION:
+            raise ValueError("unsupported stored MAINTAIN_PLAN payload schema version")
+        return deserialize_contract(row["payload_json"], RecoveryAssessmentCandidateSet)
+
+    def _validate_recovery_candidate_set_row(
+        self, row: sqlite3.Row, candidate_set_id: str,
+        value: RecoveryAssessmentCandidateSet,
+    ) -> None:
+        self._require_valid(validate_recovery_candidate_set(value))
+        session_ref = value.actual_session_ref
+        if session_ref.artifact_type != "actual-session":
+            raise ValueError("stored recovery candidate set has invalid session ref")
+        session = self.get_actual_session(session_ref.artifact_id)
+        if session is None or session.subject_ref != value.subject_ref:
+            raise ValueError("stored recovery candidate set has unresolved ownership")
+        if (
+            row["candidate_set_id"], row["subject_ref"], row["actual_session_ref"],
+            row["contract_version"], row["captured_at"], row["evaluated_cutoff_at"],
+        ) != (
+            candidate_set_id, value.subject_ref, session_ref.artifact_id,
+            value.contract_version, value.captured_at.isoformat(),
+            value.evaluated_cutoff_at.isoformat(),
+        ):
+            raise ValueError("stored recovery candidate set metadata does not match payload")
 
     def create_actual_session(self, value: ActualSession) -> None:
         self._require_valid(validate_actual_session(value))
--- /dev/null
+++ backend/maintain_plan/runtime_recovery_candidate_capture.py
@@ -0,0 +1,73 @@
+"""Opt-in capture and persistence of explicit recovery candidate sets."""
+
+from __future__ import annotations
+
+from .repository import MaintainPlanRepository
+from .runtime_recovery_adapter import (
+    RuntimeRecoveryAdapterError,
+    build_recovery_candidate_set,
+)
+from .stability_models import RecoveryAssessmentCandidateSet
+from .stability_validators import validate_recovery_candidate_set
+
+
+class RecoveryCandidateSetCaptureError(ValueError):
+    def __init__(self, errors, *, code="INPUT_INVALID"):
+        self.code = code
+        self.errors = tuple(errors)
+        super().__init__("; ".join(self.errors))
+
+
+def build_recovery_candidate_set_capture(
+    *,
+    records,
+    actual_session_ref,
+    subject_ref,
+    captured_at,
+    evaluated_cutoff_at,
+    provenance_ref,
+    analyzer_ref=None,
+) -> RecoveryAssessmentCandidateSet:
+    """Build one candidate set from caller-scoped records without source lookup."""
+    try:
+        value = build_recovery_candidate_set(
+            records,
+            actual_session_ref=actual_session_ref,
+            subject_ref=subject_ref,
+            captured_at=captured_at,
+            evaluated_cutoff_at=evaluated_cutoff_at,
+            provenance_ref=provenance_ref,
+            analyzer_ref=analyzer_ref,
+        )
+    except RuntimeRecoveryAdapterError as error:
+        raise RecoveryCandidateSetCaptureError(error.errors, code=error.code) from error
+    except ValueError as error:
+        if isinstance(error, RecoveryCandidateSetCaptureError):
+            raise
+        raise RecoveryCandidateSetCaptureError((str(error),)) from error
+    errors = validate_recovery_candidate_set(value)
+    if errors:
+        raise RecoveryCandidateSetCaptureError(errors)
+    return value
+
+
+class RuntimeRecoveryCandidateSetCapture:
+    def __init__(self, repository_factory=MaintainPlanRepository):
+        self._repository_factory = repository_factory
+
+    def capture(self, *, candidate_set_id, enabled=False, database_path=None, **inputs):
+        """Validate before opening SQLite; disabled calls have no side effects."""
+        if enabled is not True:
+            return None
+        if type(candidate_set_id) is not str or not candidate_set_id.strip():
+            raise RecoveryCandidateSetCaptureError(
+                ("candidate_set_id must be a non-empty string",),
+                code="INPUT_MISSING",
+            )
+        value = build_recovery_candidate_set_capture(**inputs)
+        if database_path is None:
+            raise RecoveryCandidateSetCaptureError(
+                ("database_path is required",), code="INPUT_MISSING",
+            )
+        repository = self._repository_factory(database_path)
+        return repository.acquire_recovery_candidate_set(candidate_set_id, value)
--- /dev/null
+++ tests/maintain_plan/test_recovery_candidate_capture.py
@@ -0,0 +1,129 @@
+from datetime import timedelta
+
+import pytest
+
+from backend.maintain_plan.repository import MaintainPlanRepository
+from backend.maintain_plan.runtime_recovery_candidate_capture import (
+    RecoveryCandidateSetCaptureError,
+    RuntimeRecoveryCandidateSetCapture,
+    build_recovery_candidate_set_capture,
+)
+from backend.maintain_plan.stability_models import (
+    ProvenanceRef, VersionedArtifactRef,
+)
+from backend.maintain_plan.stability_validators import validate_recovery_candidate_set
+from tests.maintain_plan.fixtures import NOW, RUN_SESSION
+
+
+SESSION_REF = VersionedArtifactRef("actual-session", "session-1", "1")
+PROVENANCE = ProvenanceRef(
+    VersionedArtifactRef("candidate-set-capture", "capture-1", "1"),
+    "candidate-set-capture", "capture-1", "1",
+)
+
+
+def _record(**overrides):
+    value = {
+        "source": "garmin",
+        "source_id": "garmin-recovery:2026-01-01-follow-up",
+        "date": "2026-01-01",
+        "observed_at": "2026-01-01T10:00:00Z",
+        "assessed_at": "2026-01-01T10:05:00Z",
+        "category": "LOW",
+    }
+    value.update(overrides)
+    return value
+
+
+def _inputs(**overrides):
+    value = {
+        "records": [_record()],
+        "actual_session_ref": SESSION_REF,
+        "subject_ref": "athlete-1",
+        "captured_at": NOW + timedelta(hours=6),
+        "evaluated_cutoff_at": NOW + timedelta(hours=8),
+        "provenance_ref": PROVENANCE,
+    }
+    value.update(overrides)
+    return value
+
+
+def test_candidate_set_capture_is_explicit_and_valid():
+    value = build_recovery_candidate_set_capture(**_inputs())
+    assert validate_recovery_candidate_set(value) == ()
+    assert value.subject_ref == "athlete-1"
+    assert value.actual_session_ref == SESSION_REF
+    assert value.candidates[0].category.value == "LOW"
+
+
+def test_capture_is_disabled_without_constructing_repository():
+    class FailRepository:
+        def __init__(self, *_):
+            raise AssertionError("repository must not be constructed")
+
+    capture = RuntimeRecoveryCandidateSetCapture(FailRepository)
+    assert capture.capture(candidate_set_id="set-1", enabled=False) is None
+
+
+def test_candidate_set_round_trip_retry_and_listing(tmp_path):
+    repository = MaintainPlanRepository(tmp_path / "candidate-set.db")
+    repository.create_actual_session(RUN_SESSION)
+    capture = RuntimeRecoveryCandidateSetCapture(lambda _: repository)
+    value = capture.capture(
+        candidate_set_id="candidate-set-1", enabled=True, database_path="ignored",
+        **_inputs(),
+    )
+    assert repository.get_recovery_candidate_set("candidate-set-1") == value
+    assert repository.list_recovery_candidate_sets("athlete-1") == (value,)
+    retry = capture.capture(
+        candidate_set_id="candidate-set-1", enabled=True, database_path="ignored",
+        **_inputs(),
+    )
+    assert retry == value
+
+
+def test_candidate_set_semantic_retry_conflict_is_rejected(tmp_path):
+    repository = MaintainPlanRepository(tmp_path / "candidate-set.db")
+    repository.create_actual_session(RUN_SESSION)
+    capture = RuntimeRecoveryCandidateSetCapture(lambda _: repository)
+    capture.capture(
+        candidate_set_id="candidate-set-1", enabled=True, database_path="ignored",
+        **_inputs(),
+    )
+    with pytest.raises(ValueError, match="different content"):
+        capture.capture(
+            candidate_set_id="candidate-set-1", enabled=True, database_path="ignored",
+            **_inputs(records=[_record(category="HIGH")]),
+        )
+
+
+def test_candidate_set_rejects_missing_session_and_foreign_subject(tmp_path):
+    repository = MaintainPlanRepository(tmp_path / "candidate-set.db")
+    capture = RuntimeRecoveryCandidateSetCapture(lambda _: repository)
+    with pytest.raises(ValueError, match="missing actual session"):
+        capture.capture(
+            candidate_set_id="candidate-set-1", enabled=True, database_path="ignored",
+            **_inputs(),
+        )
+    repository.create_actual_session(RUN_SESSION)
+    with pytest.raises(ValueError, match="ownership"):
+        capture.capture(
+            candidate_set_id="candidate-set-foreign", enabled=True, database_path="ignored",
+            **_inputs(subject_ref="other-athlete"),
+        )
+
+
+def test_candidate_set_capture_rejects_bad_identity_and_timestamps():
+    with pytest.raises(RecoveryCandidateSetCaptureError, match="candidate_set_id"):
+        RuntimeRecoveryCandidateSetCapture().capture(
+            candidate_set_id="", enabled=True, database_path="ignored", **_inputs(),
+        )
+    with pytest.raises(RecoveryCandidateSetCaptureError, match="must not follow"):
+        build_recovery_candidate_set_capture(
+            **_inputs(captured_at=NOW + timedelta(hours=9)),
+        )
+    with pytest.raises(RecoveryCandidateSetCaptureError) as error:
+        build_recovery_candidate_set_capture(
+            **_inputs(records=[_record(observed_at=None)]),
+        )
+    assert error.value.code == "INPUT_MISSING"
--- tests/maintain_plan/test_persistence.py
+++ tests/maintain_plan/test_persistence.py
@@ -28,6 +28,7 @@
     "maintain_plan_execution_evaluations",
     "maintain_plan_stability_evaluations",
     "maintain_plan_recovery_baselines",
+    "maintain_plan_recovery_candidate_sets",
 }
 
 
@@ -49,7 +50,7 @@
         versions = connection.execute(
             "SELECT version, checksum FROM maintain_plan_schema_migrations"
         ).fetchall()
-        assert [item[0] for item in versions] == list(range(1, 13))
+        assert [item[0] for item in versions] == list(range(1, 14))
         assert all(len(item[1]) == 64 for item in versions)
         assert {row[1:3] for row in connection.execute(
             "PRAGMA index_list(maintain_plan_prescription_mappings)"
@@ -69,7 +70,7 @@
         assert before == after
         assert connection.execute(
             "SELECT count(*) FROM maintain_plan_schema_migrations"
-                ).fetchone() == (12,)
+                ).fetchone() == (13,)
 
 
 def _seed_confirmation_parents(connection):
@@ -108,7 +109,7 @@
     with sqlite3.connect(path) as connection:
         assert connection.execute("SELECT * FROM maintain_plan_confirmations").fetchall() == before
         assert [row[0] for row in connection.execute(
-            "SELECT version FROM maintain_plan_schema_migrations ORDER BY version")] == list(range(1, 13))
+            "SELECT version FROM maintain_plan_schema_migrations ORDER BY version")] == list(range(1, 14))
         assert {
             "maintain_plan_confirmations_validate_insert",
             "maintain_plan_confirmations_validate_update",
@@ -179,7 +180,7 @@
         assert connection.execute(
             "SELECT count(*) FROM sqlite_master WHERE type='trigger' AND name LIKE 'maintain_plan_confirmations_validate_%'"
         ).fetchone() == (0,)
-    assert SCHEMA_VERSION == 12
+    assert SCHEMA_VERSION == 13
 
 
 def test_migration_preserves_legacy_schema_and_record_exactly(tmp_path):
@@ -273,7 +274,7 @@
         ).fetchall() == mappings
         assert connection.execute(
             "SELECT version FROM maintain_plan_schema_migrations ORDER BY version"
-        ).fetchall() == [(version,) for version in range(1, 13)]
+        ).fetchall() == [(version,) for version in range(1, 14)]
         assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
         assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
 
--- tests/maintain_plan/test_subject_ownership.py
+++ tests/maintain_plan/test_subject_ownership.py
@@ -31,8 +31,8 @@
 
 
 def test_v7_is_exactly_append_only_after_v1_through_v6(tmp_path):
-    assert SCHEMA_VERSION == 12
-    assert [migration.version for migration in MIGRATIONS] == list(range(1, 13))
+    assert SCHEMA_VERSION == 13
+    assert [migration.version for migration in MIGRATIONS] == list(range(1, 14))
     path = tmp_path / "upgrade.db"
     run_migrations(path, MIGRATIONS[:6])
     with sqlite3.connect(path) as connection:
@@ -45,7 +45,7 @@
             "SELECT version, checksum FROM maintain_plan_schema_migrations ORDER BY version"
         ).fetchall()
         assert before == after[:6]
-        assert [row[0] for row in after] == list(range(1, 13))
+        assert [row[0] for row in after] == list(range(1, 14))
         assert "subject_ref" in {row[1] for row in connection.execute(
             "PRAGMA table_info(maintain_plan_prescription_snapshots)")}
         assert "subject_ref" in {row[1] for row in connection.execute(
--- tests/maintain_plan/test_execution_evaluation_hardening.py
+++ tests/maintain_plan/test_execution_evaluation_hardening.py
@@ -230,6 +230,6 @@
     run_migrations(path)
     run_migrations(path)
     with sqlite3.connect(path) as connection:
-        assert connection.execute("SELECT count(*) FROM maintain_plan_schema_migrations").fetchone() == (12,)
+        assert connection.execute("SELECT count(*) FROM maintain_plan_schema_migrations").fetchone() == (13,)
         assert connection.execute("SELECT count(*) FROM maintain_plan_source_conflict_impact_evaluations").fetchone() == (0,)
         assert before
--- tests/maintain_plan/test_execution_evaluation_review26.py
+++ tests/maintain_plan/test_execution_evaluation_review26.py
@@ -112,7 +112,7 @@
     run_migrations(path); run_migrations(path)
     with sqlite3.connect(path) as connection:
         assert connection.execute("SELECT * FROM maintain_plan_source_conflict_impact_evaluations").fetchall() == before
-        assert connection.execute("SELECT count(*) FROM maintain_plan_schema_migrations").fetchone() == (12,)
+        assert connection.execute("SELECT count(*) FROM maintain_plan_schema_migrations").fetchone() == (13,)
         info = connection.execute("PRAGMA table_info(maintain_plan_source_conflict_impact_evaluations)").fetchall()
         assert next(row for row in info if row[1] == "prescription_mapping_ref")[3] == 0
-    assert SCHEMA_VERSION == 12
+    assert SCHEMA_VERSION == 13
--- /dev/null
+++ docs/MAINTAIN_PLAN_RECOVERY_CANDIDATE_SET_CONTRACT.md
@@ -0,0 +1,27 @@
+# MAINTAIN_PLAN recovery candidate set contract
+
+`runtime_recovery_candidate_capture.py` conserva il candidate set recovery
+costruito dal chiamante per una sessione reale. Riceve solo record già scoping,
+la loro provenance, la sessione, il soggetto e il cutoff temporale. Non legge
+l'archivio Garmin, non seleziona il follow-up e non deduce categorie da numeri.
+
+## Identità e validazione
+
+Il chiamante fornisce un `candidate_set_id` stabile. Il payload deve contenere
+un `VersionedArtifactRef` di tipo `actual-session`, un soggetto non vuoto,
+timestamp timezone-aware, cutoff non precedente a `captured_at`, provenance
+valida e assessment con timestamp entro il cutoff. La categoria resta valida
+solo quando è esplicita; dati mancanti restano `CategoryMissingness.MISSING`.
+
+La persistenza richiede che la sessione esista già e che il suo `subject_ref`
+coincida con quello del candidate set. La migration 13 aggiunge la tabella
+`maintain_plan_recovery_candidate_sets`, con metadata verificabili e payload
+serializzato. Un retry con lo stesso ID e contenuto identico restituisce il
+payload già salvato; un contenuto diverso viene rifiutato senza sovrascrittura.
+
+## Attivazione
+
+`RuntimeRecoveryCandidateSetCapture` è default-off. Quando è abilitato, valida
+prima il candidate set e apre SQLite solo per l'acquisizione append-only. Il
+bridge stability può poi ricevere il candidate set insieme alla baseline
+persistita; la valutazione e la selezione del follow-up restano pure.
--- docs/BETA_0_4_HANDOFF.md
+++ docs/BETA_0_4_HANDOFF.md
@@ -1105,3 +1105,19 @@
 lettura SQLite o wiring del runtime legacy. La proiezione reported-problems
 resta esplicita e assente nel chiamante corrente; la valutazione conserva
 `INSUFFICIENT_DATA` finché quella dimensione non viene fornita.
+
+## Persistenza candidate set recovery — 11 ottobre 2026
+
+È stata aggiunta la cattura opt-in di un `RecoveryAssessmentCandidateSet` da
+record recovery già espliciti. Il chiamante dichiara `candidate_set_id`,
+soggetto, sessione reale, cutoff, provenance e record; la cattura non esegue
+lookup nell'archivio e non seleziona automaticamente il follow-up.
+
+La migration 13 aggiunge `maintain_plan_recovery_candidate_sets`. La riga è
+append-only: il retry con stesso ID e stesso payload è idempotente, mentre una
+divergenza semantica viene rifiutata. La sessione deve essere già persistita e
+avere lo stesso `subject_ref`.
+
+Il contratto è in
+`docs/MAINTAIN_PLAN_RECOVERY_CANDIDATE_SET_CONTRACT.md`. La cattura resta
+default-off e non viene collegata a `backend/main.py`.
PATCH_FILE

patch --dry-run --forward --batch -p0 < .ironcoach_runtime_recovery_candidate_capture.patch
patch --forward --batch -p0 < .ironcoach_runtime_recovery_candidate_capture.patch
rm -f .ironcoach_runtime_recovery_candidate_capture.patch

python -m compileall -q backend tests
git diff --check
python -m pytest -q tests/maintain_plan/test_recovery_candidate_capture.py tests/maintain_plan/test_runtime_recovery_adapter.py
python -m pytest -q

git add -- "${targets[@]}"
git diff --cached --check
git commit -m 'feat: persist recovery candidate sets'
committed=1
git push origin feature/beta-0.4-decision-memory

echo '=== VERIFICA FINALE ==='
git status --short --branch
git log -1 --oneline
echo '=== FINE REPORT ==='
rm -rf "$backup"
IRONCOACH_RUNTIME_RECOVERY_CANDIDATE_CAPTURE
