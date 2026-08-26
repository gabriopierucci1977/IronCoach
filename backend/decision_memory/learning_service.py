"""
IronCoach Decision Memory Learning Service.

Combina repository, analyzer e policy per costruire
l'evidenza storica utilizzabile dal DecisionEngine.

Non modifica le decisioni e non applica regole coaching.
"""

from __future__ import annotations

from backend.decision_memory.learning_analyzer import (
    DecisionMemoryLearningAnalyzer,
)
from backend.decision_memory.learning_policy import (
    DecisionMemoryLearningPolicy,
)


class DecisionMemoryLearningService:
    """
    Costruisce l'evidenza storica per un atleta.
    """

    def __init__(
        self,
        repository,
        minimum_evaluable_count=3,
        analyzer=None,
        policy=None,
    ):
        self.repository = repository

        self.analyzer = (
            analyzer
            if analyzer is not None
            else DecisionMemoryLearningAnalyzer()
        )

        self.policy = (
            policy
            if policy is not None
            else DecisionMemoryLearningPolicy(
                minimum_evaluable_count=(
                    minimum_evaluable_count
                ),
            )
        )

    def build_evidence(
        self,
        athlete_id,
    ):
        """
        Restituisce statistiche per rule_id
        con sufficienza dell'evidenza e
        calibrazione confidence proposta.
        """
        episodes = (
            self.repository
            .list_evaluated_by_athlete(
                athlete_id
            )
        )

        summaries = self.analyzer.analyze(
            episodes
        )

        evidence = {}

        for rule_id, summary in summaries.items():
            rule_evidence = dict(
                summary
            )

            rule_evidence[
                "sufficient_evidence"
            ] = self.policy.has_sufficient_evidence(
                summary
            )

            rule_evidence[
                "confidence_delta"
            ] = self.policy.confidence_delta(
                summary
            )

            evidence[
                rule_id
            ] = rule_evidence

        return evidence
