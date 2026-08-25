"""
Test Decision Memory demo flow.
"""

import backend.main as main_module


def test_main_decision_memory_demo(
    monkeypatch,
    capsys,
):

    calls = []

    class FakeRepository:

        def create(
            self,
            episode,
        ):
            calls.append(
                episode
            )

        def latest(
            self,
            limit=10,
        ):
            return [
                {
                    "decision_timestamp":
                        "2026-08-25T08:00:00Z",
                    "decision_action":
                        "ADATTA",
                    "strategy":
                        "ADAPT",
                    "primary_intent":
                        "REDUCE_LOAD",
                    "status":
                        "WAITING_FOR_ACTIVITY",
                    "recommended_workout": {
                        "sport": "RUN",
                        "duration_minutes": 40,
                    },
                }
            ]

    monkeypatch.setattr(
        main_module,
        "DecisionMemoryRepository",
        lambda path: FakeRepository(),
    )

    result = main_module.main(
        [
            "--decision-memory-demo",
        ]
    )

    output = capsys.readouterr().out

    assert result == 0
    assert "ADATTA" in output
    assert "RUN" in output