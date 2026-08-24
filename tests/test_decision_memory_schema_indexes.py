"""
Test Decision Memory SQLite indexes.

Gli indici devono supportare le query principali
della Decision Memory senza sovra-indicizzare
la tabella decision_episodes.
"""

import sqlite3

from backend.decision_memory.schema import initialize_database


def test_decision_episodes_has_query_indexes(
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
        rows = connection.execute(
            """
            PRAGMA index_list(decision_episodes)
            """
        ).fetchall()
    finally:
        connection.close()

    indexes = {
        row[1]
        for row in rows
    }

    assert (
        "idx_decision_episodes_athlete_timestamp"
        in indexes
    )

    assert (
        "idx_decision_episodes_athlete_intent"
        in indexes
    )

    assert (
        "idx_decision_episodes_athlete_outcome"
        in indexes
    )

    assert (
        "idx_decision_episodes_status"
        in indexes
    )