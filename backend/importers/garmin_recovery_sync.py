"""
Garmin Recovery Sync

Legge le osservazioni fisiologiche giornaliere
da Garmin Connect e le salva nell'archivio locale
IronCoach.

Principi:
- Garmin viene usato in sola lettura;
- una giornata viene aggiornata tramite upsert;
- Body Battery resta distinta da readiness;
- source_checked_at viene scritto soltanto dopo
  una lettura Garmin completa e un archivio validato;
- un errore non deve produrre uno stato sorgente
  falsamente aggiornato.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from garminconnect import Garmin

from backend.importers.garmin_recovery_adapter import (
    GarminRecoveryAdapter,
)
from backend.importers.garmin_recovery_archive import (
    DEFAULT_RECOVERY_ARCHIVE_PATH,
    GarminRecoveryArchive,
)


DEFAULT_RECOVERY_SYNC_STATE_PATH = Path(
    "data/garmin/garmin_recovery_sync_state.json"
)


class GarminRecoverySyncError(Exception):
    """Errore durante il sync Recovery Garmin."""


@dataclass(frozen=True)
class GarminRecoverySyncResult:
    source_checked_at: str
    last_observation_date: str
    sync_date: str
    existing_count: int
    inserted_count: int
    updated_count: int
    record_count: int
    archive_path: str
    state_path: str


class GarminRecoverySync:
    """Sincronizza una giornata Recovery Garmin."""

    def __init__(
        self,
        *,
        archive_path: str = str(
            DEFAULT_RECOVERY_ARCHIVE_PATH
        ),
        state_path: str = str(
            DEFAULT_RECOVERY_SYNC_STATE_PATH
        ),
        tokenstore: Optional[str] = None,
        client=None,
    ):
        self.archive_path = Path(
            archive_path
        )
        self.state_path = Path(
            state_path
        )
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
        sync_date: Optional[str] = None,
    ) -> GarminRecoverySyncResult:
        resolved_date = (
            sync_date
            or datetime.now(
                timezone.utc
            ).date().isoformat()
        )

        self._validate_date(
            resolved_date
        )

        try:
            self.client.login(
                tokenstore=self.tokenstore
            )

            sleep = (
                self.client.get_sleep_data(
                    resolved_date
                )
                or {}
            )

            hrv = (
                self.client.get_hrv_data(
                    resolved_date
                )
                or {}
            )

            training_readiness = (
                self.client
                .get_morning_training_readiness(
                    resolved_date
                )
            )

            stress = (
                self.client.get_stress_data(
                    resolved_date
                )
                or {}
            )

            body_battery = (
                self.client.get_body_battery(
                    resolved_date,
                    resolved_date,
                )
                or []
            )

            stats = (
                self.client.get_stats_and_body(
                    resolved_date
                )
                or {}
            )

            observation = (
                GarminRecoveryAdapter.convert(
                    date=resolved_date,
                    sleep=sleep,
                    hrv=hrv,
                    training_readiness=(
                        training_readiness
                    ),
                    stress=stress,
                    body_battery=body_battery,
                    stats=stats,
                )
            )

            archive = GarminRecoveryArchive(
                archive_path=str(
                    self.archive_path
                )
            )

            update_result = archive.upsert(
                [observation]
            )

            # Verifica esplicita finale:
            # il record appena scritto deve essere
            # nuovamente leggibile e presente.
            records = archive.load()

            if not any(
                item.get("date")
                == resolved_date
                for item in records
            ):
                raise GarminRecoverySyncError(
                    "Osservazione Recovery Garmin "
                    "non presente dopo il salvataggio."
                )

        except GarminRecoverySyncError:
            raise
        except Exception as exc:
            raise GarminRecoverySyncError(
                "Sincronizzazione Recovery Garmin "
                "non completata."
            ) from exc

        source_checked_at = self._utc_now()

        result = GarminRecoverySyncResult(
            source_checked_at=source_checked_at,
            last_observation_date=(
                resolved_date
            ),
            sync_date=resolved_date,
            existing_count=(
                update_result.existing_count
            ),
            inserted_count=(
                update_result.inserted_count
            ),
            updated_count=(
                update_result.updated_count
            ),
            record_count=(
                update_result.record_count
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
                self.state_path.name
                + f".{os.getpid()}.tmp"
            )
        )

        try:
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

        except (
            OSError,
            TypeError,
            ValueError,
        ) as exc:
            temporary_path.unlink(
                missing_ok=True
            )

            raise GarminRecoverySyncError(
                "Impossibile salvare lo stato "
                "del sync Recovery Garmin."
            ) from exc

    @staticmethod
    def _validate_date(
        value: str,
    ) -> None:
        try:
            parsed = (
                datetime.strptime(
                    value,
                    "%Y-%m-%d",
                )
                .date()
            )
        except ValueError as exc:
            raise GarminRecoverySyncError(
                "Data sync Recovery Garmin "
                f"non valida: {value}"
            ) from exc

        if parsed.isoformat() != value:
            raise GarminRecoverySyncError(
                "Data sync Recovery Garmin "
                f"non canonica: {value}"
            )

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
