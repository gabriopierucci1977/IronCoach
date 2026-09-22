"""Normative tests for the v7 subject ownership binding."""

from dataclasses import replace
import json
import sqlite3

import pytest

from backend.maintain_plan.models import ActualSession
from backend.maintain_plan.prescription_snapshot_service import (
    CommunicatedPrescription,
    PrescriptionSnapshotConflictError,
    PrescriptionSnapshotService,
)
from backend.maintain_plan.repository import MaintainPlanRepository
from backend.maintain_plan.schema import MIGRATIONS, SCHEMA_VERSION, run_migrations
from backend.maintain_plan.serialization import PAYLOAD_SCHEMA_VERSION, serialize_contract
from backend.maintain_plan.validators import (
    validate_actual_session,
    validate_mapping_ownership,
    validate_prescription,
)
from tests.maintain_plan.fixtures import RUN_MAPPING, RUN_PRESCRIPTION, RUN_SESSION


def _legacy_payload(value) -> str:
    encoded = json.loads(serialize_contract(value))
    del encoded["payload"]["fields"]["subject_ref"]
    return json.dumps(encoded, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def test_v7_is_exactly_append_only_after_v1_through_v6(tmp_path):
    assert SCHEMA_VERSION == 8
    assert [migration.version for migration in MIGRATIONS] == list(range(1, 9))
    path = tmp_path / "upgrade.db"
    run_migrations(path, MIGRATIONS[:6])
    with sqlite3.connect(path) as connection:
        before = connection.execute(
            "SELECT version, checksum FROM maintain_plan_schema_migrations ORDER BY version"
        ).fetchall()
    run_migrations(path)
    with sqlite3.connect(path) as connection:
        after = connection.execute(
            "SELECT version, checksum FROM maintain_plan_schema_migrations ORDER BY version"
        ).fetchall()
        assert before == after[:6]
        assert [row[0] for row in after] == list(range(1, 9))
        assert "subject_ref" in {row[1] for row in connection.execute(
            "PRAGMA table_info(maintain_plan_prescription_snapshots)")}
        assert "subject_ref" in {row[1] for row in connection.execute(
            "PRAGMA table_info(maintain_plan_actual_sessions)")}


def test_snapshot_and_session_subject_round_trip_exact_unicode(tmp_path):
    subject = "Atleta-é/東京"
    snapshot = replace(RUN_PRESCRIPTION, subject_ref=subject)
    session = replace(RUN_SESSION, subject_ref=subject)
    repository = MaintainPlanRepository(tmp_path / "roundtrip.db")
    repository.create_prescription_snapshot(snapshot)
    repository.create_actual_session(session)
    assert repository.get_prescription_snapshot(snapshot.prescription_snapshot_id) == snapshot
    assert repository.get_actual_session(session.session_id) == session


@pytest.mark.parametrize("subject", [None, "", "   ", 123, "bad\ud800"])
def test_missing_malformed_and_isolated_surrogate_are_rejected(subject):
    assert validate_prescription(replace(RUN_PRESCRIPTION, subject_ref=subject))
    assert validate_actual_session(replace(RUN_SESSION, subject_ref=subject))


def test_binding_is_case_sensitive_and_never_normalized():
    exact = " Athlete-é "
    assert validate_prescription(replace(RUN_PRESCRIPTION, subject_ref=exact)) == ()
    assert validate_actual_session(replace(RUN_SESSION, subject_ref=exact)) == ()
    assert validate_mapping_ownership(
        RUN_MAPPING,
        replace(RUN_PRESCRIPTION, subject_ref=exact),
        replace(RUN_SESSION, subject_ref=exact),
    ) == ()
    errors = validate_mapping_ownership(
        RUN_MAPPING,
        replace(RUN_PRESCRIPTION, subject_ref="Athlete-é"),
        replace(RUN_SESSION, subject_ref="athlete-é"),
    )
    assert any("subject_ref mismatch" in error for error in errors)


def test_mapping_missing_or_cross_athlete_binding_is_fail_closed(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "cross-athlete.db")
    repository.create_prescription_snapshot(RUN_PRESCRIPTION)
    repository.create_actual_session(replace(RUN_SESSION, subject_ref="athlete-2"))
    with pytest.raises(ValueError, match="subject_ref mismatch"):
        repository.create_prescription_mapping(RUN_MAPPING)
    with sqlite3.connect(repository.database_path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM maintain_plan_prescription_mappings"
        ).fetchone() == (0,)
    assert validate_mapping_ownership(
        RUN_MAPPING,
        replace(RUN_PRESCRIPTION, subject_ref=None),
        RUN_SESSION,
    )


def test_v6_legacy_payloads_remain_readable_but_not_mapping_eligible(tmp_path):
    path = tmp_path / "legacy.db"
    run_migrations(path, MIGRATIONS[:6])
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO maintain_plan_prescription_snapshots VALUES (?, ?, ?, ?, ?, ?)",
            (RUN_PRESCRIPTION.prescription_snapshot_id, RUN_PRESCRIPTION.workout_id,
             RUN_PRESCRIPTION.decision_id, RUN_PRESCRIPTION.contract_version,
             PAYLOAD_SCHEMA_VERSION, _legacy_payload(RUN_PRESCRIPTION)),
        )
        connection.execute(
            "INSERT INTO maintain_plan_actual_sessions VALUES (?, ?, ?, ?, ?, ?)",
            (RUN_SESSION.session_id, RUN_SESSION.start.isoformat(),
             RUN_SESSION.composition.value, RUN_SESSION.contract_version,
             PAYLOAD_SCHEMA_VERSION, _legacy_payload(RUN_SESSION)),
        )
    repository = MaintainPlanRepository(path)
    snapshot = repository.get_prescription_snapshot("snapshot-1")
    session = repository.get_actual_session("session-1")
    assert snapshot.subject_ref is None
    assert session.subject_ref is None
    with pytest.raises(ValueError, match="requires subject_ref"):
        repository.create_prescription_mapping(RUN_MAPPING)


