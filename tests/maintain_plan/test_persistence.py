"""Temporary-database tests for the isolated MAINTAIN_PLAN persistence layer."""

import sqlite3
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path

import pytest

from backend.maintain_plan.models import (
    ActualSession, MatchingResult, MatchingStatus, PolicyRef,
)
from backend.maintain_plan.repository import MaintainPlanRepository
from backend.maintain_plan.schema import Migration, run_migrations
from backend.maintain_plan.serialization import PAYLOAD_SCHEMA_VERSION
from backend.maintain_plan.serialization import deserialize_contract, serialize_contract
from tests.maintain_plan.fixtures import (
    NOW, RUN_EXECUTION, RUN_MAPPING, RUN_PRESCRIPTION, RUN_SESSION,
)


TABLES = {
    "maintain_plan_schema_migrations",
    "maintain_plan_prescription_snapshots",
    "maintain_plan_actual_sessions",
    "maintain_plan_prescription_mappings",
    "maintain_plan_matching_results",
    "maintain_plan_execution_evaluations",
}


def _tables(path):
    with sqlite3.connect(path) as connection:
        return {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}


def test_migration_on_empty_database_is_versioned_and_idempotent(tmp_path):
    path = tmp_path / "empty.db"
    run_migrations(path)
    assert TABLES <= _tables(path)
    with sqlite3.connect(path) as connection:
        before = connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall()
        versions = connection.execute(
            "SELECT version, checksum FROM maintain_plan_schema_migrations"
        ).fetchall()
        assert [item[0] for item in versions] == [1, 2]
        assert all(len(item[1]) == 64 for item in versions)
    run_migrations(path)
    with sqlite3.connect(path) as connection:
        after = connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall()
        assert before == after
        assert connection.execute(
            "SELECT count(*) FROM maintain_plan_schema_migrations"
        ).fetchone() == (2,)


def test_migration_preserves_legacy_schema_and_record_exactly(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE decision_episodes (episode_id TEXT PRIMARY KEY, payload TEXT)")
        connection.execute("INSERT INTO decision_episodes VALUES ('legacy-1', 'unchanged')")
        legacy_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='decision_episodes'"
        ).fetchone()[0]
    run_migrations(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='decision_episodes'"
        ).fetchone()[0] == legacy_sql
        assert connection.execute("SELECT * FROM decision_episodes").fetchall() == [
            ("legacy-1", "unchanged")
        ]


def test_failed_migration_rolls_back_every_statement(tmp_path):
    path = tmp_path / "rollback.db"

    def fail(connection):
        connection.execute("CREATE TABLE should_rollback (id INTEGER)")
        connection.execute("THIS IS NOT SQL")

    with pytest.raises(sqlite3.OperationalError):
        run_migrations(path, (Migration(2, "failed-migration", fail),))
    assert "should_rollback" not in _tables(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT version, checksum FROM maintain_plan_schema_migrations"
        ).fetchall() == []


def test_applied_migration_rejects_changed_content_for_same_version(tmp_path):
    path = tmp_path / "checksum.db"
    run_migrations(path)
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        run_migrations(path, (Migration(1, "different-content", lambda connection: None),))


def test_insert_read_round_trip_reopen_and_deep_immutability(tmp_path):
    path = tmp_path / "roundtrip.db"
    repository = MaintainPlanRepository(path)
    repository.create_prescription_snapshot(RUN_PRESCRIPTION)
    repository.create_actual_session(RUN_SESSION)
    repository.create_prescription_mapping(RUN_MAPPING)
    matching = MatchingResult("match-1", MatchingStatus.MATCHED, RUN_MAPPING,
                              PolicyRef("maintain-plan-matching", "1.0.0-draft"))
    repository.create_matching_result(matching)
    repository.create_execution_evaluation(RUN_EXECUTION)

    reopened = MaintainPlanRepository(path)
    assert reopened.get_prescription_snapshot("snapshot-1") == RUN_PRESCRIPTION
    actual = reopened.get_actual_session("session-1")
    assert actual == RUN_SESSION
    assert reopened.get_prescription_mapping("mapping-1") == RUN_MAPPING
    assert reopened.get_matching_result("match-1") == matching
    assert reopened.get_execution_evaluation("evaluation-1") == RUN_EXECUTION
    assert actual.components[0].quantity_observation["seconds"] == 3600
    with pytest.raises(TypeError):
        actual.components[0].quantity_observation["seconds"] = 1
    with pytest.raises(FrozenInstanceError):
        actual.session_id = "changed"


