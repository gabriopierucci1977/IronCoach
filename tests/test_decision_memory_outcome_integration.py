"""
Test outcome runtime updates decision memory.
"""


class FakeRepository:

    def __init__(self):
        self.updated = []


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
        episode.overall_outcome_status = (
            "SUCCESS"
        )

        episode.overall_outcome_confidence = (
            0.9
        )

        return episode


def test_outcome_runtime_updates_episode():

    from backend.decision_memory.outcome_runtime import (
        DecisionMemoryOutcomeRuntime,
    )

    repository = FakeRepository()

    runtime = DecisionMemoryOutcomeRuntime(
        repository=repository,
        evaluator=FakeEvaluator(),
    )

    result = runtime.evaluate_outcome(
        "episode-1",
    )

    assert result.overall_outcome_status == (
        "SUCCESS"
    )

    assert result.overall_outcome_confidence == (
        0.9
    )