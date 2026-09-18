"""Pure adapter from explicit runtime fields to a communicated prescription.

The adapter accepts only explicit structured metadata. It never infers an
intensity method from zones, workout names, free text, or legacy analyzers.
Runtime wiring and persistence deliberately remain outside this module.
"""

from __future__ import annotations

from datetime import date, datetime, time
from math import isfinite
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import (
    Applicability,
    BlockType,
    Composition,
    Discipline,
    DoseContract,
    Environment,
    EvaluationWindow,
    IntensityContract,
    IntensityMethod,
    Mode,
    Objective,
    ObjectiveEvaluability,
    PlannedBlock,
    PlannedComponent,
    PolicyRef,
    PrescribedTarget,
    PrescriptionAudit,
    PrescriptionSnapshot,
    Provenance,
    QuantityContract,
    QuantityMetric,
    RecoveryContract,
    Requiredness,
    ScheduledWindow,
    SessionType,
    StructureContract,
    SupportStatus,
)
from .prescription_snapshot_service import CommunicatedPrescription
from .validators import validate_prescription
from .ownership import require_subject_ref


_CAPABILITY_POLICY = PolicyRef(
    "maintain-plan-evaluator-capability",
    "1.0.0-draft",
)
_IDENTITY_POLICY = PolicyRef(
    "maintain-plan-sport-taxonomy",
    "1.0.0-draft",
)
_QUANTITY_POLICY = PolicyRef(
    "maintain-plan-quantity",
    "1.0.0-draft",
)
_INTENSITY_POLICY = PolicyRef(
    "maintain-plan-continuous-intensity",
    "1.0.0-draft",
)
_STRUCTURE_POLICY = PolicyRef(
    "maintain-plan-structure",
    "1.0.0-draft",
)
_DOSE_POLICY = PolicyRef(
    "maintain-plan-dose-matrix",
    "1.0.0-draft",
)
_MATCHING_POLICY = PolicyRef(
    "maintain-plan-matching",
    "1.0.0-draft",
)
_NULL_POLICY = PolicyRef(None, None)

_SUPPORTED_DISCIPLINES = frozenset({
    Discipline.RUN,
    Discipline.BIKE,
    Discipline.SWIM,
})


class RuntimePrescriptionError(ValueError):
    """The runtime data cannot form an authoritative P0 prescription."""


def _required_string(value: dict, name: str) -> str:
    item = value.get(name)
    if type(item) is not str or not item.strip():
        raise RuntimePrescriptionError(
            f"{name} must be an explicit non-empty string"
        )
    return item.strip()


def _optional_enum(value: dict, name: str, enum_type):
    item = value.get(name)
    if item is None:
        return None
    if type(item) is not str or not item.strip():
        raise RuntimePrescriptionError(
            f"{name} must be null or an explicit enum value"
        )
    try:
        return enum_type(item.strip().upper())
    except ValueError as error:
        raise RuntimePrescriptionError(
            f"{name} has an unsupported value"
        ) from error


def _positive_number(value: dict, name: str) -> int | float:
    item = value.get(name)
    if type(item) not in (int, float):
        raise RuntimePrescriptionError(
            f"{name} must be an explicit number"
        )
    if type(item) is float and not isfinite(item):
        raise RuntimePrescriptionError(
            f"{name} must be finite"
        )
    if item <= 0:
        raise RuntimePrescriptionError(
            f"{name} must be positive"
        )
    return item


def _prescribed_target(value: dict, name: str) -> PrescribedTarget:
    item = value.get(name)
    if type(item) is str:
        if not item.strip():
            raise RuntimePrescriptionError(
                f"{name} must not be empty"
            )
    elif type(item) is int:
        pass
    elif type(item) is float:
        if not isfinite(item):
            raise RuntimePrescriptionError(
                f"{name} must be finite"
            )
    else:
        raise RuntimePrescriptionError(
            f"{name} must be an explicit string or number"
        )
    return PrescribedTarget(item)


def _planned_date(value: dict) -> date:
    raw = _required_string(value, "date")
    try:
        result = date.fromisoformat(raw)
    except ValueError as error:
        raise RuntimePrescriptionError(
            "date must use the exact YYYY-MM-DD format"
        ) from error
    if result.isoformat() != raw:
        raise RuntimePrescriptionError(
            "date must use the exact YYYY-MM-DD format"
        )
    return result


def _timezone(value: str) -> ZoneInfo:
    if type(value) is not str or not value.strip():
        raise RuntimePrescriptionError(
            "timezone_name must be an explicit IANA timezone"
        )
    try:
        return ZoneInfo(value.strip())
    except ZoneInfoNotFoundError as error:
        raise RuntimePrescriptionError(
            "timezone_name must be a valid IANA timezone"
        ) from error


def _aware_datetime(value: object) -> datetime:
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise RuntimePrescriptionError(
            "communicated_at must be an exact timezone-aware datetime"
        )
    return value


