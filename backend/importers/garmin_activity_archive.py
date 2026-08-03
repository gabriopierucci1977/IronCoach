"""
Garmin Activity Archive

Accesso rapido all'export persistente delle attività Garmin.
Non esegue il parsing dei file grezzi e non scrive nel database.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from backend.importers.garmin_activity_exporter import GarminActivityExporter
from backend.models.activity import IronCoachActivity


DEFAULT_ARCHIVE_PATH = Path(
    "data/garmin/garmin_activities_merged.jsonl.gz"
)


class GarminActivityArchiveError(Exception):
    """Errore durante l'accesso all'archivio Garmin."""


@dataclass(frozen=True)
class GarminActivityArchiveStats:
    activity_count: int
    segment_count: int
    first_start_time: Optional[str]
    last_start_time: Optional[str]
    sport_counts: Dict[str, int]
    merge_status_counts: Dict[str, int]


class GarminActivityArchive:
    """Archivio in memoria indicizzato per activity_id e source_id."""

    def __init__(
        self,
        archive_path: str = str(DEFAULT_ARCHIVE_PATH),
        manifest_path: Optional[str] = None,
        validate_manifest: bool = True,
    ):
        self.archive_path = Path(archive_path)
        self.manifest_path = Path(manifest_path) if manifest_path else None
        self.validate_manifest = bool(validate_manifest)
        self._activities: Optional[List[IronCoachActivity]] = None
        self._by_activity_id: Dict[str, IronCoachActivity] = {}
        self._by_source_id: Dict[str, IronCoachActivity] = {}

    def count(self) -> int:
        return len(self._load())

    def all(self) -> List[IronCoachActivity]:
        return list(self._load())

    def iter_all(self) -> Iterable[IronCoachActivity]:
        return iter(self._load())

    def get_by_activity_id(
        self,
        activity_id: str,
    ) -> Optional[IronCoachActivity]:
        self._load()
        key = str(activity_id).strip()
        return self._by_activity_id.get(key) if key else None

    def get_by_source_id(
        self,
        source_id: str,
    ) -> Optional[IronCoachActivity]:
        self._load()
        key = str(source_id).strip()
        return self._by_source_id.get(key) if key else None

    def require_by_source_id(
        self,
        source_id: str,
    ) -> IronCoachActivity:
        activity = self.get_by_source_id(source_id)

        if activity is None:
            raise GarminActivityArchiveError(
                f"Attività Garmin non trovata: {source_id}"
            )

        return activity

    def latest(
        self,
        limit: int = 10,
        sports: Optional[Sequence[str]] = None,
    ) -> List[IronCoachActivity]:
        if limit < 0:
            raise ValueError("limit non può essere negativo.")

        if limit == 0:
            return []

        activities = self._filter_sports(self._load(), sports)
        return list(reversed(activities[-limit:]))

    def between(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        sports: Optional[Sequence[str]] = None,
    ) -> List[IronCoachActivity]:
        start_dt = self._parse_datetime(start, "start") if start else None
        end_dt = self._parse_datetime(end, "end") if end else None

        if start_dt and end_dt and start_dt > end_dt:
            raise ValueError("start non può essere successivo a end.")

        selected: List[IronCoachActivity] = []

        for activity in self._filter_sports(self._load(), sports):
            activity_dt = self._activity_datetime(activity)

            if activity_dt is None:
                continue

            if start_dt and activity_dt < start_dt:
                continue

            if end_dt and activity_dt > end_dt:
                continue

            selected.append(activity)

        return selected

    def by_sport(
        self,
        sport: str,
    ) -> List[IronCoachActivity]:
        normalized = self._normalize_sport(sport)

        if not normalized:
            return []

        return [
            activity
            for activity in self._load()
            if self._normalize_sport(activity.sport) == normalized
        ]

    def stats(self) -> GarminActivityArchiveStats:
        activities = self._load()
        sport_counts: Counter[str] = Counter()
        merge_status_counts: Counter[str] = Counter()
        segment_count = 0
        start_times: List[str] = []

        for activity in activities:
            sport_counts[
                self._normalize_sport(activity.sport) or "UNKNOWN"
            ] += 1
            segment_count += len(activity.segments or [])

            if activity.start_time:
                start_times.append(activity.start_time)

            metadata = activity.metadata if isinstance(activity.metadata, dict) else {}
            merge_metadata = metadata.get("garmin_merge", {})
            status = str(merge_metadata.get("merge_status") or "UNKNOWN")
            merge_status_counts[status] += 1

        return GarminActivityArchiveStats(
            activity_count=len(activities),
            segment_count=segment_count,
            first_start_time=start_times[0] if start_times else None,
            last_start_time=start_times[-1] if start_times else None,
            sport_counts=dict(sorted(sport_counts.items())),
            merge_status_counts=dict(sorted(merge_status_counts.items())),
        )

    def reload(self) -> None:
        self._activities = None
        self._by_activity_id = {}
        self._by_source_id = {}

    def _load(self) -> List[IronCoachActivity]:
        if self._activities is not None:
            return self._activities

        exporter = GarminActivityExporter(
            output_path=str(self.archive_path),
            manifest_path=(
                str(self.manifest_path)
                if self.manifest_path
                else None
            ),
        )

        try:
            activities = exporter.load(
                validate_manifest=self.validate_manifest
            )
        except (FileNotFoundError, OSError, ValueError) as exc:
            raise GarminActivityArchiveError(
                f"Impossibile caricare l'archivio Garmin: {self.archive_path}"
            ) from exc

        activities.sort(
            key=lambda activity: (
                self._activity_datetime(activity)
                or datetime.min.replace(tzinfo=timezone.utc),
                activity.source_id or "",
            )
        )

        self._activities = activities
        self._by_activity_id = {
            str(activity.activity_id): activity
            for activity in activities
            if activity.activity_id
        }
        self._by_source_id = {
            str(activity.source_id): activity
            for activity in activities
            if activity.source_id
        }

        return self._activities

    @classmethod
    def _filter_sports(
        cls,
        activities: Sequence[IronCoachActivity],
        sports: Optional[Sequence[str]],
    ) -> List[IronCoachActivity]:
        if not sports:
            return list(activities)

        normalized_sports = {
            cls._normalize_sport(sport)
            for sport in sports
            if cls._normalize_sport(sport)
        }

        return [
            activity
            for activity in activities
            if cls._normalize_sport(activity.sport) in normalized_sports
        ]

    @staticmethod
    def _normalize_sport(
        sport: Optional[str],
    ) -> str:
        return str(sport or "").strip().upper()

    @classmethod
    def _activity_datetime(
        cls,
        activity: IronCoachActivity,
    ) -> Optional[datetime]:
        if not activity.start_time:
            return None

        try:
            return cls._parse_datetime(
                activity.start_time,
                "activity.start_time",
            )
        except ValueError:
            return None

    @staticmethod
    def _parse_datetime(
        value: str,
        field_name: str,
    ) -> datetime:
        normalized = str(value).strip()

        if not normalized:
            raise ValueError(f"{field_name} non può essere vuoto.")

        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"

        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(
                f"{field_name} non è un timestamp ISO-8601 valido: {value}"
            ) from exc

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)