def test_round_trip_preserves_none_tuple_frozenset_and_nested_mapping(tmp_path):
    session = ActualSession(
        "session-complex", NOW, None,
        (RUN_SESSION.components[0].__class__(
            "run", 0, None, (),
            {"missing": None, "nested": {"tuple": (1, 2), "set": frozenset({"b", "a"})}},
        ),),
    )
    repository = MaintainPlanRepository(tmp_path / "complex.db")
    repository.create_actual_session(session)
    restored = repository.get_actual_session("session-complex")
    assert restored == session
    assert restored.composition is None
    assert isinstance(restored.components, tuple)
    assert restored.components[0].quantity_observation["nested"]["set"] == frozenset({"a", "b"})
    with pytest.raises(TypeError):
        restored.components[0].quantity_observation["nested"]["new"] = 1


@pytest.mark.parametrize("kind", ["snapshot", "session", "mapping", "matching", "evaluation"])
def test_duplicate_ids_are_rejected_without_overwrite(tmp_path, kind):
    repository = MaintainPlanRepository(tmp_path / "duplicates.db")
    repository.create_prescription_snapshot(RUN_PRESCRIPTION)
    repository.create_actual_session(RUN_SESSION)
    repository.create_prescription_mapping(RUN_MAPPING)
    matching = MatchingResult("match-1", MatchingStatus.MATCHED, RUN_MAPPING, PolicyRef("p", "1"))
    creators = {
        "snapshot": (repository.create_prescription_snapshot, RUN_PRESCRIPTION),
        "session": (repository.create_actual_session, RUN_SESSION),
        "mapping": (repository.create_prescription_mapping, RUN_MAPPING),
        "matching": (repository.create_matching_result, matching),
        "evaluation": (repository.create_execution_evaluation, RUN_EXECUTION),
    }
    create, value = creators[kind]
    if kind in {"matching", "evaluation"}:
        create(value)
    with pytest.raises(sqlite3.IntegrityError):
        create(value)


def test_required_references_and_exact_mapping_are_enforced(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "refs.db")
    with pytest.raises(ValueError, match="persisted snapshot"):
        repository.create_prescription_mapping(RUN_MAPPING)
    repository.create_prescription_snapshot(RUN_PRESCRIPTION)
    repository.create_actual_session(RUN_SESSION)
    repository.create_prescription_mapping(RUN_MAPPING)
    wrong = MatchingResult("match-wrong", MatchingStatus.MATCHED,
                           RUN_MAPPING.__class__("other", "snapshot-1", "session-1",
                                                 RUN_MAPPING.resolution_method,
                                                 RUN_MAPPING.component_mappings), PolicyRef("p", "1"))
    with pytest.raises(ValueError, match="exact persisted mapping"):
        repository.create_matching_result(wrong)
    broken_evaluation = RUN_EXECUTION.__class__(
        RUN_EXECUTION.evaluation_id, RUN_EXECUTION.prescription_mapping_ref,
        "wrong-snapshot", RUN_EXECUTION.actual_session_ref,
        RUN_EXECUTION.component_results, RUN_EXECUTION.session_composition_result,
        RUN_EXECUTION.evaluation_coverage, RUN_EXECUTION.identity_aggregate,
        RUN_EXECUTION.quantity_aggregate, RUN_EXECUTION.intensity_aggregate,
        RUN_EXECUTION.structure_aggregate, RUN_EXECUTION.dose_aggregate,
        RUN_EXECUTION.overall, RUN_EXECUTION.policy,
    )
    with pytest.raises(ValueError, match="exact persisted mapping"):
        repository.create_execution_evaluation(broken_evaluation)


