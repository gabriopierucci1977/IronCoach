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

        if self._enrich_existing_live_metadata(
            updated,
            live_activities,
        ):
            exporter.export(
                updated
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

    @staticmethod
    def _enrich_existing_live_metadata(
        existing,
        live_activities,
    ) -> bool:
        """
        Arricchisce soltanto metadata.garmin_live delle attività
        già archiviate con identità perfettamente coincidente.

        Non modifica activity_id, source_id o metriche canoniche.
        """

        by_activity_id = {
            str(
                activity.activity_id
            ).strip(): activity
            for activity in existing
            if activity.activity_id
        }

        by_source_id = {
            str(
                activity.source_id
            ).strip(): activity
            for activity in existing
            if activity.source_id
        }

        changed = False

        for incoming in live_activities:
            activity_id = str(
                incoming.activity_id
                or ""
            ).strip()
            source_id = str(
                incoming.source_id
                or ""
            ).strip()

            if not activity_id or not source_id:
                continue

            by_id = by_activity_id.get(
                activity_id
            )
            by_source = by_source_id.get(
                source_id
            )

            if (
                by_id is None
                or by_source is None
            ):
                continue

            if by_id is not by_source:
                raise GarminLiveSyncError(
                    "Identità Garmin incoerente durante "
                    "l'enrichment live: "
                    f"{activity_id}/{source_id}"
                )

            incoming_metadata = (
                incoming.metadata
                if isinstance(
                    incoming.metadata,
                    dict,
                )
                else {}
            )

            incoming_live = (
                incoming_metadata.get(
                    "garmin_live"
                )
                or {}
            )

            if not isinstance(
                incoming_live,
                dict,
            ) or not incoming_live:
                continue

            target_metadata = (
                dict(by_id.metadata)
                if isinstance(
                    by_id.metadata,
                    dict,
                )
                else {}
            )

            existing_live = (
                target_metadata.get(
                    "garmin_live"
                )
                or {}
            )

            if not isinstance(
                existing_live,
                dict,
            ):
                existing_live = {}

            merged_live = {
                **existing_live,
                **incoming_live,
            }

            if merged_live == existing_live:
                continue

            target_metadata[
                "garmin_live"
            ] = merged_live

            by_id.metadata = (
                target_metadata
            )

            changed = True

        return changed

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
