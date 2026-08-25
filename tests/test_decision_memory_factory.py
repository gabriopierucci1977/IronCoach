"""
Test Decision Memory Factory.

Verifica la costruzione del runtime completo.
"""

from backend.decision_memory.factory import (
    create_decision_memory_orchestrator,
)
from backend.decision_memory.orchestrator import (
    DecisionMemoryOrchestrator,
)


class FakeRuntimeConfig:
    decision_memory_database_path = (
        "data/test_memory.db"
    )


def test_factory_returns_orchestrator():

    orchestrator = (
        create_decision_memory_orchestrator(
            FakeRuntimeConfig()
        )
    )

    assert isinstance(
        orchestrator,
        DecisionMemoryOrchestrator,
    )

    assert (
        orchestrator.decision_runtime
        is not None
    )

    assert (
        orchestrator.activity_runtime
        is not None
    )

    assert (
        orchestrator.outcome_runtime
        is not None
    )