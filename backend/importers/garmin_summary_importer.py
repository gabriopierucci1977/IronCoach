"""
Garmin Summarized Activities Importer

Converte uno o più file Garmin *_summarizedActivities.json
nel modello interno IronCoachActivity.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from backend.models.activity import IronCoachActivity


class GarminSummaryImportError(Exception):
    """Errore durante la lettura o conversione dei riepiloghi Garmin."""


class GarminSummaryImporter:
    """Importatore dei file Garmin summarizedActivities."""

    SUMMARY_PATTERN = "*_summarizedActivities.json"

    def __init__(self, source_path: str):
        self.source_path = Path(source_path)

    def import_activities(self) -> List[IronCoachActivity]:
        """Importa, deduplica per activityId e ordina cronologicamente."""
        activities_by_source_id: Dict[str, IronCoachActivity] = {}

        for source_file in self._discover_source_files():
            for record in self._load_records(source_file):
                activity = self._build_activity(record, source_file)
                source_id = activity.source_id

                if source_id is None:
                    raise GarminSummaryImportError(
                        f"Attività Garmin senza source_id in {source_file}"
                    )

                if source_id in activities_by_source_id:
                    raise GarminSummaryImportError(
                        f"activityId Garmin duplicato: {source_id}"
                    )

                activities_by_source_id[source_id] = activity

        return sorted(
            activities_by_source_id.values(),
            key=lambda activity: (
                activity.start_time or "",
                activity.source_id or "",
            ),
        )

    def import_activity(self, activity_id: str) -> IronCoachActivity:
        """Importa una sola attività Garmin identificata da activityId."""
        requested_id = str(activity_id).strip()

        for activity in self.import_activities():
            if activity.source_id == requested_id:
                return activity

        raise GarminSummaryImportError(
            f"Attività Garmin non trovata: {requested_id}"
        )

    def _discover_source_files(self) -> List[Path]:
        if not self.source_path.exists():
            raise FileNotFoundError(
                f"Garmin summary source not found: {self.source_path}"
            )

        if self.source_path.is_file():
            if self.source_path.suffix.lower() != ".json":
                raise GarminSummaryImportError(
                    f"Il file sorgente non è JSON: {self.source_path}"
                )
            return [self.source_path]

        source_files = sorted(
            self.source_path.rglob(self.SUMMARY_PATTERN)
        )

        if not source_files:
            raise GarminSummaryImportError(
                "Nessun file *_summarizedActivities.json trovato in: "
                f"{self.source_path}"
            )

        return source_files

    def _load_records(self, source_file: Path) -> List[Dict[str, Any]]:
        try:
            payload = json.loads(source_file.read_text(encoding="utf-8"))
        except OSError as exc:
            raise GarminSummaryImportError(
                f"Impossibile leggere il file: {source_file}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise GarminSummaryImportError(
                f"JSON Garmin non valido: {source_file}"
            ) from exc

        if not isinstance(payload, list):
            raise GarminSummaryImportError(
                "Formato Garmin inatteso: la radice JSON deve essere "
                f"una lista in {source_file}"
            )

        records: List[Dict[str, Any]] = []

        for block in payload:
            if not isinstance(block, dict):
                continue

            exported = block.get("summarizedActivitiesExport")
            if not isinstance(exported, list):
                continue

            records.extend(
                item for item in exported if isinstance(item, dict)
            )

        return records

    def _build_activity(
        self,
        record: Dict[str, Any],
        source_file: Path,
    ) -> IronCoachActivity:
        source_id = self._required_source_id(record)
        start_datetime = self._start_datetime(record)
        duration_seconds = self._milliseconds_to_seconds_int(
            record.get("duration")
        )
        activity_type = self._optional_string(record.get("activityType"))
        sport_type = self._optional_string(record.get("sportType"))

        activity_training_load = self._number(
            record.get("activityTrainingLoad")
        )
        if activity_training_load is None:
            activity_training_load = self._number(
                record.get("activityTrainingLoadSrvrCalc")
            )

        calories_kj = self._number(record.get("calories"))

        return IronCoachActivity(
            activity_id=f"garmin:{source_id}",
            source="garmin",
            source_id=source_id,
            file_hash=None,
            start_time=self._datetime_to_iso(start_datetime),
            end_time=self._end_time(start_datetime, duration_seconds),
            sport=self._normalize_sport(activity_type, sport_type),
            activity_type=activity_type,
            duration_seconds=duration_seconds,
            distance_meters=self._centimeters_to_meters(
                record.get("distance")
            ),
            elevation_gain=self._centimeters_to_meters(
                record.get("elevationGain")
            ),
            elevation_loss=self._centimeters_to_meters(
                record.get("elevationLoss")
            ),
            calories=self._kilojoules_to_kilocalories_int(calories_kj),
            avg_speed=self._centimeters_per_millisecond_to_mps(
                record.get("avgSpeed")
            ),
            max_speed=self._centimeters_per_millisecond_to_mps(
                record.get("maxSpeed")
            ),
            avg_hr=self._integer(record.get("avgHr")),
            max_hr=self._integer(record.get("maxHr")),
            avg_cadence=self._first_number(
                record,
                ("avgRunCadence", "avgBikeCadence", "avgSwimCadence"),
            ),
            max_cadence=self._first_number(
                record,
                ("maxRunCadence", "maxBikeCadence", "maxSwimCadence"),
            ),
            avg_power=self._number(record.get("avgPower")),
            normalized_power=self._number(record.get("normPower")),
            training_load=activity_training_load,
            training_effect=self._number(
                record.get("aerobicTrainingEffect")
            ),
            segments=[],
            metadata=self._build_metadata(
                record=record,
                source_file=source_file,
                calories_kj=calories_kj,
            ),
        )

    def _build_metadata(
        self,
        record: Dict[str, Any],
        source_file: Path,
        calories_kj: Optional[float],
    ) -> Dict[str, Any]:
        garmin: Dict[str, Any] = {
            "summary_file": source_file.name,
            "activity_id": self._required_source_id(record),
            "name": record.get("name"),
            "sport_type": record.get("sportType"),
            "activity_type": record.get("activityType"),
            "rule": record.get("rule"),
            "event_type_id": record.get("eventTypeId"),
            "time_zone_id": record.get("timeZoneId"),
            "start_time_local": self._local_time_text(
                record.get("startTimeLocal")
            ),
            "elapsed_duration_seconds": self._milliseconds_to_seconds_float(
                record.get("elapsedDuration")
            ),
            "moving_duration_seconds": self._milliseconds_to_seconds_float(
                record.get("movingDuration")
            ),
            "min_hr": self._integer(record.get("minHr")),
            "max_power": self._number(record.get("maxPower")),
            "training_stress_score": self._number(
                record.get("trainingStressScore")
            ),
            "intensity_factor": self._number(
                record.get("intensityFactor")
            ),
            "anaerobic_training_effect": self._number(
                record.get("anaerobicTrainingEffect")
            ),
            "training_effect_label": (
                record.get("trainingEffectLabel")
                or record.get("trainingEffectLabelSrvrCalc")
            ),
            "vo2_max": self._number(record.get("vO2MaxValue")),
            "steps": self._integer(record.get("steps")),
            "lap_count": self._integer(record.get("lapCount")),
            "manufacturer": record.get("manufacturer"),
            "device_id": record.get("deviceId"),
            "location_name": record.get("locationName"),
            "pool_length_meters": self._centimeters_to_meters(
                record.get("poolLength")
            ),
            "active_lengths": self._integer(record.get("activeLengths")),
            "avg_swolf": self._number(record.get("avgSwolf")),
            "avg_stride_length_centimeters": self._number(
                record.get("avgStrideLength")
            ),
            "avg_vertical_oscillation": self._number(
                record.get("avgVerticalOscillation")
            ),
            "avg_vertical_ratio": self._number(
                record.get("avgVerticalRatio")
            ),
            "avg_ground_contact_time": self._number(
                record.get("avgGroundContactTime")
            ),
            "avg_ground_contact_balance": self._number(
                record.get("avgGroundContactBalance")
            ),
            "lactate_threshold_bpm": self._number(
                record.get("lactateThresholdBpm")
            ),
            "lactate_threshold_speed_mps": (
                self._centimeters_per_millisecond_to_mps(
                    record.get("lactateThresholdSpeed")
                )
            ),
            "workout_rpe": self._number(record.get("workoutRpe")),
            "workout_feel": self._number(record.get("workoutFeel")),
            "moderate_intensity_minutes": self._integer(
                record.get("moderateIntensityMinutes")
            ),
            "vigorous_intensity_minutes": self._integer(
                record.get("vigorousIntensityMinutes")
            ),
            "calories_raw_kilojoules": calories_kj,
            "bmr_calories_raw_kilojoules": self._number(
                record.get("bmrCalories")
            ),
            "is_parent": bool(record.get("parent")),
            "favorite": bool(record.get("favorite")),
            "personal_record": bool(record.get("pr")),
            "purposeful": bool(record.get("purposeful")),
            "start_latitude": self._number(record.get("startLatitude")),
            "start_longitude": self._number(record.get("startLongitude")),
            "end_latitude": self._number(record.get("endLatitude")),
            "end_longitude": self._number(record.get("endLongitude")),
            "hr_time_in_zone_ms": self._zone_values(
                record, "hrTimeInZone_"
            ),
            "power_time_in_zone_ms": self._zone_values(
                record, "powerTimeInZone_"
            ),
            "split_summaries": record.get("splitSummaries"),
            "splits": record.get("splits"),
        }

        return {"garmin": self._remove_none_values(garmin)}

    @staticmethod
    def _required_source_id(record: Dict[str, Any]) -> str:
        value = record.get("activityId")
        if value is None:
            raise GarminSummaryImportError("Record Garmin senza activityId")

        source_id = str(value).strip()
        if not source_id:
            raise GarminSummaryImportError(
                "Record Garmin con activityId vuoto"
            )

        return source_id

    @staticmethod
    def _start_datetime(record: Dict[str, Any]) -> Optional[datetime]:
        value = record.get("beginTimestamp") or record.get("startTimeGmt")
        number = GarminSummaryImporter._number(value)

        if number is None:
            return None

        try:
            return datetime.fromtimestamp(
                number / 1000.0,
                tz=timezone.utc,
            )
        except (OSError, OverflowError, ValueError):
            return None

    @staticmethod
    def _end_time(
        start_datetime: Optional[datetime],
        duration_seconds: Optional[int],
    ) -> Optional[str]:
        if start_datetime is None or duration_seconds is None:
            return None

        return GarminSummaryImporter._datetime_to_iso(
            start_datetime + timedelta(seconds=duration_seconds)
        )

    @staticmethod
    def _datetime_to_iso(value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None

        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)

        return value.isoformat().replace("+00:00", "Z")

    @staticmethod
    def _local_time_text(value: Any) -> Optional[str]:
        number = GarminSummaryImporter._number(value)
        if number is None:
            return None

        try:
            local_time = datetime.fromtimestamp(
                number / 1000.0,
                tz=timezone.utc,
            )
        except (OSError, OverflowError, ValueError):
            return None

        return local_time.strftime("%Y-%m-%dT%H:%M:%S")

    @staticmethod
    def _milliseconds_to_seconds_int(value: Any) -> Optional[int]:
        number = GarminSummaryImporter._number(value)
        return None if number is None else int(round(number / 1000.0))

    @staticmethod
    def _milliseconds_to_seconds_float(value: Any) -> Optional[float]:
        number = GarminSummaryImporter._number(value)
        return None if number is None else round(number / 1000.0, 3)

    @staticmethod
    def _centimeters_to_meters(value: Any) -> Optional[float]:
        number = GarminSummaryImporter._number(value)
        return None if number is None else round(number / 100.0, 3)

    @staticmethod
    def _centimeters_per_millisecond_to_mps(
        value: Any,
    ) -> Optional[float]:
        number = GarminSummaryImporter._number(value)
        return None if number is None else round(number * 10.0, 6)

    @staticmethod
    def _kilojoules_to_kilocalories_int(
        value: Optional[float],
    ) -> Optional[int]:
        return None if value is None else int(round(value / 4.184))

    @staticmethod
    def _number(value: Any) -> Optional[float]:
        if value is None or value == "":
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _integer(value: Any) -> Optional[int]:
        number = GarminSummaryImporter._number(value)
        return None if number is None else int(round(number))

    @staticmethod
    def _optional_string(value: Any) -> Optional[str]:
        if value is None:
            return None

        text = str(value).strip()
        return text or None

    @staticmethod
    def _first_number(
        record: Dict[str, Any],
        keys: Iterable[str],
    ) -> Optional[float]:
        for key in keys:
            value = GarminSummaryImporter._number(record.get(key))
            if value is not None:
                return value

        return None

    @staticmethod
    def _normalize_sport(
        activity_type: Optional[str],
        sport_type: Optional[str],
    ) -> Optional[str]:
        activity = (activity_type or "").strip().lower()
        sport = (sport_type or "").strip().lower()

        mapping = {
            "running": "RUN",
            "track_running": "RUN",
            "street_running": "RUN",
            "trail_running": "RUN",
            "treadmill_running": "RUN",
            "cycling": "BIKE",
            "road_biking": "BIKE",
            "indoor_cycling": "BIKE",
            "virtual_ride": "BIKE",
            "mountain_biking": "BIKE",
            "gravel_cycling": "BIKE",
            "lap_swimming": "SWIM",
            "open_water_swimming": "SWIM",
            "swimming": "SWIM",
            "strength_training": "STRENGTH",
            "strength": "STRENGTH",
            "multi_sport": "MULTISPORT",
            "multisport": "MULTISPORT",
            "transition": "TRANSITION",
            "transition_v2": "TRANSITION",
            "walking": "WALK",
            "hiking": "HIKE",
            "indoor_cardio": "INDOOR_CARDIO",
            "rowing_v2": "ROW",
            "rowing": "ROW",
            "yoga": "YOGA",
            "pilates": "PILATES",
            "other": "OTHER",
        }

        if activity in mapping:
            return mapping[activity]
        if sport in mapping:
            return mapping[sport]
        if "run" in activity:
            return "RUN"
        if any(token in activity for token in ("cycl", "bike", "ride")):
            return "BIKE"
        if "swim" in activity:
            return "SWIM"
        if "strength" in activity:
            return "STRENGTH"
        if "multi" in activity:
            return "MULTISPORT"

        fallback = activity or sport
        return fallback.upper() if fallback else None

    @staticmethod
    def _zone_values(
        record: Dict[str, Any],
        prefix: str,
    ) -> Dict[str, int]:
        values: Dict[str, int] = {}

        for key, raw_value in record.items():
            if not key.startswith(prefix):
                continue

            value = GarminSummaryImporter._integer(raw_value)
            if value is not None:
                values[key.removeprefix(prefix)] = value

        return values

    @staticmethod
    def _remove_none_values(data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            key: value
            for key, value in data.items()
            if value is not None and value != {}
        }