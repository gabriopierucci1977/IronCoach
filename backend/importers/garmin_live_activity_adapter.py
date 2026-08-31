"""
Garmin Live Activity Adapter

Converte le attività restituite dall'API Garmin Connect
nel modello interno IronCoachActivity.

Il formato Garmin live è diverso dall'export storico:
- duration è già in secondi;
- distance/elevation sono già in metri;
- calories sono già kcal;
- speed è già m/s;
- activityType è normalmente un dizionario.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from backend.importers.garmin_summary_importer import (
    GarminSummaryImporter,
)
from backend.models.activity import IronCoachActivity


class GarminLiveActivityAdapterError(Exception):
    """Errore nella conversione di una attività Garmin live."""


class GarminLiveActivityAdapter:
    """Converte un record Garmin Connect in IronCoachActivity."""

    @classmethod
    def convert(
        cls,
        record: Dict[str, Any],
    ) -> IronCoachActivity:
        if not isinstance(record, dict):
            raise GarminLiveActivityAdapterError(
                "Il record Garmin live deve essere un dizionario."
            )

        source_id = cls._required_source_id(record)
        activity_type = cls._activity_type(record)
        start_datetime = cls._start_datetime(
            record.get("startTimeGMT")
        )
        duration_seconds = cls._integer(
            record.get("duration")
        )

        return IronCoachActivity(
            activity_id=f"garmin:{source_id}",
            source="garmin",
            source_id=source_id,
            file_hash=None,
            start_time=cls._datetime_to_iso(
                start_datetime
            ),
            end_time=cls._end_time(
                start_datetime,
                duration_seconds,
            ),
            sport=GarminSummaryImporter._normalize_sport(
                activity_type,
                None,
            ),
            activity_type=activity_type,
            duration_seconds=duration_seconds,
            distance_meters=cls._number(
                record.get("distance")
            ),
            elevation_gain=cls._number(
                record.get("elevationGain")
            ),
            elevation_loss=cls._number(
                record.get("elevationLoss")
            ),
            calories=cls._integer(
                record.get("calories")
            ),
            avg_speed=cls._number(
                record.get("averageSpeed")
            ),
            max_speed=cls._number(
                record.get("maxSpeed")
            ),
            avg_hr=cls._integer(
                record.get("averageHR")
            ),
            max_hr=cls._integer(
                record.get("maxHR")
            ),
            avg_cadence=None,
            max_cadence=None,
            avg_power=cls._number(
                record.get("averagePower")
            ),
            normalized_power=cls._number(
                record.get("normalizedPower")
            ),
            training_load=cls._number(
                record.get("activityTrainingLoad")
            ),
            training_effect=cls._number(
                record.get("aerobicTrainingEffect")
            ),
            segments=[],
            metadata={
                "garmin_live": cls._remove_none_values(
                    {
                        "activity_id": source_id,
                        "name": record.get(
                            "activityName"
                        ),
                        "start_time_local": record.get(
                            "startTimeLocal"
                        ),
                        "elapsed_duration_seconds": (
                            cls._number(
                                record.get(
                                    "elapsedDuration"
                                )
                            )
                        ),
                        "moving_duration_seconds": (
                            cls._number(
                                record.get(
                                    "movingDuration"
                                )
                            )
                        ),
                        "anaerobic_training_effect": (
                            cls._number(
                                record.get(
                                    "anaerobicTrainingEffect"
                                )
                            )
                        ),
                        "vo2_max": cls._number(
                            record.get(
                                "vO2MaxValue"
                            )
                        ),
                    }
                )
            },
        )

    @staticmethod
    def _required_source_id(
        record: Dict[str, Any],
    ) -> str:
        value = record.get("activityId")

        if value is None:
            raise GarminLiveActivityAdapterError(
                "Record Garmin live senza activityId."
            )

        source_id = str(value).strip()

        if not source_id:
            raise GarminLiveActivityAdapterError(
                "Record Garmin live con activityId vuoto."
            )

        return source_id

    @staticmethod
    def _activity_type(
        record: Dict[str, Any],
    ) -> Optional[str]:
        value = record.get("activityType")

        if isinstance(value, dict):
            value = value.get("typeKey")

        if value is None:
            return None

        text = str(value).strip()
        return text or None

    @staticmethod
    def _start_datetime(
        value: Any,
    ) -> Optional[datetime]:
        if value is None:
            return None

        text = str(value).strip()

        if not text:
            return None

        normalized = text.replace(
            "Z",
            "+00:00",
        )

        try:
            parsed = datetime.fromisoformat(
                normalized
            )
        except ValueError:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )
        else:
            parsed = parsed.astimezone(
                timezone.utc
            )

        return parsed

    @staticmethod
    def _datetime_to_iso(
        value: Optional[datetime],
    ) -> Optional[str]:
        if value is None:
            return None

        return (
            value.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )

    @classmethod
    def _end_time(
        cls,
        start_datetime: Optional[datetime],
        duration_seconds: Optional[int],
    ) -> Optional[str]:
        if (
            start_datetime is None
            or duration_seconds is None
        ):
            return None

        return cls._datetime_to_iso(
            start_datetime
            + timedelta(
                seconds=duration_seconds
            )
        )

    @staticmethod
    def _number(
        value: Any,
    ) -> Optional[float]:
        if value is None or value == "":
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _integer(
        cls,
        value: Any,
    ) -> Optional[int]:
        number = cls._number(value)

        if number is None:
            return None

        return int(round(number))

    @staticmethod
    def _remove_none_values(
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            key: value
            for key, value in data.items()
            if value is not None
        }
