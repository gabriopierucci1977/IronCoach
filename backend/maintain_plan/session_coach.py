"""AI-backed review of an actual session, independent from a training plan."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from typing import Callable

from .repository import MaintainPlanRepository


@dataclass(frozen=True)
class SessionFacts:
    session_id: str
    start: str
    sport: str
    duration_minutes: float | None
    sources: tuple[str, ...]
    rpe: int | None
    missing: tuple[str, ...]


@dataclass(frozen=True)
class AiComment:
    available: bool
    observed: str = ""
    interpretation: str = ""
    uncertainties: str = ""
    unavailable_reason: str = ""


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _duration_minutes(component) -> float | None:
    """Read an observed duration only when metric semantics and unit are explicit."""
    for metric in component.secondary_metrics:
        if (metric.get("metric") == "duration" and metric.get("unit") == "min"
                and _number(metric.get("value")) is not None):
            return metric["value"]
    legacy = component.quantity_observation or {}
    if (legacy.get("metric") == "duration" and legacy.get("unit") == "min"
            and _number(legacy.get("value")) is not None):
        return legacy["value"]
    nested = legacy.get("duration")
    if (isinstance(nested, dict) and nested.get("unit") == "min"
            and _number(nested.get("value")) is not None):
        return nested["value"]
    return None


def session_facts(session, *, rpe: int | None = None) -> SessionFacts:
    durations = [duration for component in session.components
                 if (duration := _duration_minutes(component)) is not None]
    sports = sorted({component.discipline.value for component in session.components
                     if component.discipline is not None})
    return SessionFacts(
        session.session_id, session.start.isoformat(), ", ".join(sports) or "non indicato",
        round(sum(durations), 1) if durations else None,
        tuple(sorted({item.source for item in session.source_activities})), rpe,
        tuple(session.missing_fields),
    )


def _openai_comment(payload: dict) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or api_key == "your_openai_api_key":
        raise RuntimeError("OPENAI_API_KEY non configurata")
    from openai import OpenAI
    response = OpenAI(api_key=api_key).responses.create(
        model=os.getenv("IRONCOACH_AI_MODEL", "gpt-5-mini"),
        instructions=(
            "Sei IronCoach. Rispondi in italiano come coach personale. Usa soltanto il JSON "
            "fornito, senza inventare valori Garmin/Strava. Restituisci solo JSON con le chiavi "
            "observed, interpretation, uncertainties. Separa fatti, lettura prudente e limiti. "
            "Se session.duration_minutes è presente, riportala in observed soltanto come durata "
            "osservata: non chiamarla active_duration né quantità primaria. Se è null, non "
            "inventarla. La storia serve come contesto, non come prescrizione."),
        input=json.dumps(payload, ensure_ascii=False),
    )
    return json.loads(response.output_text)


def ai_comment(repository: MaintainPlanRepository, subject_ref: str, session_id: str,
               *, generator: Callable[[dict], dict] | None = None) -> AiComment:
    """Generate a grounded comment from the selected activity and prior history."""
    session = repository.get_actual_session(session_id)
    if session is None or session.subject_ref != subject_ref:
        raise ValueError("sessione non disponibile per questo atleta")
    from .rpe_feedback import session_rpe_state
    state = session_rpe_state(repository, session_id)
    rpe = state.value if state.status == "VALUE" else None
    selected = session_facts(session, rpe=rpe)
    previous = sorted(
        (item for item in repository.list_actual_sessions(subject_ref)
         if item.start < session.start), key=lambda item: item.start)[-5:]
    payload = {
        "session": selected.__dict__,
        "pertinent_history": [session_facts(item).__dict__ for item in previous],
        "plan_comparison": None,
    }
    try:
        result = (generator or _openai_comment)(payload)
        fields = tuple(result.get(key) for key in
                       ("observed", "interpretation", "uncertainties"))
        if not all(isinstance(value, str) and value.strip() for value in fields):
            raise ValueError("risposta IA non conforme")
        return AiComment(True, *fields)
    except Exception as error:
        return AiComment(False, unavailable_reason=str(error))


def save_relation(repository: MaintainPlanRepository, subject_ref: str, session_id: str,
                  relation: str, prescription_id: str | None = None,
                  *, now: datetime | None = None) -> None:
    session = repository.get_actual_session(session_id)
    if session is None or session.subject_ref != subject_ref:
        raise ValueError("sessione non disponibile per questo atleta")
    repository.save_session_relation(
        session_id, relation, prescription_id,
        decided_at=now or datetime.now(timezone.utc), actor="athlete")
