"""
Test Decision Memory Orchestrator Learning.

Verifica che l'orchestrator deleghi la costruzione
dell'evidenza storica al Learning Service.
"""

from backend.decision_memory.orchestrator import (
    DecisionMemoryOrchestrator,
)


class FakeDecisionRuntime:
    pass


class FakeActivityRuntime:
    pass


class FakeOutcomeRuntime:
    pass


class FakeLearningService:

    def __init__(
        self,
    ):
        self.calls = []

    def build_evidence(
        self,
        athlete_id,
    ):
        self.calls.append(
            athlete_id
        )

        return {
            "RULE-A": {
                "evaluable_count": 3,
                "sufficient_evidence": True,
            }
        }


def test_orchestrator_delegates_learning_evidence():

    learning_service = FakeLearningService()

    orchestrator = DecisionMemoryOrchestrator(
        decision_runtime=FakeDecisionRuntime(),
        activity_runtime=FakeActivityRuntime(),
        outcome_runtime=FakeOutcomeRuntime(),
        learning_service=learning_service,
    )

    result = (
        orchestrator.build_learning_evidence(
            "athlete-123"
        )
    )

    assert result == {
        "RULE-A": {
            "evaluable_count": 3,
            "sufficient_evidence": True,
        }
    }

    assert learning_service.calls == [
        "athlete-123",
    ]
