"""
Test di integrazione del flusso principale con WorkoutAdapter.
"""

import backend.main as main_module


class FakeRuntimeConfig:
    recovery_max_age_days = 3
    training_max_age_days = 7


def test_main_attaches_priority_aware_modified_workout(
    monkeypatch,
    capsys,
) -> None:
    captured = {}
    runtime_config = FakeRuntimeConfig()

    context = {
        "training": {
            "sport": "RUN",
            "Nome seduta": "Seduta qualità",
            "Tipo seduta": "Intervalli",
            "Zona prevista": "Z4",
            "Durata minuti": 60,
        },
    }

    decision = {
        "strategy": "ADAPT",
        "training_priority": "SPECIFICITA_GARA",
        "reason": "Test",
        "recommended_action": "Test",
    }

    class FakeAirtableClient:
        pass

    class FakeContextBuilder:
        def __init__(
            self,
            client,
            runtime_config=None,
        ):
            captured["context_client"] = client
            captured[
                "context_runtime_config"
            ] = runtime_config

        def build(self):
            return context

    class FakeCoachEngine:
        def __init__(
            self,
            runtime_config=None,
        ):
            captured[
                "coach_runtime_config"
            ] = runtime_config

        def evaluate(
            self,
            received_context,
        ):
            captured[
                "coach_context"
            ] = received_context
            return dict(decision)

    class FakeDecisionWriter:
        def __init__(
            self,
            client,
        ):
            captured[
                "writer_client"
            ] = client

        def save(
            self,
            saved_decision,
        ):
            captured[
                "saved_decision"
            ] = saved_decision

    class FakeReportBuilder:
        def build(
            self,
            received_context,
            received_decision,
        ):
            captured[
                "report_context"
            ] = received_context
            captured[
                "report_decision"
            ] = received_decision
            return "REPORT TEST"

    monkeypatch.setattr(
        main_module,
        "get_runtime_config",
        lambda: runtime_config,
    )
    monkeypatch.setattr(
        main_module,
        "AirtableClient",
        FakeAirtableClient,
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
        "DecisionWriter",
        FakeDecisionWriter,
    )
    monkeypatch.setattr(
        main_module,
        "ReportBuilder",
        FakeReportBuilder,
    )

    main_module.main()

    saved_decision = captured[
        "saved_decision"
    ]
    workout = saved_decision[
        "modified_workout"
    ]

    assert captured[
        "context_runtime_config"
    ] is runtime_config
    assert captured[
        "coach_runtime_config"
    ] is runtime_config
    assert captured[
        "coach_context"
    ] is context
    assert captured[
        "report_context"
    ] is context
    assert captured[
        "report_decision"
    ] is saved_decision

    assert workout[
        "strategy"
    ] == "ADAPT"
    assert workout[
        "training_priority"
    ] == "SPECIFICITA_GARA"
    assert workout[
        "stimulus_adjustment"
    ][
        "type"
    ] == "SPECIFICITY"
    assert workout[
        "intensity"
    ] == "Z2-Z4 controllata"
    assert "ritmo gara" in workout[
        "main_set"
    ]

    output = capsys.readouterr().out
    assert "IRONCOACH BETA 0.3" in output
    assert "REPORT TEST" in output