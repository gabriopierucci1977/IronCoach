"""
IronCoach Decision Memory Outcome Evaluator

Valuta l'aderenza tra allenamento pianificato
e attività realmente svolta.

Non valuta:
- qualità della performance;
- miglioramento atleta;
- correttezza della decisione.
"""

from __future__ import annotations


class OutcomeEvaluator:
    """
    Valuta la coerenza tra piano e attività reale.
    """

    def evaluate(
        self,
        episode,
    ):
        planned = (
            episode.planned_workout
            or {}
        )

        actual = (
            episode.actual_activity
            or {}
        )

        planned_sport = planned.get(
            "sport"
        )

        actual_sport = actual.get(
            "sport"
        )

        planned_duration = planned.get(
            "duration_minutes"
        )

        actual_duration = actual.get(
            "duration_minutes"
        )

        evidence = {
            "planned_sport": planned_sport,
            "actual_sport": actual_sport,
            "planned_duration_minutes": (
                planned_duration
            ),
            "actual_duration_minutes": (
                actual_duration
            ),
        }

        if (
            planned_sport
            and actual_sport
            and planned_sport == actual_sport
        ):
            return {
                "adherence_status": (
                    "MATCHED"
                ),
                "evidence": evidence,
            }

        return {
            "adherence_status": (
                "MISMATCHED"
            ),
            "evidence": evidence,
        }