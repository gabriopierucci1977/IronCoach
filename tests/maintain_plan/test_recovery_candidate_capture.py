from datetime import timedelta

import pytest

from backend.maintain_plan.repository import MaintainPlanRepository
from backend.maintain_plan.runtime_recovery_candidate_capture import (
    RecoveryCandidateSetCaptureError,
    RuntimeRecoveryCandidateSetCapture,
    build_recovery_candidate_set_capture,
)
from backend.maintain_plan.stability_models import (
    ProvenanceRef, VersionedArtifactRef,
)
from backend.maintain_plan.stability_validators import validate_recovery_candidate_set
from tests.maintain_plan.fixtures import NOW, RUN_SESSION


SESSION_REF = VersionedArtifactRef("actual-session", "session-1", "1")
PROVENANCE = ProvenanceRef(
    VersionedArtifactRef("candidate-set-capture", "capture-1", "1"),
    "candidate-set-capture", "capture-1", "1",
)


def _record(**overrides):
    value = {
        "source": "garmin",
        "source_id": "garmin-recovery:2026-01-01-follow-up",
        "date": "2026-01-01",
        "observed_at": "2026-01-01T10:00:00Z",
        "assessed_at": "2026-01-01T10:05:00Z",
        "category": "LOW",
    }
    value.update(overrides)
    return value


def _inputs(**overrides):
    value = {
        "records": [_record()],
        "actual_session_ref": SESSION_REF,
        "subject_ref": "athlete-1",
        "captured_at": NOW + timedelta(hours=6),
        "evaluated_cutoff_at": NOW + timedelta(hours=8),
        "provenance_ref": PROVENANCE,
    }
    value.update(overrides)
    return value


def test_candidate_set_capture_is_explicit_and_valid():
    value = build_recovery_candidate_set_capture(**_inputs())
    assert validate_recovery_candidate_set(value) == ()
    assert value.subject_ref == "athlete-1"
    assert value.actual_session_ref == SESSION_REF
    assert value.candidates[0].category.value == "LOW"


def test_capture_is_disabled_without_constructing_repository():
    class FailRepository:
        def __init__(self, *_):
            raise AssertionError("repository must not be constructed")

    capture = RuntimeRecoveryCandidateSetCapture(FailRepository)
    assert capture.capture(candidate_set_id="set-1", enabled=False) is None


def test_candidate_set_round_trip_retry_and_listing(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "candidate-set.db")
    repository.create_actual_session(RUN_SESSION)
    capture = RuntimeRecoveryCandidateSetCapture(lambda _: repository)
    value = capture.capture(
        candidate_set_id="candidate-set-1", enabled=True, database_path="ignored",
        **_inputs(),
    )
    assert repository.get_recovery_candidate_set("candidate-set-1") == value
    assert repository.list_recovery_candidate_sets("athlete-1") == (value,)
    retry = capture.capture(
        candidate_set_id="candidate-set-1", enabled=True, database_path="ignored",
        **_inputs(),
    )
    assert retry == value


def test_candidate_set_semantic_retry_conflict_is_rejected(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "candidate-set.db")
    repository.create_actual_session(RUN_SESSION)
    capture = RuntimeRecoveryCandidateSetCapture(lambda _: repository)
    capture.capture(
        candidate_set_id="candidate-set-1", enabled=True, database_path="ignored",
        **_inputs(),
    )
    with pytest.raises(ValueError, match="different content"):
        capture.capture(
            candidate_set_id="candidate-set-1", enabled=True, database_path="ignored",
            **_inputs(records=[_record(category="HIGH")]),
        )


def test_candidate_set_rejects_missing_session_and_foreign_subject(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "candidate-set.db")
    capture = RuntimeRecoveryCandidateSetCapture(lambda _: repository)
    with pytest.raises(ValueError, match="missing actual session"):
        capture.capture(
            candidate_set_id="candidate-set-1", enabled=True, database_path="ignored",
            **_inputs(),
        )
    repository.create_actual_session(RUN_SESSION)
    with pytest.raises(ValueError, match="ownership"):
        capture.capture(
            candidate_set_id="candidate-set-foreign", enabled=True, database_path="ignored",
            **_inputs(subject_ref="other-athlete"),
        )


def test_candidate_set_capture_rejects_bad_identity_and_timestamps():
    with pytest.raises(RecoveryCandidateSetCaptureError, match="candidate_set_id"):
        RuntimeRecoveryCandidateSetCapture().capture(
            candidate_set_id="", enabled=True, database_path="ignored", **_inputs(),
        )
    with pytest.raises(RecoveryCandidateSetCaptureError, match="must not follow"):
        build_recovery_candidate_set_capture(
            **_inputs(captured_at=NOW + timedelta(hours=9)),
        )
    with pytest.raises(RecoveryCandidateSetCaptureError) as error:
        build_recovery_candidate_set_capture(
            **_inputs(records=[_record(observed_at=None)]),
        )
    assert error.value.code == "INPUT_MISSING"
