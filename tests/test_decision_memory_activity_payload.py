"""
Test activity recording payload.
"""

import backend.main as main_module


def test_record_activity_sends_real_activity_payload(
    monkeypatch,
):

    received = []

    class FakeActivityRuntime:

        def record_activity(
            self,
            activity,
        ):
            received.append(
                activity
            )

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

    assert received[0]["sport"] == "RUN"
    assert received[0]["duration_minutes"] == 45