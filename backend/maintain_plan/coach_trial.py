"""Isolated, explicitly hypothetical coach review built from archived sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .models import (
    ActualSession, Applicability, BlockType, Composition, Discipline,
    EvaluationWindow, IntensityContract, IntensityMethod, Objective,
    ObjectiveEvaluability, PlannedBlock, PlannedComponent, PolicyRef,
    PrescribedTarget, PrescriptionAudit, PrescriptionSnapshot, Provenance,
    QuantityContract, QuantityMetric, RecoveryContract, Requiredness,
    ScheduledWindow, SessionType, StructureContract, SupportStatus, DoseContract,
)
from .repository import MaintainPlanRepository
from .validators import validate_prescription


POLICY_VERSION = "1.0.0-draft"


@dataclass(frozen=True)
class TrialActivity:
    session_id: str
    start: datetime
    sports: tuple[str, ...]
    source: str


def available_activities(archive_path: str | Path, subject_ref: str) -> tuple[TrialActivity, ...]:
    """Read supported historical activities without writing to the archive."""
    repository = MaintainPlanRepository(archive_path)
    supported = {Discipline.SWIM, Discipline.BIKE, Discipline.RUN}
    result = []
    for session in repository.list_actual_sessions(subject_ref):
        sports = tuple(dict.fromkeys(
            component.discipline.value for component in session.components
            if component.discipline in supported))
        if not sports:
            continue
        sources = sorted({source.source for source in session.source_activities})
        result.append(TrialActivity(session.session_id, session.start, sports,
                                    ", ".join(sources) or "Garmin"))
    return tuple(sorted(result, key=lambda item: (item.start, item.session_id), reverse=True))


def _policy(name: str) -> PolicyRef:
    return PolicyRef(name, POLICY_VERSION)


def hypothetical_prescription(subject_ref: str, session: ActualSession, *,
                              sport: str, duration_minutes: float,
                              rpe: float, now: datetime | None = None,
                              identifier: str | None = None) -> PrescriptionSnapshot:
    """Create a coach-authored trial contract; observed metrics are never inputs."""
    discipline = Discipline(sport)
    if duration_minutes <= 0 or not 1 <= rpe <= 10:
        raise ValueError("durata e RPE del piano devono essere positivi (RPE 1–10)")
    timestamp = now or datetime.now(timezone.utc)
    identifier = identifier or uuid4().hex
    quantity = PrescribedTarget(duration_minutes)
    intensity = PrescribedTarget(rpe)
    component = PlannedComponent(
        "main", 0, discipline, None, None, Requiredness.REQUIRED,
        SupportStatus.SUPPORTED, _policy("maintain-plan-evaluator-capability"),
        Applicability.REQUIRED, (), _policy("maintain-plan-sport-taxonomy"),
        QuantityContract(Applicability.REQUIRED, QuantityMetric.ACTIVE_DURATION,
                         quantity, "minutes", (), _policy("maintain-plan-quantity"),
                         PolicyRef(None, None)),
        IntensityContract(Applicability.REQUIRED, IntensityMethod.RPE, intensity,
                          "RPE", (), _policy("maintain-plan-continuous-intensity")),
        StructureContract(Applicability.REQUIRED, SessionType.CONTINUOUS,
                          _policy("maintain-plan-structure"), (
            PlannedBlock("main", 0, BlockType.MAIN_SET, Requiredness.REQUIRED,
                         quantity, intensity, IntensityMethod.RPE, "RPE", intensity,
                         EvaluationWindow.WHOLE_BLOCK,
                         _policy("maintain-plan-continuous-intensity"), None,
                         RecoveryContract(Applicability.NOT_APPLICABLE, None), (),
                         _policy("maintain-plan-structure")),)),
        DoseContract(Applicability.REQUIRED, _policy("maintain-plan-dose-matrix"),
                     "quantity-main", "intensity-main"),
    )
    value = PrescriptionSnapshot(
        f"trial-plan-{identifier}", f"trial-workout-{identifier}",
        f"trial-decision-{identifier}", timestamp,
        # The selected activity timestamp only scopes the comparison. Targets above
        # are exclusively coach-authored and are not inferred from this session.
        ScheduledWindow(session.start, session.start, "UTC", False),
        Composition.SINGLE, (component,), (),
        Objective(ObjectiveEvaluability.CONTEXT_ONLY, None,
                  context_text="Scenario di prova ipotetico", policy=PolicyRef(None, None)),
        _policy("maintain-plan-matching"), PolicyRef(None, None),
        Provenance("coach-hypothetical-trial", timestamp), PrescriptionAudit(None),
        subject_ref=subject_ref,
    )
    errors = validate_prescription(value)
    if errors:
        raise ValueError("; ".join(errors))
    return value


def create_trial(archive_path: str | Path, trial_path: str | Path, subject_ref: str,
                 choices: tuple[dict[str, object], ...], *, now: datetime | None = None
                 ) -> MaintainPlanRepository:
    """Copy chosen activities and authored plans into a fresh, separate database."""
    if not choices:
        raise ValueError("scegli almeno un’attività")
    archive = MaintainPlanRepository(archive_path)
    trial_path = Path(trial_path)
    if trial_path.resolve() == Path(archive_path).resolve():
        raise ValueError("l’archivio di prova deve essere separato dall’archivio reale")
    if trial_path.exists():
        trial_path.unlink()
    trial = MaintainPlanRepository(trial_path)
    seen = set()
    for index, choice in enumerate(choices):
        session_id = str(choice["session_id"])
        if session_id in seen:
            raise ValueError("un’attività può essere scelta una sola volta")
        seen.add(session_id)
        session = archive.get_actual_session(session_id)
        if session is None or session.subject_ref != subject_ref:
            raise ValueError("attività non disponibile per l’atleta")
        sport = str(choice["sport"])
        if sport not in {item.discipline.value for item in session.components
                         if item.discipline is not None}:
            raise ValueError("lo sport scelto non corrisponde all’attività selezionata")
        trial.create_actual_session(session)
        trial.create_prescription_snapshot(hypothetical_prescription(
            subject_ref, session, sport=sport,
            duration_minutes=float(choice["duration_minutes"]),
            rpe=float(choice["rpe"]), now=now, identifier=str(index + 1)))
    return trial
