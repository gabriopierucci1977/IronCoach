"""User-confirmed, session-owned commentary, stored separately from activity facts."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

MAX_ANALYSIS_LENGTH = 30000


def _owned_session(repository, subject: str, session_id: str):
    session = repository.get_actual_session(session_id)
    if session is None or not subject or session.subject_ref != subject:
        raise ValueError("Questa attività non è disponibile per l’atleta selezionato.")
    return session


def analysis_database_path(repository) -> Path:
    archive = Path(repository.database_path).resolve()
    return archive.with_name(archive.stem + "_manual_analyses.sqlite3")


def load_manual_analysis(repository, subject: str, session_id: str):
    _owned_session(repository, subject, session_id)
    path = analysis_database_path(repository)
    if not path.exists():
        return None
    # Reading an activity must never create the commentary store or a row.
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT text, created_at, origin FROM manual_session_analyses "
            "WHERE subject = ? AND session_id = ? ORDER BY id DESC LIMIT 1",
            (subject, session_id),
        ).fetchone()
    return dict(row) if row is not None else None


def save_manual_analysis(repository, subject: str, session_id: str, text: str):
    _owned_session(repository, subject, session_id)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Incolla il parere prima di salvarlo.")
    text = text.strip()
    if len(text) > MAX_ANALYSIS_LENGTH:
        raise ValueError("Il parere è troppo lungo: massimo 30.000 caratteri.")
    created_at = datetime.now(timezone.utc).isoformat()
    path = analysis_database_path(repository)
    with sqlite3.connect(path, timeout=10) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS manual_session_analyses ("
            "id INTEGER PRIMARY KEY, subject TEXT NOT NULL, session_id TEXT NOT NULL, "
            "text TEXT NOT NULL, created_at TEXT NOT NULL, origin TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO manual_session_analyses "
            "(subject, session_id, text, created_at, origin) VALUES (?, ?, ?, ?, ?)",
            (subject, session_id, text, created_at, "chatgpt_manual"),
        )
    return {"text": text, "created_at": created_at, "origin": "chatgpt_manual"}
