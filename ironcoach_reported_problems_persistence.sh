#!/usr/bin/env bash
cd /workspaces/IronCoach
bash <<'IRONCOACH_REPORTED_PROBLEMS_PERSISTENCE'
set -Eeuo pipefail

report="ironcoach_reported_problems_persistence_result.txt"
exec > >(tee "$report") 2>&1

echo '=== PERSISTENZA REPORTED-PROBLEMS PROJECTION ==='
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
if ! grep -q '^SCHEMA_VERSION = 13$' backend/maintain_plan/schema.py; then
  echo 'STOP: schema corrente diverso da v13; script non applicato.'
  grep -n '^SCHEMA_VERSION' backend/maintain_plan/schema.py || true
  exit 1
fi
if ! grep -q 'maintain_plan_recovery_candidate_sets' backend/maintain_plan/schema.py; then
  echo 'STOP: migration 13 non presente; prima verificare lo stato del branch.'
  exit 1
fi

targets=(
  backend/maintain_plan/schema.py
  backend/maintain_plan/repository.py
  backend/maintain_plan/runtime_reported_problems_capture.py
  tests/maintain_plan/test_persistence.py
  tests/maintain_plan/test_subject_ownership.py
  tests/maintain_plan/test_execution_evaluation_hardening.py
  tests/maintain_plan/test_execution_evaluation_review26.py
  tests/maintain_plan/test_reported_problems_persistence.py
  docs/MAINTAIN_PLAN_REPORTED_PROBLEMS_PROJECTION_CONTRACT.md
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
  rm -f .ironcoach_reported_problems_persistence.patch
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

cat > .ironcoach_reported_problems_persistence.patch <<'PATCH_FILE'
--- backend/maintain_plan/schema.py	2026-10-11 12:04:07.917098380 +0100
+++ backend/maintain_plan/schema.py	2026-10-11 13:39:15.301999810 +0100
@@ -12,7 +12,7 @@
 from .archive_lock import archive_lock
 
 
-SCHEMA_VERSION = 13
+SCHEMA_VERSION = 14
 
 
 @dataclass(frozen=True)
@@ -598,6 +598,48 @@
 ),)
 
 
+_MIGRATION_14_SQL = """
+CREATE TABLE maintain_plan_reported_problems_projections (
+    projection_id TEXT PRIMARY KEY,
+    subject_ref TEXT NOT NULL,
+    actual_session_ref TEXT NOT NULL
+        REFERENCES maintain_plan_actual_sessions(session_id),
+    projection_version TEXT,
+    projection_schema_version TEXT,
+    projection_status TEXT,
+    event_cursor_event_id TEXT,
+    event_cursor_sequence INTEGER,
+    event_window_start_at TEXT,
+    event_window_start_boundary TEXT,
+    event_window_end_at TEXT,
+    event_window_end_boundary TEXT,
+    checked_through_at TEXT,
+    channel_check_status TEXT,
+    result TEXT,
+    reliable_canonical_safety_signal INTEGER,
+    payload_schema_version TEXT NOT NULL,
+    payload_json TEXT NOT NULL
+);
+CREATE INDEX idx_mp_reported_problems_subject
+    ON maintain_plan_reported_problems_projections(subject_ref);
+CREATE INDEX idx_mp_reported_problems_session
+    ON maintain_plan_reported_problems_projections(actual_session_ref);
+CREATE INDEX idx_mp_reported_problems_version
+    ON maintain_plan_reported_problems_projections(projection_version);
+""".strip()
+
+
+def _migration_14(connection: sqlite3.Connection) -> None:
+    for statement in _MIGRATION_14_SQL.split(";"):
+        if statement.strip():
+            connection.execute(statement)
+
+
+MIGRATIONS = MIGRATIONS + (Migration(
+    14, hashlib.sha256(_MIGRATION_14_SQL.encode("utf-8")).hexdigest(), _migration_14,
+),)
+
+
 def run_migrations(database_path: str | Path, migrations: Iterable[Migration] = MIGRATIONS) -> None:
     """Apply each migration exactly once and atomically, without touching legacy tables."""
     path = Path(database_path)
--- backend/maintain_plan/repository.py	2026-10-11 12:04:07.917349337 +0100
+++ backend/maintain_plan/repository.py	2026-10-11 13:38:44.181135677 +0100
@@ -13,7 +13,10 @@
                      PrescriptionSnapshot, SourceConflictProjection,
                      SourceConflictImpactEvaluation, SourceConflictResolutionEvent,
                      SourceConflictResolutionLog)
