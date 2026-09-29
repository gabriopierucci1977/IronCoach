"""Isolated, explicitly hypothetical coach review built from archived sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
import hmac
import math
import os
import shutil
import sqlite3
import tempfile

from .models import (
    ActualSession, Applicability, BlockType, Composition, Discipline,
    EvaluationWindow, IntensityContract, IntensityMethod, Objective,
    ObjectiveEvaluability, PlannedBlock, PlannedComponent, PolicyRef,
    PrescribedTarget, PrescriptionAudit, PrescriptionSnapshot, Provenance,
    QuantityContract, QuantityMetric, RecoveryContract, Requiredness,
    ScheduledWindow, SessionType, StructureContract, SupportStatus, DoseContract,
)
from .archive_lock import archive_lock, lock_path
from .repository import MaintainPlanRepository
from .serialization import PAYLOAD_SCHEMA_VERSION, deserialize_contract
from .validators import validate_actual_session, validate_prescription


POLICY_VERSION = "1.0.0-draft"
_TRIAL_STATE_TABLE = "ironcoach_coach_trial_state"


def _trial_state_token_unlocked(path: Path) -> str:
    """Fingerprint one persisted trial generation while its writer lock is held."""
    digest = sha256()
    if not path.exists():
        digest.update(b"missing")
        return digest.hexdigest()
    with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as connection:
        row = connection.execute(
            f"SELECT scenario_id FROM {_TRIAL_STATE_TABLE} LIMIT 1"
        ).fetchone()
    if row is None:
        raise ValueError("scenario di prova privo di identificatore persistito")
    digest.update(str(row[0]).encode())
    for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
        digest.update(candidate.name.encode())
        if candidate.exists():
            digest.update(candidate.read_bytes())
    return digest.hexdigest()


def trial_state_token(trial_path: str | Path) -> str:
    """Return an opaque token for the complete persisted trial state."""
    path = Path(trial_path)
    with archive_lock(path):
        return _trial_state_token_unlocked(path)


def _archive_signature(path: Path) -> dict[str, tuple[int, str]]:
    """Fingerprint the database set without opening it through SQLite."""
    result = {}
    for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
        if candidate.exists():
            payload = candidate.read_bytes()
            result[candidate.name] = (len(payload), sha256(payload).hexdigest())
    return result


def _copy_stable_archive(path: Path, directory: str) -> Path:
    """Copy one stable DB/WAL/SHM generation or fail instead of mixing generations."""
    with archive_lock(path):
        before = _archive_signature(path)
        snapshot = Path(directory) / path.name
        shutil.copy2(path, snapshot)
        for suffix in ("-wal", "-shm"):
            sidecar = Path(f"{path}{suffix}")
            if sidecar.exists():
                shutil.copy2(sidecar, Path(f"{snapshot}{suffix}"))
        after = _archive_signature(path)
        copied = _archive_signature(snapshot)
    if before != after or copied != after:
        raise RuntimeError(
            "archivio MAINTAIN_PLAN cambiato durante la lettura; riprova quando "
            "la scrittura concorrente è terminata")
    return snapshot


@dataclass(frozen=True)
class TrialActivity:
    session_id: str
    start: datetime
    sports: tuple[str, ...]
    source: str
    comparison_notes: tuple[str, ...]


def _comparison_notes(session: ActualSession, supported: set[Discipline]) -> tuple[str, ...]:
    """Describe evaluability without reinterpreting secondary Garmin metrics."""
    notes = []
    for component in session.components:
        if component.discipline not in supported:
            continue
        sport = component.discipline.value
        quantity = component.quantity_observation
        primary_duration = (
            component.quantity_primary_metric == QuantityMetric.ACTIVE_DURATION.value
            and component.quantity_unit == "minutes"
            and quantity is not None
            and isinstance(quantity.get("value"), (int, float))
            and not isinstance(quantity.get("value"), bool))
        secondary_duration = any(
            metric.get("metric") == "duration"
            for metric in component.secondary_metrics)
        if primary_duration:
            notes.append(f"{sport} · durata primaria: confronto quantitativo supportato")
        elif secondary_duration:
            notes.append(
                f"{sport} · durata: non valutabile quantitativamente; Garmin la espone "
                "solo nelle metriche secondarie, che non equivalgono alla durata primaria")
        else:
            notes.append(
                f"{sport} · durata: non valutabile quantitativamente; durata primaria assente")

        intensity = component.intensity_observations
        rpe_supported = (
            "RPE" in component.intensity_methods
            and intensity is not None
            and type(intensity.get("valid_coverage")) in (int, float)
            and intensity.get("valid_coverage") >= .8
            and type(intensity.get("time_in_target")) in (int, float))
        if rpe_supported:
            notes.append(f"{sport} · RPE: confronto quantitativo supportato")
        else:
            notes.append(
                f"{sport} · RPE: non valutabile quantitativamente; RPE osservato assente")
    return tuple(notes)


def _readonly_archive_sessions(archive_path: str | Path,
                               subject_ref: str) -> tuple[ActualSession, ...]:
    """Decode archive sessions through a query-only connection, without migrations."""
    path = Path(archive_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Archivio MAINTAIN_PLAN non trovato: {path}")
    # Even a SQLite read-only connection may create or update -shm for a WAL
    # database. Read a private byte-for-byte snapshot of the database and its
    # existing WAL sidecars instead, so recovery and shared memory stay private.
    with tempfile.TemporaryDirectory(prefix="ironcoach-archive-read-") as directory:
        snapshot = _copy_stable_archive(path, directory)
        connection = sqlite3.connect(snapshot)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA query_only = ON")
            columns = {row[1] for row in connection.execute(
                "PRAGMA table_info(maintain_plan_actual_sessions)")}
            required = {"session_id", "start", "composition", "contract_version",
                        "payload_schema_version", "payload_json"}
            if not required <= columns:
                raise ValueError("schema storico privo della tabella attività compatibile")
            if "subject_ref" in columns:
                # Filter ownership before payload decoding: corrupt data belonging to
                # another athlete must not poison this athlete's read-only journey.
                rows = connection.execute(
                    "SELECT * FROM maintain_plan_actual_sessions "
                    "WHERE subject_ref = ? ORDER BY session_id", (subject_ref,)).fetchall()
            else:
                # Legacy schemas predate the indexed ownership column. Their payload
                # ownership is checked conservatively after decoding below.
                rows = connection.execute(
                    "SELECT * FROM maintain_plan_actual_sessions ORDER BY session_id").fetchall()
        finally:
            connection.close()
    sessions = []
    for row in rows:
        if row["payload_schema_version"] != PAYLOAD_SCHEMA_VERSION:
            raise ValueError("versione payload MAINTAIN_PLAN storica non supportata")
        session = deserialize_contract(row["payload_json"], ActualSession)
        stored_subject = row["subject_ref"] if "subject_ref" in columns else session.subject_ref
        errors = validate_actual_session(session, allow_legacy_subject=stored_subject is None)
        if errors:
            raise ValueError("; ".join(errors))
        metadata = (session.session_id, session.start.isoformat(),
                    None if session.composition is None else session.composition.value,
                    session.contract_version)
        if metadata != (row["session_id"], row["start"], row["composition"],
                        row["contract_version"]):
            raise ValueError("metadati dell’attività archiviata incoerenti")
        # A legacy artifact without ownership cannot safely be attributed.
        if stored_subject == subject_ref and session.subject_ref == subject_ref:
            sessions.append(session)
    return tuple(sessions)


def available_activities(archive_path: str | Path, subject_ref: str) -> tuple[TrialActivity, ...]:
    """Read supported historical activities without writing to the archive."""
    supported = {Discipline.SWIM, Discipline.BIKE, Discipline.RUN}
    result = []
    for session in _readonly_archive_sessions(archive_path, subject_ref):
        if session.composition is not Composition.SINGLE or len(session.components) != 1:
            # This minimal authoring form creates exactly one planned component;
            # offering BRICK/MULTISPORT here would guarantee an unmatchable plan.
            continue
        sports = tuple(dict.fromkeys(
            component.discipline.value for component in session.components
            if component.discipline in supported))
        if not sports:
            continue
        sources = sorted({source.source for source in session.source_activities})
        result.append(TrialActivity(
            session.session_id, session.start, sports,
            ", ".join(sources) or "Garmin", _comparison_notes(session, supported)))
    return tuple(sorted(result, key=lambda item: (item.start, item.session_id), reverse=True))


def _policy(name: str) -> PolicyRef:
    return PolicyRef(name, POLICY_VERSION)


def hypothetical_prescription(subject_ref: str, session: ActualSession, *,
                              sport: str, duration_minutes: float,
                              rpe: float, now: datetime | None = None,
                              identifier: str | None = None) -> PrescriptionSnapshot:
    """Create a coach-authored trial contract; observed metrics are never inputs."""
    discipline = Discipline(sport)
    if (not math.isfinite(duration_minutes) or not math.isfinite(rpe)
            or duration_minutes <= 0 or not 1 <= rpe <= 10):
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
                 choices: tuple[dict[str, object], ...], *, now: datetime | None = None,
                 expected_state_token: str | None = None
                 ) -> MaintainPlanRepository:
    """Copy chosen activities and authored plans into a fresh, separate database."""
    if not choices:
        raise ValueError("scegli almeno un’attività")
    archive_sessions = {item.session_id: item for item in
                        _readonly_archive_sessions(archive_path, subject_ref)}
    trial_path = Path(trial_path)
    if trial_path.resolve() == Path(archive_path).resolve():
        raise ValueError("l’archivio di prova deve essere separato dall’archivio reale")
    temporary_path = trial_path.with_name(f".{trial_path.name}.{uuid4().hex}.tmp")
    try:
        trial = MaintainPlanRepository(temporary_path)
        with sqlite3.connect(temporary_path) as connection:
            connection.execute(
                f"CREATE TABLE {_TRIAL_STATE_TABLE} (scenario_id TEXT NOT NULL UNIQUE)")
            connection.execute(
                f"INSERT INTO {_TRIAL_STATE_TABLE} (scenario_id) VALUES (?)",
                (uuid4().hex,))
        seen = set()
        for index, choice in enumerate(choices):
            session_id = str(choice["session_id"])
            if session_id in seen:
                raise ValueError("un’attività può essere scelta una sola volta")
            seen.add(session_id)
            session = archive_sessions.get(session_id)
            if session is None:
                raise ValueError("attività non disponibile per l’atleta")
            if (session.composition is not Composition.SINGLE
                    or len(session.components) != 1):
                raise ValueError(
                    "lo scenario di prova supporta soltanto attività SINGLE")
            sport = str(choice["sport"])
            if sport not in {item.discipline.value for item in session.components
                             if item.discipline is not None}:
                raise ValueError("lo sport scelto non corrisponde all’attività selezionata")
            trial.create_actual_session(session)
            trial.create_prescription_snapshot(hypothetical_prescription(
                subject_ref, session, sport=sport,
                duration_minutes=float(choice["duration_minutes"]),
                rpe=float(choice["rpe"]), now=now, identifier=str(index + 1)))
        # Publish only a fully validated scenario. os.replace also makes retries
        # replace the prior trial instead of accumulating duplicate artifacts.
        lock_path(temporary_path).unlink(missing_ok=True)
        with archive_lock(trial_path):
            if trial_path.exists():
                current_token = _trial_state_token_unlocked(trial_path)
                with sqlite3.connect(trial_path) as current:
                    progressed = current.execute(
                        "SELECT count(*) FROM maintain_plan_prescription_mappings"
                    ).fetchone()[0]
                if expected_state_token is not None:
                    if not hmac.compare_digest(expected_state_token, current_token):
                        raise RuntimeError(
                            "scenario di prova modificato da una conferma, valutazione "
                            "o sostituzione concorrente; ricarica la pagina")
                elif progressed:
                    raise RuntimeError(
                        "scenario di prova modificato da una conferma o valutazione; "
                        "ricarica la pagina prima di sostituirlo")
            elif (expected_state_token is not None
                  and not hmac.compare_digest(
                      expected_state_token, _trial_state_token_unlocked(trial_path))):
                raise RuntimeError(
                    "scenario di prova sostituito nel frattempo; ricarica la pagina")
            os.replace(temporary_path, trial_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        lock_path(temporary_path).unlink(missing_ok=True)
        for sidecar in temporary_path.parent.glob(f"{temporary_path.name}-*"):
            sidecar.unlink(missing_ok=True)
        raise
    return MaintainPlanRepository(trial_path)
