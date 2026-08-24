"""
Test Decision Memory SQLite constraints.

SQLite deve impedire la persistenza di valori
fuori dai vocabolari ufficiali della Decision Memory.
"""

import sqlite3

import pytest

from backend.decision_memory.schema import initialize_database


def _valid_episode_values():
    return {
        "episode_id": "episode-123",
        "athlete_id": "athlete-123",
        "decision_timestamp": "2026-08-24T09:00:00Z",
        "status": "OPEN",
        "schema_version": "1",
        "decision_action": "CONFERMA",
        "rule_id": "DEFAULT_CONFIRM",
        "primary_intent": "MAINTAIN_PLAN",
        "supporting_intents_json": "[]",
        "pre_decision_state_json": "{}",
        "athlete_state_json": "{}",
        "adherence_evidence_json": "{}",
        "outcome_24h_evidence_json": "{}",
        "outcome_72h_evidence_json": "{}",
        "outcome_7d_evidence_json": "{}",
        "overall_outcome_evidence_json": "{}",
        "created_at": "2026-08-24T09:00:00Z",
        "updated_at": "2026-08-24T09:00:00Z",
    }


def _insert_episode(
    connection,
    **overrides,
):
    values = _valid_episode_values()
    values.update(
        overrides
    )

    columns = ", ".join(
        values.keys()
    )

    placeholders = ", ".join(
        f":{key}"
        for key in values
    )

    connection.execute(
        f"""
        INSERT INTO decision_episodes (
            {columns}
        )
        VALUES (
            {placeholders}
        )
        """,
        values,
    )


def test_rejects_invalid_episode_status(
    tmp_path,
):
    database_path = (
        tmp_path
        / "ironcoach_memory.db"
    )

    initialize_database(
        database_path
    )

    connection = sqlite3.connect(
        database_path
    )

    try:
        with pytest.raises(
            sqlite3.IntegrityError
        ):
            _insert_episode(
                connection,
                status="DONE",
            )
    finally:
        connection.close()


def test_rejects_invalid_decision_action(
    tmp_path,
):
    database_path = (
        tmp_path
        / "ironcoach_memory.db"
    )

    initialize_database(
        database_path
    )

    connection = sqlite3.connect(
        database_path
    )

    try:
        with pytest.raises(
            sqlite3.IntegrityError
        ):
            _insert_episode(
                connection,
                decision_action="SKIP",
            )
    finally:
        connection.close()


def test_rejects_invalid_primary_intent(
    tmp_path,
):
    database_path = (
        tmp_path
        / "ironcoach_memory.db"
    )

    initialize_database(
        database_path
    )

    connection = sqlite3.connect(
        database_path
    )

    try:
        with pytest.raises(
            sqlite3.IntegrityError
        ):
            _insert_episode(
                connection,
                primary_intent="RECOVER",
            )
    finally:
        connection.close()


def test_rejects_invalid_adherence_status(
    tmp_path,
):
    database_path = (
        tmp_path
        / "ironcoach_memory.db"
    )

    initialize_database(
        database_path
    )

    connection = sqlite3.connect(
        database_path
    )

    try:
        with pytest.raises(
            sqlite3.IntegrityError
        ):
            _insert_episode(
                connection,
                adherence_status="YES",
            )
    finally:
        connection.close()


@pytest.mark.parametrize(
    "column",
    [
        "outcome_24h_status",
        "outcome_72h_status",
        "outcome_7d_status",
        "overall_outcome_status",
    ],
)
def test_rejects_invalid_outcome_status(
    tmp_path,
    column,
):
    database_path = (
        tmp_path
        / "ironcoach_memory.db"
    )

    initialize_database(
        database_path
    )

    connection = sqlite3.connect(
        database_path
    )

    try:
        with pytest.raises(
            sqlite3.IntegrityError
        ):
            _insert_episode(
                connection,
                **{
                    column: "SUCCESS",
                },
            )
    finally:
        connection.close()