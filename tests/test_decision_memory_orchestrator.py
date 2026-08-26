"""
Test Decision Memory Orchestrator.

Coordina i runtime della memoria decisionale.
"""

from backend.decision_memory.orchestrator import (
    DecisionMemoryOrchestrator,
)


class FakeDecisionRuntime:

    def __init__(
        self,
    ):
        self.calls = []

    def save_decision_memory(
        self,
        context,
        decision,
        airtable_record,
    ):
        self.calls.append(
            (
                context,
                decision,
                airtable_record,
            )
        )

        return "episode"


class FakeActivityRuntime:

    def __init__(
        self,
    ):
        self.calls = []

    def process_activities(
        self,
        athlete_id,
        activities,
    ):
        self.calls.append(
            (
                athlete_id,
                activities,
            )
        )

        return "activities"


class FakeOutcomeRuntime:

    def __init__(
        self,
    ):
        self.calls = []

    def process_outcomes(
        self,
        athlete_id,
        recovery_history=None,
        as_of=None,
    ):
        self.calls.append(
            (
                athlete_id,
                recovery_history,
                as_of,
            )
        )

        return "outcomes"


def test_orchestrator_delegates_to_runtime_components():

    decision_runtime = FakeDecisionRuntime()
    activity_runtime = FakeActivityRuntime()
    outcome_runtime = FakeOutcomeRuntime()

    orchestrator = DecisionMemoryOrchestrator(
        decision_runtime=decision_runtime,
        activity_runtime=activity_runtime,
        outcome_runtime=outcome_runtime,
    )

    assert (
        orchestrator.save_decision(
            "context",
            "decision",
            "airtable",
        )
        == "episode"
    )

    assert (
        orchestrator.process_activity(
            "athlete-123",
            [],
        )
        == "activities"
    )

    assert (
        orchestrator.process_outcome(
            "athlete-123",
        )
        == "outcomes"
    )

    assert decision_runtime.calls == [
        (
            "context",
            "decision",
            "airtable",
        )
    ]

    assert activity_runtime.calls == [
        (
            "athlete-123",
            [],
        )
    ]

    assert outcome_runtime.calls == [
        (
            "athlete-123",
            None,
            None,
        )
    ]
