"""Small coach-facing journey from persisted plan and activities to evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from .execution_evaluation_service import evaluate
from .matching_service import build_mapping
from .models import ResolutionMethod
from .repository import MaintainPlanRepository
from .runtime_matching_decision import (
    CandidatePair, MatchingDecision, DecisionStatus, decide_runtime_matching,
)
from .runtime_matching_persistence import persist_runtime_matching_decision
from .runtime_matching_scope import validate_runtime_matching_scope


@dataclass(frozen=True)
class CoachReview:
    decision: MatchingDecision
    evaluation: object | None = None
    candidate_details: tuple[dict[str, str], ...] = ()
    saved_pair: CandidatePair | None = None
    evaluation_message: str | None = None


def _details(decision, snapshots, sessions) -> tuple[dict[str, str], ...]:
    by_snapshot = {item.prescription_snapshot_id: item for item in snapshots}
    by_session = {item.session_id: item for item in sessions}
    result = []
    for candidate in decision.candidates:
        snapshot = by_snapshot[candidate.prescription_snapshot_id]
        session = by_session[candidate.session_id]
        result.append({
            "prescription_id": candidate.prescription_snapshot_id,
            "session_id": candidate.session_id,
            "planned_time": snapshot.scheduled_window.start.isoformat(),
            "activity_time": session.start.isoformat(),
            "sport": ", ".join(item.discipline.value for item in session.components
                                if item.discipline is not None),
            "source": ", ".join(sorted({item.source for item in session.source_activities}))
                      or "sorgente non dichiarata",
        })
    return tuple(result)


def _stable_id(kind: str, prescription_id: str, session_id: str) -> str:
    return f"coach-{kind}-{uuid5(NAMESPACE_URL, f'ironcoach:{kind}:{prescription_id}:{session_id}')}"


def _evaluate_saved(repository, snapshot, session, mapping, timestamp):
    """Finish an evaluation idempotently after its mapping has been committed."""
    pair = CandidatePair(snapshot.prescription_snapshot_id, session.session_id)
    if session.source_conflicts:
        return None, pair, (
            "Valutazione non eseguita: l’attività contiene dati in conflitto "
            "che devono essere chiariti dal coach."
        )
    evaluation_id = _stable_id("evaluation", snapshot.prescription_snapshot_id,
                               session.session_id)
    existing = repository.get_execution_evaluation(evaluation_id)
    if existing is not None:
        return existing, pair, None
    try:
        value = evaluate(snapshot, session, mapping, evaluation_id=evaluation_id,
                         evaluated_at=timestamp,
                         provenance={"source": "coach-review"})
        repository.create_execution_evaluation(value)
        return value, pair, None
    except Exception as error:
        return None, pair, (
            "Collegamento salvato; valutazione non completata. "
            f"Riprova la revisione: {type(error).__name__}: {error}"
        )


def review_subject(repository: MaintainPlanRepository, subject_ref: str,
                   *, now: datetime | None = None) -> CoachReview:
    """Match every still-unmapped persisted artifact, then evaluate a unique pair.

    Corrupt storage is deliberately allowed to raise. Ambiguous and empty scopes
    are returned without a write: absence in imported data is not non-completion.
    """
    mappings = repository.list_prescription_mappings()
    snapshots_all = repository.list_prescription_snapshots(subject_ref)
    sessions_all = repository.list_actual_sessions(subject_ref)
    snapshots_by_id = {item.prescription_snapshot_id: item for item in snapshots_all}
    sessions_by_id = {item.session_id: item for item in sessions_all}
    # A mapping is committed before its evaluation. Recover that second step on
    # every later visit, making a process interruption safe and retryable.
    for mapping in mappings:
        snapshot = snapshots_by_id.get(mapping.prescription_snapshot_ref)
        session = sessions_by_id.get(mapping.actual_session_ref)
        if snapshot is None or session is None:
            continue
        evaluation_id = _stable_id("evaluation", snapshot.prescription_snapshot_id,
                                   session.session_id)
        if repository.get_execution_evaluation(evaluation_id) is None:
            scope = validate_runtime_matching_scope(subject_ref, (), ())
            decision = decide_runtime_matching(scope)
            evaluation, pair, message = _evaluate_saved(
                repository, snapshot, session, mapping, now or datetime.now(timezone.utc))
            return CoachReview(decision, evaluation, saved_pair=pair,
                               evaluation_message=message)
    mapped_prescriptions = {item.prescription_snapshot_ref for item in mappings}
    mapped_sessions = {item.actual_session_ref for item in mappings}
    snapshots = tuple(item for item in snapshots_all
                      if item.prescription_snapshot_id not in mapped_prescriptions)
    sessions = tuple(item for item in sessions_all
                     if item.session_id not in mapped_sessions)
    scope = validate_runtime_matching_scope(subject_ref, snapshots, sessions)
    decision = decide_runtime_matching(scope)
    details = _details(decision, snapshots, sessions)
    if decision.status is not DecisionStatus.MATCHED or decision.selected_pair is None:
        return CoachReview(decision, candidate_details=details)

    pair = decision.selected_pair
    timestamp = now or datetime.now(timezone.utc)
    mapping = persist_runtime_matching_decision(
        repository, scope, decision,
        mapping_id=_stable_id("mapping", pair.prescription_snapshot_id, pair.session_id),
        created_at=timestamp,
        provenance={"source": "coach-review"},
    )
    assert mapping is not None
    snapshot = next(item for item in snapshots
                    if item.prescription_snapshot_id == pair.prescription_snapshot_id)
    session = next(item for item in sessions if item.session_id == pair.session_id)
    evaluation, saved_pair, message = _evaluate_saved(
        repository, snapshot, session, mapping, timestamp)
    return CoachReview(decision, evaluation, details, saved_pair, message)


def resolve_coach_choice(repository: MaintainPlanRepository, subject_ref: str,
                         prescription_id: str, session_id: str, *,
                         now: datetime | None = None) -> CoachReview:
    """Persist an explicit coach choice only if it is still a current candidate."""
    mappings = repository.list_prescription_mappings()
    used_prescriptions = {item.prescription_snapshot_ref for item in mappings}
    used_sessions = {item.actual_session_ref for item in mappings}
    snapshots = tuple(item for item in repository.list_prescription_snapshots(subject_ref)
                      if item.prescription_snapshot_id not in used_prescriptions)
    sessions = tuple(item for item in repository.list_actual_sessions(subject_ref)
                     if item.session_id not in used_sessions)
    scope = validate_runtime_matching_scope(subject_ref, snapshots, sessions)
    decision = decide_runtime_matching(scope)
    details = _details(decision, snapshots, sessions)
    selected = next((item for item in decision.candidates
                     if item.prescription_snapshot_id == prescription_id
                     and item.session_id == session_id), None)
    if selected is None:
        raise ValueError("la scelta non è una corrispondenza ancora disponibile")
    snapshot = next(item for item in snapshots
                    if item.prescription_snapshot_id == prescription_id)
    session = next(item for item in sessions if item.session_id == session_id)
    timestamp = now or datetime.now(timezone.utc)
    mapping = build_mapping(
        snapshot, session,
        mapping_id=_stable_id("mapping", prescription_id, session_id),
        created_at=timestamp, resolution_method=ResolutionMethod.ATHLETE_CONFIRMATION,
        actor="coach", provenance={"source": "coach-review", "answer": "selected"},
    )
    repository.create_prescription_mapping(mapping)
    evaluation, saved_pair, message = _evaluate_saved(
        repository, snapshot, session, mapping, timestamp)
    return CoachReview(decision, evaluation, details, saved_pair, message)


def review_database(database_path: str, subject_ref: str) -> CoachReview:
    """Runtime boundary that keeps repository construction inside the subsystem."""
    return review_subject(MaintainPlanRepository(database_path), subject_ref)


def resolve_database_choice(database_path: str, subject_ref: str,
                            prescription_id: str, session_id: str) -> CoachReview:
    return resolve_coach_choice(MaintainPlanRepository(database_path), subject_ref,
                                prescription_id, session_id)


def format_coach_review(review: CoachReview) -> str:
    decision = review.decision
    lines = ["MAINTAIN PLAN — REVISIONE COACH", f"Esito confronto: {decision.status.value}"]
    for candidate in decision.candidates:
        lines.append(
            f"Possibile corrispondenza: {candidate.prescription_snapshot_id} ← {candidate.session_id}"
        )
    if review.saved_pair is not None:
        pair = review.saved_pair
        lines.append(f"Corrispondenza affidabile salvata: {pair.prescription_snapshot_id} ← {pair.session_id}")
        if review.evaluation_message:
            lines.append(review.evaluation_message)
        elif review.evaluation is None:
            lines.append("Valutazione non completata.")
        else:
            lines.append(f"Conseguenza sul piano: {review.evaluation.overall.value}")
            lines.append(f"Copertura valutazione: {review.evaluation.evaluation_coverage.status.value}")
    elif decision.status is DecisionStatus.CONFIRMATION_REQUIRED:
        lines.append("Scelta richiesta al coach: quale attività corrisponde all'allenamento previsto?")
        lines.append("Nessuna corrispondenza è stata salvata.")
    else:
        lines.append("Dati mostrati ma non conclusivi: nessun allenamento è considerato saltato.")
        lines.append("Nessuna corrispondenza è stata salvata.")
    if decision.reasons:
        lines.append("Motivi: " + ", ".join(item.value for item in decision.reasons))
    return "\n".join(lines)
