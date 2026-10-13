"""Opt-in lookup of one persisted projection for a runtime stability input.

The caller chooses the projection ID. No latest-projection discovery or event
interpretation takes place here; the stability provider remains pure.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .repository import MaintainPlanRepository
from .stability_models import GeneralStabilityInput
from .stability_validators import validate_general_stability_input


class ReportedProblemsRuntimeBridgeError(ValueError):
    def __init__(self, errors, *, code="INPUT_INVALID"):
        self.code = code
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


def attach_persisted_reported_problems_projection(
    stability_input: GeneralStabilityInput,
    *,
    enabled: bool = False,
    projection_id: str | None = None,
    database_path: str | Path | None = None,
) -> GeneralStabilityInput:
    """Attach exactly one caller-selected projection; disabled calls do no I/O."""
    if enabled is not True:
        return stability_input
    if type(stability_input) is not GeneralStabilityInput:
        raise ReportedProblemsRuntimeBridgeError(
            ("stability_input must be a GeneralStabilityInput",)
        )
    if stability_input.reported_problems_projection is not None:
        raise ReportedProblemsRuntimeBridgeError(
            ("stability_input already has a reported-problems projection",)
        )
    errors = validate_general_stability_input(stability_input)
    if errors:
        raise ReportedProblemsRuntimeBridgeError(errors)
    if type(projection_id) is not str or not projection_id.strip():
        raise ReportedProblemsRuntimeBridgeError(
            ("projection_id is required",), code="INPUT_MISSING"
        )
    if (database_path is None or not isinstance(database_path, (str, Path))
            or not str(database_path).strip()):
        raise ReportedProblemsRuntimeBridgeError(
            ("database_path is required",), code="INPUT_MISSING"
        )
    if not Path(database_path).is_file():
        raise ReportedProblemsRuntimeBridgeError(
            ("projection database does not exist",), code="INPUT_MISSING"
        )

    # The repository checks row metadata, the stored payload and the ownership
    # of its persisted session. Never substitute a projection from another run.
    projection = MaintainPlanRepository(database_path).get_reported_problems_projection(projection_id)
    if projection is None:
        raise ReportedProblemsRuntimeBridgeError(
            ("projection_id was not found",), code="INPUT_MISSING"
        )
    if projection.subject_ref != stability_input.prescription_binding.subject_ref:
        raise ReportedProblemsRuntimeBridgeError(
            ("reported-problems projection ownership does not match the prescription",)
        )
    if projection.actual_session_ref != stability_input.actual_session_boundary.actual_session_ref:
        raise ReportedProblemsRuntimeBridgeError(
            ("reported-problems projection does not match the exact actual session",)
        )
    attached = replace(stability_input, reported_problems_projection=projection)
    errors = validate_general_stability_input(attached)
    if errors:
        raise ReportedProblemsRuntimeBridgeError(errors)
    return attached
