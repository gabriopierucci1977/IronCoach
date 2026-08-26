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
        processor=None,
        processor_class=DecisionMemoryActivityProcessor,
    ):
        self.repository = repository

        self.processor = (
            processor
            if processor is not None
            else processor_class(
                repository
            )
        )

    def record_activity(
        self,
        activity,
    ):
        if hasattr(
            self.repository,
            "list_pending_by_athlete",
        ):
            episodes = (
                self.repository
                .list_pending_by_athlete(
                    activity.get(
                        "athlete_id",
                        "demo-athlete",
                    )
                )
            )

            if not episodes:
                return None

            episode = episodes[0]

        elif hasattr(
            self.repository,
            "pending",
        ):
            episodes = self.repository.pending

            if not episodes:
                return None

            episode = episodes[0]

        else:
            from backend.models.decision_episode import (
                DecisionEpisode,
            )

            episode = DecisionEpisode(
                athlete_id=activity.get(
                    "athlete_id",
                    "demo-athlete",
                ),
                decision_timestamp="",
                decision_action="ADATTA",
                rule_id="MANUAL_ACTIVITY",
                primary_intent="MAINTAIN_PLAN",
                pre_decision_state={},
                athlete_state={},
            )

        result = self.processor.process(
            episode,
            [
                activity,
            ],
        )

        if result is not None:
            return result

        return None

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

        episodes = [
            episode
            for episode in episodes
            if episode.status
            == "WAITING_FOR_ACTIVITY"
        ]

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
