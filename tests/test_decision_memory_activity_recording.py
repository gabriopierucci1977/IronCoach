"""
Test manual activity recording flow.
"""

import backend.main as main_module


def test_record_activity_updates_decision_memory(
    monkeypatch,
):

    calls = []

    class FakeActivityRuntime:

        def record_activity(
            self,
            activity,
        ):
            calls.append(activity)

    monkeypatch.setattr(
        main_module,
        "create_activity_runtime",
        lambda runtime_config: FakeActivityRuntime(),
    )

    result = main_module.main(
        [
            "--record-activity",
        ]
    )

    assert result == 0
    assert len(calls) == 1