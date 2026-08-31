"""
IronCoach Decision Memory Activity Matcher

Collega un DecisionEpisode ad una attività reale.

Non valuta:
- aderenza;
- outcome;
- qualità della prestazione.

Trova solo una possibile attività successiva.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ActivityMatcher:
    """
    Cerca attività compatibili con un DecisionEpisode.

    Un match viene accettato solo quando esiste
    una singola attività compatibile.

    Se non esistono candidate oppure il risultato
    è ambiguo, restituisce None.
    """

    def find_match(
        self,
        episode,
        activities: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        candidates = self.find_candidates(
            episode,
            activities,
        )

        if len(candidates) != 1:
            return None

        return candidates[0]

    def find_candidates(
        self,
        episode,
        activities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        decision_time = self._parse_datetime(
            episode.decision_timestamp
        )

        if decision_time is None:
            return []

        expected_sport = self._expected_sport(
            episode
        )

        candidates = []

        for activity in activities:
            activity_time = self._parse_datetime(
                activity.get(
                    "date"
                )
            )

            if activity_time is None:
                continue

            if activity_time <= decision_time:
                continue

            if expected_sport:
                activity_sport = str(
                    activity.get(
                        "sport"
                    )
                    or ""
                ).strip().upper()

                if activity_sport != expected_sport:
                    continue

            candidates.append(
                activity
            )

        return candidates

    def _expected_sport(
        self,
        episode,
    ) -> Optional[str]:
        recommended_workout = (
            episode.recommended_workout
            or {}
        )

        recommended_sport = str(
            recommended_workout.get(
                "sport"
            )
            or ""
        ).strip().upper()

        if recommended_sport not in {
            "",
            "UNKNOWN",
        }:
            return recommended_sport

        planned_workout = (
            episode.planned_workout
            or {}
        )

        planned_sport = str(
            planned_workout.get(
                "sport"
            )
            or ""
        ).strip().upper()

        if planned_sport in {
            "",
            "UNKNOWN",
        }:
            return None

        return planned_sport

    def _parse_datetime(
        self,
        value,
    ):
        if not value:
            return None

        try:
            parsed = datetime.fromisoformat(
                str(value).replace(
                    "Z",
                    "+00:00",
                )
            )

            if parsed.tzinfo is None:
                parsed = parsed.replace(
                    tzinfo=timezone.utc
                )

            return parsed

        except ValueError:
            return None