def test_subject_participates_in_snapshot_retry_idempotency(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "retry.db")
    service = PrescriptionSnapshotService(repository)
    assert service.acquire(CommunicatedPrescription(RUN_PRESCRIPTION)) == RUN_PRESCRIPTION
    assert service.acquire(CommunicatedPrescription(RUN_PRESCRIPTION)) == RUN_PRESCRIPTION
    with pytest.raises(PrescriptionSnapshotConflictError):
        service.acquire(CommunicatedPrescription(
            replace(RUN_PRESCRIPTION, subject_ref="athlete-2")))


def test_repository_rejects_new_records_without_binding(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "required.db")
    with pytest.raises(ValueError, match="subject_ref"):
        repository.create_prescription_snapshot(replace(RUN_PRESCRIPTION, subject_ref=None))
    with pytest.raises(ValueError, match="subject_ref"):
        repository.create_actual_session(replace(RUN_SESSION, subject_ref=None))


def test_runtime_prescription_uses_only_authoritative_athlete_source_id(tmp_path):
    from datetime import datetime, timezone

    from backend.maintain_plan.runtime_prescription_capture import RuntimePrescriptionCapture
    from tests.maintain_plan.test_runtime_prescription_capture import (
        _CaptureConfig, _runtime_decision, _runtime_training,
    )

    config = _CaptureConfig()
    config.maintain_plan_database_path = str(tmp_path / "runtime.db")
    result = RuntimePrescriptionCapture(
        clock=lambda: datetime(2026, 9, 18, tzinfo=timezone.utc)
    ).capture(
        runtime_config=config,
        athlete={"source_id": "Athlete-É", "name": "ignored"},
        training=_runtime_training(source_id="technical-workout-id"),
        decision=_runtime_decision(decision_id="technical-decision-id"),
    )
    assert result.subject_ref == "Athlete-É"

    with pytest.raises(ValueError, match="subject_ref"):
        RuntimePrescriptionCapture().capture(
            runtime_config=config,
            athlete={"name": "must-not-be-a-fallback"},
            training=_runtime_training(),
            decision=_runtime_decision(),
        )
