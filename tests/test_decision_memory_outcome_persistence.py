"""
Test outcome persistence.
"""


def test_outcome_runtime_persists_updated_episode():

    from backend.decision_memory.outcome_runtime import (
        DecisionMemoryOutcomeRuntime,
    )

    calls = []

    class FakeRepository:

        def update(
            self,
            episode,
        ):
            calls.append(
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

            return episode


    runtime = DecisionMemoryOutcomeRuntime(
        repository=FakeRepository(),
        evaluator=FakeEvaluator(),
    )

    result = runtime.evaluate_outcome(
        "episode-1",
    )

    assert result.overall_outcome_status == (
        "SUCCESS"
    )

    assert len(calls) == 1