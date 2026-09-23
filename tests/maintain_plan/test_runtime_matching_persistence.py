"""Focused tests for the deliberately unwired runtime-decision bridge."""

from dataclasses import replace
import sqlite3

import pytest

from backend.maintain_plan.runtime_matching_decision import decide_runtime_matching
from backend.maintain_plan.runtime_matching_persistence import (
    RuntimeMatchingPersistenceError,
    persist_runtime_matching_decision,
)
from backend.maintain_plan.runtime_matching_scope import validate_runtime_matching_scope
from backend.maintain_plan.repository import MaintainPlanRepository
from backend.maintain_plan.serialization import serialize_contract
from tests.maintain_plan.fixtures import NOW, RUN_PRESCRIPTION, RUN_SESSION


def _scope(*, snapshots=(RUN_PRESCRIPTION,), sessions=(RUN_SESSION,)):
    return validate_runtime_matching_scope("athlete-1", snapshots, sessions)


def _count(repository):
    with sqlite3.connect(repository.database_path) as connection:
        return connection.execute(
            "SELECT count(*) FROM maintain_plan_prescription_mappings"
        ).fetchone()[0]


def _seed(repository):
    repository.create_prescription_snapshot(RUN_PRESCRIPTION)
    repository.create_actual_session(RUN_SESSION)


def _persist(repository, scope, decision, mapping_id="runtime-mapping"):
    return persist_runtime_matching_decision(
        repository, scope, decision, mapping_id=mapping_id, created_at=NOW)


def test_matched_one_is_persisted_and_identical_retry_is_idempotent(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "matching.db")
    _seed(repository)
    scope = _scope()
    decision = decide_runtime_matching(scope)

    first = _persist(repository, scope, decision)
    second = _persist(repository, scope, decision)

    assert first == second
    assert first.prescription_snapshot_ref == RUN_PRESCRIPTION.prescription_snapshot_id
    assert first.actual_session_ref == RUN_SESSION.session_id
    assert _count(repository) == 1


@pytest.mark.parametrize("outcome", ["zero", "multiple"])
def test_non_unique_decisions_are_no_ops(tmp_path, outcome):
    repository = MaintainPlanRepository(tmp_path / "matching.db")
    snapshots = (RUN_PRESCRIPTION,)
    sessions = () if outcome == "zero" else (
        RUN_SESSION, replace(RUN_SESSION, session_id="session-2"))
    scope = _scope(snapshots=snapshots, sessions=sessions)

    assert _persist(repository, scope, decide_runtime_matching(scope)) is None
    assert _count(repository) == 0


def test_decision_from_another_scope_is_rejected_without_writing(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "matching.db")
    _seed(repository)
    scope = _scope()
    other_scope = _scope(sessions=(replace(RUN_SESSION, session_id="other"),))

    with pytest.raises(RuntimeMatchingPersistenceError, match="complete validated scope"):
        _persist(repository, scope, decide_runtime_matching(other_scope))
    assert _count(repository) == 0


@pytest.mark.parametrize("artifact", ["snapshot", "session"])
def test_changed_artifact_is_rejected_inside_atomic_persistence(tmp_path, artifact):
    repository = MaintainPlanRepository(tmp_path / "matching.db")
    _seed(repository)
    scope = _scope()
    decision = decide_runtime_matching(scope)
    with sqlite3.connect(repository.database_path) as connection:
        if artifact == "snapshot":
            changed = replace(RUN_PRESCRIPTION, communicated_at=NOW.replace(hour=9))
            connection.execute(
                "UPDATE maintain_plan_prescription_snapshots SET payload_json=?",
                (serialize_contract(changed),),
            )
        else:
            changed = replace(RUN_SESSION, start=NOW.replace(minute=1))
            connection.execute(
                "UPDATE maintain_plan_actual_sessions SET start=?, payload_json=?",
                (changed.start.isoformat(), serialize_contract(changed)),
            )

    with pytest.raises(ValueError, match=f"{artifact} changed since matching decision"):
        _persist(repository, scope, decision)
    assert _count(repository) == 0


def test_occupied_mapping_side_is_rejected_without_a_second_write(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "matching.db")
    _seed(repository)
    scope = _scope()
    decision = decide_runtime_matching(scope)
    _persist(repository, scope, decision, "first-mapping")

    with pytest.raises(ValueError, match="snapshot is already mapped"):
        _persist(repository, scope, decision, "different-mapping")
    assert _count(repository) == 1


def test_incoherent_persisted_ownership_is_rejected(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "matching.db")
    _seed(repository)
    scope = _scope()
    decision = decide_runtime_matching(scope)
    changed = replace(RUN_SESSION, subject_ref="athlete-2")
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute(
            "UPDATE maintain_plan_actual_sessions SET subject_ref=?, payload_json=?",
            (changed.subject_ref, serialize_contract(changed)),
        )

    with pytest.raises(ValueError, match="changed since matching decision|subject_ref mismatch"):
        _persist(repository, scope, decision)
    assert _count(repository) == 0
