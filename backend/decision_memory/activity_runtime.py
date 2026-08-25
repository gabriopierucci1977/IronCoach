"""
IronCoach Decision Memory Activity Runtime

Coordina il recupero degli episodi in attesa
di attività e il collegamento con attività reali.

Responsabilità:
- recuperare episodi pending;
- invocare ActivityProcessor;
- restituire episodi processati.

Non gestisce:
- matching diretto;
- valutazione aderenza;
- outcome.
"""

from __future__ import annotations

from backend.decision_memory.activity_processor import (
    DecisionMemoryActivityProcessor,
)


class DecisionMemoryActivityRuntime:
    """
    Runtime per collegare attività reali agli episodi.
    """

    def __init__(
        self,
        repository,
        processor_class=DecisionMemoryActivityProcessor,
    ):
        self.repository = repository

        self.processor = processor_class(
            repository
        )

    def process_activities(
        self,
        athlete_id,
        activities,
    ):
        episodes = (
            self.repository
            .list_pending_by_athlete(
                athlete_id
            )
        )

        processed = []

        for episode in episodes:
            result = self.processor.process(
                episode,
                activities,
            )

            if result is not None:
                processed.append(
                    result
                )

        return processed