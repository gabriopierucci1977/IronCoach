"""
IronCoach Decision Memory Activity Processor

Coordina il collegamento tra:
- DecisionEpisode in attesa di attività;
- ActivityMatcher;
- DecisionEpisodeLifecycle;
- DecisionMemoryRepository.

Non valuta:
- aderenza;
- outcome;
- qualità della prestazione.
"""

from __future__ import annotations

from backend.decision_memory.activity_matcher import (
    ActivityMatcher,
)
from backend.decision_memory.lifecycle import (
    DecisionEpisodeLifecycle,
)


class DecisionMemoryActivityProcessor:
    """
    Collega attività reali agli episodi pending.
    """

    def __init__(
        self,
        repository,
        matcher=None,
        lifecycle=None,
    ):
        self.repository = repository
        self.matcher = matcher or ActivityMatcher()
        self.lifecycle = lifecycle or DecisionEpisodeLifecycle()

    def process(
        self,
        episode,
        activities,
    ):
        candidates = self.matcher.find_candidates(
            episode,
            activities,
        )

        if not candidates:
            return None

        activity = (
            candidates[0]
            if len(candidates) == 1
            else None
        )

        self.lifecycle.mark_waiting_for_outcome(
            episode,
            activity,
        )

        self.repository.update(
            episode
        )

        return episode