def test_schema_has_explicit_versions_constraints_and_no_backfill(tmp_path):
    path = tmp_path / "schema.db"
    repository = MaintainPlanRepository(path)
    repository.create_prescription_snapshot(RUN_PRESCRIPTION)
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT contract_version, payload_schema_version FROM maintain_plan_prescription_snapshots"
        ).fetchone() == (RUN_PRESCRIPTION.contract_version, PAYLOAD_SCHEMA_VERSION)
        assert all(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
                   for table in TABLES - {"maintain_plan_schema_migrations",
                                          "maintain_plan_prescription_snapshots"})
    assert not any(name.startswith("update_") or name.startswith("upsert_")
                   for name in dir(repository))


def test_schema_allows_versioned_results_for_same_relationship(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "versions.db")
    repository.create_prescription_snapshot(RUN_PRESCRIPTION)
    repository.create_actual_session(RUN_SESSION)
    repository.create_prescription_mapping(RUN_MAPPING)
    second_mapping = replace(RUN_MAPPING, mapping_id="mapping-2")
    repository.create_prescription_mapping(second_mapping)
    repository.create_execution_evaluation(RUN_EXECUTION)
    repository.create_execution_evaluation(replace(RUN_EXECUTION, evaluation_id="evaluation-2"))
    assert repository.get_prescription_mapping("mapping-2") == second_mapping
    assert repository.get_execution_evaluation("evaluation-2").evaluation_id == "evaluation-2"


def test_schema_enforces_matching_state_and_exact_evaluation_relationship(tmp_path):
    path = tmp_path / "schema-relations.db"
    repository = MaintainPlanRepository(path)
    repository.create_prescription_snapshot(RUN_PRESCRIPTION)
    repository.create_actual_session(RUN_SESSION)
    repository.create_prescription_mapping(RUN_MAPPING)
    payload = serialize_contract(MatchingResult(
        "unresolved", MatchingStatus.CONFIRMATION_REQUIRED, None, PolicyRef("p", "1")))
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO maintain_plan_matching_results VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("invalid", "CONFIRMATION_REQUIRED", "mapping-1", "p", "1",
                 PAYLOAD_SCHEMA_VERSION, payload),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO maintain_plan_execution_evaluations VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("invalid", "mapping-1", "snapshot-1", "different-session", None,
                 "p", "1", PAYLOAD_SCHEMA_VERSION, serialize_contract(RUN_EXECUTION)),
            )


@pytest.mark.parametrize("mutation", [
    lambda envelope: envelope.update(payload_schema_version="unknown"),
    lambda envelope: envelope.update(extra=True),
    lambda envelope: envelope["payload"].update(name="UnknownContract"),
    lambda envelope: envelope["payload"]["fields"].pop("session_id"),
])
def test_codec_rejects_unknown_versions_types_and_malformed_shapes(mutation):
    envelope = json.loads(serialize_contract(RUN_SESSION))
    mutation(envelope)
    with pytest.raises(ValueError):
        deserialize_contract(json.dumps(envelope), ActualSession)
    with pytest.raises(ValueError, match="expected PrescriptionSnapshot"):
        deserialize_contract(serialize_contract(RUN_SESSION), type(RUN_PRESCRIPTION))


def test_reads_reject_corrupt_payload_metadata_and_invalid_contract(tmp_path):
    path = tmp_path / "tampered.db"
    repository = MaintainPlanRepository(path)
    repository.create_actual_session(RUN_SESSION)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE maintain_plan_actual_sessions SET composition = 'brick' WHERE session_id = ?",
            (RUN_SESSION.session_id,),
        )
    with pytest.raises(ValueError, match="metadata does not match"):
        repository.get_actual_session(RUN_SESSION.session_id)

    invalid = replace(RUN_SESSION, components=(RUN_SESSION.components[0], RUN_SESSION.components[0]))
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE maintain_plan_actual_sessions SET composition = ?, payload_json = ? WHERE session_id = ?",
            (RUN_SESSION.composition.value, serialize_contract(invalid), RUN_SESSION.session_id),
        )
    with pytest.raises(ValueError, match="component_id must be unique"):
        repository.get_actual_session(RUN_SESSION.session_id)


def test_existing_runtime_does_not_import_persistence_layer():
    backend = Path(__file__).parents[2] / "backend"
    runtime_files = [path for path in backend.rglob("*.py")
                     if "maintain_plan" not in path.parts]
    forbidden = "backend.maintain_plan." + "repository"
    assert not [path for path in runtime_files if forbidden in path.read_text(encoding="utf-8")]