-from .stability_models import GeneralStabilityEvaluation, RecoveryAssessmentCandidateSet
+from .stability_models import (
+    GeneralStabilityEvaluation, RecoveryAssessmentCandidateSet,
+    ReportedProblemsProjectionSnapshot,
+)
 from .recovery_baseline_models import (
     PrescriptionRecoveryBaseline, validate_recovery_baseline,
 )
@@ -31,6 +34,7 @@
                          validate_source_conflict_impact)
 from .stability_validators import (
     validate_general_stability_evaluation, validate_recovery_candidate_set,
+    validate_projection_structure,
 )
 
 if TYPE_CHECKING:
@@ -405,6 +409,132 @@
         ):
             raise ValueError("stored recovery candidate set metadata does not match payload")
 
+    @staticmethod
+    def _reported_projection_row_metadata(value: ReportedProblemsProjectionSnapshot) -> tuple[Any, ...]:
+        cursor = value.event_cursor
+        window = value.event_window
+        return (
+            value.projection_id, value.subject_ref, value.actual_session_ref.artifact_id,
+            value.projection_version, value.projection_schema_version,
+            None if value.projection_status is None else value.projection_status.value,
+            None if cursor is None else cursor.event_id,
+            None if cursor is None else cursor.event_sequence,
+            None if window is None else window.start_at.isoformat(),
+            None if window is None else window.start_boundary.value,
+            None if window is None else window.end_at.isoformat(),
+            None if window is None else window.end_boundary.value,
+            None if value.checked_through_at is None else value.checked_through_at.isoformat(),
+            None if value.channel_check_status is None else value.channel_check_status.value,
+            None if value.result is None else value.result.value,
+            None if value.reliable_canonical_safety_signal is None
+            else int(value.reliable_canonical_safety_signal),
+        )
+
+    def acquire_reported_problems_projection(
+        self, value: ReportedProblemsProjectionSnapshot,
+    ) -> ReportedProblemsProjectionSnapshot:
+        """Atomically acquire one immutable reported-problems projection snapshot."""
+        self._require_valid(validate_projection_structure(value))
+        session_ref = value.actual_session_ref
+        if session_ref.artifact_type != "actual-session":
+            raise ValueError("reported-problems projection must reference an actual session")
+        session = self.get_actual_session(session_ref.artifact_id)
+        if session is None:
+            raise ValueError("reported-problems projection references a missing actual session")
+        if session.subject_ref != value.subject_ref:
+            raise ValueError("reported-problems projection session ownership is incoherent")
+        stored_row = None
+        stored = None
+        with self._connect() as connection:
+            connection.row_factory = sqlite3.Row
+            connection.execute("BEGIN IMMEDIATE")
+            stored_row = connection.execute(
+                "SELECT * FROM maintain_plan_reported_problems_projections "
+                "WHERE projection_id = ?", (value.projection_id,),
+            ).fetchone()
+            if stored_row is None:
+                metadata = self._reported_projection_row_metadata(value)
+                connection.execute(
+                    "INSERT INTO maintain_plan_reported_problems_projections "
+                    "(projection_id, subject_ref, actual_session_ref, projection_version, "
+                    "projection_schema_version, projection_status, event_cursor_event_id, "
+                    "event_cursor_sequence, event_window_start_at, event_window_start_boundary, "
+                    "event_window_end_at, event_window_end_boundary, checked_through_at, "
+                    "channel_check_status, result, reliable_canonical_safety_signal, "
+                    "payload_schema_version, payload_json) "
+                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
+                    metadata + (PAYLOAD_SCHEMA_VERSION, serialize_contract(value)),
+                )
+                return value
+            stored = self._decode_reported_problems_projection_row(stored_row)
+        self._validate_reported_problems_projection_row(stored_row, stored)
+        if stored == value:
+            return stored
+        raise ValueError(
+            "reported-problems projection already exists with different content"
+        )
+
+    def get_reported_problems_projection(
+        self, projection_id: str,
+    ) -> ReportedProblemsProjectionSnapshot | None:
+        stored = self._get(
+            "maintain_plan_reported_problems_projections", "projection_id",
+            projection_id, ReportedProblemsProjectionSnapshot,
+        )
+        if stored is None:
+            return None
+        row, value = stored
+        self._validate_reported_problems_projection_row(row, value)
+        return value
+
+    def list_reported_problems_projections(
+        self, subject_ref: str,
+    ) -> tuple[ReportedProblemsProjectionSnapshot, ...]:
+        with self._connect() as connection:
+            connection.row_factory = sqlite3.Row
+            rows = connection.execute(
+                "SELECT * FROM maintain_plan_reported_problems_projections "
+                "WHERE subject_ref = ? ORDER BY projection_id", (subject_ref,),
+            ).fetchall()
+        values = []
+        for row in rows:
+            value = self._decode_reported_problems_projection_row(row)
+            self._validate_reported_problems_projection_row(row, value)
+            values.append(value)
+        return tuple(values)
+
+    def _decode_reported_problems_projection_row(
+        self, row: sqlite3.Row,
+    ) -> ReportedProblemsProjectionSnapshot:
+        if row["payload_schema_version"] != PAYLOAD_SCHEMA_VERSION:
+            raise ValueError("unsupported stored MAINTAIN_PLAN payload schema version")
+        return deserialize_contract(row["payload_json"], ReportedProblemsProjectionSnapshot)
+
+    def _validate_reported_problems_projection_row(
+        self, row: sqlite3.Row, value: ReportedProblemsProjectionSnapshot,
+    ) -> None:
+        self._require_valid(validate_projection_structure(value))
+        session_ref = value.actual_session_ref
+        if session_ref.artifact_type != "actual-session":
+            raise ValueError("stored reported-problems projection has invalid session ref")
+        session = self.get_actual_session(session_ref.artifact_id)
+        if session is None or session.subject_ref != value.subject_ref:
+            raise ValueError("stored reported-problems projection has unresolved ownership")
+        expected = self._reported_projection_row_metadata(value)
+        actual = tuple(row[name] for name in (
+            "projection_id", "subject_ref", "actual_session_ref",
+            "projection_version", "projection_schema_version", "projection_status",
+            "event_cursor_event_id", "event_cursor_sequence",
+            "event_window_start_at", "event_window_start_boundary",
+            "event_window_end_at", "event_window_end_boundary",
+            "checked_through_at", "channel_check_status", "result",
+            "reliable_canonical_safety_signal",
+        ))
+        if actual != expected:
+            raise ValueError(
+                "stored reported-problems projection metadata does not match payload"
+            )
+
     def create_actual_session(self, value: ActualSession) -> None:
         self._require_valid(validate_actual_session(value))
         self._insert(
--- /dev/null	2026-10-11 11:01:00.043117762 +0100
+++ backend/maintain_plan/runtime_reported_problems_capture.py	2026-10-11 13:38:44.181281717 +0100
@@ -0,0 +1,43 @@
+"""Opt-in capture and persistence of a canonical reported-problems projection."""
+
+from __future__ import annotations
+
+from .repository import MaintainPlanRepository
+from .stability_models import ReportedProblemsProjectionSnapshot
+from .stability_validators import validate_projection_structure
+
+
+class ReportedProblemsProjectionCaptureError(ValueError):
+    def __init__(self, errors, *, code="INPUT_INVALID"):
+        self.code = code
+        self.errors = tuple(errors)
+        super().__init__("; ".join(self.errors))
+
+
+def build_reported_problems_projection_capture(
+    value: ReportedProblemsProjectionSnapshot,
+) -> ReportedProblemsProjectionSnapshot:
+    """Validate one caller-scoped projection without reading events or sources."""
+    errors = validate_projection_structure(value)
+    if errors:
+        raise ReportedProblemsProjectionCaptureError(errors)
+    return value
+
+
+class RuntimeReportedProblemsProjectionCapture:
+    def __init__(self, repository_factory=MaintainPlanRepository):
+        self._repository_factory = repository_factory
+
+    def capture(
+        self, *, value, enabled=False, database_path=None,
+    ) -> ReportedProblemsProjectionSnapshot | None:
+        """Validate before opening SQLite; disabled calls have no side effects."""
+        if enabled is not True:
+            return None
+        value = build_reported_problems_projection_capture(value)
+        if database_path is None:
+            raise ReportedProblemsProjectionCaptureError(
+                ("database_path is required",), code="INPUT_MISSING",
+            )
+        repository = self._repository_factory(database_path)
+        return repository.acquire_reported_problems_projection(value)
--- tests/maintain_plan/test_persistence.py	2026-10-11 12:04:07.917769198 +0100
+++ tests/maintain_plan/test_persistence.py	2026-10-11 13:38:44.181429140 +0100
@@ -29,6 +29,7 @@
     "maintain_plan_stability_evaluations",
     "maintain_plan_recovery_baselines",
     "maintain_plan_recovery_candidate_sets",
+    "maintain_plan_reported_problems_projections",
 }
 
 
