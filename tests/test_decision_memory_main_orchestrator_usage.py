"""
Test main uses DecisionMemoryOrchestrator.
"""

import backend.main as main_module


class FakeOrchestrator:
    calls = []

    def save_decision(
        self,
        context,
        decision,
        airtable_record,
    ):
        self.calls.append(
            (
                context,
                decision,
                airtable_record,
            )
        )


def test_save_decision_memory_uses_orchestrator(
    monkeypatch,
):
    fake = FakeOrchestrator()

    monkeypatch.setattr(
        main_module,
        "create_decision_memory_orchestrator",
        lambda runtime_config: fake,
    )

    main_module._save_decision_memory(
        runtime_config="config",
        context="context",
        decision="decision",
        airtable_record="record",
    )

    assert fake.calls == [
        (
            "context",
            "decision",
            "record",
        )
    ]