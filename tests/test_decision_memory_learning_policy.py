"""
Test Decision Memory Learning Policy.

La memoria storica non deve influenzare le decisioni
quando l'evidenza disponibile è insufficiente.
"""

from backend.decision_memory.learning_policy import (
    DecisionMemoryLearningPolicy,
)


def test_learning_policy_requires_minimum_evidence():
    policy = DecisionMemoryLearningPolicy(
        minimum_evaluable_count=3,
    )

    insufficient = {
        "positive_count": 2,
        "neutral_count": 0,
        "negative_count": 0,
        "insufficient_data_count": 5,
        "evaluable_count": 2,
        "positive_rate": 1.0,
    }

    sufficient = {
        "positive_count": 2,
        "neutral_count": 1,
        "negative_count": 0,
        "insufficient_data_count": 5,
        "evaluable_count": 3,
        "positive_rate": 2 / 3,
    }

    assert policy.has_sufficient_evidence(
        insufficient
    ) is False

    assert policy.has_sufficient_evidence(
        sufficient
    ) is True
