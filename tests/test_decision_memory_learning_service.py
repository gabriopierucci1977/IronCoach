"""
Test Decision Memory Learning Service.

Combina repository, analyzer e policy per produrre
l'evidenza storica utilizzabile dal DecisionEngine.
"""

from backend.decision_memory.learning_service import (
    DecisionMemoryLearningService,
)


class FakeRepository:
    def list_evaluated_by_athlete(
        self,
        athlete_id,
    ):
        assert athlete_id == "athlete-1"

        return [
            type(
                "Episode",
                (),
                {
                    "rule_id": "RULE-A",
                    "overall_outcome_status": "POSITIVE",
                },
            )(),
            type(
                "Episode",
                (),
                {
                    "rule_id": "RULE-A",
                    "overall_outcome_status": "POSITIVE",
                },
            )(),
            type(
                "Episode",
                (),
                {
                    "rule_id": "RULE-A",
                    "overall_outcome_status": "NEGATIVE",
                },
            )(),
            type(
                "Episode",
                (),
                {
                    "rule_id": "RULE-B",
                    "overall_outcome_status": "POSITIVE",
                },
            )(),
        ]


def test_learning_service_builds_rule_evidence():
    service = DecisionMemoryLearningService(
        repository=FakeRepository(),
        minimum_evaluable_count=3,
    )

    evidence = service.build_evidence(
        "athlete-1"
    )

    assert evidence["RULE-A"][
        "positive_count"
    ] == 2

    assert evidence["RULE-A"][
        "negative_count"
    ] == 1

    assert evidence["RULE-A"][
        "evaluable_count"
    ] == 3

    assert evidence["RULE-A"][
        "sufficient_evidence"
    ] is True

    assert evidence["RULE-B"][
        "evaluable_count"
    ] == 1

    assert evidence["RULE-B"][
        "sufficient_evidence"
    ] is False
