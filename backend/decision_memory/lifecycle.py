"""
IronCoach Decision Memory Lifecycle

Gestisce le transizioni di stato dei DecisionEpisode.

Non si occupa di:
- persistenza;
- matching attività;
- valutazione aderenza;
- valutazione outcome.
"""

from __future__ import annotations

from backend.models.decision_episode import (
    DecisionEpisode,
)


class DecisionEpisodeLifecycle:
    """
    Gestisce il ciclo di vita di un DecisionEpisode.
    """

    def mark_waiting_for_activity(
        self,
        episode: DecisionEpisode,
    ) -> DecisionEpisode:
        if episode.status != "OPEN":
            raise ValueError(
                "La transizione a WAITING_FOR_ACTIVITY "
                "richiede un episodio in stato OPEN."
            )

        episode.status = "WAITING_FOR_ACTIVITY"

        return episode

    def mark_waiting_for_outcome(
        self,
        episode: DecisionEpisode,
        activity=None,
    ) -> DecisionEpisode:
        if episode.status != "WAITING_FOR_ACTIVITY":
            raise ValueError(
                "La transizione a WAITING_FOR_OUTCOME "
                "richiede un episodio in stato "
                "WAITING_FOR_ACTIVITY."
            )

        if activity is not None:
            episode.actual_activity = activity

            episode.actual_activity_id = (
                activity.get("activity_id")
                or activity.get("source_id")
            )

            episode.actual_activity_source = (
                activity.get("source")
            )

        episode.status = "WAITING_FOR_OUTCOME"

        return episode
