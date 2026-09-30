"""Coach-portal capture of optional, explicitly qualified observed RPE."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5

from .lifecycle_service import (
    FEEDBACK_EVENT_SCHEMA, FEEDBACK_LOG_SCHEMA, SUBJECTIVE_FEEDBACK_SCHEMA,
    project_feedback,
)
from .models import (
    ActualSessionRef, FeedbackEvent, FeedbackEventLog, FeedbackEventType,
    FeedbackLogRef, FeedbackRef,
)
from .repository import MaintainPlanRepository


def _identifier(kind: str, session_id: str) -> str:
    return f"coach-rpe-{kind}-{uuid5(NAMESPACE_URL, f'ironcoach:rpe:{kind}:{session_id}')}"


@dataclass(frozen=True)
class RpeFeedbackState:
    status: str
    value: int | float | None = None
    attribution: str = "NEUTRAL"
    source: str | None = None


def _projection_id(session_id: str, sequence: int) -> str:
    return _identifier(f"projection:{sequence}", session_id)


def qualified_rpe(payload: Mapping[str, Any] | None) -> int | float | None:
    """Return RPE only when meaning, scale and origin are explicitly verified."""
    if not isinstance(payload, Mapping):
        return None
    value = payload.get("rpe")
    provenance = payload.get("provenance")
    qualification = (provenance.get("rpe_qualification")
                     if isinstance(provenance, Mapping) else None)
    if (type(value) not in (int, float) or not 1 <= value <= 10 or
            not isinstance(qualification, Mapping) or
            qualification.get("meaning") != "session_rpe" or
            qualification.get("scale") != "1-10" or
            qualification.get("verified") is not True or
            not qualification.get("source")):
        return None
    return value


def rpe_attribution(payload: Mapping[str, Any] | None) -> tuple[str, str | None]:
    """Describe attribution without changing whether the RPE is qualified."""
    if not isinstance(payload, Mapping):
        return "NEUTRAL", None
    provenance = payload.get("provenance")
    if not isinstance(provenance, Mapping):
        return "NEUTRAL", None
    if (provenance.get("source") == "ironcoach-coach-portal" and
            provenance.get("declared_by") == "ironcoach-user" and
            provenance.get("capture_method") in {
                "direct-user-declaration", "direct-user-correction"}):
        return "PORTAL_USER", "IronCoach"
    qualification = provenance.get("rpe_qualification")
    source = (qualification.get("source")
              if isinstance(qualification, Mapping) else None)
    if isinstance(source, str) and source.strip():
        return "IMPORTED_SOURCE", source.strip()
    return "NEUTRAL", None


def session_rpe_state(repository: MaintainPlanRepository, session_id: str) -> RpeFeedbackState:
    log = repository.get_feedback_log(_identifier("log", session_id))
    if log is not None:
        projection = repository.get_latest_feedback_projection(log.feedback_log_id)
        if projection is None or projection.projected_payload is None:
            raise ValueError("feedback RPE privo di proiezione corrente")
        value = qualified_rpe(projection.projected_payload)
        attribution, source = rpe_attribution(projection.projected_payload)
        return RpeFeedbackState(
            "OMITTED" if value is None else "VALUE", value, attribution, source)
    session = repository.get_actual_session(session_id)
    value = None if session is None else qualified_rpe(session.athlete_feedback)
    attribution, source = rpe_attribution(
        None if session is None else session.athlete_feedback)
    return RpeFeedbackState(
        "UNANSWERED" if value is None else "VALUE", value, attribution, source)


def session_rpe(repository: MaintainPlanRepository, session_id: str) -> int | float | None:
    return session_rpe_state(repository, session_id).value


def capture_observed_rpe(repository: MaintainPlanRepository, *, subject_ref: str,
                         session_id: str, submitted_rpe: str | None,
                         captured_at: datetime | None = None):
    """Append one user declaration; a blank answer is a first-class missing value."""
    session = repository.get_actual_session(session_id)
    if session is None or session.subject_ref != subject_ref:
        raise ValueError("sessione non disponibile per il soggetto configurato")
    text = "" if submitted_rpe is None else submitted_rpe.strip()
    if text:
        try:
            rpe: int | float = int(text)
        except ValueError as error:
            raise ValueError("RPE deve essere un intero da 1 a 10") from error
        if not 1 <= rpe <= 10:
            raise ValueError("RPE deve essere un intero da 1 a 10")
    else:
        rpe = None

    log_id = _identifier("log", session_id)
    existing = repository.get_feedback_log(log_id)
    if existing is not None:
        projection = repository.get_latest_feedback_projection(log_id)
        if projection is None or projection.projected_payload is None:
            raise ValueError("feedback RPE privo di proiezione corrente")
        existing_value = projection.projected_payload.get("rpe")
        if existing_value == rpe:
            return projection
        timestamp = captured_at or datetime.now(timezone.utc)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("captured_at deve includere il fuso orario")
        baseline = repository._feedback_baseline(existing)
        if baseline is None:
            raise ValueError("baseline RPE non disponibile")
        prior_events = repository.list_feedback_events(log_id)
        sequence = len(prior_events) + 1
        corrected_payload = dict(projection.projected_payload)
        corrected_payload["rpe"] = rpe
        corrected_payload["missing_fields"] = tuple(
            name for name in corrected_payload["missing_fields"] if name != "rpe")
        if rpe is None:
            corrected_payload["missing_fields"] = (
                "rpe", *corrected_payload["missing_fields"])
        provenance = {
            "source": "ironcoach-coach-portal",
            "declared_by": "ironcoach-user",
            "capture_method": "direct-user-correction",
            "rpe_qualification": {
                "source": "ironcoach-user", "meaning": "session_rpe",
                "scale": "1-10", "verified": True,
            },
        }
        event = FeedbackEvent(
            _identifier(f"event:{sequence}", session_id),
            FeedbackLogRef(log_id, session_id, existing.feedback_ref.feedback_id),
            existing.feedback_ref, existing.actual_session_ref,
            FeedbackEventType.CORRECTED, baseline["schema_version"],
            baseline["payload_hash"], sequence, sequence, timestamp,
            "ironcoach-user", provenance, FEEDBACK_EVENT_SCHEMA,
            prior_events[-1].feedback_event_id, prior_events[-1].feedback_event_id,
            corrected_payload, None,
            {"reason": "user-updated-observed-rpe"}, (), ())
        revised = project_feedback(
            projection_id=_projection_id(session_id, sequence),
            projection_version=str(sequence), log=existing, baseline=baseline,
            events=prior_events + (event,),
            provenance={"source": "feedback-event-stream"})
        repository.persist_feedback_revision(existing, baseline, event, revised)
        return revised

    timestamp = captured_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("captured_at deve includere il fuso orario")
    feedback_id = _identifier("feedback", session_id)
    provenance = {
        "source": "ironcoach-coach-portal",
        "declared_by": "ironcoach-user",
        "capture_method": "direct-user-declaration",
        "rpe_qualification": {
            "source": "ironcoach-user", "meaning": "session_rpe",
            "scale": "1-10", "verified": True,
        },
    }
    preimage = {
        "feedback_id": feedback_id, "rpe": rpe,
        "captured_at": timestamp.isoformat(), "provenance": provenance,
    }
    payload_hash = hashlib.sha256(json.dumps(
        preimage, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    baseline = {
        "feedback_id": feedback_id,
        "schema_version": SUBJECTIVE_FEEDBACK_SCHEMA,
        "payload_hash": payload_hash,
        "rpe": rpe, "pain": None, "unusual_fatigue": None,
        "interruption": None, "reason": None, "note": None,
        "captured_at": timestamp.isoformat(), "provenance": provenance,
        "missing_fields": (("rpe", "pain", "unusual_fatigue", "interruption",
                            "reason", "note") if rpe is None else
                           ("pain", "unusual_fatigue", "interruption", "reason", "note")),
        "warnings": (),
    }
    feedback_ref = FeedbackRef(session_id, feedback_id)
    session_ref = ActualSessionRef(session_id)
    log = FeedbackEventLog(log_id, FEEDBACK_LOG_SCHEMA, feedback_ref, session_ref)
    event_id = _identifier("event:1", session_id)
    event = FeedbackEvent(
        event_id, FeedbackLogRef(log_id, session_id, feedback_id), feedback_ref,
        session_ref, FeedbackEventType.CAPTURED, SUBJECTIVE_FEEDBACK_SCHEMA,
        payload_hash, 1, 1, timestamp, "ironcoach-user", provenance,
        FEEDBACK_EVENT_SCHEMA, None, None, None, None, (), (),
    )
    projection = project_feedback(
        projection_id=_projection_id(session_id, 1), projection_version="1", log=log,
        baseline=baseline, events=(event,),
        provenance={"source": "feedback-event-stream"})
    repository.persist_feedback_capture(log, baseline, event, projection)
    return projection


def capture_database_observed_rpe(database_path: str, **kwargs):
    repository = MaintainPlanRepository(database_path)
    configured = repository.configured_subject_refs()
    if len(configured) != 1:
        raise ValueError("l’archivio deve contenere un solo soggetto configurato")
    # Deliberately discard any request/form identity. The archive is the
    # authority for this personal, single-athlete phase.
    kwargs.pop("subject_ref", None)
    return capture_observed_rpe(
        repository, subject_ref=configured[0], **kwargs)
