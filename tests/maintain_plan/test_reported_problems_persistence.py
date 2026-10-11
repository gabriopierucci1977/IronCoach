import sqlite3
from dataclasses import replace

import pytest

from backend.maintain_plan.repository import MaintainPlanRepository
from backend.maintain_plan.runtime_reported_problems_capture import (
    ReportedProblemsProjectionCaptureError,
    RuntimeReportedProblemsProjectionCapture,
)
from backend.maintain_plan.stability_models import VersionedArtifactRef
from backend.maintain_plan.stability_validators import validate_projection_structure
from tests.maintain_plan.fixtures import RUN_SESSION
from tests.maintain_plan.test_general_stability_service import make_input


SESSION_REF = VersionedArtifactRef("actual-session", "session-1", "1")


def projection(**changes):
    value = make_input().reported_problems_projection
    value = replace(value, actual_session_ref=SESSION_REF)
    return replace(value, **changes)


def repository(tmp_path):
    value = MaintainPlanRepository(tmp_path / "reported-problems.db")
    value.create_actual_session(replace(RUN_SESSION, subject_ref="athlete"))
    return value


def test_projection_capture_is_explicit_and_valid():
    value = projection()
    assert validate_projection_structure(value) == ()
    assert RuntimeReportedProblemsProjectionCapture().capture(
        value=value, enabled=False
    ) is None


def test_projection_round_trip_and_identical_retry(tmp_path):
    repo = repository(tmp_path)
    capture = RuntimeReportedProblemsProjectionCapture(lambda _: repo)
    value = projection()
    assert capture.capture(value=value, enabled=True, database_path="ignored") == value
    assert repo.get_reported_problems_projection(value.projection_id) == value
    assert repo.list_reported_problems_projections("athlete") == (value,)
    assert capture.capture(value=value, enabled=True, database_path="ignored") == value


def test_projection_semantic_retry_conflict_is_rejected(tmp_path):
    repo = repository(tmp_path)
    capture = RuntimeReportedProblemsProjectionCapture(lambda _: repo)
    value = projection()
    capture.capture(value=value, enabled=True, database_path="ignored")
    with pytest.raises(ValueError, match="different content"):
        capture.capture(
            value=replace(value, projection_version="2"),
            enabled=True, database_path="ignored",
        )


def test_projection_rejects_missing_or_foreign_session(tmp_path):
    repo = MaintainPlanRepository(tmp_path / "reported-problems.db")
    capture = RuntimeReportedProblemsProjectionCapture(lambda _: repo)
    with pytest.raises(ValueError, match="missing actual session"):
        capture.capture(value=projection(), enabled=True, database_path="ignored")
    repo.create_actual_session(RUN_SESSION)
    with pytest.raises(ValueError, match="ownership"):
        capture.capture(
            value=replace(projection(), subject_ref="other-athlete"),
            enabled=True, database_path="ignored",
        )


def test_projection_payload_metadata_tampering_is_detected(tmp_path):
    repo = repository(tmp_path)
    value = projection()
    repo.acquire_reported_problems_projection(value)
    with sqlite3.connect(repo.database_path) as connection:
        connection.execute(
            "UPDATE maintain_plan_reported_problems_projections "
            "SET result='ISSUE_REPORTED' WHERE projection_id=?",
            (value.projection_id,),
        )
    with pytest.raises(ValueError, match="metadata"):
        repo.get_reported_problems_projection(value.projection_id)


def test_projection_capture_rejects_wrong_payload():
    with pytest.raises(ReportedProblemsProjectionCaptureError):
        RuntimeReportedProblemsProjectionCapture().capture(
            value=object(), enabled=True, database_path="ignored"
        )
