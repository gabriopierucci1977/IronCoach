"""Append-only persistence tests for canonical GeneralStabilityEvaluation."""

import sqlite3
from dataclasses import replace

import pytest

from backend.maintain_plan.general_stability_service import evaluate_general_stability
from backend.maintain_plan.repository import MaintainPlanRepository
from backend.maintain_plan.stability_models import VersionedArtifactRef
from tests.maintain_plan.fixtures import RUN_PRESCRIPTION, RUN_SESSION
from tests.maintain_plan.test_general_stability_service import make_input


SNAPSHOT_REF = VersionedArtifactRef("prescription-snapshot", "snapshot-1", "1")
SESSION_REF = VersionedArtifactRef("actual-session", "session-1", "1")


def stability_input():
    value = make_input()
    binding = replace(value.prescription_binding, prescription_snapshot_ref=SNAPSHOT_REF)
    boundary = replace(value.actual_session_boundary, actual_session_ref=SESSION_REF)
    candidates = replace(value.candidate_set, actual_session_ref=SESSION_REF)
    projection = replace(value.reported_problems_projection, actual_session_ref=SESSION_REF)
    return replace(value, prescription_binding=binding,
                   actual_session_boundary=boundary, candidate_set=candidates,
                   reported_problems_projection=projection)


def seed_repository(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "maintain-plan.sqlite")
    repository.create_prescription_snapshot(
        replace(RUN_PRESCRIPTION, subject_ref="athlete"))
    repository.create_actual_session(
        replace(RUN_SESSION, subject_ref="athlete"))
    return repository


def evaluation():
    return evaluate_general_stability(stability_input(), evaluation_id="stability-1")


def test_stability_evaluation_round_trips_and_lists_by_subject(tmp_path):
    repository = seed_repository(tmp_path)
    value = evaluation()
    repository.create_stability_evaluation(value)
    assert repository.get_stability_evaluation(value.evaluation_id) == value
    assert repository.list_stability_evaluations("athlete") == (value,)
    assert repository.list_stability_evaluations("other") == ()


def test_stability_evaluation_is_append_only_and_retry_does_not_overwrite(tmp_path):
    repository = seed_repository(tmp_path)
    value = evaluation()
    repository.create_stability_evaluation(value)
    with pytest.raises(sqlite3.IntegrityError):
        repository.create_stability_evaluation(value)
    assert repository.get_stability_evaluation(value.evaluation_id) == value


def test_stability_evaluation_rejects_foreign_persisted_snapshot_owner(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "maintain-plan.sqlite")
    repository.create_prescription_snapshot(
        replace(RUN_PRESCRIPTION, subject_ref="other"))
    repository.create_actual_session(
        replace(RUN_SESSION, subject_ref="athlete"))
    with pytest.raises(ValueError, match="snapshot ownership"):
        repository.create_stability_evaluation(evaluation())


def test_stability_evaluation_rejects_foreign_persisted_session_owner(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "maintain-plan.sqlite")
    repository.create_prescription_snapshot(
        replace(RUN_PRESCRIPTION, subject_ref="athlete"))
    repository.create_actual_session(
        replace(RUN_SESSION, subject_ref="other"))
    with pytest.raises(ValueError, match="actual-session ownership"):
        repository.create_stability_evaluation(evaluation())


def test_stability_evaluation_payload_tampering_is_detected(tmp_path):
    repository = seed_repository(tmp_path)
    value = evaluation()
    repository.create_stability_evaluation(value)
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute(
            "UPDATE maintain_plan_stability_evaluations SET subject_ref='other' "
            "WHERE evaluation_id=?", (value.evaluation_id,))
    with pytest.raises(ValueError, match="metadata"):
        repository.get_stability_evaluation(value.evaluation_id)
