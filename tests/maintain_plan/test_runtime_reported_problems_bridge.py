"""End-to-end opt-in read of an already persisted reported-problems projection."""

import sqlite3
from dataclasses import replace
from datetime import timedelta

import pytest

from backend.maintain_plan.repository import MaintainPlanRepository
from backend.maintain_plan import runtime_reported_problems_bridge as projection_bridge
from backend.maintain_plan.runtime_recovery_adapter import (
    RuntimeRecoveryAdapterError,
    provide_runtime_stability_from_prescription_baseline,
    provide_runtime_stability_from_recovery_records,
)
from backend.maintain_plan.runtime_reported_problems_bridge import (
    ReportedProblemsRuntimeBridgeError,
    attach_persisted_reported_problems_projection,
)
from backend.maintain_plan.stability_models import (
    EventBoundary, ReportedProblemsEventWindow, StabilityResult,
)
from tests.maintain_plan.fixtures import NOW, RUN_SESSION
from tests.maintain_plan.test_general_stability_service import make_input
from tests.maintain_plan.test_recovery_baseline_capture import baseline as make_baseline


def _runtime_kwargs():
    context = make_input()
    return dict(
        prescription_binding=replace(context.prescription_binding, baseline_assessment_ref=None),
        actual_session_boundary=context.actual_session_boundary,
        records=[], captured_at=context.evaluated_at,
        evaluated_at=context.evaluated_at,
        provenance_ref=context.provenance_ref,
        evaluation_id="reported-runtime",
    )


def _store_projection(tmp_path, *, context=None, projection=None):
    context = context or make_input()
    projection = projection or context.reported_problems_projection
    path = tmp_path / "reported.db"
    repo = MaintainPlanRepository(path)
    repo.create_actual_session(replace(
        RUN_SESSION, session_id=context.actual_session_boundary.actual_session_ref.artifact_id,
        subject_ref=projection.subject_ref,
    ))
    repo.acquire_reported_problems_projection(projection)
    return path, projection


def test_disabled_runtime_never_reads_or_creates_database(tmp_path, monkeypatch):
    def fail_repository(*args, **kwargs):
        raise AssertionError("disabled wiring must never open SQLite")
    monkeypatch.setattr(projection_bridge, "MaintainPlanRepository", fail_repository)
    path = tmp_path / "does-not-exist.db"
    result = provide_runtime_stability_from_recovery_records(
        **_runtime_kwargs(),
        reported_problems_projection_id="projection",
        projection_database_path=path,
    )
    assert result.stability_input.reported_problems_projection is None
    assert result.evaluation.reported_problems.stability_result is StabilityResult.INSUFFICIENT_DATA
    assert not path.exists()


def test_enabled_runtime_uses_exact_projection_after_repository_restart(tmp_path):
    path, projection = _store_projection(tmp_path)
    result = provide_runtime_stability_from_recovery_records(
        **_runtime_kwargs(),
        enable_reported_problems_projection=True,
        reported_problems_projection_id=projection.projection_id,
        projection_database_path=path,
    )
    assert result.stability_input.reported_problems_projection == projection
    assert result.evaluation.reported_problems.stability_result is StabilityResult.STABLE
    assert result.evaluation.reported_problems.projection_ref.projection_id == projection.projection_id
    # A second call constructs a new repository and produces the same answer.
    assert provide_runtime_stability_from_recovery_records(
        **_runtime_kwargs(),
        enable_reported_problems_projection=True,
        reported_problems_projection_id=projection.projection_id,
        projection_database_path=path,
    ) == result


def test_enabled_baseline_bridge_uses_same_persisted_projection(tmp_path):
    captured = make_baseline()
    context = make_input()
    boundary = replace(
        context.actual_session_boundary,
        subject_ref=captured.binding.subject_ref,
        session_end=NOW + timedelta(hours=2),
    )
    evaluated = NOW + timedelta(hours=8)
    projection = replace(
        context.reported_problems_projection,
        subject_ref=captured.binding.subject_ref,
        event_window=ReportedProblemsEventWindow(
            boundary.session_end, EventBoundary.EXCLUSIVE,
            evaluated, EventBoundary.INCLUSIVE,
        ),
        checked_through_at=evaluated,
    )
    path, projection = _store_projection(
        tmp_path, context=replace(context, actual_session_boundary=boundary), projection=projection,
    )
    result = provide_runtime_stability_from_prescription_baseline(
        baseline=captured, actual_session_boundary=boundary,
        records=[], captured_at=evaluated, evaluated_at=evaluated,
        provenance_ref=context.provenance_ref, evaluation_id="baseline-with-projection",
        enable_reported_problems_projection=True,
        reported_problems_projection_id=projection.projection_id,
        projection_database_path=path,
    )
    assert result.stability_input.baseline_assessment == captured.assessment
    assert result.evaluation.reported_problems.stability_result is StabilityResult.STABLE