@@ -50,7 +51,7 @@
         versions = connection.execute(
             "SELECT version, checksum FROM maintain_plan_schema_migrations"
         ).fetchall()
-        assert [item[0] for item in versions] == list(range(1, 14))
+        assert [item[0] for item in versions] == list(range(1, 15))
         assert all(len(item[1]) == 64 for item in versions)
         assert {row[1:3] for row in connection.execute(
             "PRAGMA index_list(maintain_plan_prescription_mappings)"
@@ -70,7 +71,7 @@
         assert before == after
         assert connection.execute(
             "SELECT count(*) FROM maintain_plan_schema_migrations"
-                ).fetchone() == (13,)
+                ).fetchone() == (14,)
 
 
 def _seed_confirmation_parents(connection):
@@ -109,7 +110,7 @@
     with sqlite3.connect(path) as connection:
         assert connection.execute("SELECT * FROM maintain_plan_confirmations").fetchall() == before
         assert [row[0] for row in connection.execute(
-            "SELECT version FROM maintain_plan_schema_migrations ORDER BY version")] == list(range(1, 14))
+            "SELECT version FROM maintain_plan_schema_migrations ORDER BY version")] == list(range(1, 15))
         assert {
             "maintain_plan_confirmations_validate_insert",
             "maintain_plan_confirmations_validate_update",
@@ -180,7 +181,7 @@
         assert connection.execute(
             "SELECT count(*) FROM sqlite_master WHERE type='trigger' AND name LIKE 'maintain_plan_confirmations_validate_%'"
         ).fetchone() == (0,)
-    assert SCHEMA_VERSION == 13
+    assert SCHEMA_VERSION == 14
 
 
 def test_migration_preserves_legacy_schema_and_record_exactly(tmp_path):
@@ -274,7 +275,7 @@
         ).fetchall() == mappings
         assert connection.execute(
             "SELECT version FROM maintain_plan_schema_migrations ORDER BY version"
-        ).fetchall() == [(version,) for version in range(1, 14)]
+        ).fetchall() == [(version,) for version in range(1, 15)]
         assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
         assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
 
