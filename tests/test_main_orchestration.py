"""
Test orchestrazione applicazione principale.

Verifica che il flusso principale:

- costruisca il contesto;
- valuti la decisione;
- applichi l'adattamento workout;
- generi il report;
- salvi la decisione finale;
- mantenga la freschezza dati strutturata lungo tutto il flusso.

Non usa servizi esterni.
"""

import backend.main as main_module


class FakeRuntimeConfig:
    recovery_max_age_days = 3
    training_max_age_days = 7


FAKE_RUNTIME_CONFIG = FakeRuntimeConfig()


def fake_get_runtime_config():
    return FAKE_RUNTIME_CONFIG


class FakeClient:
    pass


class FakeContextBuilder:
    built_context = None
    received_runtime_config = None

    def __init__(
        self,
        client,
        runtime_config=None,
    ):
        self.client = client
        FakeContextBuilder.received_runtime_config = (
            runtime_config
        )

    def build(
        self,
    ):
        context = {
            "athlete_profile": {},
            "training": {},
            "recovery": {},
            "nutrition": {},
            "decision": {},
            "data_freshness": {
                "level": "HIGH",
                "reasons": [
                    (
                        "Recovery: dato obsoleto di 12 giorni "
                        "(data 2026-07-25, soglia 3 giorni)"
                    ),
                ],
                "recovery": {
                    "status": "STALE",
                    "level": "HIGH",
                    "date": "2026-07-25",
                    "age_days": 12,
                    "max_age_days": 3,
                },
                "training": {
                    "status": "CURRENT",
                    "level": "LOW",
                    "date": "2026-08-05",
                    "age_days": 2,
                    "max_age_days": 7,
                },
            },
            "context_warnings": [
                (
                    "Recovery: dato obsoleto di 12 giorni "
                    "(data 2026-07-25, soglia 3 giorni)"
                ),
            ],
        }

        FakeContextBuilder.built_context = context
        return context


class FakeCoachEngine:
    received_context = None

    def evaluate(
        self,
        context,
    ):
        FakeCoachEngine.received_context = context

        freshness = context[
            "data_freshness"
        ]

        return {
            "decision": "ADATTA",
            "reason": "Test",
            "confidence": 75,
            "strategy": "ADAPT",
            "reasoning": [
                "Freschezza dati: alto",
                *freshness["reasons"],
            ],
            "intelligence": {
                "data_freshness": freshness,
            },
        }


class FakeWorkoutAdapter:
    received_context = None
    received_decision = None

    def adapt(
        self,
        context,
        decision,
    ):
        FakeWorkoutAdapter.received_context = context
        FakeWorkoutAdapter.received_decision = decision

        return {
            "strategy": "ADAPT",
            "duration_minutes": 40,
        }


class FakeReportBuilder:
    received_context = None
    received_decision = None

    def build(
        self,
        context,
        decision,
    ):
        FakeReportBuilder.received_context = context
        FakeReportBuilder.received_decision = decision

        assert decision[
            "modified_workout"
        ][
            "duration_minutes"
        ] == 40

        assert context[
            "data_freshness"
        ][
            "level"
        ] == "HIGH"

        assert decision[
            "intelligence"
        ][
            "data_freshness"
        ] is context[
            "data_freshness"
        ]

        return "REPORT TEST"


class FakeDecisionWriter:
    saved = None

    def __init__(
        self,
        client,
    ):
        self.client = client

    def save(
        self,
        decision,
    ):
        FakeDecisionWriter.saved = decision


def _reset_fakes() -> None:
    FakeContextBuilder.built_context = None
    FakeContextBuilder.received_runtime_config = None
    FakeCoachEngine.received_context = None
    FakeWorkoutAdapter.received_context = None
    FakeWorkoutAdapter.received_decision = None
    FakeReportBuilder.received_context = None
    FakeReportBuilder.received_decision = None
    FakeDecisionWriter.saved = None


def _patch_main_dependencies(
    monkeypatch,
) -> None:
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


def test_main_orchestration_keeps_full_flow(
    monkeypatch,
    capsys,
) -> None:
    _reset_fakes()
    _patch_main_dependencies(
        monkeypatch
    )

    main_module.main()

    assert FakeDecisionWriter.saved is not None

    assert (
        FakeDecisionWriter.saved[
            "decision"
        ]
        == "ADATTA"
    )

    assert (
        FakeDecisionWriter.saved[
            "modified_workout"
        ][
            "duration_minutes"
        ]
        == 40
    )

    output = capsys.readouterr().out

    assert "REPORT TEST" in output


def test_main_preserves_structured_freshness_end_to_end(
    monkeypatch,
) -> None:
    _reset_fakes()
    _patch_main_dependencies(
        monkeypatch
    )

    main_module.main()

    context = FakeContextBuilder.built_context
    saved = FakeDecisionWriter.saved

    assert context is not None
    assert saved is not None

    assert (
        FakeCoachEngine.received_context
        is context
    )

    assert (
        FakeWorkoutAdapter.received_context
        is context
    )

    assert (
        FakeReportBuilder.received_context
        is context
    )

    assert saved[
        "confidence"
    ] == 75

    assert saved[
        "intelligence"
    ][
        "data_freshness"
    ] is context[
        "data_freshness"
    ]

    assert (
        "Freschezza dati: alto"
        in saved[
            "reasoning"
        ]
    )

    assert (
        context[
            "data_freshness"
        ][
            "reasons"
        ][0]
        in saved[
            "reasoning"
        ]
    )


def test_main_passes_enriched_decision_to_report_and_writer(
    monkeypatch,
) -> None:
    _reset_fakes()
    _patch_main_dependencies(
        monkeypatch
    )

    main_module.main()

    report_decision = (
        FakeReportBuilder
        .received_decision
    )
    saved_decision = (
        FakeDecisionWriter
        .saved
    )

    assert report_decision is saved_decision

    assert report_decision[
        "modified_workout"
    ] == {
        "strategy": "ADAPT",
        "duration_minutes": 40,
    }

    assert (
        FakeWorkoutAdapter
        .received_decision[
            "intelligence"
        ][
            "data_freshness"
        ][
            "level"
        ]
        == "HIGH"
    )


def test_main_injects_single_runtime_config_into_context_builder(
    monkeypatch,
) -> None:
    _reset_fakes()
    _patch_main_dependencies(
        monkeypatch
    )

    main_module.main()

    assert (
        FakeContextBuilder
        .received_runtime_config
        is FAKE_RUNTIME_CONFIG
    )
