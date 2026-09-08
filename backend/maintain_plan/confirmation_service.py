"""Explicit, immutable confirmation workflow for matching ambiguity."""

from __future__ import annotations

from datetime import datetime

from .matching_service import build_mapping
from .models import (ActualSession, Confirmation, ConfirmationAnswerType,
                     ConfirmationStatus, MatchingResult, MatchingStatus, PolicyRef,
                     PrescriptionSnapshot, ResolutionMethod)


QUESTION_NO_CANDIDATE = "Non ho trovato un'attività associabile alla seduta prevista"


def request_confirmation(result: MatchingResult, *, confirmation_id: str,
                         asked_at: datetime, provenance, question: str | None = None) -> Confirmation:
    if result.status is not MatchingStatus.CONFIRMATION_REQUIRED or result.prescription_mapping is not None:
        raise ValueError("confirmation can only be requested for an unresolved matching result")
    return Confirmation(
        confirmation_id, result.matching_result_id, result.prescription_snapshot_ref,
        result.candidate_set, ConfirmationStatus.REQUIRED,
        question or (QUESTION_NO_CANDIDATE if not result.candidate_set
                     else "Quale attività corrisponde alla seduta prevista?"),
        tuple({"session_id": item.session_id, "reasons": item.reasons}
              for item in result.candidate_evidence),
        tuple({"answer_type": ConfirmationAnswerType.SELECT_CANDIDATE.value,
               "session_id": item} for item in result.candidate_set),
        None, None, None, asked_at, None,
        {"matching_result_id": result.matching_result_id,
         "candidate_session_refs": result.candidate_set}, provenance,
    )


def answer_confirmation(request: Confirmation, result: MatchingResult,
                        snapshot: PrescriptionSnapshot, sessions: tuple[ActualSession, ...], *,
                        confirmation_id: str, matching_result_id: str, mapping_id: str,
                        answer_type: ConfirmationAnswerType, selected_session_ref: str | None,
                        actor: str, answered_at: datetime, provenance) -> tuple[Confirmation, MatchingResult]:
    if request.status is not ConfirmationStatus.REQUIRED:
        raise ValueError("only a REQUIRED confirmation can be answered")
    if request.matching_result_ref != result.matching_result_id:
        raise ValueError("confirmation references a different matching result")
    if (request.prescription_snapshot_ref != snapshot.prescription_snapshot_id or
            result.prescription_snapshot_ref != snapshot.prescription_snapshot_id or
            request.candidate_session_refs != result.candidate_set):
        raise ValueError("confirmation snapshot or candidate set does not match")
    by_id = {item.session_id: item for item in sessions}
    selected = answer_type in {ConfirmationAnswerType.SELECT_CANDIDATE,
                               ConfirmationAnswerType.MANUAL_ASSOCIATION}
    if selected and (selected_session_ref is None or
                     selected_session_ref not in request.candidate_session_refs):
        raise ValueError("selected session does not belong to the exact candidate set")
    if not selected and selected_session_ref is not None:
        raise ValueError("this confirmation answer cannot select a session")
    if selected_session_ref is not None and selected_session_ref not in by_id:
        raise ValueError("selected session is unavailable or cross-session")
    status = (ConfirmationStatus.UNKNOWN_ANSWER
              if answer_type is ConfirmationAnswerType.DONT_KNOW else ConfirmationStatus.ANSWERED)
    answered = Confirmation(
        confirmation_id, request.matching_result_ref, request.prescription_snapshot_ref,
        request.candidate_session_refs, status, request.question, request.ambiguous_data,
        request.interpretations, answer_type, selected_session_ref, actor,
        request.asked_at, answered_at, request.evidence, provenance, request.policy)
    mapping = None
    matching_status = MatchingStatus.NOT_EVALUABLE
    if selected:
        mapping = build_mapping(snapshot, by_id[selected_session_ref], mapping_id=mapping_id,
                                created_at=answered_at,
                                resolution_method=ResolutionMethod.ATHLETE_CONFIRMATION,
                                confirmation_ref=answered.confirmation_id, actor=actor,
                                provenance=provenance)
        matching_status = MatchingStatus.MATCHED
    resolved = MatchingResult(matching_result_id, matching_status, mapping,
                              PolicyRef("maintain-plan-matching", "1.0.0-draft"),
                              snapshot.prescription_snapshot_id, result.candidate_set,
                              result.candidate_evidence, answered.confirmation_id, provenance)
    return answered, resolved
