"""
IronCoach Decision Memory Learning Policy.

Definisce quando l'evidenza storica è sufficiente
e come può calibrare prudentemente la confidence.

La policy è deterministica e non modifica
i dati ricevuti.
"""

from __future__ import annotations


class DecisionMemoryLearningPolicy:
    """
    Valuta e traduce l'evidenza storica
    in un aggiustamento prudente.
    """

    def __init__(
        self,
        minimum_evaluable_count=3,
        maximum_confidence_delta=5,
    ):
        self.minimum_evaluable_count = (
            minimum_evaluable_count
        )

        self.maximum_confidence_delta = (
            maximum_confidence_delta
        )

    def has_sufficient_evidence(
        self,
        summary,
    ):
        """
        True solo quando il numero di outcome
        valutabili raggiunge la soglia minima.
        """
        evaluable_count = summary.get(
            "evaluable_count",
            0,
        )

        return (
            evaluable_count
            >= self.minimum_evaluable_count
        )

    def confidence_delta(
        self,
        summary,
    ):
        """
        Calcola un aggiustamento compreso tra
        -maximum_confidence_delta e
        +maximum_confidence_delta.

        POSITIVE aumenta il segnale.
        NEGATIVE lo riduce.
        NEUTRAL resta nel denominatore.
        INSUFFICIENT_DATA non entra nel calcolo.
        """
        if not self.has_sufficient_evidence(
            summary
        ):
            return 0

        evaluable_count = summary.get(
            "evaluable_count",
            0,
        )

        if evaluable_count <= 0:
            return 0

        positive_count = summary.get(
            "positive_count",
            0,
        )

        negative_count = summary.get(
            "negative_count",
            0,
        )

        score = (
            positive_count
            - negative_count
        ) / evaluable_count

        delta = round(
            score
            * self.maximum_confidence_delta
        )

        return max(
            -self.maximum_confidence_delta,
            min(
                self.maximum_confidence_delta,
                delta,
            ),
        )
