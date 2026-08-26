"""
IronCoach Decision Memory Learning Analyzer.

Estrae statistiche deterministiche dagli outcome
storici delle decisioni.

Regole:
- raggruppa gli episodi per rule_id;
- conta gli outcome validi;
- INSUFFICIENT_DATA viene tracciato ma non entra
  nel denominatore delle metriche di efficacia;
- non modifica gli episodi ricevuti.
"""

from __future__ import annotations


class DecisionMemoryLearningAnalyzer:
    """
    Analizza gli outcome storici per regola decisionale.
    """

    OUTCOME_POSITIVE = "POSITIVE"
    OUTCOME_NEUTRAL = "NEUTRAL"
    OUTCOME_NEGATIVE = "NEGATIVE"
    OUTCOME_INSUFFICIENT = "INSUFFICIENT_DATA"

    def analyze(
        self,
        episodes,
    ):
        """
        Restituisce una sintesi degli outcome per rule_id.
        """
        result = {}

        for episode in episodes:
            rule_id = episode.rule_id
            outcome = episode.overall_outcome_status

            if rule_id not in result:
                result[rule_id] = {
                    "positive_count": 0,
                    "neutral_count": 0,
                    "negative_count": 0,
                    "insufficient_data_count": 0,
                    "evaluable_count": 0,
                    "positive_rate": 0.0,
                }

            summary = result[rule_id]

            if outcome == self.OUTCOME_POSITIVE:
                summary["positive_count"] += 1
                summary["evaluable_count"] += 1

            elif outcome == self.OUTCOME_NEUTRAL:
                summary["neutral_count"] += 1
                summary["evaluable_count"] += 1

            elif outcome == self.OUTCOME_NEGATIVE:
                summary["negative_count"] += 1
                summary["evaluable_count"] += 1

            elif outcome == self.OUTCOME_INSUFFICIENT:
                summary["insufficient_data_count"] += 1

        for summary in result.values():
            evaluable_count = summary[
                "evaluable_count"
            ]

            if evaluable_count > 0:
                summary["positive_rate"] = (
                    summary["positive_count"]
                    / evaluable_count
                )

        return result
