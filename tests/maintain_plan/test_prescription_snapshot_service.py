"""Synthetic tests for explicit communicated-prescription acquisition."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from datetime import datetime
from pathlib import Path
import sqlite3
from threading import Barrier

import pytest

from backend.maintain_plan.models import (
    AllowedSubstitution, Composition, Discipline, Environment, Mode,
    PolicyRef, PrescribedTarget, PrescriptionAudit, Provenance,
)
from backend.maintain_plan.prescription_snapshot_service import (
    CommunicatedPrescription, PrescriptionSnapshotConflictError,
    PrescriptionSnapshotService,
)
from backend.maintain_plan.repository import MaintainPlanRepository
from tests.maintain_plan.fixtures import (
    BRICK_PRESCRIPTION, INTERVAL_PRESCRIPTION, NOW, RUN_PRESCRIPTION,
)


def service(tmp_path, name="snapshot.db"):
    return PrescriptionSnapshotService(MaintainPlanRepository(tmp_path / name))


@pytest.mark.parametrize(
    "snapshot",
    (RUN_PRESCRIPTION, INTERVAL_PRESCRIPTION, BRICK_PRESCRIPTION),
)
def test_acquires_continuous_intervals_and_brick_round_trip(tmp_path, snapshot):
    acquired = service(tmp_path).acquire(CommunicatedPrescription(snapshot))
    assert acquired == snapshot
    assert acquired.components == snapshot.components
    assert acquired.transitions == snapshot.transitions


def test_preserves_all_authored_dimensions_window_provenance_audit_and_policies(tmp_path):
    substitution = AllowedSubstitution(
        Discipline.BIKE, Environment.INDOOR, Mode.INDOOR_TRAINER,
        PolicyRef("substitution", "1.0.0-draft"),
    )
    component = replace(
        RUN_PRESCRIPTION.components[0],
        allowed_substitutions=(substitution,),
        quantity=replace(
            RUN_PRESCRIPTION.components[0].quantity,
            target=PrescribedTarget(None, 50, 70),
        ),
    )
    snapshot = replace(
        RUN_PRESCRIPTION,
        components=(component,),
        provenance=Provenance("synthetic-communication", NOW),
        audit=PrescriptionAudit("original-plan-7"),
    )
    acquired = service(tmp_path).acquire(CommunicatedPrescription(snapshot))
    assert acquired == snapshot
    assert acquired.components[0].quantity.target.value is None
    assert acquired.components[0].allowed_substitutions == (substitution,)
    assert acquired.scheduled_window.timezone == "UTC"
    assert acquired.provenance.source == "synthetic-communication"
    assert acquired.audit.original_plan_snapshot_id == "original-plan-7"


def test_defensively_copies_input_and_result_is_deeply_immutable(tmp_path):
    criteria = {"ranges": [1, 2], "labels": {"steady"}}
    objective = replace(RUN_PRESCRIPTION.objective, success_criteria=(criteria,))
    source = replace(RUN_PRESCRIPTION, objective=objective)
    acquired = service(tmp_path).acquire(CommunicatedPrescription(source))

    criteria["ranges"].append(3)
    criteria["labels"].add("changed")
    assert acquired.objective.success_criteria[0]["ranges"] == (1, 2)
    assert acquired.objective.success_criteria[0]["labels"] == frozenset({"steady"})
    with pytest.raises(FrozenInstanceError):
        acquired.workout_id = "changed"
    with pytest.raises(TypeError):
        acquired.objective.success_criteria[0]["new"] = True
    with pytest.raises(AttributeError):
        acquired.objective.success_criteria[0]["ranges"].append(3)


@pytest.mark.parametrize(
    "invalid",
    (
        replace(RUN_PRESCRIPTION, components=()),
        replace(
            RUN_PRESCRIPTION,
            matching_policy=PolicyRef("maintain-plan-matching", None),
        ),
        replace(
            RUN_PRESCRIPTION,
            components=(replace(
                RUN_PRESCRIPTION.components[0],
                quantity=replace(RUN_PRESCRIPTION.components[0].quantity, target=None),
            ),),
        ),
        replace(RUN_PRESCRIPTION, communicated_at=datetime(2026, 1, 1, 8)),
    ),
)
def test_invalid_snapshot_is_rejected_before_any_write(tmp_path, invalid):
    path = tmp_path / "invalid.db"
    with pytest.raises(ValueError):
        PrescriptionSnapshotService(MaintainPlanRepository(path)).acquire(
            CommunicatedPrescription(invalid)
        )
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM maintain_plan_prescription_snapshots"
        ).fetchone() == (0,)


def test_retry_is_idempotent_but_changed_content_conflicts(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "append-only.db")
    snapshot_service = PrescriptionSnapshotService(repository)
    first = snapshot_service.acquire(CommunicatedPrescription(RUN_PRESCRIPTION))
    retry = replace(
        RUN_PRESCRIPTION,
        communicated_at=NOW.replace(hour=9),
        provenance=replace(
            RUN_PRESCRIPTION.provenance,
            captured_at=NOW.replace(hour=9),
        ),
    )
    assert snapshot_service.acquire(CommunicatedPrescription(retry)) == first

    changed_duplicate = replace(RUN_PRESCRIPTION, workout_id="different")
    with pytest.raises(PrescriptionSnapshotConflictError):
        snapshot_service.acquire(CommunicatedPrescription(changed_duplicate))
    assert repository.get_prescription_snapshot(first.prescription_snapshot_id) == first

    second = replace(
        RUN_PRESCRIPTION,
        prescription_snapshot_id="snapshot-2",
        decision_id="decision-2",
        communicated_at=NOW.replace(hour=9),
    )
    assert snapshot_service.acquire(CommunicatedPrescription(second)) == second
    assert repository.get_prescription_snapshot("snapshot-1") == first


def test_same_decision_id_with_a_different_snapshot_id_conflicts(tmp_path):
    snapshot_service = service(tmp_path)
    snapshot_service.acquire(CommunicatedPrescription(RUN_PRESCRIPTION))
    changed = replace(
        RUN_PRESCRIPTION,
        prescription_snapshot_id="alternate-id",
    )
    with pytest.raises(PrescriptionSnapshotConflictError):
        snapshot_service.acquire(CommunicatedPrescription(changed))


def _concurrent_acquire(path, snapshots):
    MaintainPlanRepository(path)
    barrier = Barrier(len(snapshots))

    def acquire(snapshot):
        snapshot_service = PrescriptionSnapshotService(MaintainPlanRepository(path))
        barrier.wait()
        return snapshot_service.acquire(CommunicatedPrescription(snapshot))

    with ThreadPoolExecutor(max_workers=len(snapshots)) as executor:
        futures = [executor.submit(acquire, snapshot) for snapshot in snapshots]
        results = []
        errors = []
        for future in futures:
            try:
                results.append(future.result(timeout=10))
            except Exception as error:  # assertions below inspect concurrent outcomes
                errors.append(error)
    return results, errors


def test_concurrent_different_snapshots_serialize_by_decision_id(tmp_path):
    path = tmp_path / "concurrent-conflict.db"
    changed = replace(
        RUN_PRESCRIPTION,
        prescription_snapshot_id="concurrent-alternate",
        workout_id="different-workout",
    )

    results, errors = _concurrent_acquire(path, (RUN_PRESCRIPTION, changed))

    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], PrescriptionSnapshotConflictError)
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM maintain_plan_prescription_snapshots "
            "WHERE decision_id = ?", (RUN_PRESCRIPTION.decision_id,),
        ).fetchone() == (1,)


def test_concurrent_equivalent_retries_are_idempotent(tmp_path):
    path = tmp_path / "concurrent-retry.db"
    retry = replace(
        RUN_PRESCRIPTION,
        communicated_at=NOW.replace(hour=9),
        provenance=replace(RUN_PRESCRIPTION.provenance, captured_at=NOW.replace(hour=9)),
    )

    results, errors = _concurrent_acquire(path, (RUN_PRESCRIPTION, retry))

    assert errors == []
    assert len(results) == 2
    assert results[0] == results[1]
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM maintain_plan_prescription_snapshots"
        ).fetchone() == (1,)


def test_preexisting_duplicate_decision_id_is_rejected_without_arbitrary_lookup(tmp_path):
    path = tmp_path / "ambiguous.db"
    repository = MaintainPlanRepository(path)
    repository.create_prescription_snapshot(RUN_PRESCRIPTION)
    repository.create_prescription_snapshot(replace(
        RUN_PRESCRIPTION, prescription_snapshot_id="duplicate-snapshot",
    ))

    with pytest.raises(PrescriptionSnapshotConflictError, match="multiple .* decision_id"):
        PrescriptionSnapshotService(repository).acquire(
            CommunicatedPrescription(RUN_PRESCRIPTION)
        )


def test_conflict_rolls_back_and_releases_transaction_lock(tmp_path):
    path = tmp_path / "conflict-rollback.db"
    repository = MaintainPlanRepository(path)
    snapshot_service = PrescriptionSnapshotService(repository)
    snapshot_service.acquire(CommunicatedPrescription(RUN_PRESCRIPTION))

    with pytest.raises(PrescriptionSnapshotConflictError):
        snapshot_service.acquire(CommunicatedPrescription(replace(
            RUN_PRESCRIPTION,
            prescription_snapshot_id="conflicting-snapshot",
            workout_id="conflicting-workout",
        )))

    subsequent = replace(
        RUN_PRESCRIPTION,
        prescription_snapshot_id="subsequent-snapshot",
        decision_id="subsequent-decision",
    )
    assert PrescriptionSnapshotService(MaintainPlanRepository(path)).acquire(
        CommunicatedPrescription(subsequent)
    ) == subsequent
    with sqlite3.connect(path, timeout=0) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()
        assert connection.execute(
            "SELECT count(*) FROM maintain_plan_prescription_snapshots"
        ).fetchone() == (2,)


def test_sqlite_persistence_failure_leaves_no_partial_snapshot(tmp_path):
    path = tmp_path / "failed-write.db"
    repository = MaintainPlanRepository(path)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TRIGGER reject_snapshot BEFORE INSERT ON "
            "maintain_plan_prescription_snapshots BEGIN SELECT RAISE(ABORT, 'rejected'); END"
        )

    with pytest.raises(sqlite3.IntegrityError, match="rejected"):
        PrescriptionSnapshotService(repository).acquire(
            CommunicatedPrescription(RUN_PRESCRIPTION)
        )
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM maintain_plan_prescription_snapshots"
        ).fetchone() == (0,)


def test_reopen_returns_identical_canonical_snapshot(tmp_path):
    path = tmp_path / "reopen.db"
    service(tmp_path, "reopen.db").acquire(CommunicatedPrescription(INTERVAL_PRESCRIPTION))
    assert MaintainPlanRepository(path).get_prescription_snapshot(
        INTERVAL_PRESCRIPTION.prescription_snapshot_id
    ) == INTERVAL_PRESCRIPTION


def test_requires_explicit_communication_wrapper_and_has_no_runtime_imports():
    with pytest.raises(TypeError):
        PrescriptionSnapshotService(object()).acquire(RUN_PRESCRIPTION)  # type: ignore[arg-type]

    backend = Path(__file__).parents[2] / "backend"
    runtime_files = [path for path in backend.rglob("*.py") if "maintain_plan" not in path.parts]
    module = "backend.maintain_plan." + "prescription_snapshot_service"
    assert not [path for path in runtime_files if module in path.read_text(encoding="utf-8")]