--- tests/maintain_plan/test_subject_ownership.py	2026-10-11 12:04:07.917916409 +0100
+++ tests/maintain_plan/test_subject_ownership.py	2026-10-11 13:38:44.181572247 +0100
@@ -31,8 +31,8 @@
 
 
 def test_v7_is_exactly_append_only_after_v1_through_v6(tmp_path):
-    assert SCHEMA_VERSION == 13
-    assert [migration.version for migration in MIGRATIONS] == list(range(1, 14))
+    assert SCHEMA_VERSION == 14
+    assert [migration.version for migration in MIGRATIONS] == list(range(1, 15))
     path = tmp_path / "upgrade.db"
     run_migrations(path, MIGRATIONS[:6])
     with sqlite3.connect(path) as connection:
@@ -45,7 +45,7 @@
             "SELECT version, checksum FROM maintain_plan_schema_migrations ORDER BY version"
         ).fetchall()
         assert before == after[:6]
-        assert [row[0] for row in after] == list(range(1, 14))
+        assert [row[0] for row in after] == list(range(1, 15))
         assert "subject_ref" in {row[1] for row in connection.execute(
             "PRAGMA table_info(maintain_plan_prescription_snapshots)")}
         assert "subject_ref" in {row[1] for row in connection.execute(
--- tests/maintain_plan/test_execution_evaluation_hardening.py	2026-10-11 12:04:07.918039535 +0100
+++ tests/maintain_plan/test_execution_evaluation_hardening.py	2026-10-11 13:38:44.181677736 +0100
@@ -230,6 +230,6 @@
     run_migrations(path)
     run_migrations(path)
     with sqlite3.connect(path) as connection:
-        assert connection.execute("SELECT count(*) FROM maintain_plan_schema_migrations").fetchone() == (13,)
+        assert connection.execute("SELECT count(*) FROM maintain_plan_schema_migrations").fetchone() == (14,)
         assert connection.execute("SELECT count(*) FROM maintain_plan_source_conflict_impact_evaluations").fetchone() == (0,)
         assert before
--- tests/maintain_plan/test_execution_evaluation_review26.py	2026-10-11 12:04:07.918150211 +0100
+++ tests/maintain_plan/test_execution_evaluation_review26.py	2026-10-11 13:38:44.181736315 +0100
@@ -112,7 +112,7 @@
     run_migrations(path); run_migrations(path)
     with sqlite3.connect(path) as connection:
         assert connection.execute("SELECT * FROM maintain_plan_source_conflict_impact_evaluations").fetchall() == before
-        assert connection.execute("SELECT count(*) FROM maintain_plan_schema_migrations").fetchone() == (13,)
+        assert connection.execute("SELECT count(*) FROM maintain_plan_schema_migrations").fetchone() == (14,)
         info = connection.execute("PRAGMA table_info(maintain_plan_source_conflict_impact_evaluations)").fetchall()
         assert next(row for row in info if row[1] == "prescription_mapping_ref")[3] == 0
-    assert SCHEMA_VERSION == 13
+    assert SCHEMA_VERSION == 14
--- /dev/null	2026-10-11 11:01:00.043117762 +0100
+++ tests/maintain_plan/test_reported_problems_persistence.py	2026-10-11 13:38:44.181804728 +0100
@@ -0,0 +1,93 @@
+import sqlite3
+from dataclasses import replace
+
+import pytest
+
+from backend.maintain_plan.repository import MaintainPlanRepository
+from backend.maintain_plan.runtime_reported_problems_capture import (
+    ReportedProblemsProjectionCaptureError,
+    RuntimeReportedProblemsProjectionCapture,
+)
+from backend.maintain_plan.stability_models import VersionedArtifactRef
+from backend.maintain_plan.stability_validators import validate_projection_structure
+from tests.maintain_plan.fixtures import RUN_SESSION
+from tests.maintain_plan.test_general_stability_service import make_input
+
+
+SESSION_REF = VersionedArtifactRef("actual-session", "session-1", "1")
+
+
+def projection(**changes):
+    value = make_input().reported_problems_projection
+    value = replace(value, actual_session_ref=SESSION_REF)
+    return replace(value, **changes)
+
+
+def repository(tmp_path):
+    value = MaintainPlanRepository(tmp_path / "reported-problems.db")
+    value.create_actual_session(RUN_SESSION)
+    return value
+
+
+def test_projection_capture_is_explicit_and_valid():
+    value = projection()
+    assert validate_projection_structure(value) == ()
+    assert RuntimeReportedProblemsProjectionCapture().capture(
+        value=value, enabled=False
+    ) is None
+
+
+def test_projection_round_trip_and_identical_retry(tmp_path):
+    repo = repository(tmp_path)
+    capture = RuntimeReportedProblemsProjectionCapture(lambda _: repo)
+    value = projection()
+    assert capture.capture(value=value, enabled=True, database_path="ignored") == value
+    assert repo.get_reported_problems_projection(value.projection_id) == value
+    assert repo.list_reported_problems_projections("athlete") == (value,)
+    assert capture.capture(value=value, enabled=True, database_path="ignored") == value
+
+
+def test_projection_semantic_retry_conflict_is_rejected(tmp_path):
+    repo = repository(tmp_path)
+    capture = RuntimeReportedProblemsProjectionCapture(lambda _: repo)
+    value = projection()
+    capture.capture(value=value, enabled=True, database_path="ignored")
+    with pytest.raises(ValueError, match="different content"):
+        capture.capture(
+            value=replace(value, projection_version="2"),
+            enabled=True, database_path="ignored",
+        )
+
+
+def test_projection_rejects_missing_or_foreign_session(tmp_path):
+    repo = MaintainPlanRepository(tmp_path / "reported-problems.db")
+    capture = RuntimeReportedProblemsProjectionCapture(lambda _: repo)
+    with pytest.raises(ValueError, match="missing actual session"):
+        capture.capture(value=projection(), enabled=True, database_path="ignored")
+    repo.create_actual_session(RUN_SESSION)
+    with pytest.raises(ValueError, match="ownership"):
+        capture.capture(
+            value=replace(projection(), subject_ref="other-athlete"),
+            enabled=True, database_path="ignored",
+        )
+
+
+def test_projection_payload_metadata_tampering_is_detected(tmp_path):
+    repo = repository(tmp_path)
+    value = projection()
+    repo.acquire_reported_problems_projection(value)
+    with sqlite3.connect(repo.database_path) as connection:
+        connection.execute(
+            "UPDATE maintain_plan_reported_problems_projections "
+            "SET result='ISSUE_REPORTED' WHERE projection_id=?",
+            (value.projection_id,),
+        )
+    with pytest.raises(ValueError, match="metadata"):
+        repo.get_reported_problems_projection(value.projection_id)
+
+
+def test_projection_capture_rejects_wrong_payload():
+    with pytest.raises(ReportedProblemsProjectionCaptureError):
+        RuntimeReportedProblemsProjectionCapture().capture(
+            value=object(), enabled=True, database_path="ignored"
+        )
--- /dev/null	2026-10-11 11:01:00.043117762 +0100
+++ docs/MAINTAIN_PLAN_REPORTED_PROBLEMS_PROJECTION_CONTRACT.md	2026-10-11 13:38:44.181836817 +0100
@@ -0,0 +1,17 @@
+# MAINTAIN_PLAN reported-problems projection contract
+
+`runtime_reported_problems_capture.py` conserva una proiezione canonica già
+costruita dal chiamante. Non legge il log degli eventi, non interpreta testo
+libero e non calcola automaticamente safety signal o risultato.
+
+La proiezione è validata con `validate_projection_structure`, deve riferire una
+sessione `actual-session` già persistita e il suo `subject_ref` deve coincidere
+con quello della sessione. La migration 14 aggiunge la tabella
+`maintain_plan_reported_problems_projections` con metadata scalari verificabili
+e payload tipizzato serializzato.
+
+La persistenza è append-only e default-off: stesso `projection_id` e payload
+identico sono un retry idempotente; lo stesso ID con contenuto diverso viene
+rifiutato senza sovrascrittura. Nuove proiezioni devono usare un ID distinto.
+Il modulo non è collegato a `backend/main.py` e non modifica la valutazione
+stability esistente.
--- docs/BETA_0_4_HANDOFF.md	2026-10-11 12:04:07.918363742 +0100
+++ docs/BETA_0_4_HANDOFF.md	2026-10-11 13:38:44.181909356 +0100
@@ -1121,3 +1121,17 @@
 Il contratto è in
 `docs/MAINTAIN_PLAN_RECOVERY_CANDIDATE_SET_CONTRACT.md`. La cattura resta
 default-off e non viene collegata a `backend/main.py`.
+
+
+## Persistenza reported-problems projection — 11 ottobre 2026
+
+È stata aggiunta la cattura opt-in di una `ReportedProblemsProjectionSnapshot`
+già costruita dal chiamante. La cattura non legge eventi e non promuove testo
+libero a safety signal. La migration 14 aggiunge la tabella
+`maintain_plan_reported_problems_projections`; la sessione deve essere già
+persistita e appartenere allo stesso soggetto.
+
+Il retry con stesso `projection_id` e contenuto identico è idempotente; una
+divergenza semantica è rifiutata senza sovrascrittura. Il modulo resta
+default-off e non è collegato al runtime legacy. Il contratto è in
+`docs/MAINTAIN_PLAN_REPORTED_PROBLEMS_PROJECTION_CONTRACT.md`.
PATCH_FILE

patch --dry-run --forward --batch -p0 < .ironcoach_reported_problems_persistence.patch
patch --forward --batch -p0 < .ironcoach_reported_problems_persistence.patch
rm -f .ironcoach_reported_problems_persistence.patch

python -m compileall -q backend tests
git diff --check
python -m pytest -q tests/maintain_plan/test_reported_problems_persistence.py tests/maintain_plan/test_persistence.py
python -m pytest -q

git add -- "${targets[@]}"
git diff --cached --check
git commit -m 'feat: persist reported-problems projections'
committed=1
git push origin feature/beta-0.4-decision-memory

echo '=== VERIFICA FINALE ==='
git status --short --branch
git log -1 --oneline
echo '=== FINE REPORT ==='
rm -rf "$backup"
IRONCOACH_REPORTED_PROBLEMS_PERSISTENCE
