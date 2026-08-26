"""
IronCoach Decision Memory Outcome Evaluator

Valuta l'aderenza tra allenamento pianificato
e attività realmente svolta.

Non valuta:
- qualità della performance;
- miglioramento atleta;
- correttezza della decisione;
- outcome fisiologico a 24h, 72h o 7d.
"""

from __future__ import annotations


class OutcomeEvaluator:
    """
    Valuta la coerenza tra piano e attività reale.

    Stati ammessi dallo schema:
    - FOLLOWED
    - PARTIALLY_FOLLOWED
    - NOT_FOLLOWED
    - UNKNOWN
    """

    def evaluate(
        self,
        episode,
    ):
        planned = (
            episode.planned_workout
            or episode.recommended_workout
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

        if not planned_sport or not actual_sport:
            return {
                "adherence_status": "UNKNOWN",
                "evidence": evidence,
            }

        if (
            str(planned_sport).upper()
            == str(actual_sport).upper()
        ):
            return {
                "adherence_status": "FOLLOWED",
                "evidence": evidence,
            }

        return {
            "adherence_status": "NOT_FOLLOWED",
            "evidence": evidence,
        }
