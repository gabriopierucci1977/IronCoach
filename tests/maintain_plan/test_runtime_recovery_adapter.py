from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.maintain_plan.runtime_recovery_adapter import (
    RuntimeRecoveryAdapterError,
    build_recovery_assessment,
    provide_runtime_stability_from_recovery_records,
)
from backend.importers.garmin_recovery_adapter import GarminRecoveryAdapter
from backend.maintain_plan.stability_models import (
    ActualSessionBoundary,
    CategoryMissingness,
    GeneralStabilityInput,
    ProvenanceRef,
    RecoveryCategory,
    VersionedArtifactRef,
)
from tests.maintain_plan.test_general_stability_service import make_input


def _record(**overrides):
    value = {
        "source": "garmin",
        "source_id": "garmin-recovery:2026-01-01",
        "date": "2026-01-01",
        "observed_at": "2026-01-01T06:00:00Z",
        "assessed_at": "2026-01-01T06:05:00Z",
        "training_readiness": 72,
    }
    value.update(overrides)
    return value


def _context():
    value = make_input()
    value = replace(
        value,
        prescription_binding=replace(value.prescription_binding, baseline_assessment_ref=None),
        baseline_assessment=None,
    )
    provenance = value.provenance_ref
    return value, provenance


def test_adapter_keeps_numeric_training_readiness_out_of_category():
    assessment = build_recovery_assessment(_record(), subject_ref="athlete")
    assert assessment.category is None
    assert assessment.category_missingness is CategoryMissingness.MISSING
    assert assessment.missing_fields == ("candidate_set.candidates[].category",)


def test_adapter_accepts_only_explicit_category():
    assessment = build_recovery_assessment(
        _record(category="LOW"),
        subject_ref="athlete",
    )
    assert assessment.category is RecoveryCategory.LOW
    assert assessment.category_missingness is CategoryMissingness.NOT_MISSING


def test_adapter_rejects_unknown_category():
    with pytest.raises(RuntimeRecoveryAdapterError, match="one of LOW"):
        build_recovery_assessment(_record(category="GOOD"), subject_ref="athlete")


def test_adapter_rejects_missing_explicit_timestamp():
    with pytest.raises(RuntimeRecoveryAdapterError) as error:
        build_recovery_assessment(_record(observed_at=None), subject_ref="athlete")
    assert error.value.code == "INPUT_MISSING"


def test_current_garmin_daily_shape_is_rejected_until_timestamp_is_explicit():
    daily = GarminRecoveryAdapter.convert(date="2026-01-01", training_readiness={"score": 72})
    with pytest.raises(RuntimeRecoveryAdapterError) as error:
        build_recovery_assessment(daily, subject_ref="athlete")
    assert error.value.code == "INPUT_MISSING"


def test_adapter_rejects_foreign_subject_claim():
    with pytest.raises(RuntimeRecoveryAdapterError, match="subject_ref"):
        build_recovery_assessment(_record(subject_ref="other-athlete"), subject_ref="athlete")


def test_adapter_runs_pure_provider_and_reports_missing_dimensions():
    value, provenance = _context()
    result = provide_runtime_stability_from_recovery_records(
        prescription_binding=value.prescription_binding,
        actual_session_boundary=value.actual_session_boundary,
        records=[_record()],
        captured_at=value.evaluated_at,
        evaluated_at=value.evaluated_at,
        provenance_ref=provenance,
        evaluation_id="runtime-recovery-1",
    )
    assert result.evaluation.evaluation_id == "runtime-recovery-1"
    assert result.evaluation.recovery_result.value == "INSUFFICIENT_DATA"
    assert "baseline_assessment" in result.evaluation.missing_fields
    assert "reported_problems_projection" in result.evaluation.missing_fields
    assert "candidate_set.candidates" not in result.evaluation.missing_fields


def test_adapter_is_deterministic_for_same_input():
    value, provenance = _context()
    kwargs = dict(
        prescription_binding=value.prescription_binding,
        actual_session_boundary=value.actual_session_boundary,
        records=[_record()],
        captured_at=value.evaluated_at,
        evaluated_at=value.evaluated_at,
        provenance_ref=provenance,
        evaluation_id="runtime-recovery-1",
    )
    assert provide_runtime_stability_from_recovery_records(**kwargs).evaluation == provide_runtime_stability_from_recovery_records(**kwargs).evaluation


def test_adapter_rejects_naive_runtime_context_timestamp():
    value, provenance = _context()
    with pytest.raises(RuntimeRecoveryAdapterError, match="timezone-aware"):
        provide_runtime_stability_from_recovery_records(
            prescription_binding=value.prescription_binding,
            actual_session_boundary=value.actual_session_boundary,
            records=[_record()],
            captured_at=datetime(2026, 10, 10, 7, 0),
            evaluated_at=value.evaluated_at,
            provenance_ref=provenance,
            evaluation_id="runtime-recovery-1",
        )
