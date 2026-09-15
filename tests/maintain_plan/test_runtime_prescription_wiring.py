"""Pipeline ordering and failure semantics for prescription capture."""

import pytest

import backend.main as main_module
from tests.test_main_orchestration import (
    FakeClient,
    FakeDecisionMemoryOrchestrator,
    FakeDecisionWriter,
)


class Config:
    decision_memory_database_path = "unused-memory.db"
    maintain_plan_snapshot_enabled = True
    maintain_plan_database_path = "unused-maintain.db"
    maintain_plan_timezone = "Europe/Rome"


class Builder:
    def __init__(self, *args, **kwargs):
        pass

    def build(self):
        return {"training": {"source_id": "rec-1"}}


class Coach:
    def __init__(self, *args, **kwargs):
        pass

    def evaluate(self, context):
        return {
            "decision_id": "decision-1",
            "primary_intent": "MAINTAIN_PLAN",
            "strategy": "KEEP_PLAN",
        }


def _patch_pipeline(monkeypatch, events, capture_error=None):
    monkeypatch.setattr(main_module, "get_runtime_config", lambda: Config())
    monkeypatch.setattr(main_module, "AirtableClient", FakeClient)
    monkeypatch.setattr(main_module, "ContextBuilder", Builder)
    monkeypatch.setattr(main_module, "CoachEngine", Coach)
    monkeypatch.setattr(main_module, "_attach_decision_memory_learning", lambda **kw: kw["context"])
    monkeypatch.setattr(main_module, "_sync_garmin_live_best_effort", lambda: None)
    monkeypatch.setattr(main_module, "_sync_garmin_recovery_best_effort", lambda: None)
    monkeypatch.setattr(main_module, "create_decision_memory_orchestrator", lambda config: FakeDecisionMemoryOrchestrator())

    class Adapter:
        def adapt(self, context, decision):
            events.append("adapt")
            return {"strategy": "KEEP_PLAN"}

    class Capture:
        def capture(self, **kwargs):
            events.append("capture")
            assert kwargs["decision"]["modified_workout"] == {"strategy": "KEEP_PLAN"}
            if capture_error:
                raise capture_error

    class Report:
        def build(self, context, decision):
            events.append("report")
            return "report"

    class Writer:
        def __init__(self, client):
            events.append("writer")

        def save(self, decision):
            events.append("airtable")
            return {}

    monkeypatch.setattr(main_module, "WorkoutAdapter", Adapter)
    monkeypatch.setattr(main_module, "RuntimePrescriptionCapture", Capture)
    monkeypatch.setattr(main_module, "ReportBuilder", Report)
    monkeypatch.setattr(main_module, "DecisionWriter", Writer)
    monkeypatch.setattr(main_module, "_save_decision_memory", lambda **kw: events.append("memory"))


def test_capture_runs_after_adaptation_and_before_report_and_writes(monkeypatch):
    events = []
    _patch_pipeline(monkeypatch, events)
    assert main_module.run_pipeline() == "report"
    assert events == ["adapt", "capture", "report", "writer", "airtable", "memory"]


def test_capture_is_never_constructed_in_dry_run(monkeypatch):
    events = []
    _patch_pipeline(monkeypatch, events)
    assert main_module.run_pipeline(dry_run=True) == "report"
    assert events == ["adapt", "report"]


def test_capture_failure_blocks_report_airtable_and_memory(monkeypatch):
    events = []
    _patch_pipeline(monkeypatch, events, RuntimeError("capture failed"))
    with pytest.raises(main_module.IronCoachExecutionError) as error:
        main_module.run_pipeline()
    assert error.value.phase == "cattura prescrizione MAINTAIN_PLAN"
    assert events == ["adapt", "capture"]
