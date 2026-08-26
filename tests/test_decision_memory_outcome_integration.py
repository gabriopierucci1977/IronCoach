"""
Test integrazione Outcome Runtime + Processor.
"""

from types import SimpleNamespace

from backend.decision_memory.outcome_processor import (
    DecisionMemoryOutcomeProcessor,
)
from backend.decision_memory.outcome_runtime import (
    DecisionMemoryOutcomeRuntime,
)


class FakeRepository:

    def __init__(self):
        self.episode = SimpleNamespace(
            adherence_status=None,
            adherence_evidence={},
            adherence_evaluated_at=None,
        )
        self.updated = []

    def get_by_episode_id(
        self,
        episode_id,
    ):
        assert episode_id == "episode-1"
        return self.episode

    def update(
        self,
        episode,
    ):
        self.updated.append(
            episode
        )


class FakeEvaluator:

    def evaluate(
        self,
        episode,
    ):
        return {
            "adherence_status": "FOLLOWED",
            "evidence": {
                "source": "integration-test",
            },
        }


def test_outcome_runtime_updates_episode():
    repository = FakeRepository()

    processor = DecisionMemoryOutcomeProcessor(
        repository=repository,
        evaluator=FakeEvaluator(),
    )

    runtime = DecisionMemoryOutcomeRuntime(
        repository=repository,
        processor=processor,
    )

    result = runtime.evaluate_outcome(
        "episode-1"
    )

    assert result.adherence_status == (
        "FOLLOWED"
    )

    assert repository.updated == [
        result,
    ]
