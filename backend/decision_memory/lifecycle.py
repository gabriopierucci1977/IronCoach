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
        """
        Porta un episodio OPEN nello stato
        WAITING_FOR_ACTIVITY.

        La transizione è valida solo da OPEN.
        """

        if episode.status != "OPEN":
            raise ValueError(
                "La transizione a WAITING_FOR_ACTIVITY "
                "richiede un episodio in stato OPEN."
            )

        episode.status = "WAITING_FOR_ACTIVITY"

        return episode