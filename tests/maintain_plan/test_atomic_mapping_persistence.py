"""Focused atomicity, idempotency, and concurrency tests for decided mappings."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import sqlite3
import threading
import time

import pytest

from backend.maintain_plan.models import ObservedComponentRef, PlannedComponentRef
from backend.maintain_plan.repository import MaintainPlanRepository
from backend.maintain_plan.schema import MIGRATIONS, Migration, run_migrations
from backend.maintain_plan.serialization import PAYLOAD_SCHEMA_VERSION, serialize_contract
from tests.maintain_plan.fixtures import RUN_MAPPING, RUN_PRESCRIPTION, RUN_SESSION


def _mapping(mapping_id="mapping-1", snapshot_id="snapshot-1", session_id="session-1"):
    component = RUN_MAPPING.component_mappings[0]
    return replace(
        RUN_MAPPING,
        mapping_id=mapping_id,
        prescription_snapshot_ref=snapshot_id,
        actual_session_ref=session_id,
        component_mappings=(replace(
            component,
            planned_component_ref=PlannedComponentRef(snapshot_id, "run"),
            observed_component_ref=ObservedComponentRef(session_id, "run"),
        ),),
    )


def _seed(repository, *, second_snapshot=False, second_session=False):
    repository.create_prescription_snapshot(RUN_PRESCRIPTION)
    repository.create_actual_session(RUN_SESSION)
    if second_snapshot:
        repository.create_prescription_snapshot(replace(
            RUN_PRESCRIPTION, prescription_snapshot_id="snapshot-2", decision_id="decision-2"))
    if second_session:
        repository.create_actual_session(replace(RUN_SESSION, session_id="session-2"))


def _count(repository):
    with sqlite3.connect(repository.database_path) as connection:
        return connection.execute(
            "SELECT count(*) FROM maintain_plan_prescription_mappings"
        ).fetchone()[0]


def test_successful_mapping_and_identical_retry(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "mapping.db")
    _seed(repository)
    assert repository.persist_prescription_mapping(RUN_MAPPING) == RUN_MAPPING
    assert repository.persist_prescription_mapping(RUN_MAPPING) == RUN_MAPPING
    assert _count(repository) == 1


def test_same_mapping_id_with_different_content_fails_closed(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "mapping.db")
    _seed(repository)
    repository.persist_prescription_mapping(RUN_MAPPING)
    with pytest.raises(ValueError, match="mapping_id already exists"):
        repository.persist_prescription_mapping(replace(RUN_MAPPING, actor="different"))
    assert _count(repository) == 1


@pytest.mark.parametrize(("first", "retry", "message"), [
    (_mapping(session_id="session-1"), _mapping("mapping-2", session_id="session-2"),
     "snapshot is already mapped"),
    (_mapping(snapshot_id="snapshot-1"), _mapping("mapping-2", snapshot_id="snapshot-2"),
     "session is already mapped"),
    (RUN_MAPPING, _mapping("mapping-2"), "snapshot is already mapped"),
])
def test_each_uniqueness_conflict_fails_closed(tmp_path, first, retry, message):
    repository = MaintainPlanRepository(tmp_path / "mapping.db")
    _seed(repository, second_snapshot=True, second_session=True)
    repository.persist_prescription_mapping(first)
    with pytest.raises(ValueError, match=message):
        repository.persist_prescription_mapping(retry)
    assert _count(repository) == 1


@pytest.mark.parametrize("artifact", ["missing-snapshot", "missing-session", "corrupt-snapshot",
                                      "corrupt-session"])
def test_missing_or_corrupt_artifacts_roll_back_without_a_mapping(tmp_path, artifact):
    repository = MaintainPlanRepository(tmp_path / "mapping.db")
    _seed(repository)
    with sqlite3.connect(repository.database_path) as connection:
        if artifact == "missing-snapshot":
            connection.execute("DELETE FROM maintain_plan_prescription_snapshots")
        elif artifact == "missing-session":
            connection.execute("DELETE FROM maintain_plan_actual_sessions")
        else:
            table = ("maintain_plan_prescription_snapshots" if artifact == "corrupt-snapshot"
                     else "maintain_plan_actual_sessions")
            connection.execute(f"UPDATE {table} SET payload_json='not-json'")
    with pytest.raises((ValueError, TypeError)):
        repository.persist_prescription_mapping(RUN_MAPPING)
    assert _count(repository) == 0


def test_cross_subject_and_legacy_null_ownership_fail_closed(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "mapping.db")
    _seed(repository)
    with sqlite3.connect(repository.database_path) as connection:
        session = replace(RUN_SESSION, subject_ref="athlete-2")
        connection.execute(
            "UPDATE maintain_plan_actual_sessions SET subject_ref=?, payload_json=?",
            (session.subject_ref, serialize_contract(session)),
        )
    with pytest.raises(ValueError, match="subject_ref mismatch"):
        repository.persist_prescription_mapping(RUN_MAPPING)
    assert _count(repository) == 0

    with sqlite3.connect(repository.database_path) as connection:
        legacy = replace(RUN_SESSION, subject_ref=None)
        connection.execute(
            "UPDATE maintain_plan_actual_sessions SET subject_ref=NULL, payload_json=?",
            (serialize_contract(legacy),),
        )
    with pytest.raises(ValueError, match="requires subject_ref"):
        repository.persist_prescription_mapping(RUN_MAPPING)
    assert _count(repository) == 0


def test_artifact_mutation_since_decision_is_revalidated_transactionally(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "mapping.db")
    _seed(repository)
    mutated = replace(
        RUN_PRESCRIPTION,
        components=(replace(RUN_PRESCRIPTION.components[0], component_id="other"),),
    )
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute(
            "UPDATE maintain_plan_prescription_snapshots SET payload_json=?",
            (serialize_contract(mutated),),
        )
    with pytest.raises(ValueError, match="dangling|unresolvable component"):
        repository.persist_prescription_mapping(RUN_MAPPING)
    assert _count(repository) == 0


def test_corrupt_existing_mapping_rolls_back_retry(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "mapping.db")
    _seed(repository)
    repository.persist_prescription_mapping(RUN_MAPPING)
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute(
            "UPDATE maintain_plan_prescription_mappings SET payload_json='not-json'"
        )
    with pytest.raises((ValueError, TypeError)):
        repository.persist_prescription_mapping(RUN_MAPPING)
    assert _count(repository) == 1


def test_concurrent_conflicting_writers_have_exactly_one_success(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "mapping.db")
    _seed(repository, second_session=True)
    barrier = threading.Barrier(2)

    def persist(value):
        barrier.wait()
        try:
            return repository.persist_prescription_mapping(value)
        except ValueError:
            return None

    candidates = (RUN_MAPPING, _mapping("mapping-2", session_id="session-2"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(persist, candidates))
    assert sum(result is not None for result in results) == 1
    assert _count(repository) == 1


def test_concurrent_identical_retries_observe_same_mapping(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "mapping.db")
    _seed(repository)
    barrier = threading.Barrier(2)

    def persist():
        barrier.wait()
        return repository.persist_prescription_mapping(RUN_MAPPING)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: persist(), range(2)))
    assert results == [RUN_MAPPING, RUN_MAPPING]
    assert _count(repository) == 1


def test_concurrent_v8_initializers_accept_locked_winner_record(tmp_path):
    path = tmp_path / "upgrade.db"
    run_migrations(path, MIGRATIONS[:7])
    entered = threading.Event()
    original = MIGRATIONS[7]

    def slow_apply(connection):
        entered.set()
        time.sleep(0.2)  # permits the loser to take its pre-lock migration snapshot
        original.apply(connection)

    slow_v8 = Migration(original.version, original.checksum, slow_apply)

    with ThreadPoolExecutor(max_workers=2) as pool:
        winner = pool.submit(run_migrations, path, (slow_v8,))
        assert entered.wait(timeout=2)
        loser = pool.submit(run_migrations, path, (original,))
        winner.result()
        loser.result()

    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT checksum FROM maintain_plan_schema_migrations WHERE version=8"
        ).fetchone() == (original.checksum,)
        assert {row[1] for row in connection.execute(
            "PRAGMA index_list('maintain_plan_prescription_mappings')"
        ) if row[2]} >= {
            "idx_mp_mappings_snapshot_unique", "idx_mp_mappings_session_unique"
        }
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
