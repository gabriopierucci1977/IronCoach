"""
IronCoach Decision Memory Formatter

Trasforma gli episodi della Decision Memory
in un formato leggibile dall'atleta.

Responsabilità:
- presentazione;
- leggibilità;
- nessuna logica decisionale.
"""

from __future__ import annotations


class DecisionMemoryFormatter:
    """
    Formatter testuale della Decision Memory.
    """

    def format(
        self,
        episode,
    ) -> str:
        workout = (
            episode.get(
                "recommended_workout",
                {},
            )
            or {}
        )

        lines = [
            "=" * 50,
            "IRONCOACH DECISION MEMORY",
            "=" * 50,
            "",
            f"Data: {episode.get('decision_timestamp', '')}",
            "",
            (
                "Decisione: "
                f"{episode.get('decision_action', '')}"
            ),
            (
                "Strategia: "
                f"{episode.get('strategy', '')}"
            ),
            (
                "Intento: "
                f"{episode.get('primary_intent', '')}"
            ),
            (
                "Stato: "
                f"{episode.get('status', '')}"
            ),
            "",
            "Allenamento consigliato:",
            (
                f"{workout.get('sport', '')} "
                f"{workout.get('duration_minutes', '')} minuti"
            ),
            "",
            "=" * 50,
        ]

        return "\n".join(lines)