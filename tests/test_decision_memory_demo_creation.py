"""
Test Decision Memory demo creates episode.
"""

import backend.main as main_module


def test_decision_memory_demo_creates_episode(
    monkeypatch,
):

    created = []

    class FakeRepository:

        def create(
            self,
            episode,
        ):
            created.append(
                episode
            )

        def latest(
            self,
            limit=10,
        ):
            return []

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

    assert result == 0
    assert len(created) == 1