def test_missing_projection_and_database_fail_closed_without_creating_files(tmp_path):
    path = tmp_path / "absent.db"
    for overrides in (
        {"projection_database_path": path},
        {"reported_problems_projection_id": "projection"},
        {"reported_problems_projection_id": "projection", "projection_database_path": path},
    ):
        with pytest.raises(RuntimeRecoveryAdapterError):
            provide_runtime_stability_from_recovery_records(
                **_runtime_kwargs(), enable_reported_problems_projection=True, **overrides,
            )
    assert not path.exists()
    path, _ = _store_projection(tmp_path)
    with pytest.raises(RuntimeRecoveryAdapterError, match="not found"):
        provide_runtime_stability_from_recovery_records(
            **_runtime_kwargs(), enable_reported_problems_projection=True,
            reported_problems_projection_id="unknown", projection_database_path=path,
        )


def test_foreign_owner_or_session_is_never_attached(tmp_path):
    path, projection = _store_projection(tmp_path)
    kwargs = _runtime_kwargs()
    foreign_owner = replace(
        kwargs["prescription_binding"], subject_ref="foreign-athlete",
    )
    with pytest.raises(RuntimeRecoveryAdapterError, match="ownership"):
        provide_runtime_stability_from_recovery_records(
            **{**kwargs, "prescription_binding": foreign_owner,
               "actual_session_boundary": replace(kwargs["actual_session_boundary"],
                                                   subject_ref="foreign-athlete")},
            enable_reported_problems_projection=True,
            reported_problems_projection_id=projection.projection_id,
            projection_database_path=path,
        )
    other_session = replace(
        kwargs["actual_session_boundary"],
        actual_session_ref=replace(projection.actual_session_ref, artifact_id="another-session"),
    )
    with pytest.raises(RuntimeRecoveryAdapterError, match="exact actual session"):
        provide_runtime_stability_from_recovery_records(
            **{**kwargs, "actual_session_boundary": other_session},
            enable_reported_problems_projection=True,
            reported_problems_projection_id=projection.projection_id,
            projection_database_path=path,
        )


def test_corrupt_stored_metadata_and_stale_window_are_not_promoted(tmp_path):
    context = make_input()
    old = replace(
        context.reported_problems_projection,
        event_window=replace(context.reported_problems_projection.event_window,
                             end_at=context.evaluated_at - timedelta(minutes=1)),
    )
    path, projection = _store_projection(tmp_path, projection=old)
    result = provide_runtime_stability_from_recovery_records(
        **_runtime_kwargs(), enable_reported_problems_projection=True,
        reported_problems_projection_id=projection.projection_id,
        projection_database_path=path,
    )
    assert result.evaluation.reported_problems.stability_result is StabilityResult.INSUFFICIENT_DATA
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE maintain_plan_reported_problems_projections SET result='ISSUE_REPORTED' "
            "WHERE projection_id=?", (projection.projection_id,),
        )
    with pytest.raises(RuntimeRecoveryAdapterError, match="metadata"):
        provide_runtime_stability_from_recovery_records(
            **_runtime_kwargs(), enable_reported_problems_projection=True,
            reported_problems_projection_id=projection.projection_id,
            projection_database_path=path,
        )


def test_bridge_rejects_replacing_an_existing_projection(tmp_path):
    path, projection = _store_projection(tmp_path)
    with pytest.raises(ReportedProblemsRuntimeBridgeError, match="already has"):
        attach_persisted_reported_problems_projection(
            make_input(), enabled=True, projection_id=projection.projection_id,
            database_path=path,
        )


def test_invalid_context_is_rejected_before_repository_access(tmp_path, monkeypatch):
    def fail_repository(*args, **kwargs):
        raise AssertionError("invalid input must never open SQLite")
    monkeypatch.setattr(projection_bridge, "MaintainPlanRepository", fail_repository)
    value = replace(make_input(projection=False), prescription_binding=None)
    with pytest.raises(ReportedProblemsRuntimeBridgeError, match="prescription_binding"):
        attach_persisted_reported_problems_projection(
            value, enabled=True, projection_id="projection",
            database_path=tmp_path / "ignored.db",
        )
