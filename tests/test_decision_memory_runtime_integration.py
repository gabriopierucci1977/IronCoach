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
        garmin_source_state_path=None,
    ):
        self.client = client
        self.runtime_config = runtime_config
        self.garmin_source_state_path = garmin_source_state_path

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
            "modified_workout": {
                "sport": "RUN",
                "duration_minutes": 40,
            },
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


class FakeDecisionMemoryOrchestrator:
    calls = []

    def save_decision(
        self,
        context,
        decision,
        airtable_record,
    ):
        self.__class__.calls.append(
            {
                "context": context,
                "decision": decision,
                "airtable_record": airtable_record,
            }
        )


def _reset_fakes():
    FakeDecisionMemoryOrchestrator.calls = []


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
        "create_decision_memory_orchestrator",
        lambda runtime_config: FakeDecisionMemoryOrchestrator(),
    )
    monkeypatch.setattr(
        main_module,
        "_sync_garmin_live_best_effort",
        lambda: None,
    )


def test_run_pipeline_uses_decision_memory_runtime_service(
    monkeypatch,
):
    _reset_fakes()
    _patch_dependencies(
        monkeypatch
    )

    report = main_module.run_pipeline()

    assert report == "REPORT TEST"

    assert len(
        FakeDecisionMemoryOrchestrator.calls
    ) == 1

    call = (
        FakeDecisionMemoryOrchestrator.calls[0]
    )

    assert (
        call["decision"]["decision"]
        == "ADATTA"
    )

    assert (
        call["airtable_record"]["id"]
        == "recDecision789"
    )


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
        FakeDecisionMemoryOrchestrator.calls
        == []
    )
