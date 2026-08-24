import backend.main as main_module


class FakeRuntimeConfig:
    recovery_max_age_days = 3
    training_max_age_days = 7
    decision_memory_database_path = (
        "data/test_ironcoach_memory.db"
    )


FAKE_RUNTIME_CONFIG = FakeRuntimeConfig()


def fake_get_runtime_config():
    return FAKE_RUNTIME_CONFIG


class FakeClient:
    pass


class FakeContextBuilder:
    def __init__(
        self,
        client,
        runtime_config=None,
    ):
        self.client = client
        self.runtime_config = runtime_config

    def build(self):
        return {
            "athlete": {
                "source": "airtable",
                "source_id": "recAthlete123",
                "identity": {
                    "name": "Gabrio",
                },
            },
            "athlete_profile": {
                "source": "airtable",
                "source_id": "recAthlete123",
                "identity": {
                    "name": "Gabrio",
                },
            },
            "training": {
                "source": "airtable",
                "source_id": "training-123",
                "sport": "RUN",
                "duration_minutes": 60,
            },
            "recovery": {
                "level": "LOW",
            },
            "nutrition": {},
            "decision": {},
            "training_history": [],
            "recovery_history": [],
            "performance_history": [],
            "data_freshness": {
                "level": "LOW",
                "reasons": [],
            },
            "context_warnings": [],
        }


class FakeCoachEngine:
    def __init__(
        self,
        runtime_config=None,
    ):
        self.runtime_config = runtime_config

    def evaluate(
        self,
        context,
    ):
        return {
            "decision": "ADATTA",
            "reason": "Test Decision Memory",
            "priority": "Performance",
            "confidence": 88,
            "strategy": "ADAPT",
            "recommended_action": (
                "Riduci moderatamente la seduta."
            ),
            "modified_workout": None,
            "reasoning": [],
            "risk_level": "CAUTION",
            "intelligence": {
                "data_freshness": context[
                    "data_freshness"
                ],
            },
            "decision_id": (
                "123e4567-e89b-42d3-a456-426614174000"
            ),
            "rule_id": (
                "PERFORMANCE_DECLINING_LOAD_HIGH"
            ),
            "primary_intent": (
                "PROTECT_PERFORMANCE"
            ),
            "supporting_intents": [
                "REDUCE_LOAD",
            ],
            "training_priority": (
                "SVILUPPO_PRESTAZIONE"
            ),
        }


class FakeWorkoutAdapter:
    def adapt(
        self,
        context,
        decision,
    ):
        return {
            "strategy": "ADAPT",
            "sport": "RUN",
            "duration_minutes": 40,
            "intensity": "EASY",
        }


class FakeReportBuilder:
    def build(
        self,
        context,
        decision,
    ):
        return "REPORT TEST"


class FakeDecisionWriter:
    def __init__(
        self,
        client,
    ):
        self.client = client

    def save(
        self,
        decision,
    ):
        return {
            "id": "recDecision789",
            "fields": {},
        }


class FakeDecisionMemoryRepository:
    initialized_paths = []
    created_episodes = []

    def __init__(
        self,
        database_path,
    ):
        self.database_path = database_path
        self.__class__.initialized_paths.append(
            database_path
        )

    def create(
        self,
        episode,
    ):
        self.__class__.created_episodes.append(
            episode
        )


def _reset_fakes():
    FakeDecisionMemoryRepository.initialized_paths = []
    FakeDecisionMemoryRepository.created_episodes = []


def _patch_dependencies(
    monkeypatch,
):
    monkeypatch.setattr(
        main_module,
        "get_runtime_config",
        fake_get_runtime_config,
    )
    monkeypatch.setattr(
        main_module,
        "AirtableClient",
        FakeClient,
    )
    monkeypatch.setattr(
        main_module,
        "ContextBuilder",
        FakeContextBuilder,
    )
    monkeypatch.setattr(
        main_module,
        "CoachEngine",
        FakeCoachEngine,
    )
    monkeypatch.setattr(
        main_module,
        "WorkoutAdapter",
        FakeWorkoutAdapter,
    )
    monkeypatch.setattr(
        main_module,
        "ReportBuilder",
        FakeReportBuilder,
    )
    monkeypatch.setattr(
        main_module,
        "DecisionWriter",
        FakeDecisionWriter,
    )
    monkeypatch.setattr(
        main_module,
        "DecisionMemoryRepository",
        FakeDecisionMemoryRepository,
        raising=False,
    )


def test_run_pipeline_creates_decision_memory_episode(
    monkeypatch,
):
    _reset_fakes()
    _patch_dependencies(
        monkeypatch
    )

    report = main_module.run_pipeline()

    assert report == "REPORT TEST"

    assert (
        FakeDecisionMemoryRepository.initialized_paths
        == [
            "data/test_ironcoach_memory.db",
        ]
    )

    assert len(
        FakeDecisionMemoryRepository.created_episodes
    ) == 1

    episode = (
        FakeDecisionMemoryRepository.created_episodes[0]
    )

    assert episode.athlete_id == "recAthlete123"

    assert (
        episode.decision_id
        == "123e4567-e89b-42d3-a456-426614174000"
    )

    assert episode.decision_action == "ADATTA"

    assert (
        episode.rule_id
        == "PERFORMANCE_DECLINING_LOAD_HIGH"
    )

    assert (
        episode.primary_intent
        == "PROTECT_PERFORMANCE"
    )

    assert episode.supporting_intents == [
        "REDUCE_LOAD",
    ]

    assert episode.strategy == "ADAPT"

    assert episode.decision_confidence == 88

    assert episode.planned_workout == {
        "source": "airtable",
        "source_id": "training-123",
        "sport": "RUN",
        "duration_minutes": 60,
    }

    assert episode.recommended_workout == {
        "strategy": "ADAPT",
        "sport": "RUN",
        "duration_minutes": 40,
        "intensity": "EASY",
    }

    assert episode.status == "OPEN"


def test_run_pipeline_dry_run_does_not_write_decision_memory(
    monkeypatch,
):
    _reset_fakes()
    _patch_dependencies(
        monkeypatch
    )

    report = main_module.run_pipeline(
        dry_run=True,
    )

    assert report == "REPORT TEST"

    assert (
        FakeDecisionMemoryRepository.initialized_paths
        == []
    )

    assert (
        FakeDecisionMemoryRepository.created_episodes
        == []
    )