"""Opt-in capture of an explicit recovery result used by a prescription.

The caller declares the result already used, its source owner and timestamps.
No new analysis, latest-record lookup, network call or numeric inference occurs.
"""

from __future__ import annotations

import json

from .general_stability_service import recovery_assessment_ref
from .models import PrescriptionSnapshot
from .recovery_baseline_models import (
    PrescriptionRecoveryBaseline, RECOVERY_ANALYZER_REF, validate_recovery_baseline,
)
from .repository import MaintainPlanRepository
from .stability_models import (
    CategoryMissingness, PrescriptionBaselineBinding, RecoveryAssessment,
    RecoveryCategory, STABILITY_CONTRACT_VERSION, VersionedArtifactRef,
)
from .stability_validators import validate_artifact_ref, validate_provenance
from .validators import validate_prescription


class RecoveryBaselineCaptureError(ValueError):
    def __init__(self, errors, *, code="INPUT_INVALID"):
        self.code = code
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


def build_prescription_recovery_baseline(
    *, snapshot, analyzer_result, source_subject_ref, observation_ref,
    assessment_id, observed_at, assessed_at, captured_at, decision_ref,
    baseline_use_attestation_ref, assessment_provenance_ref, binding_provenance_ref,
) -> PrescriptionRecoveryBaseline:
    """Freeze the exact analyzer output and explicit evidence used for a decision."""
    if type(snapshot) is not PrescriptionSnapshot:
        raise RecoveryBaselineCaptureError(("snapshot must be a PrescriptionSnapshot",))
    errors = list(validate_prescription(snapshot))
    errors.extend(validate_artifact_ref(observation_ref, "observation_ref"))
    errors.extend(validate_provenance(assessment_provenance_ref, "assessment_provenance_ref"))
    errors.extend(validate_provenance(binding_provenance_ref, "binding_provenance_ref"))
    errors.extend(validate_artifact_ref(decision_ref, "decision_ref"))
    errors.extend(validate_artifact_ref(baseline_use_attestation_ref, "baseline_use_attestation_ref"))
    if source_subject_ref != snapshot.subject_ref:
        errors.append("source subject must equal snapshot ownership")
    if errors:
        raise RecoveryBaselineCaptureError(errors)
    if type(analyzer_result) is not dict:
        raise RecoveryBaselineCaptureError(("analyzer_result must be an explicit dictionary",))
    level = analyzer_result.get("level")
    if level is None:
        raise RecoveryBaselineCaptureError(("analyzer_result.level is required",), code="INPUT_MISSING")
    if type(level) is not str or level not in ("LOW", "MODERATE", "HIGH", "CRITICAL", "UNKNOWN"):
        raise RecoveryBaselineCaptureError(("analyzer_result.level is unsupported",))
    if level == "UNKNOWN":
        category, missingness = None, CategoryMissingness.NOT_ASSESSABLE
        missing_fields = ("baseline_assessment.category",)
    else:
        category, missingness = RecoveryCategory(level), CategoryMissingness.NOT_MISSING
        missing_fields = ()
    try:
        output_json = json.dumps(analyzer_result, allow_nan=False, ensure_ascii=False,
                                 sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise RecoveryBaselineCaptureError(("analyzer_result must be finite JSON data",)) from error
    assessment = RecoveryAssessment(
        assessment_id=assessment_id, contract_version=STABILITY_CONTRACT_VERSION,
        analyzer_ref=RECOVERY_ANALYZER_REF, subject_ref=snapshot.subject_ref,
        observed_at=observed_at, assessed_at=assessed_at,
        category=category, category_missingness=missingness,
        evidence_refs=(observation_ref,), provenance_ref=assessment_provenance_ref,
        missing_fields=missing_fields,
    )
    binding = PrescriptionBaselineBinding(
        prescription_snapshot_ref=VersionedArtifactRef(
            "prescription-snapshot", snapshot.prescription_snapshot_id, snapshot.contract_version),
        decision_ref=decision_ref, subject_ref=snapshot.subject_ref,
        prescription_communicated_at=snapshot.communicated_at,
        baseline_assessment_ref=recovery_assessment_ref(assessment),
        baseline_use_attestation_ref=baseline_use_attestation_ref,
        provenance_ref=binding_provenance_ref,
    )
    value = PrescriptionRecoveryBaseline(binding, assessment, output_json, captured_at)
    errors = validate_recovery_baseline(value, snapshot)
    if errors:
        raise RecoveryBaselineCaptureError(errors)
    return value


class RuntimeRecoveryBaselineCapture:
    def __init__(self, repository_factory=MaintainPlanRepository):
        self._repository_factory = repository_factory

    def capture(self, *, enabled=False, database_path=None, **inputs):
        """Validate before opening SQLite; disabled calls have no side effects."""
        if enabled is not True:
            return None
        value = build_prescription_recovery_baseline(**inputs)
        if database_path is None:
            raise RecoveryBaselineCaptureError(("database_path is required",), code="INPUT_MISSING")
        repository = self._repository_factory(database_path)
        return repository.acquire_recovery_baseline(value)
