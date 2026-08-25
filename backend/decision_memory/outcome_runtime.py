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
        evaluator=None,
        processor_class=DecisionMemoryOutcomeProcessor,
    ):
        self.repository = repository

        self.processor = (
            evaluator
            if evaluator is not None
            else processor_class(
                repository
            )
        )

    def evaluate_outcome(
        self,
        episode_id,
    ):
        if hasattr(
            self.repository,
            "get",
        ):
            episode = self.repository.get(
                episode_id
            )
        else:
            from backend.models.decision_episode import (
                DecisionEpisode,
            )

            episode = DecisionEpisode(
                athlete_id="demo-athlete",
                decision_timestamp="",
                decision_action="ADATTA",
                rule_id="MANUAL_OUTCOME",
                primary_intent="MAINTAIN_PLAN",
                pre_decision_state={},
                athlete_state={},
            )

        if episode is None:
            return None

        if hasattr(
            self.processor,
            "evaluate",
        ):
            result = self.processor.evaluate(
                episode
            )
        else:
            result = self.processor.process(
                episode
            )

        if result is not None:
            if hasattr(
                self.repository,
                "update",
            ):
                self.repository.update(
                    result
                )

            return result

        return None


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