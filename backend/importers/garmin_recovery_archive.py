"""
Garmin Recovery Archive

Archivio locale delle osservazioni fisiologiche
giornaliere Garmin.

Ogni data identifica un solo record. Un nuovo sync
della stessa giornata sostituisce il record precedente,
perché i dati Garmin possono completarsi nel corso
della giornata.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List


DEFAULT_RECOVERY_ARCHIVE_PATH = Path(
    "data/garmin/garmin_recovery_daily.json"
)


class GarminRecoveryArchiveError(Exception):
    """Errore nell'archivio Recovery Garmin."""


@dataclass(frozen=True)
class GarminRecoveryArchiveUpdateResult:
    existing_count: int
    inserted_count: int
    updated_count: int
    record_count: int
    archive_path: str


class GarminRecoveryArchive:
    """Archivio giornaliero Garmin indicizzato per data."""

    def __init__(
        self,
        archive_path: str = str(
            DEFAULT_RECOVERY_ARCHIVE_PATH
        ),
    ):
        self.archive_path = Path(
            archive_path
        )

    def load(
        self,
    ) -> List[Dict[str, Any]]:
        if not self.archive_path.is_file():
            return []

        try:
            payload = json.loads(
                self.archive_path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            raise GarminRecoveryArchiveError(
                "Archivio Recovery Garmin "
                "non leggibile."
            ) from exc

        if not isinstance(payload, list):
            raise GarminRecoveryArchiveError(
                "Archivio Recovery Garmin "
                "deve essere una lista JSON."
            )

        seen_dates = set()
        records = []

        for record in payload:
            self._validate_record(
                record
            )

            record_date = record["date"]

            if record_date in seen_dates:
                raise GarminRecoveryArchiveError(
                    "Data duplicata nell'archivio "
                    "Recovery Garmin: "
                    f"{record_date}"
                )

            seen_dates.add(
                record_date
            )
            records.append(
                record
            )

        records.sort(
            key=lambda item: item["date"]
        )

        return records

    def upsert(
        self,
        observations: Iterable[
            Dict[str, Any]
        ],
    ) -> GarminRecoveryArchiveUpdateResult:
        existing = self.load()

        by_date = {
            item["date"]: item
            for item in existing
        }

        existing_count = len(
            existing
        )
        inserted_count = 0
        updated_count = 0

        for observation in observations:
            self._validate_record(
                observation
            )

            observation_date = (
                observation["date"]
            )

            if observation_date in by_date:
                updated_count += 1
            else:
                inserted_count += 1

            by_date[
                observation_date
            ] = observation

        records = sorted(
            by_date.values(),
            key=lambda item: item["date"],
        )

        self._write_atomic(
            records
        )

        # Verifica che quanto scritto sia
        # nuovamente leggibile e valido.
        validated = self.load()

        return (
            GarminRecoveryArchiveUpdateResult(
                existing_count=existing_count,
                inserted_count=inserted_count,
                updated_count=updated_count,
                record_count=len(validated),
                archive_path=str(
                    self.archive_path
                ),
            )
        )

    def latest(
        self,
        limit: int = 1,
    ) -> List[Dict[str, Any]]:
        if limit < 0:
            raise ValueError(
                "limit non può essere negativo."
            )

        if limit == 0:
            return []

        records = self.load()

        return list(
            reversed(
                records[-limit:]
            )
        )

    def _write_atomic(
        self,
        records: List[
            Dict[str, Any]
        ],
    ) -> None:
        self.archive_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = (
            self.archive_path.with_name(
                self.archive_path.name
                + f".{os.getpid()}.tmp"
            )
        )

        try:
            temporary_path.write_text(
                json.dumps(
                    records,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                )
                + "\n",
                encoding="utf-8",
            )

            temporary_path.replace(
                self.archive_path
            )
        except (
            OSError,
            TypeError,
            ValueError,
        ) as exc:
            temporary_path.unlink(
                missing_ok=True
            )

            raise GarminRecoveryArchiveError(
                "Impossibile scrivere "
                "l'archivio Recovery Garmin."
            ) from exc

    @staticmethod
    def _validate_record(
        record: Dict[str, Any],
    ) -> None:
        if not isinstance(
            record,
            dict,
        ):
            raise GarminRecoveryArchiveError(
                "Record Recovery Garmin "
                "non valido."
            )

        record_date = str(
            record.get("date") or ""
        ).strip()

        if not record_date:
            raise GarminRecoveryArchiveError(
                "Record Recovery Garmin "
                "senza data."
            )

        try:
            parsed = date.fromisoformat(
                record_date
            )
        except ValueError as exc:
            raise GarminRecoveryArchiveError(
                "Data Recovery Garmin "
                f"non valida: {record_date}"
            ) from exc

        if (
            parsed.isoformat()
            != record_date
        ):
            raise GarminRecoveryArchiveError(
                "Data Recovery Garmin "
                f"non canonica: {record_date}"
            )

        if (
            record.get("source")
            != "garmin"
        ):
            raise GarminRecoveryArchiveError(
                "Sorgente Recovery Garmin "
                "non valida."
            )

        try:
            json.dumps(
                record,
                allow_nan=False,
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise GarminRecoveryArchiveError(
                "Record Recovery Garmin "
                "non serializzabile."
            ) from exc
