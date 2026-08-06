"""
Test di integrazione report preview con training priority.
"""

import backend.report_preview as preview_module


def test_report_preview_includes_priority_aware_workout(
    monkeypatch,
) -> None:
    captured = {}

    context = {
        "training": {
            "sport": "BIKE",
            "Nome seduta": "Seduta qualità",
            "Tipo seduta": "Intervalli",
            "Zona prevista": "Z4",
            "Durata minuti": 60,
        },
    }

    decision = {
        "strategy": "ADAPT",
        "training_priority": "SVILUPPO_PRESTAZIONE",
        "reason": "Test",
        "recommended_action": "Test",
    }

    class FakeAirtableClient:
        pass

    class FakeContextBuilder:
        def __init__(self, client):
            captured["client"] = client

        def build(self):
            return context

    class FakeCoachEngine:
        def evaluate(self, received_context):
            captured["coach_context"] = received_context
            return dict(decision)

    class FakeReportBuilder:
        def build(self, received_context, received_decision):
            captured["report_context"] = received_context
            captured["report_decision"] = received_decision
            return "PREVIEW TEST"

    monkeypatch.setattr(
        preview_module,
        "AirtableClient",
        FakeAirtableClient,
    )
    monkeypatch.setattr(
        preview_module,
        "ContextBuilder",
        FakeContextBuilder,
    )
    monkeypatch.setattr(
        preview_module,
        "CoachEngine",
        FakeCoachEngine,
    )
    monkeypatch.setattr(
        preview_module,
        "ReportBuilder",
        FakeReportBuilder,
    )

    report = preview_module.generate_report_preview()

    preview_decision = captured["report_decision"]
    workout = preview_decision["modified_workout"]

    assert report == "PREVIEW TEST"
    assert captured["coach_context"] is context
    assert captured["report_context"] is context

    assert workout["strategy"] == "ADAPT"
    assert (
        workout["training_priority"]
        == "SVILUPPO_PRESTAZIONE"
    )
    assert (
        workout["stimulus_adjustment"]["type"]
        == "QUALITY"
    )
    assert workout["intensity"] == "Z3-Z4 controllata"
    assert "intervalli controllati" in workout["main_set"]


def test_report_preview_uses_supplied_client(
    monkeypatch,
) -> None:
    captured = {}
    supplied_client = object()

    class FakeContextBuilder:
        def __init__(self, client):
            captured["client"] = client

        def build(self):
            return {
                "training": {},
            }

    class FakeCoachEngine:
        def evaluate(self, context):
            return {
                "strategy": "KEEP_PLAN",
                "training_priority": "CONTINUITA",
            }

    class FakeReportBuilder:
        def build(self, context, decision):
            return "PREVIEW CLIENT TEST"

    monkeypatch.setattr(
        preview_module,
        "ContextBuilder",
        FakeContextBuilder,
    )
    monkeypatch.setattr(
        preview_module,
        "CoachEngine",
        FakeCoachEngine,
    )
    monkeypatch.setattr(
        preview_module,
        "ReportBuilder",
        FakeReportBuilder,
    )

    report = preview_module.generate_report_preview(
        client=supplied_client,
    )

    assert captured["client"] is supplied_client
    assert report == "PREVIEW CLIENT TEST"