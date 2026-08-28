"""
Garmin Live Sync

Sincronizza le attività correnti da Garmin Connect
nell'archivio persistente IronCoach.

Principi:
- Garmin Connect viene interrogato realmente;
- le attività live vengono convertite in IronCoachActivity;
- l'archivio esistente viene aggiornato tramite export_incremental;
- source_checked_at viene scritto solo dopo un sync completato;
- last_activity_at descrive l'ultima attività realmente archiviata.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from garminconnect import Garmin

from backend.importers.garmin_activity_archive import (
    DEFAULT_ARCHIVE_PATH,
)
from backend.importers.garmin_activity_exporter import (
    GarminActivityExporter,
)
from backend.importers.garmin_live_activity_adapter import (
    GarminLiveActivityAdapter,
)


DEFAULT_SYNC_STATE_PATH = Path(
    "data/garmin/garmin_live_sync_state.json"
)


class GarminLiveSyncError(Exception):
    """Errore durante la sincronizzazione live Garmin."""


@dataclass(frozen=True)
class GarminLiveSyncResult:
    """Riepilogo di una sincronizzazione Garmin live."""

    source_checked_at: str
    last_activity_at: Optional[str]
    start_date: str
    end_date: str
    fetched_count: int
    existing_count: int
    added_count: int
    skipped_existing: int
    activity_count: int
    archive_path: str
    state_path: str


class GarminLiveSync:
    """Sincronizza Garmin Connect con l'archivio IronCoach."""

    def __init__(
        self,
        *,
        archive_path: str = str(DEFAULT_ARCHIVE_PATH),
        state_path: str = str(DEFAULT_SYNC_STATE_PATH),
        tokenstore: Optional[str] = None,
        client=None,
    ):
        self.archive_path = Path(archive_path)
        self.state_path = Path(state_path)
        self.tokenstore = (
            tokenstore
            or os.getenv(
                "GARMINTOKENS",
                "data/garmin/auth",
            )
        )
        self.client = (
            client
            if client is not None
            else Garmin()
        )

    def sync(
        self,
        *,
        end_date: Optional[str] = None,
    ) -> GarminLiveSyncResult:
        exporter = GarminActivityExporter(
            output_path=str(
                self.archive_path
            )
        )

        existing = exporter.load(
            validate_manifest=True
        )

        last_existing_at = self._latest_start_time(
            existing
        )

        if last_existing_at is None:
            raise GarminLiveSyncError(
                "Archivio Garmin esistente senza "
                "una data attività utilizzabile."
            )

        start_date = self._date_part(
            last_existing_at
        )

        resolved_end_date = (
            end_date
            or datetime.now(
                timezone.utc
            ).date().isoformat()
        )

        self.client.login(
            tokenstore=self.tokenstore
        )

        raw_activities = (
            self.client.get_activities_by_date(
                startdate=start_date,
                enddate=resolved_end_date,
                sortorder="asc",
            )
            or []
        )

        live_activities = [
            GarminLiveActivityAdapter.convert(
                record
            )
            for record in raw_activities
        ]

        export_result = (
            exporter.export_incremental(
                live_activities
            )
        )

        updated = exporter.load(
            validate_manifest=True
        )

        last_activity_at = (
            self._latest_start_time(
                updated
            )
        )

        source_checked_at = (
            self._utc_now()
        )

        result = GarminLiveSyncResult(
            source_checked_at=source_checked_at,
            last_activity_at=last_activity_at,
            start_date=start_date,
            end_date=resolved_end_date,
            fetched_count=len(
                live_activities
            ),
            existing_count=(
                export_result.existing_count
            ),
            added_count=(
                export_result.added_count
            ),
            skipped_existing=(
                export_result.skipped_existing
            ),
            activity_count=(
                export_result.activity_count
            ),
            archive_path=str(
                self.archive_path
            ),
            state_path=str(
                self.state_path
            ),
        )

        self._write_state(
            asdict(result)
        )

        return result

    def _write_state(
        self,
        payload,
    ) -> None:
        self.state_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = (
            self.state_path.with_name(
                self.state_path.name + ".tmp"
            )
        )

        temporary_path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )

        temporary_path.replace(
            self.state_path
        )

    @staticmethod
    def _latest_start_time(
        activities,
    ) -> Optional[str]:
        values = [
            str(
                activity.start_time
            ).strip()
            for activity in activities
            if getattr(
                activity,
                "start_time",
                None,
            )
        ]

        return max(values) if values else None

    @staticmethod
    def _date_part(
        value: str,
    ) -> str:
        text = str(value).strip()

        if len(text) < 10:
            raise GarminLiveSyncError(
                "Timestamp Garmin non valido: "
                f"{value}"
            )

        return text[:10]

    @staticmethod
    def _utc_now() -> str:
        return (
            datetime.now(
                timezone.utc
            )
            .isoformat()
            .replace(
                "+00:00",
                "Z",
            )
        )
