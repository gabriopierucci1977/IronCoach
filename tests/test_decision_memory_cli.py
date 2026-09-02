"""
Test Decision Memory CLI.
"""

import backend.main as main_module
from backend.decision_memory.factory import (
    create_decision_memory_orchestrator,
)
from backend.decision_memory.repository import (
    DecisionMemoryRepository,
)
from backend.models.decision_episode import (
    DecisionEpisode,
)


def test_main_accepts_decision_memory_flag():

    parser = main_module._build_argument_parser()

    args = parser.parse_args(
        [
            "--decision-memory",
        ]
    )

    assert args.decision_memory is True


def test_main_accepts_process_pending_memory_flag():
    parser = main_module._build_argument_parser()

    args = parser.parse_args(
        ["--process-pending-memory"]
    )

    assert args.process_pending_memory is True


def test_process_pending_memory_uses_only_existing_runtime_paths(
    monkeypatch,
):
    calls = []

    class FakeBuilder:
        def __init__(self, client, **kwargs):
            calls.append(("builder", client, kwargs))

        def build(self):
            return {
                "athlete": {"source_id": "athlete-test"},
                "garmin_training_history": ["activity"],
                "recovery_history": ["recovery"],
                "airtable_training_history": ["training"],
                "context_warnings": [],
            }

    class FakeOrchestrator:
        def process_activity(self, athlete_id, activities):
            calls.append(
                ("activity", athlete_id, activities)
            )

        def process_outcome(self, athlete_id, **kwargs):
            calls.append(
                ("outcome", athlete_id, kwargs)
            )
            return []

        def save_decision(self, *args, **kwargs):
            raise AssertionError(
                "the command must not save a decision"
            )

    monkeypatch.setattr(
        main_module,
        "get_runtime_config",
        lambda: "config",
    )
    monkeypatch.setattr(
        main_module,
        "AirtableClient",
        lambda: "fake-client",
    )
    monkeypatch.setattr(
        main_module,
        "ContextBuilder",
        FakeBuilder,
    )
    monkeypatch.setattr(
        main_module,
        "GarminRecoveryArchive",
        lambda: "fake-archive",
    )
    monkeypatch.setattr(
        main_module,
        "create_decision_memory_orchestrator",
        lambda config: FakeOrchestrator(),
    )
    monkeypatch.setattr(
        main_module,
        "CoachEngine",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("CoachEngine must not run")
        ),
    )
    monkeypatch.setattr(
        main_module,
        "DecisionWriter",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("DecisionWriter must not run")
        ),
    )

    assert main_module.main(
        ["--process-pending-memory"]
    ) == 0

    assert [call[0] for call in calls] == [
        "builder",
        "activity",
        "outcome",
    ]
    assert calls[1] == (
        "activity",
        "athlete-test",
        ["activity"],
    )
    assert calls[2] == (
        "outcome",
        "athlete-test",
        {
            "recovery_history": ["recovery"],
            "airtable_training_history": ["training"],
        },
    )


def test_process_pending_memory_does_not_force_immature_episode(
    tmp_path,
):
    database_path = tmp_path / "memory.db"

    class Config:
        decision_memory_database_path = str(
            database_path
        )

    repository = DecisionMemoryRepository(
        str(database_path)
    )
    episode = DecisionEpisode(
        athlete_id="athlete-test",
        decision_timestamp=main_module._utc_now(),
        decision_action="ADATTA",
        rule_id="RECOVERY_LOW",
        primary_intent="RESTORE_RECOVERY",
        pre_decision_state={
            "recovery": {"level": "LOW"},
        },
        athlete_state={},
        status="WAITING_FOR_OUTCOME",
        planned_workout={"sport": "RUN"},
        actual_activity={"sport": "RUN"},
    )
    repository.create(episode)

    orchestrator = create_decision_memory_orchestrator(
        Config()
    )
    main_module._process_pending_decision_memory(
        orchestrator=orchestrator,
        athlete_id="athlete-test",
        context={
            "recovery_history": [],
            "airtable_training_history": [],
        },
    )

    stored = repository.get_by_episode_id(
        episode.episode_id
    )
    assert stored.status == "WAITING_FOR_OUTCOME"
    assert stored.outcome_24h_status is None
    assert stored.outcome_72h_status is None
    assert stored.outcome_7d_status is None
    assert repository.list_pending_by_athlete(
        "athlete-test"
    ) == [stored]
