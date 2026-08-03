"""
Test del runner di anteprima report.

Il runner deve:
- costruire il contesto;
- eseguire CoachEngine;
- applicare WorkoutAdapter;
- costruire il report;
- non importare né usare DecisionWriter;
- non scrivere su Airtable.
"""

import importlib
import inspect


def test_preview_module_does_not_reference_decision_writer() -> None:
    module = importlib.import_module(
        "backend.report_preview"
    )

    source = inspect.getsource(
        module
    )

    assert "DecisionWriter" not in source
    assert ".save(" not in source


def test_generate_report_preview_runs_safe_pipeline(
    monkeypatch,
) -> None:
    module = importlib.import_module(
        "backend.report_preview"
    )

    events = []

    fake_client = object()

    class FakeAirtableClient:
        def __new__(
            cls,
        ):
            events.append(
                "client"
            )
            return fake_client

    class FakeContextBuilder:
        def __init__(
            self,
            client,
        ):
            assert client is fake_client
            events.append(
                "builder_init"
            )

        def build(
            self,
        ):
            events.append(
                "context"
            )
            return {
                "training": {
                    "sport": "RUN",
                },
            }

    class FakeCoachEngine:
        def evaluate(
            self,
            context,
        ):
            assert context == {
                "training": {
                    "sport": "RUN",
                },
            }
            events.append(
                "decision"
            )
            return {
                "decision": "CONFERMA",
            }

    class FakeWorkoutAdapter:
        def adapt(
            self,
            *,
            context,
            decision,
        ):
            assert context[
                "training"
            ][
                "sport"
            ] == "RUN"
            assert decision[
                "decision"
            ] == "CONFERMA"
            events.append(
                "workout"
            )
            return {
                "sport": "RUN",
                "duration_minutes": 45,
            }

    class FakeReportBuilder:
        def build(
            self,
            context,
            decision,
        ):
            assert decision[
                "modified_workout"
            ] == {
                "sport": "RUN",
                "duration_minutes": 45,
            }
            events.append(
                "report"
            )
            return "REPORT SICURO"

    monkeypatch.setattr(
        module,
        "AirtableClient",
        FakeAirtableClient,
    )
    monkeypatch.setattr(
        module,
        "ContextBuilder",
        FakeContextBuilder,
    )
    monkeypatch.setattr(
        module,
        "CoachEngine",
        FakeCoachEngine,
    )
    monkeypatch.setattr(
        module,
        "WorkoutAdapter",
        FakeWorkoutAdapter,
    )
    monkeypatch.setattr(
        module,
        "ReportBuilder",
        FakeReportBuilder,
    )

    report = module.generate_report_preview()

    assert report == "REPORT SICURO"
    assert events == [
        "client",
        "builder_init",
        "context",
        "decision",
        "workout",
        "report",
    ]


def test_generate_report_preview_accepts_existing_client(
    monkeypatch,
) -> None:
    module = importlib.import_module(
        "backend.report_preview"
    )

    fake_client = object()
    received = {}

    class ForbiddenAirtableClient:
        def __new__(
            cls,
        ):
            raise AssertionError(
                "AirtableClient non deve essere creato"
            )

    class FakeContextBuilder:
        def __init__(
            self,
            client,
        ):
            received[
                "client"
            ] = client

        def build(
            self,
        ):
            return {}

    class FakeCoachEngine:
        def evaluate(
            self,
            context,
        ):
            return {}

    class FakeWorkoutAdapter:
        def adapt(
            self,
            *,
            context,
            decision,
        ):
            return {}

    class FakeReportBuilder:
        def build(
            self,
            context,
            decision,
        ):
            return "REPORT"

    monkeypatch.setattr(
        module,
        "AirtableClient",
        ForbiddenAirtableClient,
    )
    monkeypatch.setattr(
        module,
        "ContextBuilder",
        FakeContextBuilder,
    )
    monkeypatch.setattr(
        module,
        "CoachEngine",
        FakeCoachEngine,
    )
    monkeypatch.setattr(
        module,
        "WorkoutAdapter",
        FakeWorkoutAdapter,
    )
    monkeypatch.setattr(
        module,
        "ReportBuilder",
        FakeReportBuilder,
    )

    assert module.generate_report_preview(
        client=fake_client
    ) == "REPORT"

    assert received[
        "client"
    ] is fake_client