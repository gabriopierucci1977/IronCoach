from dataclasses import replace
from datetime import timedelta

import pytest

from backend.maintain_plan.recovery_baseline_models import (
    RECOVERY_ANALYZER_ARTIFACT,
    RECOVERY_ANALYZER_REF,
    validate_recovery_baseline,
)
from backend.maintain_plan.repository import MaintainPlanRepository
from backend.maintain_plan.runtime_recovery_baseline_capture import (
    RecoveryBaselineCaptureError,
    RuntimeRecoveryBaselineCapture,
    build_prescription_recovery_baseline,
)
from backend.maintain_plan.stability_models import (
    ProvenanceRef, VersionedArtifactRef,
)
from tests.maintain_plan.fixtures import NOW, RUN_PRESCRIPTION


OBSERVATION = VersionedArtifactRef("recovery-observation", "garmin:baseline", "1")
ATTESTATION = VersionedArtifactRef("baseline-use-attestation", "snapshot-1:baseline", "1")
DECISION = VersionedArtifactRef("decision", "decision-1", "1")


def baseline(*, snapshot=RUN_PRESCRIPTION, level="LOW", subject="athlete-1", captured=None):
    return build_prescription_recovery_baseline(
        snapshot=snapshot,
        analyzer_result={
            "level": level,
            "state": "VERDE" if level == "LOW" else "",
            "score": 72 if level == "LOW" else None,
            "sleep_score": 80,
            "reasons": (),
        },
        source_subject_ref=subject,
        observation_ref=OBSERVATION,
        assessment_id="assessment-1",
        observed_at=NOW - timedelta(minutes=10),
        assessed_at=NOW - timedelta(minutes=5),
        captured_at=captured or NOW + timedelta(hours=1),
        decision_ref=DECISION,
        baseline_use_attestation_ref=ATTESTATION,
        assessment_provenance_ref=ProvenanceRef(
            RECOVERY_ANALYZER_ARTIFACT, "recovery-analysis", "garmin:baseline", "1"),
        binding_provenance_ref=ProvenanceRef(
            ATTESTATION, "baseline-capture", "snapshot-1", "1"),
    )


def test_baseline_is_pinned_to_snapshot_and_analyzer_version():
    value = baseline()
    assert validate_recovery_baseline(value, RUN_PRESCRIPTION) == ()
    assert value.assessment.analyzer_ref == RECOVERY_ANALYZER_REF
    assert value.binding.prescription_snapshot_ref.artifact_id == "snapshot-1"


def test_unknown_analyzer_result_remains_not_assessable():
    value = baseline(level="UNKNOWN")
    assert value.assessment.category is None
    assert value.assessment.missing_fields == ("baseline_assessment.category",)


def test_capture_is_disabled_without_constructing_repository():
    class FailRepository:
        def __init__(self, *_):
            raise AssertionError("repository must not be constructed")

    assert RuntimeRecoveryBaselineCapture(FailRepository).capture(enabled=False) is None


def test_capture_round_trip_retry_and_listing(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "baseline.db")
    repository.create_prescription_snapshot(RUN_PRESCRIPTION)
    value = baseline()
    capture = RuntimeRecoveryBaselineCapture(lambda _: repository)
    stored = capture.capture(enabled=True, database_path="ignored", **value_inputs(value))
    assert repository.get_recovery_baseline(value.baseline_id) == stored
    retry = capture.capture(
        enabled=True, database_path="ignored",
        **value_inputs(value, captured=NOW + timedelta(hours=2)),
    )
    assert retry == stored
    assert repository.list_recovery_baselines("athlete-1") == (stored,)


def test_capture_rejects_semantic_retry_for_same_snapshot(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "baseline.db")
    repository.create_prescription_snapshot(RUN_PRESCRIPTION)
    capture = RuntimeRecoveryBaselineCapture(lambda _: repository)
    capture.capture(enabled=True, database_path="ignored", **value_inputs(baseline()))
    with pytest.raises(ValueError, match="different content"):
        capture.capture(enabled=True, database_path="ignored", **value_inputs(baseline(level="HIGH")))


def test_capture_rejects_foreign_subject_and_missing_level():
    with pytest.raises(RecoveryBaselineCaptureError, match="source subject"):
        baseline(subject="other")
    with pytest.raises(RecoveryBaselineCaptureError, match="level is required"):
        build_prescription_recovery_baseline(
            snapshot=RUN_PRESCRIPTION, analyzer_result={}, source_subject_ref="athlete-1",
            observation_ref=OBSERVATION, assessment_id="assessment-1",
            observed_at=NOW - timedelta(minutes=10), assessed_at=NOW - timedelta(minutes=5),
            captured_at=NOW + timedelta(hours=1), decision_ref=DECISION,
            baseline_use_attestation_ref=ATTESTATION,
            assessment_provenance_ref=ProvenanceRef(RECOVERY_ANALYZER_ARTIFACT, "analysis", "x", "1"),
            binding_provenance_ref=ProvenanceRef(ATTESTATION, "capture", "x", "1"),
        )


def value_inputs(value, *, captured=None):
    analyzer = __import__("json").loads(value.analyzer_output_json)
    return {
        "snapshot": RUN_PRESCRIPTION,
        "analyzer_result": analyzer,
        "source_subject_ref": value.binding.subject_ref,
        "observation_ref": value.assessment.evidence_refs[0],
        "assessment_id": value.assessment.assessment_id,
        "observed_at": value.assessment.observed_at,
        "assessed_at": value.assessment.assessed_at,
        "captured_at": captured or value.captured_at,
        "decision_ref": value.binding.decision_ref,
        "baseline_use_attestation_ref": value.binding.baseline_use_attestation_ref,
        "assessment_provenance_ref": value.assessment.provenance_ref,
        "binding_provenance_ref": value.binding.provenance_ref,
    }
