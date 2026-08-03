"""
Garmin Historical Importer

Unifica:
- attività Garmin provenienti dai file summarizedActivities JSON;
- collegamenti ai file grezzi FIT/TCX/GPX prodotti da garmin_raw_matcher.py.

Questo importer non estrae gli ZIP e non scrive nel database.
Arricchisce ogni IronCoachActivity con:
- stato di importazione;
- qualità del collegamento;
- archivio ZIP e nome del file grezzo;
- metriche usate per validare il collegamento.

Classificazione:
- SAFE: match EXCELLENT o GOOD;
- REVIEW: match POSSIBLE o WEAK;
- JSON_ONLY: nessun file grezzo collegato.

Uso:

    importer = GarminHistoricalImporter(
        summary_source="data/garmin/DI-Connect-Fitness",
        raw_matches_csv="data/garmin/garmin_raw_matches.csv",
    )

    activities = importer.import_activities()
"""

from __future__ import annotations

import csv
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.importers.garmin_summary_importer import (
    GarminSummaryImporter,
)
from backend.models.activity import IronCoachActivity


class GarminHistoricalImportError(Exception):
    """
    Errore durante la costruzione
    dello storico Garmin unificato.
    """


class GarminHistoricalImporter:
    """
    Unisce il catalogo Garmin JSON
    con il report dei collegamenti FIT/TCX/GPX.
    """

    SAFE_QUALITIES = {
        "EXCELLENT",
        "GOOD",
    }

    REVIEW_QUALITIES = {
        "POSSIBLE",
        "WEAK",
    }

    REQUIRED_MATCH_COLUMNS = {
        "activity_id",
        "archive",
        "member_name",
        "extension",
        "size_bytes",
        "match_score",
        "match_quality",
    }

    def __init__(
        self,
        summary_source: str,
        raw_matches_csv: Optional[str] = None,
    ):
        self.summary_source = Path(
            summary_source
        )

        self.raw_matches_csv = (
            Path(raw_matches_csv)
            if raw_matches_csv
            else None
        )

    def import_activities(
        self,
    ) -> List[IronCoachActivity]:
        """
        Importa tutte le attività Garmin
        e applica lo stato storico.
        """

        summary_activities = (
            GarminSummaryImporter(
                str(self.summary_source)
            ).import_activities()
        )

        matches = self._load_matches()

        enriched: List[
            IronCoachActivity
        ] = []

        for activity in summary_activities:
            match = matches.get(
                activity.source_id or ""
            )

            enriched.append(
                self._enrich_activity(
                    activity=activity,
                    match=match,
                )
            )

        return enriched

    def import_safe_activities(
        self,
    ) -> List[IronCoachActivity]:
        """
        Restituisce solo le attività
        con collegamento EXCELLENT o GOOD.
        """

        return [
            activity
            for activity in self.import_activities()
            if self.import_status(
                activity
            ) == "SAFE"
        ]

    def import_review_activities(
        self,
    ) -> List[IronCoachActivity]:
        """
        Restituisce solo le attività
        che richiedono revisione.
        """

        return [
            activity
            for activity in self.import_activities()
            if self.import_status(
                activity
            ) == "REVIEW"
        ]

    def import_json_only_activities(
        self,
    ) -> List[IronCoachActivity]:
        """
        Restituisce le attività senza
        file FIT/TCX/GPX collegato.
        """

        return [
            activity
            for activity in self.import_activities()
            if self.import_status(
                activity
            ) == "JSON_ONLY"
        ]

    def counts_by_status(
        self,
    ) -> Dict[str, int]:
        """
        Conta le attività per stato.
        """

        counts = {
            "SAFE": 0,
            "REVIEW": 0,
            "JSON_ONLY": 0,
        }

        for activity in self.import_activities():
            status = self.import_status(
                activity
            )

            counts[status] = (
                counts.get(
                    status,
                    0,
                )
                + 1
            )

        return counts

    @staticmethod
    def import_status(
        activity: IronCoachActivity,
    ) -> str:
        """
        Legge lo stato storico
        dai metadata dell'attività.
        """

        historical = (
            activity.metadata.get(
                "garmin_historical",
                {}
            )
        )

        status = historical.get(
            "import_status"
        )

        if status not in {
            "SAFE",
            "REVIEW",
            "JSON_ONLY",
        }:
            raise GarminHistoricalImportError(
                "Attività senza stato storico valido: "
                f"{activity.activity_id}"
            )

        return status

    def _load_matches(
        self,
    ) -> Dict[str, Dict[str, Any]]:
        if self.raw_matches_csv is None:
            return {}

        if not self.raw_matches_csv.exists():
            raise FileNotFoundError(
                "Garmin raw matches CSV not found: "
                f"{self.raw_matches_csv}"
            )

        try:
            with self.raw_matches_csv.open(
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as source:
                reader = csv.DictReader(
                    source
                )

                columns = set(
                    reader.fieldnames
                    or []
                )

                missing_columns = (
                    self.REQUIRED_MATCH_COLUMNS
                    - columns
                )

                if missing_columns:
                    raise GarminHistoricalImportError(
                        "CSV collegamenti Garmin senza "
                        "le colonne richieste: "
                        + ", ".join(
                            sorted(
                                missing_columns
                            )
                        )
                    )

                matches: Dict[
                    str,
                    Dict[str, Any],
                ] = {}

                for row_number, row in enumerate(
                    reader,
                    start=2,
                ):
                    activity_id = str(
                        row.get(
                            "activity_id"
                        )
                        or ""
                    ).strip()

                    if not activity_id:
                        raise GarminHistoricalImportError(
                            "CSV collegamenti Garmin: "
                            "activity_id vuoto alla riga "
                            f"{row_number}"
                        )

                    if activity_id in matches:
                        raise GarminHistoricalImportError(
                            "CSV collegamenti Garmin: "
                            "activity_id duplicato "
                            f"{activity_id}"
                        )

                    quality = str(
                        row.get(
                            "match_quality"
                        )
                        or ""
                    ).strip().upper()

                    if quality not in (
                        self.SAFE_QUALITIES
                        | self.REVIEW_QUALITIES
                    ):
                        raise GarminHistoricalImportError(
                            "Qualità collegamento Garmin "
                            "non supportata per "
                            f"{activity_id}: {quality}"
                        )

                    matches[
                        activity_id
                    ] = self._normalize_match_row(
                        row
                    )

        except OSError as exc:
            raise GarminHistoricalImportError(
                "Impossibile leggere il CSV "
                "dei collegamenti Garmin: "
                f"{self.raw_matches_csv}"
            ) from exc

        return matches

    def _enrich_activity(
        self,
        activity: IronCoachActivity,
        match: Optional[
            Dict[str, Any]
        ],
    ) -> IronCoachActivity:
        metadata = deepcopy(
            activity.metadata
        )

        if match is None:
            metadata[
                "garmin_historical"
            ] = {
                "import_status": "JSON_ONLY",
                "has_raw_file": False,
                "match_quality": None,
            }

            return replace(
                activity,
                metadata=metadata,
            )

        quality = str(
            match[
                "match_quality"
            ]
        ).upper()

        if quality in self.SAFE_QUALITIES:
            status = "SAFE"
        else:
            status = "REVIEW"

        metadata[
            "garmin_historical"
        ] = {
            "import_status": status,
            "has_raw_file": True,
            "match_quality": quality,
            "raw_file": {
                "archive": match.get(
                    "archive"
                ),
                "member_name": match.get(
                    "member_name"
                ),
                "extension": match.get(
                    "extension"
                ),
                "size_bytes": match.get(
                    "size_bytes"
                ),
            },
            "validation": {
                "match_score": match.get(
                    "match_score"
                ),
                "time_difference_seconds": match.get(
                    "time_difference_seconds"
                ),
                "duration_difference_percent": match.get(
                    "duration_difference_percent"
                ),
                "distance_difference_percent": match.get(
                    "distance_difference_percent"
                ),
                "raw_start_utc": match.get(
                    "raw_start_utc"
                ),
                "raw_duration_seconds": match.get(
                    "raw_duration_seconds"
                ),
                "raw_distance_meters": match.get(
                    "raw_distance_meters"
                ),
            },
        }

        return replace(
            activity,
            metadata=metadata,
        )

    @staticmethod
    def _normalize_match_row(
        row: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "activity_id": str(
                row.get(
                    "activity_id"
                )
                or ""
            ).strip(),
            "archive": GarminHistoricalImporter._optional_text(
                row.get(
                    "archive"
                )
            ),
            "member_name": GarminHistoricalImporter._optional_text(
                row.get(
                    "member_name"
                )
            ),
            "extension": GarminHistoricalImporter._optional_text(
                row.get(
                    "extension"
                )
            ),
            "size_bytes": GarminHistoricalImporter._integer(
                row.get(
                    "size_bytes"
                )
            ),
            "match_score": GarminHistoricalImporter._number(
                row.get(
                    "match_score"
                )
            ),
            "match_quality": str(
                row.get(
                    "match_quality"
                )
                or ""
            ).strip().upper(),
            "time_difference_seconds": GarminHistoricalImporter._number(
                row.get(
                    "time_difference_seconds"
                )
            ),
            "duration_difference_percent": GarminHistoricalImporter._number(
                row.get(
                    "duration_difference_percent"
                )
            ),
            "distance_difference_percent": GarminHistoricalImporter._number(
                row.get(
                    "distance_difference_percent"
                )
            ),
            "raw_start_utc": GarminHistoricalImporter._optional_text(
                row.get(
                    "raw_start_utc"
                )
            ),
            "raw_duration_seconds": GarminHistoricalImporter._number(
                row.get(
                    "raw_duration_seconds"
                )
            ),
            "raw_distance_meters": GarminHistoricalImporter._number(
                row.get(
                    "raw_distance_meters"
                )
            ),
        }

    @staticmethod
    def _optional_text(
        value: Any,
    ) -> Optional[str]:
        if value is None:
            return None

        text = str(
            value
        ).strip()

        return text or None

    @staticmethod
    def _number(
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
            return float(
                text
            )
        except (
            TypeError,
            ValueError,
        ):
            return None

    @staticmethod
    def _integer(
        value: Any,
    ) -> Optional[int]:
        number = GarminHistoricalImporter._number(
            value
        )

        if number is None:
            return None

        return int(
            round(
                number
            )
        )