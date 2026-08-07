"""
Garmin Activity Merger

Fonde le attività Garmin storiche basate sui file
summarizedActivities JSON con i file grezzi estratti
FIT, TCX e GPX.

Principi:
- l'attività JSON mantiene identità Garmin, sport,
  tipo, tempi e metadati principali;
- il file grezzo arricchisce solo campi mancanti;
- i segmenti multisport FIT vengono conservati;
- ogni fusione registra provenienza, formato e risultato;
- nessuna scrittura nel database.

Uso:

    merger = GarminActivityMerger(
        summary_source="data/garmin",
        raw_matches_csv="data/garmin/garmin_raw_matches.csv",
        extracted_directory="data/garmin_extracted",
    )

    result = merger.merge_all()
    activities = result.activities
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from backend.importers.garmin_fit_importer import GarminFitImporter
from backend.importers.garmin_historical_importer import (
    GarminHistoricalImporter,
)
from backend.models.activity import IronCoachActivity


class GarminActivityMergeError(Exception):
    """
    Errore durante la fusione tra riepilogo JSON
    e file grezzo Garmin.
    """


@dataclass(frozen=True)
class GarminActivityMergeResult:
    """
    Risultato complessivo della fusione.
    """

    activities: List[IronCoachActivity]
    total: int
    merged: int
    json_only: int
    skipped_review: int
    missing_raw_files: int
    parse_errors: int
    excluded_existing: int


class GarminActivityMerger:
    """
    Fonde attività JSON e file grezzi Garmin.
    """

    SUPPORTED_EXTENSIONS = {
        ".fit",
        ".tcx",
        ".gpx",
    }

    MERGE_FIELDS = (
        "end_time",
        "elevation_gain",
        "elevation_loss",
        "calories",
        "avg_speed",
        "max_speed",
        "avg_hr",
        "max_hr",
        "avg_cadence",
        "max_cadence",
        "avg_power",
        "normalized_power",
        "training_load",
        "training_effect",
    )

    def __init__(
        self,
        summary_source: str,
        raw_matches_csv: str,
        extracted_directory: str,
        include_review: bool = False,
        strict: bool = False,
        excluded_source_ids: Optional[Iterable[str]] = None,
    ):
        self.summary_source = Path(summary_source)
        self.raw_matches_csv = Path(raw_matches_csv)
        self.extracted_directory = Path(extracted_directory)
        self.include_review = include_review
        self.strict = strict
        self.excluded_source_ids = {
            str(source_id).strip()
            for source_id in (excluded_source_ids or ())
            if str(source_id).strip()
        }

    def merge_all(
        self,
    ) -> GarminActivityMergeResult:
        """
        Importa lo storico Garmin e fonde i file grezzi
        disponibili nella cartella estratta.
        """

        historical = GarminHistoricalImporter(
            summary_source=str(self.summary_source),
            raw_matches_csv=str(self.raw_matches_csv),
        ).import_activities()

        activities: List[IronCoachActivity] = []

        counters = {
            "merged": 0,
            "json_only": 0,
            "skipped_review": 0,
            "missing_raw_files": 0,
            "parse_errors": 0,
            "excluded_existing": 0,
        }

        for activity in historical:
            source_id = str(
                activity.source_id or ""
            ).strip()

            if source_id in self.excluded_source_ids:
                counters["excluded_existing"] += 1
                continue

            status = GarminHistoricalImporter.import_status(
                activity
            )

            if status == "JSON_ONLY":
                activities.append(
                    self._mark_unmerged(
                        activity=activity,
                        merge_status="JSON_ONLY",
                        message="Nessun file grezzo collegato.",
                    )
                )
                counters["json_only"] += 1
                continue

            if status == "REVIEW" and not self.include_review:
                activities.append(
                    self._mark_unmerged(
                        activity=activity,
                        merge_status="SKIPPED_REVIEW",
                        message=(
                            "File grezzo non utilizzato perché "
                            "il collegamento richiede revisione."
                        ),
                    )
                )
                counters["skipped_review"] += 1
                continue

            raw_path = self._raw_path(activity)

            if not raw_path.exists():
                message = f"File grezzo estratto non trovato: {raw_path}"

                if self.strict:
                    raise FileNotFoundError(message)

                activities.append(
                    self._mark_unmerged(
                        activity=activity,
                        merge_status="MISSING_RAW_FILE",
                        message=message,
                    )
                )
                counters["missing_raw_files"] += 1
                continue

            try:
                raw_activity = self._import_raw_activity(
                    raw_path
                )

                merged = self._merge_activity(
                    summary_activity=activity,
                    raw_activity=raw_activity,
                    raw_path=raw_path,
                )

                activities.append(merged)
                counters["merged"] += 1

            except (
                GarminActivityMergeError,
                ET.ParseError,
                OSError,
                ValueError,
                IndexError,
                KeyError,
            ) as exc:
                if self.strict:
                    raise GarminActivityMergeError(
                        f"Errore nel file {raw_path}: {exc}"
                    ) from exc

                activities.append(
                    self._mark_unmerged(
                        activity=activity,
                        merge_status="PARSE_ERROR",
                        message=str(exc),
                        raw_path=raw_path,
                    )
                )
                counters["parse_errors"] += 1

        return GarminActivityMergeResult(
            activities=activities,
            total=len(activities),
            merged=counters["merged"],
            json_only=counters["json_only"],
            skipped_review=counters["skipped_review"],
            missing_raw_files=counters["missing_raw_files"],
            parse_errors=counters["parse_errors"],
            excluded_existing=counters["excluded_existing"],
        )

    def merge_activity(
        self,
        activity_id: str,
    ) -> IronCoachActivity:
        """
        Fonde una sola attività Garmin per activityId.
        """

        requested = str(activity_id).strip()

        if not requested:
            raise GarminActivityMergeError(
                "activity_id vuoto."
            )

        result = self.merge_all()

        for activity in result.activities:
            if activity.source_id == requested:
                return activity

        raise GarminActivityMergeError(
            f"Attività Garmin non trovata: {requested}"
        )

    def _raw_path(
        self,
        activity: IronCoachActivity,
    ) -> Path:
        extension = self._raw_extension(activity)
        source_id = str(
            activity.source_id or ""
        ).strip()

        if not source_id:
            raise GarminActivityMergeError(
                "Attività storica senza source_id."
            )

        return (
            self.extracted_directory
            / f"{self._safe_activity_id(source_id)}{extension}"
        )

    @staticmethod
    def _raw_extension(
        activity: IronCoachActivity,
    ) -> str:
        historical = activity.metadata.get(
            "garmin_historical",
            {},
        )

        raw_file = historical.get(
            "raw_file",
            {},
        )

        extension = str(
            raw_file.get("extension") or ""
        ).strip().lower()

        if extension not in GarminActivityMerger.SUPPORTED_EXTENSIONS:
            raise GarminActivityMergeError(
                "Estensione grezza non supportata per "
                f"{activity.activity_id}: {extension}"
            )

        return extension

    def _import_raw_activity(
        self,
        raw_path: Path,
    ) -> IronCoachActivity:
        extension = raw_path.suffix.lower()

        if extension == ".fit":
            return GarminFitImporter(
                str(raw_path)
            ).import_activity()

        if extension == ".tcx":
            return self._import_tcx(raw_path)

        if extension == ".gpx":
            return self._import_gpx(raw_path)

        raise GarminActivityMergeError(
            f"Formato grezzo non supportato: {extension}"
        )

    def _merge_activity(
        self,
        summary_activity: IronCoachActivity,
        raw_activity: IronCoachActivity,
        raw_path: Path,
    ) -> IronCoachActivity:
        updates: Dict[str, Any] = {}
        fields_from_raw: List[str] = []

        if not summary_activity.file_hash and raw_activity.file_hash:
            updates["file_hash"] = raw_activity.file_hash
            fields_from_raw.append("file_hash")

        if (
            not summary_activity.duration_seconds
            and raw_activity.duration_seconds
        ):
            updates["duration_seconds"] = raw_activity.duration_seconds
            fields_from_raw.append("duration_seconds")

        if (
            not summary_activity.distance_meters
            and raw_activity.distance_meters
        ):
            updates["distance_meters"] = raw_activity.distance_meters
            fields_from_raw.append("distance_meters")

        for field_name in self.MERGE_FIELDS:
            summary_value = getattr(
                summary_activity,
                field_name,
                None,
            )

            raw_value = getattr(
                raw_activity,
                field_name,
                None,
            )

            if self._is_missing(summary_value) and not self._is_missing(
                raw_value
            ):
                updates[field_name] = raw_value
                fields_from_raw.append(field_name)

        raw_segments = list(
            raw_activity.segments or []
        )

        if raw_segments and not summary_activity.segments:
            updates["segments"] = raw_segments
            fields_from_raw.append("segments")

        metadata = deepcopy(
            summary_activity.metadata
        )

        metadata["garmin_raw"] = deepcopy(
            raw_activity.metadata
        )

        metadata["garmin_merge"] = {
            "merge_status": "MERGED",
            "raw_format": raw_path.suffix.lower().removeprefix(".").upper(),
            "raw_file_name": raw_path.name,
            "raw_file_path": str(raw_path),
            "raw_file_hash": raw_activity.file_hash,
            "fields_from_raw": fields_from_raw,
            "summary_identity_preserved": True,
            "summary_source_id": summary_activity.source_id,
            "raw_activity_id": raw_activity.activity_id,
            "raw_source_id": raw_activity.source_id,
        }

        updates["metadata"] = metadata

        return replace(
            summary_activity,
            **updates,
        )

    def _mark_unmerged(
        self,
        activity: IronCoachActivity,
        merge_status: str,
        message: str,
        raw_path: Optional[Path] = None,
    ) -> IronCoachActivity:
        metadata = deepcopy(
            activity.metadata
        )

        metadata["garmin_merge"] = {
            "merge_status": merge_status,
            "message": message,
            "raw_file_path": (
                str(raw_path)
                if raw_path
                else None
            ),
            "fields_from_raw": [],
            "summary_identity_preserved": True,
        }

        return replace(
            activity,
            metadata=metadata,
        )

    def _import_tcx(
        self,
        path: Path,
    ) -> IronCoachActivity:
        root = ET.parse(
            path
        ).getroot()

        activities = self._xml_elements(
            root,
            "Activity",
        )

        if not activities:
            raise GarminActivityMergeError(
                f"Nessuna Activity TCX in {path}"
            )

        laps = []

        for activity_element in activities:
            laps.extend(
                self._xml_children(
                    activity_element,
                    "Lap",
                )
            )

        if not laps:
            raise GarminActivityMergeError(
                f"Nessun Lap TCX in {path}"
            )

        start_times: List[datetime] = []
        durations: List[float] = []
        distances: List[float] = []
        calories: List[int] = []
        avg_hr_values: List[int] = []
        max_hr_values: List[int] = []
        cadence_values: List[float] = []
        speed_values: List[float] = []
        power_values: List[float] = []

        for lap in laps:
            start_value = lap.attrib.get(
                "StartTime"
            )

            parsed_start = self._parse_datetime(
                start_value
            )

            if parsed_start is not None:
                start_times.append(parsed_start)

            duration = self._float_text(
                self._xml_child_text(
                    lap,
                    "TotalTimeSeconds",
                )
            )

            if duration is not None:
                durations.append(duration)

            distance = self._float_text(
                self._xml_child_text(
                    lap,
                    "DistanceMeters",
                )
            )

            if distance is not None:
                distances.append(distance)

            calorie_value = self._integer_text(
                self._xml_child_text(
                    lap,
                    "Calories",
                )
            )

            if calorie_value is not None:
                calories.append(calorie_value)

            avg_hr = self._integer_text(
                self._xml_descendant_text(
                    lap,
                    (
                        "AverageHeartRateBpm",
                        "Value",
                    ),
                )
            )

            if avg_hr is not None:
                avg_hr_values.append(avg_hr)

            max_hr = self._integer_text(
                self._xml_descendant_text(
                    lap,
                    (
                        "MaximumHeartRateBpm",
                        "Value",
                    ),
                )
            )

            if max_hr is not None:
                max_hr_values.append(max_hr)

            for trackpoint in self._xml_elements(
                lap,
                "Trackpoint",
            ):
                cadence = self._float_text(
                    self._xml_child_text(
                        trackpoint,
                        "Cadence",
                    )
                )

                if cadence is not None:
                    cadence_values.append(cadence)

                for element in trackpoint.iter():
                    local_name = self._local_name(
                        element.tag
                    )

                    if local_name == "Speed":
                        speed = self._float_text(
                            element.text
                        )

                        if speed is not None:
                            speed_values.append(speed)

                    if local_name in {
                        "Watts",
                        "Power",
                    }:
                        power = self._float_text(
                            element.text
                        )

                        if power is not None:
                            power_values.append(power)

        total_duration = (
            int(round(sum(durations)))
            if durations
            else None
        )

        total_distance = (
            round(sum(distances), 3)
            if distances
            else None
        )

        start_time = (
            min(start_times)
            if start_times
            else None
        )

        avg_speed = None

        if (
            total_distance is not None
            and total_duration
            and total_duration > 0
        ):
            avg_speed = round(
                total_distance / total_duration,
                6,
            )

        sport = self._tcx_sport(
            activities[0].attrib.get(
                "Sport"
            )
        )

        return IronCoachActivity(
            activity_id=self._sha256(path),
            source="garmin",
            source_id=self._sha256(path),
            file_hash=self._sha256(path),
            start_time=self._datetime_to_iso(
                start_time
            ),
            sport=sport,
            activity_type=(
                activities[0].attrib.get(
                    "Sport"
                )
                or "tcx"
            ),
            duration_seconds=total_duration,
            distance_meters=total_distance,
            calories=(
                sum(calories)
                if calories
                else None
            ),
            avg_speed=avg_speed,
            max_speed=(
                max(speed_values)
                if speed_values
                else None
            ),
            avg_hr=(
                int(round(sum(avg_hr_values) / len(avg_hr_values)))
                if avg_hr_values
                else None
            ),
            max_hr=(
                max(max_hr_values)
                if max_hr_values
                else None
            ),
            avg_cadence=(
                round(sum(cadence_values) / len(cadence_values), 3)
                if cadence_values
                else None
            ),
            max_cadence=(
                max(cadence_values)
                if cadence_values
                else None
            ),
            avg_power=(
                round(sum(power_values) / len(power_values), 3)
                if power_values
                else None
            ),
            metadata={
                "garmin": {
                    "file_name": path.name,
                    "format": "TCX",
                    "lap_count": len(laps),
                    "trackpoint_count": sum(
                        len(
                            self._xml_elements(
                                lap,
                                "Trackpoint",
                            )
                        )
                        for lap in laps
                    ),
                }
            },
        )

    def _import_gpx(
        self,
        path: Path,
    ) -> IronCoachActivity:
        root = ET.parse(
            path
        ).getroot()

        points = self._xml_elements(
            root,
            "trkpt",
        )

        if not points:
            raise GarminActivityMergeError(
                f"Nessun punto traccia GPX in {path}"
            )

        coordinates: List[
            Tuple[float, float]
        ] = []

        times: List[datetime] = []
        elevations: List[float] = []
        heart_rates: List[int] = []
        cadences: List[float] = []
        powers: List[float] = []

        for point in points:
            latitude = self._float_text(
                point.attrib.get("lat")
            )

            longitude = self._float_text(
                point.attrib.get("lon")
            )

            if (
                latitude is not None
                and longitude is not None
            ):
                coordinates.append(
                    (
                        latitude,
                        longitude,
                    )
                )

            point_time = self._parse_datetime(
                self._xml_child_text(
                    point,
                    "time",
                )
            )

            if point_time is not None:
                times.append(point_time)

            elevation = self._float_text(
                self._xml_child_text(
                    point,
                    "ele",
                )
            )

            if elevation is not None:
                elevations.append(elevation)

            for element in point.iter():
                local_name = self._local_name(
                    element.tag
                ).lower()

                if local_name in {
                    "hr",
                    "heartrate",
                }:
                    value = self._integer_text(
                        element.text
                    )

                    if value is not None:
                        heart_rates.append(value)

                if local_name in {
                    "cad",
                    "cadence",
                }:
                    value = self._float_text(
                        element.text
                    )

                    if value is not None:
                        cadences.append(value)

                if local_name in {
                    "power",
                    "watts",
                }:
                    value = self._float_text(
                        element.text
                    )

                    if value is not None:
                        powers.append(value)

        distance = self._gpx_distance(
            coordinates
        )

        duration = None

        if len(times) >= 2:
            duration = int(
                round(
                    (
                        max(times)
                        - min(times)
                    ).total_seconds()
                )
            )

        elevation_gain = 0.0
        elevation_loss = 0.0

        for previous, current in zip(
            elevations,
            elevations[1:],
        ):
            difference = current - previous

            if difference > 0:
                elevation_gain += difference
            elif difference < 0:
                elevation_loss += abs(difference)

        avg_speed = None

        if distance is not None and duration and duration > 0:
            avg_speed = round(
                distance / duration,
                6,
            )

        return IronCoachActivity(
            activity_id=self._sha256(path),
            source="garmin",
            source_id=self._sha256(path),
            file_hash=self._sha256(path),
            start_time=self._datetime_to_iso(
                min(times)
                if times
                else None
            ),
            sport="OTHER",
            activity_type="gpx",
            duration_seconds=duration,
            distance_meters=distance,
            elevation_gain=(
                round(elevation_gain, 3)
                if elevations
                else None
            ),
            elevation_loss=(
                round(elevation_loss, 3)
                if elevations
                else None
            ),
            avg_speed=avg_speed,
            avg_hr=(
                int(round(sum(heart_rates) / len(heart_rates)))
                if heart_rates
                else None
            ),
            max_hr=(
                max(heart_rates)
                if heart_rates
                else None
            ),
            avg_cadence=(
                round(sum(cadences) / len(cadences), 3)
                if cadences
                else None
            ),
            max_cadence=(
                max(cadences)
                if cadences
                else None
            ),
            avg_power=(
                round(sum(powers) / len(powers), 3)
                if powers
                else None
            ),
            metadata={
                "garmin": {
                    "file_name": path.name,
                    "format": "GPX",
                    "trackpoint_count": len(points),
                }
            },
        )

    @staticmethod
    def _xml_elements(
        root: ET.Element,
        local_name: str,
    ) -> List[ET.Element]:
        return [
            element
            for element in root.iter()
            if GarminActivityMerger._local_name(
                element.tag
            ) == local_name
        ]

    @staticmethod
    def _xml_children(
        root: ET.Element,
        local_name: str,
    ) -> List[ET.Element]:
        return [
            element
            for element in list(root)
            if GarminActivityMerger._local_name(
                element.tag
            ) == local_name
        ]

    @staticmethod
    def _xml_child_text(
        root: ET.Element,
        local_name: str,
    ) -> Optional[str]:
        for element in list(root):
            if GarminActivityMerger._local_name(
                element.tag
            ) == local_name:
                return element.text

        return None

    @staticmethod
    def _xml_descendant_text(
        root: ET.Element,
        path: Sequence[str],
    ) -> Optional[str]:
        current = root

        for name in path:
            found = None

            for element in list(current):
                if GarminActivityMerger._local_name(
                    element.tag
                ) == name:
                    found = element
                    break

            if found is None:
                return None

            current = found

        return current.text

    @staticmethod
    def _local_name(
        tag: str,
    ) -> str:
        return tag.rsplit(
            "}",
            1,
        )[-1]

    @staticmethod
    def _parse_datetime(
        value: Optional[str],
    ) -> Optional[datetime]:
        if not value:
            return None

        text = value.strip()

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

        if value.tzinfo is None:
            value = value.replace(
                tzinfo=timezone.utc
            )
        else:
            value = value.astimezone(
                timezone.utc
            )

        return value.isoformat().replace(
            "+00:00",
            "Z",
        )

    @staticmethod
    def _tcx_sport(
        value: Optional[str],
    ) -> Optional[str]:
        mapping = {
            "running": "RUN",
            "biking": "BIKE",
            "cycling": "BIKE",
            "swimming": "SWIM",
            "other": "OTHER",
        }

        text = str(
            value or ""
        ).strip().lower()

        return mapping.get(
            text,
            text.upper()
            if text
            else None,
        )

    @staticmethod
    def _gpx_distance(
        coordinates: Sequence[
            Tuple[float, float]
        ],
    ) -> Optional[float]:
        if len(coordinates) < 2:
            return None

        total = 0.0

        for previous, current in zip(
            coordinates,
            coordinates[1:],
        ):
            total += GarminActivityMerger._haversine(
                previous[0],
                previous[1],
                current[0],
                current[1],
            )

        return round(
            total,
            3,
        )

    @staticmethod
    def _haversine(
        latitude_1: float,
        longitude_1: float,
        latitude_2: float,
        longitude_2: float,
    ) -> float:
        radius = 6371000.0

        lat_1 = math.radians(
            latitude_1
        )

        lat_2 = math.radians(
            latitude_2
        )

        delta_lat = math.radians(
            latitude_2 - latitude_1
        )

        delta_lon = math.radians(
            longitude_2 - longitude_1
        )

        value = (
            math.sin(
                delta_lat / 2.0
            )
            ** 2
            + math.cos(lat_1)
            * math.cos(lat_2)
            * math.sin(
                delta_lon / 2.0
            )
            ** 2
        )

        return (
            2.0
            * radius
            * math.atan2(
                math.sqrt(value),
                math.sqrt(
                    1.0 - value
                ),
            )
        )

    @staticmethod
    def _sha256(
        path: Path,
    ) -> str:
        import hashlib

        sha = hashlib.sha256()

        with path.open(
            "rb"
        ) as source:
            for chunk in iter(
                lambda: source.read(
                    1024 * 1024
                ),
                b"",
            ):
                sha.update(chunk)

        return sha.hexdigest()

    @staticmethod
    def _safe_activity_id(
        activity_id: str,
    ) -> str:
        safe = "".join(
            character
            for character in activity_id
            if character.isalnum()
            or character in {
                "-",
                "_",
            }
        )

        if not safe:
            raise GarminActivityMergeError(
                "activity_id non utilizzabile come nome file."
            )

        return safe

    @staticmethod
    def _float_text(
        value: Any,
    ) -> Optional[float]:
        if value is None:
            return None

        text = str(
            value
        ).strip()

        if not text:
            return None

        try:
            return float(text)
        except (
            TypeError,
            ValueError,
        ):
            return None

    @staticmethod
    def _integer_text(
        value: Any,
    ) -> Optional[int]:
        number = GarminActivityMerger._float_text(
            value
        )

        if number is None:
            return None

        return int(
            round(number)
        )

    @staticmethod
    def _is_missing(
        value: Any,
    ) -> bool:
        if value is None:
            return True

        if isinstance(
            value,
            str,
        ):
            return not value.strip() or value.strip().lower() == "none"

        return False