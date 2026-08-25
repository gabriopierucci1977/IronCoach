"""
IronCoach Decision Memory Factory

Costruisce il runtime completo della Decision Memory.

Responsabilità:
- inizializzare i runtime;
- collegare le dipendenze;
- restituire l'orchestrator.

Non contiene logica di dominio.
"""

from __future__ import annotations

from backend.decision_memory.activity_runtime import (
    DecisionMemoryActivityRuntime,
)
from backend.decision_memory.orchestrator import (
    DecisionMemoryOrchestrator,
)
from backend.decision_memory.outcome_runtime import (
    DecisionMemoryOutcomeRuntime,
)
from backend.decision_memory.runtime_service import (
    DecisionMemoryRuntimeService,
)
from backend.decision_memory.repository import (
    DecisionMemoryRepository,
)


def create_decision_memory_orchestrator(
    runtime_config,
):
    repository = DecisionMemoryRepository(
        runtime_config.decision_memory_database_path
    )

    decision_runtime = DecisionMemoryRuntimeService(
        runtime_config=runtime_config,
        repository_class=(
            lambda path: repository
        ),
    )

    activity_runtime = DecisionMemoryActivityRuntime(
        repository=repository,
    )

    outcome_runtime = DecisionMemoryOutcomeRuntime(
        repository=repository,
    )

    return DecisionMemoryOrchestrator(
        decision_runtime=decision_runtime,
        activity_runtime=activity_runtime,
        outcome_runtime=outcome_runtime,
    )