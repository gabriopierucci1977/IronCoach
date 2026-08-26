"""
Test Decision Memory Learning Analyzer.

Verifica l'estrazione deterministica di pattern
dagli outcome storici delle decisioni.
"""

from backend.decision_memory.learning_analyzer import (
    DecisionMemoryLearningAnalyzer,
)
from backend.models.decision_episode import (
    DecisionEpisode,
)


def _episode(
    episode_id,
    outcome,
):
    return DecisionEpisode(
        athlete_id="athlete-123",
        decision_timestamp=(
            "2026-08-25T08:00:00Z"
        ),
        decision_action="ADATTA",
        rule_id=(
            "PERFORMANCE_DECLINING_LOAD_HIGH"
        ),
        primary_intent=(
            "PROTECT_PERFORMANCE"
        ),
        pre_decision_state={},
        athlete_state={},
        episode_id=episode_id,
        overall_outcome_status=outcome,
    )


def test_learning_analyzer_summarizes_rule_outcomes():
    analyzer = DecisionMemoryLearningAnalyzer()

    result = analyzer.analyze(
        [
            _episode(
                "episode-1",
                "POSITIVE",
            ),
            _episode(
                "episode-2",
                "POSITIVE",
            ),
            _episode(
                "episode-3",
                "NEUTRAL",
            ),
            _episode(
                "episode-4",
                "NEGATIVE",
            ),
            _episode(
                "episode-5",
                "INSUFFICIENT_DATA",
            ),
        ]
    )

    rule = result[
        "PERFORMANCE_DECLINING_LOAD_HIGH"
    ]

    assert rule["positive_count"] == 2
    assert rule["neutral_count"] == 1
    assert rule["negative_count"] == 1
    assert rule["insufficient_data_count"] == 1

    assert rule["evaluable_count"] == 4
    assert rule["positive_rate"] == 0.5