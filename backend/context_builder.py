"""
IronCoach Context Builder v3

Costruisce il contesto completo atleta, includendo lo storico Garmin
persistente senza interrompere il flusso Airtable se l'archivio manca.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.config import (
    RuntimeConfig,
    get_runtime_config,
)
from backend.history.performance_history import PerformanceHistory
from backend.history.recovery_history import RecoveryHistory
from backend.history.training_history import TrainingHistory
from backend.importers.garmin_activity_archive import (
    GarminActivityArchive,
    GarminActivityArchiveError,
)
from backend.importers.garmin_recovery_archive import (
    GarminRecoveryArchive,
    GarminRecoveryArchiveError,
)
from backend.models.activity import IronCoachActivity
from backend.normalization.activity_normalizer import ActivityNormalizer
from backend.normalization.athlete_normalizer import AthleteNormalizer
from backend.normalization.recovery_normalizer import RecoveryNormalizer
from backend.intelligence.athlete_profile_engine import (
    AthleteProfileEngine,
)


class ContextBuilder:
    def __init__(
        self,
        airtable_client,
        include_garmin: bool = True,
        garmin_archive: Optional[GarminActivityArchive] = None,
        runtime_config: Optional[RuntimeConfig] = None,
        recovery_max_age_days: Optional[int] = None,
        training_max_age_days: Optional[int] = None,
        garmin_source_state_path: Optional[str] = None,
        garmin_recovery_archive: Optional[
            GarminRecoveryArchive
        ] = None,
        garmin_recovery_source_state_path: Optional[
            str
        ] = None,
    ):
        self.client = airtable_client
        self.include_garmin = bool(include_garmin)
        self.garmin_archive = garmin_archive or GarminActivityArchive()
        self.garmin_source_state_path = (
            Path(garmin_source_state_path)
            if garmin_source_state_path
            else None
        )
        self.garmin_recovery_archive = (
            garmin_recovery_archive
        )
        self.garmin_recovery_source_state_path = (
            Path(
                garmin_recovery_source_state_path
            )
            if garmin_recovery_source_state_path
            else None
        )

        self.runtime_config = (
            runtime_config
            or get_runtime_config()
        )

        self.recovery_max_age_days = self._resolve_max_age_days(
            recovery_max_age_days,
            self.runtime_config.recovery_max_age_days,
        )
        self.training_max_age_days = self._resolve_max_age_days(
            training_max_age_days,
            self.runtime_config.training_max_age_days,
        )
        self.activity_normalizer = ActivityNormalizer()
        self.recovery_normalizer = RecoveryNormalizer()
        self.athlete_normalizer = AthleteNormalizer()
        self.athlete_profile_engine = AthleteProfileEngine()

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
        garmin_performance_history = (
            self._build_garmin_performance_history(
                garmin_sessions
            )
        )
        merged_sessions = self._merge_training_sessions(
            garmin_sessions,
            airtable_sessions,
        )

        garmin_source_state = (
            self._load_garmin_source_state(
                warnings
            )
        )

        garmin_recovery_history = (
            self._load_garmin_recovery_history(
                warnings
            )
        )

        garmin_recovery_source_state = (
            self._load_garmin_recovery_source_state(
                warnings
            )
        )

        source_checked_at = (
            garmin_source_state.get(
                "source_checked_at"
            )
            if garmin_source_state
            else None
        )

        last_activity_at = (
            garmin_source_state.get(
                "last_activity_at"
            )
            if garmin_source_state
            else None
        )

        training_freshness_date = training.get(
            "date"
        )
        training_freshness_label = "Allenamento"

        if source_checked_at:
            training_freshness_date = source_checked_at
            training_freshness_label = (
                "Fonte allenamenti"
            )
        elif (
            not training_freshness_date
            and merged_sessions
        ):
            training_freshness_date = (
                merged_sessions[-1].get(
                    "date"
                )
            )

        data_freshness = self._build_data_freshness(
            recovery_date=recovery.get("date"),
            training_date=training_freshness_date,
            recovery_max_age_days=self.recovery_max_age_days,
            training_max_age_days=self.training_max_age_days,
            training_label=training_freshness_label,
        )

        if source_checked_at:
            data_freshness["training"] = {
                **data_freshness["training"],
                "basis": "source_checked_at",
                "source_checked_at": source_checked_at,
                "last_activity_at": last_activity_at,
                "window_complete": (
                    data_freshness[
                        "training"
                    ].get("status")
                    == "CURRENT"
                ),
            }

        warnings.extend(
            data_freshness.get(
                "reasons",
                [],
            )
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

        athlete_profile_intelligence = (
            self.athlete_profile_engine.analyze(
                {
                    "athlete": athlete,
                    "training_history": list(
                        training_history.sessions
                    ),
                }
            )
        )

        history_sources = {
            "training_total": len(
                training_history.sessions
            ),
            "training_airtable": len(
                airtable_sessions
            ),
            "training_garmin": len(
                garmin_sessions
            ),
            "garmin_enabled": self.include_garmin,
        }

        if garmin_performance_history:
            history_sources[
                "garmin_performance_total"
            ] = len(
                garmin_performance_history
            )

        if source_checked_at:
            history_sources.update(
                {
                    "garmin_source_checked_at": (
                        source_checked_at
                    ),
                    "garmin_last_activity_at": (
                        last_activity_at
                    ),
                    "garmin_source_status": (
                        data_freshness[
                            "training"
                        ].get("status")
                    ),
                }
            )

        if (
            self.garmin_recovery_archive
            is not None
            or self.garmin_recovery_source_state_path
            is not None
        ):
            history_sources.update(
                {
                    "garmin_recovery_total": len(
                        garmin_recovery_history
                    ),
                    "garmin_recovery_enabled": (
                        self.include_garmin
                    ),
                }
            )

        if garmin_recovery_source_state:
            history_sources.update(
                {
                    "garmin_recovery_source_checked_at": (
                        garmin_recovery_source_state.get(
                            "source_checked_at"
                        )
                    ),
                    "garmin_recovery_last_observation_date": (
                        garmin_recovery_source_state.get(
                            "last_observation_date"
                        )
                    ),
                }
            )

        return {
            "athlete": athlete,
            "athlete_profile": athlete,
            "athlete_profile_intelligence": (
                athlete_profile_intelligence
            ),
            "recovery": recovery,
            "training": training,
            "nutrition": nutrition,
            "decision": decision,
            "training_history": list(training_history.sessions),
            "garmin_training_history": list(garmin_sessions),
            "airtable_training_history": list(airtable_sessions),
            "garmin_recovery_history": list(
                garmin_recovery_history
            ),
            "garmin_performance_history": list(
                garmin_performance_history
            ),
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
            "history_sources": history_sources,
            "data_freshness": data_freshness,
            "context_warnings": warnings,
        }

    def _load_garmin_recovery_history(
        self,
        warnings: List[str],
    ) -> List[Dict[str, Any]]:
        if (
            not self.include_garmin
            or self.garmin_recovery_archive
            is None
        ):
            return []

        try:
            return list(
                self.garmin_recovery_archive.load()
                or []
            )
        except (
            GarminRecoveryArchiveError,
            FileNotFoundError,
            OSError,
            ValueError,
        ) as exc:
            warnings.append(
                "Storico recovery Garmin "
                "non disponibile: "
                f"{type(exc).__name__}: {exc}"
            )
            return []

    def _load_garmin_recovery_source_state(
        self,
        warnings: List[str],
    ) -> Dict[str, Any]:
        if (
            not self.include_garmin
            or self.garmin_recovery_source_state_path
            is None
        ):
            return {}

        path = (
            self.garmin_recovery_source_state_path
        )

        if not path.is_file():
            warnings.append(
                "Stato sorgente recovery Garmin "
                "non disponibile: "
                f"file non trovato ({path})"
            )
            return {}

        try:
            payload = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception as exc:
            warnings.append(
                "Stato sorgente recovery Garmin "
                "non disponibile: "
                f"{type(exc).__name__}: {exc}"
            )
            return {}

        if not isinstance(
            payload,
            dict,
        ):
            warnings.append(
                "Stato sorgente recovery Garmin "
                "non valido"
            )
            return {}

        return payload

    def _load_garmin_source_state(
        self,
        warnings: List[str],
    ) -> Dict[str, Any]:
        if (
            not self.include_garmin
            or self.garmin_source_state_path
            is None
        ):
            return {}

        path = self.garmin_source_state_path

        if not path.is_file():
            warnings.append(
                "Stato sorgente Garmin live non disponibile: "
                f"file non trovato ({path})"
            )
            return {}

        try:
            payload = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception as exc:
            warnings.append(
                "Stato sorgente Garmin live non disponibile: "
                f"{type(exc).__name__}: {exc}"
            )
            return {}

        if not isinstance(payload, dict):
            warnings.append(
                "Stato sorgente Garmin live non valido"
            )
            return {}

        source_checked_at = payload.get(
            "source_checked_at"
        )

        if not source_checked_at:
            warnings.append(
                "Stato sorgente Garmin live senza "
                "source_checked_at"
            )
            return {}

        return payload

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

    @staticmethod
    def _build_garmin_performance_history(
        garmin_sessions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        observations: List[Dict[str, Any]] = []

        metric_by_sport = {
            "RUN": "vo2max_run",
            "BIKE": "vo2max_bike",
        }

        for session in garmin_sessions:
            if not isinstance(session, dict):
                continue

            sport = str(
                session.get("sport")
                or ""
            ).strip().upper()

            metric = metric_by_sport.get(
                sport
            )

            if metric is None:
                continue

            date = session.get("date")

            if date in (None, ""):
                continue

            metadata = (
                session.get("metadata")
                or {}
            )

            if not isinstance(
                metadata,
                dict,
            ):
                continue

            live = (
                metadata.get("garmin_live")
                or {}
            )
            historical = (
                metadata.get("garmin")
                or {}
            )

            value = None

            if isinstance(live, dict):
                value = live.get(
                    "vo2_max"
                )

            if (
                value in (None, "")
                and isinstance(
                    historical,
                    dict,
                )
            ):
                value = historical.get(
                    "vo2_max"
                )

            try:
                numeric_value = float(
                    value
                )
            except (TypeError, ValueError):
                continue

            if numeric_value <= 0:
                continue

            observations.append(
                {
                    "date": date,
                    "metric": metric,
                    "value": numeric_value,
                    "source": "garmin",
                    "source_id": session.get(
                        "source_id"
                    ),
                }
            )

        return observations

    def _merge_training_sessions(
        self,
        garmin_sessions: List[Dict[str, Any]],
        airtable_sessions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        merged: List[Dict[str, Any]] = []
        seen = set()

        # Airtable ha priorità nel totale combinato perché conserva
        # informazioni soggettive come RPE, sensazioni, note e carico
        # interno. Gli elenchi separati Garmin e Airtable restano intatti.
        for session in [*airtable_sessions, *garmin_sessions]:
            key = self._session_key(session)

            if key in seen:
                continue

            if any(
                self._sessions_match_cross_source(
                    session,
                    existing,
                )
                for existing in merged
            ):
                continue

            seen.add(key)
            merged.append(session)

        merged.sort(key=self._session_sort_key)
        return merged

    @classmethod
    def _sessions_match_cross_source(
        cls,
        first: Dict[str, Any],
        second: Dict[str, Any],
    ) -> bool:
        first_source = str(
            first.get("source") or ""
        ).strip().lower()
        second_source = str(
            second.get("source") or ""
        ).strip().lower()

        if (
            not first_source
            or not second_source
            or first_source == second_source
        ):
            return False

        first_sport = str(
            first.get("sport") or ""
        ).strip().upper()
        second_sport = str(
            second.get("sport") or ""
        ).strip().upper()

        if (
            not first_sport
            or first_sport != second_sport
        ):
            return False

        first_date = cls._parse_datetime(
            first.get("date")
        )
        second_date = cls._parse_datetime(
            second.get("date")
        )

        if first_date is None or second_date is None:
            return False

        if abs(
            (first_date.date() - second_date.date()).days
        ) > 1:
            return False

        first_duration = cls._number_or_none(
            first.get("duration_minutes")
        )
        second_duration = cls._number_or_none(
            second.get("duration_minutes")
        )

        if (
            first_duration is None
            or second_duration is None
            or first_duration <= 0
            or second_duration <= 0
            or abs(first_duration - second_duration) > 1.0
        ):
            return False

        first_distance = cls._number_or_none(
            first.get("distance_km")
        )
        second_distance = cls._number_or_none(
            second.get("distance_km")
        )

        has_distance = (
            (first_distance or 0) > 0
            or (second_distance or 0) > 0
        )

        if has_distance and (
            first_distance is None
            or second_distance is None
            or first_distance <= 0
            or second_distance <= 0
            or abs(first_distance - second_distance) > 0.2
        ):
            return False

        return True

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

    @classmethod
    def _build_data_freshness(
        cls,
        recovery_date: Any,
        training_date: Any,
        recovery_max_age_days: int,
        training_max_age_days: int,
        training_label: str = "Allenamento",
    ) -> Dict[str, Any]:
        recovery = cls._assess_data_freshness(
            label="Recovery",
            value=recovery_date,
            max_age_days=recovery_max_age_days,
            stale_level="HIGH",
        )
        training = cls._assess_data_freshness(
            label=training_label,
            value=training_date,
            max_age_days=training_max_age_days,
            stale_level="MODERATE",
        )

        reasons = [
            item["reason"]
            for item in (
                recovery,
                training,
            )
            if item.get("reason")
        ]

        levels = {
            recovery.get("level"),
            training.get("level"),
        }

        if "HIGH" in levels:
            level = "HIGH"
        elif "MODERATE" in levels:
            level = "MODERATE"
        else:
            level = "LOW"

        return {
            "level": level,
            "reasons": reasons,
            "recovery": recovery,
            "training": training,
        }

    @classmethod
    def _assess_data_freshness(
        cls,
        label: str,
        value: Any,
        max_age_days: int,
        stale_level: str,
    ) -> Dict[str, Any]:
        parsed = cls._parse_datetime(value)

        if parsed is None:
            return {
                "status": "UNKNOWN",
                "level": "LOW",
                "date": None,
                "age_days": None,
                "max_age_days": max_age_days,
                "reason": None,
            }

        date_text = parsed.date().isoformat()
        now = datetime.now(timezone.utc)
        age_days = (now.date() - parsed.date()).days

        if age_days < 0:
            return {
                "status": "FUTURE",
                "level": stale_level,
                "date": date_text,
                "age_days": age_days,
                "max_age_days": max_age_days,
                "reason": (
                    f"{label}: data futura ({date_text})"
                ),
            }

        if age_days > max_age_days:
            return {
                "status": "STALE",
                "level": stale_level,
                "date": date_text,
                "age_days": age_days,
                "max_age_days": max_age_days,
                "reason": (
                    f"{label}: dato obsoleto di {age_days} giorni "
                    f"(data {date_text}, "
                    f"soglia {max_age_days} giorni)"
                ),
            }

        return {
            "status": "CURRENT",
            "level": "LOW",
            "date": date_text,
            "age_days": age_days,
            "max_age_days": max_age_days,
            "reason": None,
        }

    @staticmethod
    def _resolve_max_age_days(
        value: Optional[int],
        default: int,
    ) -> int:
        if value is None:
            return default

        try:
            resolved = int(value)
        except (TypeError, ValueError):
            return default

        if resolved < 0:
            return default

        return resolved

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

    @staticmethod
    def _number_or_none(
        value: Any,
    ) -> Optional[float]:
        try:
            if value is None or value == "":
                return None

            return float(value)
        except (TypeError, ValueError):
            return None

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