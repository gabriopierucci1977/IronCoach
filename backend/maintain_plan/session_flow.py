"""Read-only ActualSession browser flow and ChatGPT hand-off helpers.

This module deliberately never contacts an AI service: it only prepares text for
the user's clipboard/browser and validates plans returned by the user.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from collections.abc import Mapping
from urllib.parse import quote

PAGE_SIZE = 50

@dataclass(frozen=True)
class SessionPage:
    items: tuple[Any, ...]
    page: int
    pages: int
    total: int

def list_sessions(repository, subject_ref: str, *, page: int = 1, year: int | None = None,
                  month: int | None = None, sport: str | None = None) -> SessionPage:
    """Filter and paginate without mutating the archive."""
    if page < 1: raise ValueError("page must be positive")
    items = list(repository.list_actual_sessions(subject_ref))
    def discipline(s):
        return {getattr(c.discipline, "value", c.discipline) for c in s.components}
    items = [s for s in items if (year is None or s.start.year == year)
             and (month is None or s.start.month == month)
             and (sport is None or sport.upper() in discipline(s))]
    total = len(items); pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    if page > pages: return SessionPage((), page, pages, total)
    start = (page - 1) * PAGE_SIZE
    return SessionPage(tuple(items[start:start + PAGE_SIZE]), page, pages, total)

def session_detail(session) -> dict[str, Any]:
    duration = None if session.end is None else (session.end - session.start).total_seconds() / 60
    metrics = []; missing = set(session.missing_fields)
    for component in session.components:
        if component.quantity_primary_metric: metrics.append(component.quantity_primary_metric)
        missing.update(component.missing_fields)
    return {"session_id": session.session_id, "sport": sorted({getattr(c.discipline, "value", c.discipline) for c in session.components}),
            "start": session.start.isoformat(), "duration_minutes": duration,
            "source": sorted({a.source for a in session.source_activities}), "metrics": sorted(set(metrics)),
            "missing": sorted(missing), "prescription": None, "feedback": session.athlete_feedback}

def build_export_prompt(session, recent=(), prescription=None, feedback=None) -> str:
    def compat(value):
        if isinstance(value, Mapping): return {str(k): compat(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)): return [compat(v) for v in value]
        return value
    payload = {"seduta": session_detail(session), "storico_recente": [session_detail(s) for s in recent],
               "prescrizione": prescription, "feedback": feedback or session.athlete_feedback}
    return "Analizza questa seduta e il mio storico recente. Rispondi in italiano con osservazioni pratiche.\n\n" + json.dumps(compat(payload), ensure_ascii=False, indent=2)

def export_to_chatgpt(prompt: str, *, clipboard=None, opener=None) -> str:
    if opener is None:
        import webbrowser
        opener = webbrowser.open_new_tab
    if clipboard is not None: clipboard(prompt)
    try: opener("https://chatgpt.com/?q=" + quote(prompt))
    except Exception: pass
    return prompt

def validate_imported_plan(value: str | dict[str, Any]) -> dict[str, Any]:
    try: data = json.loads(value) if isinstance(value, str) else value
    except (TypeError, json.JSONDecodeError) as exc: raise ValueError("JSON non valido") from exc
    if not isinstance(data, dict) or not isinstance(data.get("sessions"), list):
        raise ValueError("il piano deve contenere una lista 'sessions'")
    for i, item in enumerate(data["sessions"]):
        if not isinstance(item, dict) or not isinstance(item.get("date"), str) or not item.get("sport"):
            raise ValueError(f"sessions[{i}] richiede date e sport")
        try: datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
        except ValueError as exc: raise ValueError(f"sessions[{i}].date non valida") from exc
    return data


_TEXT_SPORTS = (
    ("strength", ("forza", "strength", "pesi", "palestra")),
    ("swim", ("nuoto", "swim", "piscina")),
    ("bike", ("ciclismo", "bicicletta", "bici", "bike")),
    ("run", ("corsa", "running", "run", "jogging")),
    ("mobility", ("mobilità", "mobilita", "mobility", "stretching")),
    ("rest", ("riposo", "rest", "recupero")),
)

_PLAN_DATE_RE = re.compile(
    r"(?<!\d)(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}/\d{1,2}/\d{4})(?!\d)"
)


def _plan_date(value: str) -> str:
    normalized = value.replace("/", "-")
    parts = normalized.split("-")
    if len(parts[0]) == 4:
        parsed = datetime.strptime(normalized, "%Y-%m-%d")
    else:
        parsed = datetime.strptime(normalized, "%d-%m-%Y")
    return parsed.strftime("%Y-%m-%dT00:00:00+00:00")


def text_to_plan(value: str) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("scrivi almeno una seduta")

    sessions = []
    errors = []

    for line_number, raw_line in enumerate(value.splitlines(), 1):
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        date_match = _PLAN_DATE_RE.search(line)

        if date_match is None:
            errors.append(
                f"riga {line_number}: indica una data "
                "(AAAA-MM-GG oppure GG/MM/AAAA)"
            )
            continue

        date_value = _plan_date(date_match.group(1))
        description = (
            line[:date_match.start()] + " " + line[date_match.end():]
        ).strip(" -:;\t")

        lowered = description.casefold()

        sport = next(
            (
                canonical
                for canonical, words in _TEXT_SPORTS
                if any(word in lowered for word in words)
            ),
            None,
        )

        if sport is None:
            errors.append(
                f"riga {line_number}: indica lo sport "
                "(corsa, bici, nuoto, forza o altro)"
            )
            continue

        sessions.append({
            "date": date_value,
            "sport": sport.upper(),
            "title": description or sport,
            "description": description,
        })

    if errors:
        raise ValueError("; ".join(errors))

    if not sessions:
        raise ValueError("non ho trovato sedute descrivibili")

    return {
        "sessions": sessions,
        "source": "descrizione_utente",
    }


def preview_text_plan(value: str) -> tuple[dict[str, Any], ...]:
    data = text_to_plan(value)
    return tuple(
        {
            "date": item["date"],
            "sport": item["sport"],
            "title": item["title"],
        }
        for item in data["sessions"]
    )

def preview_imported_plan(value: str | dict[str, Any]) -> tuple[dict[str, Any], ...]:
    data = validate_imported_plan(value)
    return tuple({"date": s["date"], "sport": s["sport"], "title": s.get("title", "")} for s in data["sessions"])

def persist_imported_plan(value: str | dict[str, Any], storage_path: str | Path) -> dict[str, Any]:
    """Persist a validated external plan atomically; never alters ActualSession rows."""
    data = validate_imported_plan(value)
    path = Path(storage_path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return data

def load_imported_plan(storage_path: str | Path) -> dict[str, Any] | None:
    path = Path(storage_path)
    if not path.exists(): return None
    return validate_imported_plan(path.read_text(encoding="utf-8"))
