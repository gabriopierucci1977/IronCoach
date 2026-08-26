"""
Test persistenza Outcome Runtime.

Il runtime non deve persistere una seconda volta:
la persistenza appartiene al processor.
"""

from types import SimpleNamespace

from backend.decision_memory.outcome_runtime import (
    DecisionMemoryOutcomeRuntime,
)


def test_outcome_runtime_does_not_duplicate_persistence():
    calls = []

    episode = SimpleNamespace()

    class FakeRepository:

        def get_by_episode_id(
            self,
            episode_id,
        ):
            return episode

        def update(
            self,
            updated_episode,
        ):
            calls.append(
                updated_episode
            )

    repository = FakeRepository()

    class FakeProcessor:

        def process(
            self,
            processed_episode,
        ):
            repository.update(
                processed_episode
            )
            return processed_episode

    runtime = DecisionMemoryOutcomeRuntime(
        repository=repository,
        processor=FakeProcessor(),
    )

    result = runtime.evaluate_outcome(
        "episode-1"
    )

    assert result is episode
    assert calls == [
        episode,
    ]
