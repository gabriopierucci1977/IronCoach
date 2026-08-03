"""
IronCoach Context Builder v3

Costruisce il contesto completo atleta, includendo lo storico Garmin
persistente senza interrompere il flusso Airtable se l'archivio manca.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.history.performance_history import PerformanceHistory
from backend.history.recovery_history import RecoveryHistory
from backend.history.training_history import TrainingHistory
from backend.importers.garmin_activity_archive import (
    GarminActivityArchive,
    GarminActivityArchiveError,
)
from backend.models.activity import IronCoachActivity
from backend.normalization.activity_normalizer import ActivityNormalizer
from backend.normalization.athlete_normalizer import AthleteNormalizer
from backend.normalization.recovery_normalizer import RecoveryNormalizer


class ContextBuilder:
    def __init__(
        self,
        airtable_client,
        include_garmin: bool = True,
        garmin_archive: Optional[GarminActivityArchive] = None,
    ):
        self.client = airtable_client
        self.include_garmin = bool(include_garmin)
        self.garmin_archive = garmin_archive or GarminActivityArchive()
        self.activity_normalizer = ActivityNormalizer()
        self.recovery_normalizer = RecoveryNormalizer()
        self.athlete_normalizer = AthleteNormalizer()

    def build(self) -> Dict[str, Any]:
        warnings: List[str] = []

        raw_athlete = self.client.get_athlete_profile()
        raw_recovery = self.client.get_latest_recovery()
        raw_training = self.client.get_latest_training()
        nutrition = self.client.get_latest_nutrition()
        decision = self.client.get_latest_decision()

        athlete = self.athlete_normalizer.normalize(
            raw_athlete,
            source="airtable",
        )
        recovery = self.recovery_normalizer.normalize(
            raw_recovery,
            source="airtable",
        )
        training = self.activity_normalizer.normalize(
            raw_training,
            source="airtable",
        )

        airtable_sessions = self._load_airtable_training(warnings)
        garmin_sessions = self._load_garmin_training(warnings)
        merged_sessions = self._merge_training_sessions(
            garmin_sessions,
            airtable_sessions,
        )

        training_history = TrainingHistory()
        training_history.load(merged_sessions)

        recovery_history = RecoveryHistory()
        self._load_recovery_history(
            recovery_history,
            warnings,
        )

        performance_history = PerformanceHistory()
        self._load_performance_history(
            performance_history,
            warnings,
        )

        return {
            "athlete": athlete,
            "athlete_profile": athlete,
            "recovery": recovery,
            "training": training,
            "nutrition": nutrition,
            "decision": decision,
            "training_history": list(training_history.sessions),
            "garmin_training_history": list(garmin_sessions),
            "airtable_training_history": list(airtable_sessions),
            "recovery_history": (
                recovery_history.records
                if hasattr(recovery_history, "records")
                else []
            ),
            "performance_history": (
                performance_history.metrics
                if hasattr(performance_history, "metrics")
                else []
            ),
            "history": {
                "training": training_history,
                "recovery": recovery_history,
                "performance": performance_history,
            },
            "history_sources": {
                "training_total": len(training_history.sessions),
                "training_airtable": len(airtable_sessions),
                "training_garmin": len(garmin_sessions),
                "garmin_enabled": self.include_garmin,
            },
            "context_warnings": warnings,
        }

    def _load_airtable_training(
        self,
        warnings: List[str],
    ) -> List[Dict[str, Any]]:
        sessions: List[Dict[str, Any]] = []

        try:
            for raw_session in self.client.get_training_history() or []:
                sessions.append(
                    self.activity_normalizer.normalize(
                        raw_session,
                        source="airtable",
                    )
                )
        except Exception as exc:
            warnings.append(
                "Storico allenamenti Airtable non disponibile: "
                f"{type(exc).__name__}: {exc}"
            )

        return sessions

    def _load_garmin_training(
        self,
        warnings: List[str],
    ) -> List[Dict[str, Any]]:
        if not self.include_garmin:
            return []

        sessions: List[Dict[str, Any]] = []

        try:
            for activity in self.garmin_archive.iter_all():
                sessions.append(
                    self._garmin_activity_to_session(activity)
                )
        except (
            FileNotFoundError,
            GarminActivityArchiveError,
            OSError,
            ValueError,
        ) as exc:
            warnings.append(
                "Archivio Garmin non disponibile: "
                f"{type(exc).__name__}: {exc}"
            )

        return sessions

    def _garmin_activity_to_session(
        self,
        activity: IronCoachActivity,
    ) -> Dict[str, Any]:
        raw_activity = {
            "id": activity.activity_id,
            "activity_id": activity.activity_id,
            "source_id": activity.source_id,
            "date": activity.start_time,
            "start_date": activity.start_time,
            "sport": activity.sport,
            "activity_type": activity.activity_type,
            "duration_minutes": self._seconds_to_minutes(
                activity.duration_seconds
            ),
            "distance_km": self._meters_to_kilometers(
                activity.distance_meters
            ),
            "training_load": activity.training_load,
            "average_hr": activity.avg_hr,
            "max_hr": activity.max_hr,
            "average_power": activity.avg_power,
            "normalized_power": activity.normalized_power,
        }

        normalized = self.activity_normalizer.normalize(
            raw_activity,
            source="garmin",
        )
        normalized["activity_id"] = activity.activity_id
        normalized["source_id"] = activity.source_id
        normalized["file_hash"] = activity.file_hash
        normalized["segments"] = list(activity.segments or [])
        normalized["metadata"] = dict(activity.metadata or {})
        return normalized

    def _merge_training_sessions(
        self,
        garmin_sessions: List[Dict[str, Any]],
        airtable_sessions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        merged: List[Dict[str, Any]] = []
        seen = set()

        for session in [*garmin_sessions, *airtable_sessions]:
            key = self._session_key(session)

            if key in seen:
                continue

            seen.add(key)
            merged.append(session)

        merged.sort(key=self._session_sort_key)
        return merged

    def _session_key(
        self,
        session: Dict[str, Any],
    ) -> Tuple[Any, ...]:
        source = str(session.get("source") or "").strip().lower()
        source_id = str(
            session.get("source_id")
            or session.get("activity_id")
            or ""
        ).strip()

        if source_id:
            return ("id", source, source_id)

        return (
            "fingerprint",
            self._normalized_datetime_text(session.get("date")),
            str(session.get("sport") or "").strip().upper(),
            self._rounded_number(session.get("duration_minutes")),
            self._rounded_number(session.get("distance_km")),
        )

    @classmethod
    def _session_sort_key(
        cls,
        session: Dict[str, Any],
    ) -> Tuple[datetime, str]:
        return (
            cls._parse_datetime(session.get("date"))
            or datetime.min.replace(tzinfo=timezone.utc),
            str(session.get("source_id") or ""),
        )

    def _load_recovery_history(
        self,
        history: RecoveryHistory,
        warnings: List[str],
    ) -> None:
        try:
            for record in self.client.get_recovery_history() or []:
                history.add_record(
                    self.recovery_normalizer.normalize(
                        record,
                        source="airtable",
                    )
                )
        except Exception as exc:
            warnings.append(
                "Storico recovery Airtable non disponibile: "
                f"{type(exc).__name__}: {exc}"
            )

    def _load_performance_history(
        self,
        history: PerformanceHistory,
        warnings: List[str],
    ) -> None:
        try:
            for metric in self.client.get_performance_history() or []:
                history.add_metric(metric)
        except Exception as exc:
            warnings.append(
                "Storico performance Airtable non disponibile: "
                f"{type(exc).__name__}: {exc}"
            )

    @staticmethod
    def _seconds_to_minutes(value: Any) -> float:
        try:
            return round(float(value or 0) / 60.0, 3)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _meters_to_kilometers(value: Any) -> float:
        try:
            return round(float(value or 0) / 1000.0, 3)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _rounded_number(value: Any) -> float:
        try:
            return round(float(value or 0), 3)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _normalized_datetime_text(cls, value: Any) -> str:
        parsed = cls._parse_datetime(value)

        if parsed is None:
            return str(value or "").strip()

        return parsed.isoformat().replace("+00:00", "Z")

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        text = str(value or "").strip()

        if not text:
            return None

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)