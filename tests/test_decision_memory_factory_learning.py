"""
Test Decision Memory Factory Learning wiring.

Verifica che il Learning Service venga costruito
con lo stesso repository condiviso dagli altri runtime.
"""

from backend.decision_memory.factory import (
    create_decision_memory_orchestrator,
)


class FakeRuntimeConfig:
    decision_memory_database_path = (
        "data/test_memory_learning.db"
    )


def test_factory_wires_learning_service_with_shared_repository():

    orchestrator = (
        create_decision_memory_orchestrator(
            FakeRuntimeConfig()
        )
    )

    assert (
        orchestrator.learning_service
        is not None
    )

    assert (
        orchestrator.learning_service.repository
        is orchestrator.activity_runtime.repository
    )

    assert (
        orchestrator.learning_service.repository
        is orchestrator.outcome_runtime.repository
    )