def build_communicated_prescription(
    training: dict,
    decision: dict,
    *,
    subject_ref: str,
    communicated_at: datetime,
    timezone_name: str,
) -> CommunicatedPrescription:
    """Build the minimal supported continuous prescription.

    P0 accepts only an explicit KEEP_PLAN MAINTAIN_PLAN decision and a
    continuous RUN, BIKE, or SWIM prescription containing an authored
    intensity method, target, and unit.
    """
    if type(training) is not dict:
        raise RuntimePrescriptionError(
            "training must be an exact dict"
        )
    if type(decision) is not dict:
        raise RuntimePrescriptionError(
            "decision must be an exact dict"
        )

    captured_at = _aware_datetime(communicated_at)
    subject = require_subject_ref(subject_ref)
    athlete_timezone = _timezone(timezone_name)

    decision_id = _required_string(decision, "decision_id")
    if _required_string(decision, "primary_intent") != "MAINTAIN_PLAN":
        raise RuntimePrescriptionError(
            "primary_intent must be MAINTAIN_PLAN"
        )
    if _required_string(decision, "strategy") != "KEEP_PLAN":
        raise RuntimePrescriptionError(
            "only KEEP_PLAN prescriptions are supported by this P0 adapter"
        )

    workout_id = _required_string(training, "source_id")
    planned_date = _planned_date(training)

    try:
        discipline = Discipline(
            _required_string(training, "sport").upper()
        )
    except ValueError as error:
        raise RuntimePrescriptionError(
            "sport has an unsupported value"
        ) from error
    if discipline not in _SUPPORTED_DISCIPLINES:
        raise RuntimePrescriptionError(
            "only RUN, BIKE, and SWIM are supported"
        )

    session_type = _required_string(
        training,
        "session_type",
    ).casefold()
    if session_type != SessionType.CONTINUOUS.value:
        raise RuntimePrescriptionError(
            "only an explicit continuous session is supported"
        )

    duration = _positive_number(
        training,
        "duration_minutes",
    )
    intensity_target = _prescribed_target(
        training,
        "intensity",
    )

    try:
        intensity_method = IntensityMethod(
            _required_string(
                training,
                "intensity_method",
            ).upper()
        )
    except ValueError as error:
        raise RuntimePrescriptionError(
            "intensity_method has an unsupported value"
        ) from error

    intensity_unit = _required_string(
        training,
        "intensity_unit",
    )
    environment = _optional_enum(
        training,
        "environment",
        Environment,
    )
    mode = _optional_enum(
        training,
        "mode",
        Mode,
    )

    quantity_target = PrescribedTarget(duration)
    component_id = "primary"
    quantity_ref = f"{component_id}:quantity"
    intensity_ref = f"{component_id}:intensity"

    block = PlannedBlock(
        f"{component_id}:main",
        0,
        BlockType.MAIN_SET,
        Requiredness.REQUIRED,
        quantity_target,
        intensity_target,
        intensity_method,
        intensity_unit,
        intensity_target,
        EvaluationWindow.WHOLE_BLOCK,
        _INTENSITY_POLICY,
        None,
        RecoveryContract(
            Applicability.NOT_APPLICABLE,
            None,
        ),
        (),
        _STRUCTURE_POLICY,
    )

    component = PlannedComponent(
        component_id,
        0,
        discipline,
        environment,
        mode,
        Requiredness.REQUIRED,
        SupportStatus.SUPPORTED,
        _CAPABILITY_POLICY,
        Applicability.REQUIRED,
        (),
        _IDENTITY_POLICY,
        QuantityContract(
            Applicability.REQUIRED,
            QuantityMetric.ACTIVE_DURATION,
            quantity_target,
            "minutes",
            (),
            _QUANTITY_POLICY,
            _NULL_POLICY,
        ),
        IntensityContract(
            Applicability.REQUIRED,
            intensity_method,
            intensity_target,
            intensity_unit,
            (),
            _INTENSITY_POLICY,
        ),
        StructureContract(
            Applicability.REQUIRED,
            SessionType.CONTINUOUS,
            _STRUCTURE_POLICY,
            (block,),
        ),
        DoseContract(
            Applicability.REQUIRED,
            _DOSE_POLICY,
            quantity_ref,
            intensity_ref,
        ),
    )

    start = datetime.combine(
        planned_date,
        time.min,
        athlete_timezone,
    )
    end = datetime.combine(
        planned_date,
        time.max,
        athlete_timezone,
    )

    workout_name = training.get("workout_name")
    if workout_name is not None and (
        type(workout_name) is not str
        or not workout_name.strip()
    ):
        raise RuntimePrescriptionError(
            "workout_name must be null or a non-empty string"
        )

    snapshot = PrescriptionSnapshot(
        f"maintain-plan:{decision_id}",
        workout_id,
        decision_id,
        captured_at,
        ScheduledWindow(
            start,
            end,
            timezone_name.strip(),
            True,
        ),
        Composition.SINGLE,
        (component,),
        (),
        Objective(
            ObjectiveEvaluability.CONTEXT_ONLY,
            None,
            context_text=(
                workout_name.strip()
                if type(workout_name) is str
                else None
            ),
            policy=_NULL_POLICY,
        ),
        _MATCHING_POLICY,
        _NULL_POLICY,
        Provenance(
            "runtime-prescription-capture",
            captured_at,
        ),
        PrescriptionAudit(None),
        subject_ref=subject,
    )

    errors = validate_prescription(snapshot)
    if errors:
        raise RuntimePrescriptionError("; ".join(errors))

    return CommunicatedPrescription(snapshot)
