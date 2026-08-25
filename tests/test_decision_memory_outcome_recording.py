"""
Test outcome recording flow.
"""

import backend.main as main_module


def test_record_outcome_updates_decision_memory(
    monkeypatch,
):

    calls = []

    class FakeOutcomeRuntime:

        def evaluate_outcome(
            self,
            episode_id,
        ):
            calls.append(
                episode_id
            )
            return {
                "status": "SUCCESS"
            }

    monkeypatch.setattr(
        main_module,
        "create_outcome_runtime",
        lambda runtime_config: FakeOutcomeRuntime(),
    )

    result = main_module.main(
        [
            "--evaluate-outcome",
        ]
    )

    assert result == 0
    assert len(calls) == 1