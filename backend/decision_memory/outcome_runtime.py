"""
IronCoach Decision Memory Outcome Runtime

Coordina il processamento degli episodi
in attesa di valutazione outcome.

Responsabilità:
- recuperare episodi pending;
- invocare OutcomeProcessor;
- restituire episodi processati.

Non gestisce:
- logica valutativa;
- metriche performance;
- regole coaching.
"""

from __future__ import annotations

from backend.decision_memory.outcome_processor import (
    DecisionMemoryOutcomeProcessor,
)


class DecisionMemoryOutcomeRuntime:
    """
    Runtime per la valutazione degli outcome.
    """

    def __init__(
        self,
        repository,
        processor_class=DecisionMemoryOutcomeProcessor,
    ):
        self.repository = repository

        self.processor = processor_class(
            repository
        )

    def process_outcomes(
        self,
        athlete_id,
    ):
        episodes = (
            self.repository
            .list_pending_outcomes(
                athlete_id
            )
        )

        processed = []

        for episode in episodes:
            result = self.processor.process(
                episode
            )

            if result is not None:
                processed.append(
                    result
                )

        return processed