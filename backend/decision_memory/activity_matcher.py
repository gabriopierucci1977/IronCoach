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
    """

    def find_match(
        self,
        episode,
        activities: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        decision_time = self._parse_datetime(
            episode.decision_timestamp
        )

        if decision_time is None:
            return None

        expected_sport = self._expected_sport(
            episode
        )

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
                ).upper()

                if activity_sport != expected_sport:
                    continue

            return activity

        return None

    def _expected_sport(
        self,
        episode,
    ) -> Optional[str]:
        workout = (
            episode.recommended_workout
            or {}
        )

        sport = workout.get(
            "sport"
        )

        if not sport:
            return None

        return str(
            sport
        ).upper()

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