"""
Garmin Raw File Extractor

Estrae in modo controllato dagli archivi ZIP Garmin
solo i file FIT/TCX/GPX presenti in garmin_raw_matches.csv.

Caratteristiche:
- non modifica gli ZIP originali;
- estrae solo match con qualità consentita;
- default: EXCELLENT e GOOD;
- impedisce path traversal;
- evita sovrascritture silenziose;
- verifica dimensione del file estratto;
- crea un manifest CSV dell'estrazione.

Uso:

    extractor = GarminRawFileExtractor(
        export_root="data/garmin_export",
        raw_matches_csv="data/garmin_export/garmin_raw_matches.csv",
        output_directory="data/garmin_extracted",
    )

    result = extractor.extract()
"""

from __future__ import annotations

import csv
import hashlib
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set


class GarminRawExtractionError(Exception):
    """
    Errore durante l'estrazione controllata
    dei file Garmin dagli archivi ZIP.
    """


@dataclass(frozen=True)
class GarminRawExtractionResult:
    """
    Riepilogo dell'estrazione.
    """

    requested: int
    extracted: int
    skipped_existing: int
    skipped_quality: int
    missing_archives: int
    missing_members: int
    errors: int
    manifest_path: str


class GarminRawFileExtractor:
    """
    Estrae i file grezzi Garmin collegati
    alle attività storiche.
    """

    ALLOWED_EXTENSIONS = {
        ".fit",
        ".tcx",
        ".gpx",
    }

    DEFAULT_QUALITIES = {
        "EXCELLENT",
        "GOOD",
    }

    REQUIRED_COLUMNS = {
        "activity_id",
        "archive",
        "member_name",
        "extension",
        "size_bytes",
        "match_quality",
    }

    MANIFEST_FIELDS = [
        "activity_id",
        "match_quality",
        "archive",
        "member_name",
        "extension",
        "expected_size_bytes",
        "output_path",
        "actual_size_bytes",
        "sha256",
        "status",
        "message",
    ]

    def __init__(
        self,
        export_root: str,
        raw_matches_csv: str,
        output_directory: str,
        allowed_qualities: Optional[
            Iterable[str]
        ] = None,
    ):
        self.export_root = Path(
            export_root
        )

        self.raw_matches_csv = Path(
            raw_matches_csv
        )

        self.output_directory = Path(
            output_directory
        )

        self.allowed_qualities: Set[str] = {
            str(
                quality
            ).strip().upper()
            for quality in (
                allowed_qualities
                or self.DEFAULT_QUALITIES
            )
        }

        if not self.allowed_qualities:
            raise GarminRawExtractionError(
                "Nessuna qualità di match consentita."
            )

    def extract(
        self,
    ) -> GarminRawExtractionResult:
        """
        Esegue l'estrazione controllata
        e scrive il manifest CSV.
        """

        self._validate_paths()

        rows = self._load_match_rows()

        self.output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        manifest_path = (
            self.output_directory
            / "garmin_raw_extraction_manifest.csv"
        )

        manifest_rows: List[
            Dict[str, Any]
        ] = []

        counters = {
            "requested": 0,
            "extracted": 0,
            "skipped_existing": 0,
            "skipped_quality": 0,
            "missing_archives": 0,
            "missing_members": 0,
            "errors": 0,
        }

        archive_cache: Dict[
            Path,
            zipfile.ZipFile,
        ] = {}

        try:
            for row in rows:
                quality = row[
                    "match_quality"
                ]

                if (
                    quality
                    not in self.allowed_qualities
                ):
                    counters[
                        "skipped_quality"
                    ] += 1

                    manifest_rows.append(
                        self._manifest_row(
                            row=row,
                            status="SKIPPED_QUALITY",
                            message=(
                                "Qualità non consentita: "
                                f"{quality}"
                            ),
                        )
                    )
                    continue

                counters[
                    "requested"
                ] += 1

                archive_path = (
                    self.export_root
                    / row["archive"]
                )

                if not archive_path.exists():
                    counters[
                        "missing_archives"
                    ] += 1

                    manifest_rows.append(
                        self._manifest_row(
                            row=row,
                            status="MISSING_ARCHIVE",
                            message=str(
                                archive_path
                            ),
                        )
                    )
                    continue

                try:
                    archive = archive_cache.get(
                        archive_path
                    )

                    if archive is None:
                        archive = zipfile.ZipFile(
                            archive_path,
                            "r",
                        )

                        archive_cache[
                            archive_path
                        ] = archive

                    member_name = row[
                        "member_name"
                    ]

                    try:
                        info = archive.getinfo(
                            member_name
                        )
                    except KeyError:
                        counters[
                            "missing_members"
                        ] += 1

                        manifest_rows.append(
                            self._manifest_row(
                                row=row,
                                status="MISSING_MEMBER",
                                message=member_name,
                            )
                        )
                        continue

                    output_path = self._output_path(
                        activity_id=row[
                            "activity_id"
                        ],
                        extension=row[
                            "extension"
                        ],
                    )

                    expected_size = row.get(
                        "size_bytes"
                    )

                    if output_path.exists():
                        existing_size = (
                            output_path.stat().st_size
                        )

                        if (
                            expected_size is None
                            or existing_size
                            == expected_size
                        ):
                            counters[
                                "skipped_existing"
                            ] += 1

                            manifest_rows.append(
                                self._manifest_row(
                                    row=row,
                                    output_path=output_path,
                                    actual_size=existing_size,
                                    sha256=self._sha256(
                                        output_path
                                    ),
                                    status="SKIPPED_EXISTING",
                                    message=(
                                        "File già presente "
                                        "con dimensione valida."
                                    ),
                                )
                            )
                            continue

                        raise GarminRawExtractionError(
                            "File esistente con dimensione "
                            "diversa da quella attesa: "
                            f"{output_path}"
                        )

                    temporary_path = (
                        output_path.with_suffix(
                            output_path.suffix
                            + ".tmp"
                        )
                    )

                    output_path.parent.mkdir(
                        parents=True,
                        exist_ok=True,
                    )

                    with archive.open(
                        info,
                        "r",
                    ) as source, temporary_path.open(
                        "wb"
                    ) as destination:
                        shutil.copyfileobj(
                            source,
                            destination,
                        )

                    actual_size = (
                        temporary_path.stat().st_size
                    )

                    if (
                        expected_size is not None
                        and actual_size
                        != expected_size
                    ):
                        temporary_path.unlink(
                            missing_ok=True
                        )

                        raise GarminRawExtractionError(
                            "Dimensione estratta diversa "
                            "da quella attesa per "
                            f"{row['activity_id']}: "
                            f"{actual_size} != "
                            f"{expected_size}"
                        )

                    temporary_path.replace(
                        output_path
                    )

                    file_hash = self._sha256(
                        output_path
                    )

                    counters[
                        "extracted"
                    ] += 1

                    manifest_rows.append(
                        self._manifest_row(
                            row=row,
                            output_path=output_path,
                            actual_size=actual_size,
                            sha256=file_hash,
                            status="EXTRACTED",
                            message="",
                        )
                    )

                except (
                    OSError,
                    RuntimeError,
                    zipfile.BadZipFile,
                    GarminRawExtractionError,
                ) as exc:
                    counters[
                        "errors"
                    ] += 1

                    manifest_rows.append(
                        self._manifest_row(
                            row=row,
                            status="ERROR",
                            message=str(
                                exc
                            ),
                        )
                    )

        finally:
            for archive in (
                archive_cache.values()
            ):
                archive.close()

        self._write_manifest(
            manifest_path,
            manifest_rows,
        )

        return GarminRawExtractionResult(
            requested=counters[
                "requested"
            ],
            extracted=counters[
                "extracted"
            ],
            skipped_existing=counters[
                "skipped_existing"
            ],
            skipped_quality=counters[
                "skipped_quality"
            ],
            missing_archives=counters[
                "missing_archives"
            ],
            missing_members=counters[
                "missing_members"
            ],
            errors=counters[
                "errors"
            ],
            manifest_path=str(
                manifest_path
            ),
        )

    def _validate_paths(
        self,
    ) -> None:
        if not self.export_root.exists():
            raise FileNotFoundError(
                "Garmin export root not found: "
                f"{self.export_root}"
            )

        if not self.export_root.is_dir():
            raise GarminRawExtractionError(
                "La radice dell'export Garmin "
                "non è una cartella: "
                f"{self.export_root}"
            )

        if not self.raw_matches_csv.exists():
            raise FileNotFoundError(
                "Garmin raw matches CSV not found: "
                f"{self.raw_matches_csv}"
            )

        if not self.raw_matches_csv.is_file():
            raise GarminRawExtractionError(
                "Il percorso del CSV Garmin "
                "non è un file: "
                f"{self.raw_matches_csv}"
            )

    def _load_match_rows(
        self,
    ) -> List[Dict[str, Any]]:
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
                    self.REQUIRED_COLUMNS
                    - columns
                )

                if missing_columns:
                    raise GarminRawExtractionError(
                        "CSV collegamenti Garmin senza "
                        "le colonne richieste: "
                        + ", ".join(
                            sorted(
                                missing_columns
                            )
                        )
                    )

                rows: List[
                    Dict[str, Any]
                ] = []

                seen_activity_ids: Set[
                    str
                ] = set()

                for row_number, raw_row in enumerate(
                    reader,
                    start=2,
                ):
                    row = self._normalize_row(
                        raw_row,
                        row_number,
                    )

                    activity_id = row[
                        "activity_id"
                    ]

                    if (
                        activity_id
                        in seen_activity_ids
                    ):
                        raise GarminRawExtractionError(
                            "activity_id duplicato "
                            "nel CSV dei match: "
                            f"{activity_id}"
                        )

                    seen_activity_ids.add(
                        activity_id
                    )

                    rows.append(
                        row
                    )

        except OSError as exc:
            raise GarminRawExtractionError(
                "Impossibile leggere il CSV "
                "dei collegamenti Garmin: "
                f"{self.raw_matches_csv}"
            ) from exc

        return rows

    def _normalize_row(
        self,
        row: Dict[str, Any],
        row_number: int,
    ) -> Dict[str, Any]:
        activity_id = self._required_text(
            row.get(
                "activity_id"
            ),
            "activity_id",
            row_number,
        )

        archive = self._required_text(
            row.get(
                "archive"
            ),
            "archive",
            row_number,
        )

        member_name = self._required_text(
            row.get(
                "member_name"
            ),
            "member_name",
            row_number,
        )

        extension = self._required_text(
            row.get(
                "extension"
            ),
            "extension",
            row_number,
        ).lower()

        if (
            extension
            not in self.ALLOWED_EXTENSIONS
        ):
            raise GarminRawExtractionError(
                "Estensione Garmin non supportata "
                f"alla riga {row_number}: "
                f"{extension}"
            )

        member_extension = (
            Path(
                member_name
            ).suffix.lower()
        )

        if member_extension != extension:
            raise GarminRawExtractionError(
                "Estensione incoerente "
                f"alla riga {row_number}: "
                f"{member_name} / {extension}"
            )

        quality = self._required_text(
            row.get(
                "match_quality"
            ),
            "match_quality",
            row_number,
        ).upper()

        return {
            "activity_id": activity_id,
            "archive": archive,
            "member_name": member_name,
            "extension": extension,
            "size_bytes": self._optional_integer(
                row.get(
                    "size_bytes"
                )
            ),
            "match_quality": quality,
        }

    def _output_path(
        self,
        activity_id: str,
        extension: str,
    ) -> Path:
        safe_activity_id = self._safe_activity_id(
            activity_id
        )

        output_path = (
            self.output_directory
            / f"{safe_activity_id}{extension}"
        )

        resolved_root = (
            self.output_directory.resolve()
        )

        resolved_output = (
            output_path.resolve()
        )

        try:
            resolved_output.relative_to(
                resolved_root
            )
        except ValueError as exc:
            raise GarminRawExtractionError(
                "Percorso di output non sicuro: "
                f"{output_path}"
            ) from exc

        return output_path

    @staticmethod
    def _safe_activity_id(
        activity_id: str,
    ) -> str:
        allowed = []

        for character in activity_id:
            if (
                character.isalnum()
                or character in {
                    "-",
                    "_",
                }
            ):
                allowed.append(
                    character
                )

        safe = "".join(
            allowed
        )

        if not safe:
            raise GarminRawExtractionError(
                "activity_id non utilizzabile "
                "come nome file."
            )

        return safe

    @staticmethod
    def _sha256(
        path: Path,
    ) -> str:
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
                sha.update(
                    chunk
                )

        return sha.hexdigest()

    def _manifest_row(
        self,
        row: Dict[str, Any],
        status: str,
        message: str,
        output_path: Optional[
            Path
        ] = None,
        actual_size: Optional[
            int
        ] = None,
        sha256: Optional[
            str
        ] = None,
    ) -> Dict[str, Any]:
        return {
            "activity_id": row.get(
                "activity_id"
            ),
            "match_quality": row.get(
                "match_quality"
            ),
            "archive": row.get(
                "archive"
            ),
            "member_name": row.get(
                "member_name"
            ),
            "extension": row.get(
                "extension"
            ),
            "expected_size_bytes": row.get(
                "size_bytes"
            ),
            "output_path": (
                str(
                    output_path
                )
                if output_path
                else ""
            ),
            "actual_size_bytes": (
                actual_size
                if actual_size is not None
                else ""
            ),
            "sha256": sha256 or "",
            "status": status,
            "message": message,
        }

    def _write_manifest(
        self,
        path: Path,
        rows: List[
            Dict[str, Any]
        ],
    ) -> None:
        with path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as output:
            writer = csv.DictWriter(
                output,
                fieldnames=self.MANIFEST_FIELDS,
            )

            writer.writeheader()
            writer.writerows(
                rows
            )

    @staticmethod
    def _required_text(
        value: Any,
        field_name: str,
        row_number: int,
    ) -> str:
        text = str(
            value
            or ""
        ).strip()

        if not text:
            raise GarminRawExtractionError(
                f"{field_name} vuoto "
                f"alla riga {row_number}"
            )

        return text

    @staticmethod
    def _optional_integer(
        value: Any,
    ) -> Optional[int]:
        if value is None:
            return None

        text = str(
            value
        ).strip()

        if not text:
            return None

        try:
            return int(
                round(
                    float(
                        text
                    )
                )
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise GarminRawExtractionError(
                "Valore size_bytes non valido: "
                f"{value}"
            ) from exc