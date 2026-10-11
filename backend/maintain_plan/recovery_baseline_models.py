"""Immutable baseline declaration for the recovery used by one prescription."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from .models import PrescriptionSnapshot
from .stability_models import (
    AnalyzerRef, CategoryMissingness, PrescriptionBaselineBinding,
    RecoveryAssessment, RecoveryAssessmentRef, RecoveryCategory,
    STABILITY_CONTRACT_VERSION, VersionedArtifactRef,
)
from .stability_validators import (
    aware, validate_artifact_ref, validate_assessment, validate_provenance,
)
from .validators import validate_prescription


# Identity of the existing implementation, pinned to its exact source bytes.
# A changed analyzer requires a new explicit version before comparison.
RECOVERY_ANALYZER_SOURCE_SHA256 = "b2b2c181857139ca390adbf538e2053d7e2fbbbb40d3ff594721cf9cd4b7bf42"
RECOVERY_ANALYZER_REF = AnalyzerRef(
    "ironcoach-recovery-analyzer",
    "0.4+sha256:" + RECOVERY_ANALYZER_SOURCE_SHA256,
    "ironcoach-recovery-assessment/0.4",
)
RECOVERY_ANALYZER_ARTIFACT = VersionedArtifactRef(
    "recovery-analyzer", RECOVERY_ANALYZER_REF.analyzer_id,
    RECOVERY_ANALYZER_REF.analyzer_version,
)


@dataclass(frozen=True)
class PrescriptionRecoveryBaseline:
    binding: PrescriptionBaselineBinding
    assessment: RecoveryAssessment
    analyzer_output_json: str
    captured_at: datetime

    @property
    def baseline_id(self) -> str:
        return f"{self.binding.prescription_snapshot_ref.artifact_id}:{self.assessment.assessment_id}"


def validate_recovery_baseline(
    value: object, snapshot: object = None,
) -> tuple[str, ...]:
    """Validate the declaration and optionally its exact persisted snapshot."""
    if type(value) is not PrescriptionRecoveryBaseline:
        return ("baseline must be a PrescriptionRecoveryBaseline",)
    errors = list(validate_assessment(value.assessment, "baseline_assessment"))
    binding, assessment = value.binding, value.assessment
    if type(binding) is not PrescriptionBaselineBinding:
        return tuple(errors + ["binding must be a PrescriptionBaselineBinding"])
    for ref, label, kind in (
        (binding.prescription_snapshot_ref, "snapshot_ref", "prescription-snapshot"),
        (binding.decision_ref, "decision_ref", "decision"),
        (binding.baseline_use_attestation_ref, "attestation_ref", "baseline-use-attestation"),
    ):
        errors.extend(validate_artifact_ref(ref, label))
        if type(ref) is VersionedArtifactRef and ref.artifact_type != kind:
            errors.append(f"{label} must have artifact_type {kind}")
    errors.extend(validate_provenance(binding.provenance_ref, "binding.provenance_ref"))
    if type(binding.subject_ref) is not str or not binding.subject_ref.strip():
        errors.append("binding.subject_ref must be a non-empty string")
    if not aware(binding.prescription_communicated_at):
        errors.append("prescription_communicated_at must be timezone-aware")
    if not aware(value.captured_at):
        errors.append("captured_at must be timezone-aware")
    if (aware(value.captured_at) and aware(binding.prescription_communicated_at) and
            value.captured_at < binding.prescription_communicated_at):
        errors.append("captured_at must not precede prescription communication")
    if not validate_provenance(binding.provenance_ref):
        if binding.provenance_ref.producer != binding.baseline_use_attestation_ref:
            errors.append("binding provenance must identify the explicit baseline-use attestation")
    if type(assessment) is RecoveryAssessment:
        if assessment.contract_version != STABILITY_CONTRACT_VERSION:
            errors.append("baseline stability contract version is unsupported")
        if assessment.analyzer_ref != RECOVERY_ANALYZER_REF:
            errors.append("baseline analyzer version is unsupported")
        if not assessment.evidence_refs:
            errors.append("baseline source evidence is required")
        if assessment.subject_ref != binding.subject_ref:
            errors.append("baseline ownership must agree with binding")
        expected_ref = RecoveryAssessmentRef(
            assessment.assessment_id, assessment.contract_version, assessment.analyzer_ref,
            assessment.subject_ref, assessment.observed_at, assessment.assessed_at,
        )
        if binding.baseline_assessment_ref != expected_ref:
            errors.append("baseline binding ref must equal its exact assessment")
        if not validate_provenance(assessment.provenance_ref):
            if assessment.provenance_ref.producer != RECOVERY_ANALYZER_ARTIFACT:
                errors.append("assessment provenance must identify the pinned recovery analyzer")
        if aware(binding.prescription_communicated_at):
            for timestamp in (assessment.observed_at, assessment.assessed_at):
                if aware(timestamp) and timestamp > binding.prescription_communicated_at:
                    errors.append("baseline timestamps must not follow prescription communication")
        try:
            output = json.loads(value.analyzer_output_json,
                                parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)))
            if type(output) is not dict or type(output.get("level")) is not str:
                raise ValueError("analyzer output must contain an explicit level")
            level = output["level"]
            if level == "UNKNOWN":
                if (assessment.category is not None or
                        assessment.category_missingness is not CategoryMissingness.NOT_ASSESSABLE or
                        assessment.missing_fields != ("baseline_assessment.category",)):
                    errors.append("UNKNOWN recovery must remain explicitly not assessable")
            else:
                if (assessment.category != RecoveryCategory(level) or
                        assessment.category_missingness is not CategoryMissingness.NOT_MISSING or
                        assessment.missing_fields):
                    errors.append("baseline category must equal the explicit analyzer level")
        except (ValueError, TypeError):
            errors.append("baseline analyzer_output_json is invalid")
    if snapshot is not None:
        errors.extend(validate_prescription(snapshot))
        if type(snapshot) is PrescriptionSnapshot:
            if binding.prescription_snapshot_ref != VersionedArtifactRef(
                    "prescription-snapshot", snapshot.prescription_snapshot_id,
                    snapshot.contract_version):
                errors.append("baseline must reference the exact persisted snapshot and version")
            if binding.decision_ref.artifact_id != snapshot.decision_id:
                errors.append("baseline decision must equal the persisted snapshot decision")
            if binding.subject_ref != snapshot.subject_ref:
                errors.append("baseline snapshot ownership must agree")
            if binding.prescription_communicated_at != snapshot.communicated_at:
                errors.append("baseline communication must equal the persisted snapshot timestamp")
    return tuple(errors)
