"""
Test Decision Memory SQLite schema.

Lo schema SQLite costituisce il source of truth
persistente della Decision Memory di IronCoach.
"""

import sqlite3

from backend.decision_memory.schema import initialize_database


def test_initialize_database_creates_decision_episodes_table(
    tmp_path,
):
    database_path = (
        tmp_path
        / "ironcoach_memory.db"
    )

    initialize_database(
        database_path
    )

    assert database_path.exists()

    connection = sqlite3.connect(
        database_path
    )

    try:
        row = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'decision_episodes'
            """
        ).fetchone()
    finally:
        connection.close()

    assert row == (
        "decision_episodes",
    )


def test_decision_episodes_table_has_beta_04_columns(
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
            PRAGMA table_info(decision_episodes)
            """
        ).fetchall()
    finally:
        connection.close()

    columns = {
        row[1]
        for row in rows
    }

    assert columns == {
        "episode_id",
        "athlete_id",
        "decision_id",
        "decision_timestamp",
        "status",
        "schema_version",
        "decision_action",
        "strategy",
        "rule_id",
        "primary_intent",
        "decision_confidence",
        "supporting_intents_json",
        "pre_decision_state_json",
        "athlete_state_json",
        "planned_workout_json",
        "recommended_workout_json",
        "actual_activity_json",
        "actual_activity_id",
        "actual_activity_source",
        "adherence_status",
        "adherence_evidence_json",
        "adherence_evaluated_at",
        "outcome_24h_status",
        "outcome_24h_evidence_json",
        "outcome_24h_evaluated_at",
        "outcome_72h_status",
        "outcome_72h_evidence_json",
        "outcome_72h_evaluated_at",
        "outcome_7d_status",
        "outcome_7d_evidence_json",
        "outcome_7d_evaluated_at",
        "overall_outcome_status",
        "overall_outcome_confidence",
        "overall_outcome_evidence_json",
        "overall_outcome_evaluated_at",
        "decision_engine_version",
        "adherence_evaluator_version",
        "outcome_evaluator_version",
        "airtable_decision_record_id",
        "created_at",
        "updated_at",
    }