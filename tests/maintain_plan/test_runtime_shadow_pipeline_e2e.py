from types import SimpleNamespace

import backend.main as main
from backend.config import RuntimeConfig


def install_pipeline_fakes(monkeypatch, *, shadow_enabled):
    calls = {
        "order": [],
        "actual": [],
        "snapshot": [],
        "shadow": [],
    }

    session_artifact = object()
    snapshot_artifact = object()

    context = {
        "athlete": {"source_id": "athlete-e2e"},
        "garmin_training_history": [],
        "training": {},
    }

    runtime_config = RuntimeConfig(
        maintain_plan_actual_session_enabled=True,
        maintain_plan_snapshot_enabled=True,
        maintain_plan_shadow_enabled=shadow_enabled,
    )

    class FakeContextBuilder:
        def __init__(self, *args, **kwargs):
            pass

        def build(self):
            return context

    class FakeActualCapture:
        def capture(self, **kwargs):
            calls["order"].append("actual")
            calls["actual"].append(kwargs)
            return SimpleNamespace(captured_sessions=(session_artifact,))

    class FakePrescriptionCapture:
        def capture(self, **kwargs):
            calls["order"].append("snapshot")
            calls["snapshot"].append(kwargs)
            return snapshot_artifact

    class FakeCoach:
        def __init__(self, *args, **kwargs):
            pass

        def evaluate(self, received_context):
            assert received_context is context
            return {
                "primary_intent": "MAINTAIN_PLAN",
                "strategy": "KEEP_PLAN",
            }

    class FakeAdapter:
        def adapt(self, *, context, decision):
            assert context is context
            return {}

    class FakeReportBuilder:
        def build(self, received_context, decision):
            assert received_context is context
            return "REPORT-E2E"

    class FakeDecisionWriter:
        def __init__(self, client):
            pass

        def save(self, decision):
            return {"id": "e2e-record"}

    def fake_shadow(**kwargs):
        calls["order"].append("shadow")
        calls["shadow"].append(kwargs)
        return SimpleNamespace(
            decision=SimpleNamespace(
                status=SimpleNamespace(value="MATCHED"),
                candidates=(object(),),
                pair_evaluations=(object(),),
            )
        )

    monkeypatch.setattr(
        main,
        "get_runtime_config",
        lambda: runtime_config,
    )
    monkeypatch.setattr(main, "AirtableClient", lambda: object())
    monkeypatch.setattr(main, "GarminRecoveryArchive", lambda: object())
    monkeypatch.setattr(main, "ContextBuilder", FakeContextBuilder)
    monkeypatch.setattr(main, "RuntimeActualSessionCapture", FakeActualCapture)
    monkeypatch.setattr(main, "RuntimePrescriptionCapture", FakePrescriptionCapture)
    monkeypatch.setattr(main, "CoachEngine", FakeCoach)
    monkeypatch.setattr(main, "WorkoutAdapter", FakeAdapter)
    monkeypatch.setattr(main, "ReportBuilder", FakeReportBuilder)
    monkeypatch.setattr(main, "DecisionWriter", FakeDecisionWriter)
    monkeypatch.setattr(main, "_sync_garmin_live_best_effort", lambda: None)
    monkeypatch.setattr(main, "_sync_garmin_recovery_best_effort", lambda: None)
    monkeypatch.setattr(
        main,
        "_attach_decision_memory_learning",
        lambda **kwargs: kwargs["context"],
    )
    monkeypatch.setattr(
        main,
        "_save_decision_memory",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        main,
        "evaluate_runtime_matching_shadow",
        fake_shadow,
    )

    return calls, session_artifact, snapshot_artifact


def test_pipeline_shadow_receives_both_in_memory_capture_artifacts(monkeypatch):
    calls, session_artifact, snapshot_artifact = install_pipeline_fakes(
        monkeypatch,
        shadow_enabled=True,
    )

    assert main.run_pipeline(dry_run=False) == "REPORT-E2E"

    assert calls["order"] == ["actual", "snapshot", "shadow"]
    assert len(calls["shadow"]) == 1

    shadow_input = calls["shadow"][0]
    assert shadow_input["subject_ref"] == "athlete-e2e"
    assert shadow_input["snapshots"] == (snapshot_artifact,)
    assert shadow_input["sessions"] == (session_artifact,)


def test_pipeline_shadow_is_not_called_when_flag_is_false(monkeypatch):
    calls, _, _ = install_pipeline_fakes(
        monkeypatch,
        shadow_enabled=False,
    )

    assert main.run_pipeline(dry_run=False) == "REPORT-E2E"
    assert calls["shadow"] == []


def test_pipeline_dry_run_never_calls_shadow_or_captures(monkeypatch):
    calls, _, _ = install_pipeline_fakes(
        monkeypatch,
        shadow_enabled=True,
    )

    assert main.run_pipeline(dry_run=True) == "REPORT-E2E"
    assert calls["actual"] == []
    assert calls["snapshot"] == []
    assert calls["shadow"] == []


def test_shadow_failure_does_not_abort_pipeline(monkeypatch):
    calls, _, _ = install_pipeline_fakes(
        monkeypatch,
        shadow_enabled=True,
    )

    def failing_shadow(**kwargs):
        calls["order"].append("shadow")
        raise RuntimeError("synthetic shadow failure")

    monkeypatch.setattr(
        main,
        "evaluate_runtime_matching_shadow",
        failing_shadow,
    )

    assert main.run_pipeline(dry_run=False) == "REPORT-E2E"
    assert calls["order"] == ["actual", "snapshot", "shadow"]
