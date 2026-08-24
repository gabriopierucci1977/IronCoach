"""IronCoach Activity Normalizer.

Transforms raw activities from Garmin, Strava, Airtable or manual input into
the canonical IronCoach activity contract.

The normalizer does not make coaching decisions.  It only standardizes schema,
units and field names so downstream analyzers do not need to know the source
format.
"""

from __future__ import annotations

from backend.normalization.activity_contract import NormalizedActivity


class ActivityNormalizer:
    """Normalize an external activity into the IronCoach canonical schema."""

    def normalize(
        self,
        activity,
        source="manual",
    ) -> NormalizedActivity:
        activity = activity or {}

        return {
            "source": source,
            "source_id": self._get_value(
                activity,
                [
                    "id",
                    "activity_id",
                    "source_id",
                    "Record ID",
                ],
            ),
            "date": self._get_value(
                activity,
                [
                    "date",
                    "Date",
                    "start_date",
                    "timestamp",
                    "Data allenamento",
                ],
            ),
            "sport": self._normalize_sport(
                self._get_value(
                    activity,
                    [
                        "sport",
                        "Sport",
                        "activity_type",
                        "type",
                    ],
                )
            ),
            # Canonical coaching descriptors.  These are intentionally
            # promoted out of ``raw`` because TrainingAnalyzer and
            # WorkoutAdapter consume them directly.
            "workout_name": self._get_value(
                activity,
                [
                    "workout_name",
                    "name",
                    "Nome seduta",
                    "nome_seduta",
                ],
            ),
            "session_type": self._get_value(
                activity,
                [
                    "session_type",
                    "Tipo seduta",
                    "tipo_seduta",
                    "workout_type",
                ],
            ),
            "duration_minutes": self._normalize_duration_from_activity(
                activity,
                source=source,
            ),
            "distance_km": self._normalize_distance(
                self._get_value(
                    activity,
                    [
                        "distance_km",
                        "Distanza km",
                        "distance",
                    ],
                )
            ),
            # Missing load is semantically different from an observed zero.
            # Keep None so LoadAnalyzer can distinguish missing telemetry from
            # a real zero-load session.
            "training_load": self._get_value(
                activity,
                [
                    "training_load",
                    "Carico interno",
                    "load",
                    "tss",
                    "icu_training_load",
                ],
                None,
            ),
            "intensity": self._get_value(
                activity,
                [
                    "intensity",
                    "planned_zone",
                    "zone",
                    "Zona prevista",
                    "zona_prevista",
                ],
                None,
            ),
            "heart_rate": {
                "average": self._get_value(
                    activity,
                    [
                        "average_hr",
                        "heart_rate_average",
                        "FC media",
                    ],
                ),
                "max": self._get_value(
                    activity,
                    [
                        "max_hr",
                        "heart_rate_max",
                        "FC massima",
                    ],
                ),
            },
            "power": {
                "average": self._get_value(
                    activity,
                    [
                        "average_power",
                        "power_average",
                        "Potenza media",
                    ],
                ),
                "normalized": self._get_value(
                    activity,
                    [
                        "normalized_power",
                        "Potenza normalizzata",
                    ],
                ),
            },
            "rpe": self._get_value(
                activity,
                [
                    "rpe",
                    "RPE percepito",
                    "RPE",
                    "perceived_exertion",
                ],
            ),
            "notes": self._get_value(
                activity,
                [
                    "notes",
                    "Note personali",
                    "comment",
                ],
            ),
            # Safety-relevant fields must never live only in ``raw``.  The
            # InjuryAnalyzer uses these canonical keys first and retains a raw
            # fallback for older contexts.
            "current_problem": self._get_value(
                activity,
                [
                    "current_problem",
                    "pain_notes",
                    "injury_notes",
                    "Dolori/problematiche",
                    "dolori_problematiche",
                    "Dolori",
                ],
            ),
            "pain_score": self._get_value(
                activity,
                [
                    "pain_score",
                    "Pain Score",
                    "Dolore",
                ],
            ),
            "raw": activity,
        }

    def _get_value(
        self,
        data,
        keys,
        default=None,
    ):
        for key in keys:
            value = data.get(key)

            if value not in (
                None,
                "",
            ):
                return value

        return default

    def _normalize_distance(
        self,
        value,
    ):
        if value is None:
            return 0

        try:
            value = float(value)

            if value > 1000:
                return round(
                    value / 1000,
                    2,
                )

            return round(
                value,
                2,
            )

        except Exception:
            return 0

    def _normalize_duration_from_activity(
        self,
        activity,
        source="manual",
    ):
        """Return duration in minutes without guessing from magnitude.

        The previous implementation treated every value greater than 300 as
        seconds.  That silently corrupted legitimate long endurance sessions
        (for example 360 minutes became 6 minutes).

        Unit handling is now explicit at the schema boundary:

        - canonical/Airtable ``*_minutes`` fields are always minutes;
        - explicit ``*_seconds`` fields are always seconds;
        - ``moving_time`` / ``elapsed_time`` are seconds (Garmin/Strava
          conventions);
        - the generic ``duration`` key is interpreted as seconds only for
          known second-based sources (Garmin/Strava/FIT/TCX/GPX), otherwise
          as minutes.

        Source adapters should prefer explicit unit-bearing field names.
        """

        minute_value = self._get_value(
            activity,
            [
                "duration_minutes",
                "Durata minuti",
                "duration_min",
            ],
        )

        if minute_value is not None:
            return self._normalize_duration(
                minute_value,
                unit="minutes",
            )

        second_value = self._get_value(
            activity,
            [
                "duration_seconds",
                "duration_sec",
                "moving_time_seconds",
                "elapsed_time_seconds",
            ],
        )

        if second_value is not None:
            return self._normalize_duration(
                second_value,
                unit="seconds",
            )

        moving_or_elapsed = self._get_value(
            activity,
            [
                "moving_time",
                "elapsed_time",
            ],
        )

        if moving_or_elapsed is not None:
            return self._normalize_duration(
                moving_or_elapsed,
                unit="seconds",
            )

        generic_duration = self._get_value(
            activity,
            [
                "duration",
            ],
        )

        if generic_duration is None:
            return None

        normalized_source = str(
            source or ""
        ).strip().lower()

        second_based_sources = {
            "garmin",
            "strava",
            "fit",
            "tcx",
            "gpx",
        }

        return self._normalize_duration(
            generic_duration,
            unit=(
                "seconds"
                if normalized_source in second_based_sources
                else "minutes"
            ),
        )

    def _normalize_duration(
        self,
        value,
        unit="minutes",
    ):
        # Preserve missingness.  It prevents a synthetic zero from making an
        # otherwise empty normalized training look like a valid low-stress
        # session to TrainingAnalyzer.
        if value is None:
            return None

        try:
            value = float(value)

            if unit == "seconds":
                value = value / 60.0

            return round(
                value,
                2,
            )

        except Exception:
            return None

    def _normalize_sport(
        self,
        sport,
    ):
        if not sport:
            return "UNKNOWN"

        sport = str(
            sport
        ).lower()

        mapping = {
            "run": "RUN",
            "running": "RUN",
            "corsa": "RUN",
            "bike": "BIKE",
            "cycling": "BIKE",
            "bici": "BIKE",
            "swim": "SWIM",
            "nuoto": "SWIM",
            "strength": "STRENGTH",
            "forza": "STRENGTH",
        }

        return mapping.get(
            sport,
            sport.upper(),
        )
