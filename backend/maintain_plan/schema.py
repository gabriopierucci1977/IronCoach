"""Isolated, additive SQLite migrations for draft MAINTAIN_PLAN data."""

from __future__ import annotations

import sqlite3
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Migration:
    version: int
    checksum: str
    apply: Callable[[sqlite3.Connection], None]


_MIGRATION_1_SQL = """
        CREATE TABLE maintain_plan_prescription_snapshots (
            prescription_snapshot_id TEXT PRIMARY KEY,
            workout_id TEXT NOT NULL,
            decision_id TEXT NOT NULL,
            contract_version TEXT NOT NULL,
            payload_schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
        CREATE INDEX idx_mp_snapshots_decision ON maintain_plan_prescription_snapshots(decision_id);

        CREATE TABLE maintain_plan_actual_sessions (
            session_id TEXT PRIMARY KEY,
            start TEXT NOT NULL,
            composition TEXT CHECK (composition IS NULL OR composition IN ('single', 'brick', 'multisport')),
            contract_version TEXT NOT NULL,
            payload_schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
        CREATE INDEX idx_mp_sessions_start ON maintain_plan_actual_sessions(start);

        CREATE TABLE maintain_plan_prescription_mappings (
            mapping_id TEXT PRIMARY KEY,
            prescription_snapshot_ref TEXT NOT NULL REFERENCES maintain_plan_prescription_snapshots(prescription_snapshot_id),
            actual_session_ref TEXT NOT NULL REFERENCES maintain_plan_actual_sessions(session_id),
            resolution_method TEXT NOT NULL CHECK (resolution_method IN ('AUTOMATIC', 'ATHLETE_CONFIRMATION')),
            payload_schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            UNIQUE (mapping_id, prescription_snapshot_ref, actual_session_ref)
        );

        CREATE TABLE maintain_plan_matching_results (
            matching_result_id TEXT PRIMARY KEY,
            status TEXT NOT NULL CHECK (status IN ('MATCHED', 'CONFIRMATION_REQUIRED', 'NOT_EVALUABLE')),
            prescription_mapping_ref TEXT REFERENCES maintain_plan_prescription_mappings(mapping_id),
            policy_id TEXT,
            policy_version TEXT,
            payload_schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            CHECK ((status = 'MATCHED' AND prescription_mapping_ref IS NOT NULL)
                OR (status IN ('CONFIRMATION_REQUIRED', 'NOT_EVALUABLE')
                    AND prescription_mapping_ref IS NULL))
        );
        CREATE INDEX idx_mp_matching_status ON maintain_plan_matching_results(status);

        CREATE TABLE maintain_plan_execution_evaluations (
            evaluation_id TEXT PRIMARY KEY,
            prescription_mapping_ref TEXT NOT NULL REFERENCES maintain_plan_prescription_mappings(mapping_id),
            prescription_snapshot_ref TEXT NOT NULL REFERENCES maintain_plan_prescription_snapshots(prescription_snapshot_id),
            actual_session_ref TEXT NOT NULL REFERENCES maintain_plan_actual_sessions(session_id),
            overall TEXT CHECK (overall IS NULL OR overall IN
                ('IN_LINE', 'PARTIALLY_IN_LINE', 'DIFFERENT', 'INSUFFICIENT_DATA')),
            policy_id TEXT,
            policy_version TEXT,
            payload_schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            FOREIGN KEY (prescription_mapping_ref, prescription_snapshot_ref, actual_session_ref)
                REFERENCES maintain_plan_prescription_mappings
                    (mapping_id, prescription_snapshot_ref, actual_session_ref)
        );
        """


def _migration_1(connection: sqlite3.Connection) -> None:
    # executescript commits implicitly; individual statements preserve the
    # transaction owned by the runner.
    for statement in _MIGRATION_1_SQL.split(";"):
        if statement.strip():
            connection.execute(statement)


MIGRATIONS = (Migration(
    1,
    hashlib.sha256(_MIGRATION_1_SQL.encode("utf-8")).hexdigest(),
    _migration_1,
),)


def run_migrations(database_path: str | Path, migrations: Iterable[Migration] = MIGRATIONS) -> None:
    """Apply each migration exactly once and atomically, without touching legacy tables."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS maintain_plan_schema_migrations ("
            "version INTEGER PRIMARY KEY, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
        connection.commit()
        applied = dict(connection.execute(
            "SELECT version, checksum FROM maintain_plan_schema_migrations"
        ))
        for migration in sorted(migrations, key=lambda item: item.version):
            if migration.version in applied:
                if applied[migration.version] != migration.checksum:
                    raise RuntimeError(
                        f"MAINTAIN_PLAN migration {migration.version} checksum mismatch"
                    )
                continue
            try:
                connection.execute("BEGIN IMMEDIATE")
                migration.apply(connection)
                connection.execute(
                    "INSERT INTO maintain_plan_schema_migrations"
                    "(version, checksum, applied_at) VALUES (?, ?, ?)",
                    (migration.version, migration.checksum,
                     datetime.now(timezone.utc).isoformat()),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
    finally:
        connection.close()
