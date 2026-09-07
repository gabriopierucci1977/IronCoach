"""Synthetic tests for explicit communicated-prescription acquisition."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime
from pathlib import Path
import sqlite3

import pytest

from backend.maintain_plan.models import (
    AllowedSubstitution, Composition, Discipline, Environment, Mode,
    PolicyRef, PrescribedTarget, PrescriptionAudit, Provenance,
)
from backend.maintain_plan.prescription_snapshot_service import (
    CommunicatedPrescription, PrescriptionSnapshotService,
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


def test_duplicate_does_not_overwrite_and_successive_communications_are_distinct(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "append-only.db")
    snapshot_service = PrescriptionSnapshotService(repository)
    first = snapshot_service.acquire(CommunicatedPrescription(RUN_PRESCRIPTION))
    changed_duplicate = replace(RUN_PRESCRIPTION, workout_id="different")
    with pytest.raises(sqlite3.IntegrityError):
        snapshot_service.acquire(CommunicatedPrescription(changed_duplicate))
    assert repository.get_prescription_snapshot(first.prescription_snapshot_id) == first

    second = replace(
        RUN_PRESCRIPTION,
        prescription_snapshot_id="snapshot-2",
        communicated_at=NOW.replace(hour=9),
    )
    assert snapshot_service.acquire(CommunicatedPrescription(second)) == second
    assert repository.get_prescription_snapshot("snapshot-1") == first


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
