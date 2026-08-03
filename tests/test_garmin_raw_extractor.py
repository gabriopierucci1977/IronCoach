"""
Test Garmin Raw File Extractor

Verifica:
- estrazione dei match EXCELLENT e GOOD;
- esclusione dei match non consentiti;
- creazione del manifest;
- gestione dei file già presenti;
- archivio mancante;
- membro ZIP mancante;
- colonne CSV mancanti;
- activity_id duplicati;
- estensioni incoerenti;
- filtro qualità personalizzato.
"""

from __future__ import annotations

import csv
import hashlib
import zipfile
from pathlib import Path

import pytest

from backend.importers.garmin_raw_extractor import (
    GarminRawExtractionError,
    GarminRawFileExtractor,
)


MATCH_FIELDS = [
    "activity_id",
    "activity_name",
    "activity_type",
    "activity_start_utc",
    "activity_duration_seconds",
    "activity_distance_meters",
    "archive",
    "member_name",
    "extension",
    "size_bytes",
    "raw_start_utc",
    "raw_duration_seconds",
    "raw_distance_meters",
    "time_difference_seconds",
    "duration_difference_percent",
    "distance_difference_percent",
    "match_score",
    "match_quality",
]


def _write_zip(
    path: Path,
    members: dict[str, bytes],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with zipfile.ZipFile(
        path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for member_name, data in members.items():
            archive.writestr(
                member_name,
                data,
            )


def _write_matches_csv(
    path: Path,
    rows: list[dict],
) -> None:
    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as output:
        writer = csv.DictWriter(
            output,
            fieldnames=MATCH_FIELDS,
        )
        writer.writeheader()
        writer.writerows(
            rows
        )


def _match_row(
    *,
    activity_id: str,
    archive: str,
    member_name: str,
    extension: str,
    size_bytes: int,
    quality: str,
) -> dict:
    return {
        "activity_id": activity_id,
        "activity_name": "",
        "activity_type": "",
        "activity_start_utc": "",
        "activity_duration_seconds": "",
        "activity_distance_meters": "",
        "archive": archive,
        "member_name": member_name,
        "extension": extension,
        "size_bytes": str(
            size_bytes
        ),
        "raw_start_utc": "",
        "raw_duration_seconds": "",
        "raw_distance_meters": "",
        "time_difference_seconds": "",
        "duration_difference_percent": "",
        "distance_difference_percent": "",
        "match_score": "0",
        "match_quality": quality,
    }


def _sha256(
    data: bytes,
) -> str:
    return hashlib.sha256(
        data
    ).hexdigest()


def test_extracts_excellent_and_good_matches(
    tmp_path: Path,
) -> None:
    export_root = (
        tmp_path
        / "export"
    )

    output_directory = (
        tmp_path
        / "extracted"
    )

    matches_csv = (
        tmp_path
        / "garmin_raw_matches.csv"
    )

    fit_data = b"fit-file-content"
    tcx_data = b"<TrainingCenterDatabase/>"
    gpx_data = b"<gpx/>"

    archive_path = (
        export_root
        / "DI_CONNECT"
        / "UploadedFiles.zip"
    )

    _write_zip(
        archive_path,
        {
            "folder/run.fit": fit_data,
            "folder/bike.tcx": tcx_data,
            "folder/review.gpx": gpx_data,
        },
    )

    _write_matches_csv(
        matches_csv,
        [
            _match_row(
                activity_id="1001",
                archive="DI_CONNECT/UploadedFiles.zip",
                member_name="folder/run.fit",
                extension=".fit",
                size_bytes=len(
                    fit_data
                ),
                quality="EXCELLENT",
            ),
            _match_row(
                activity_id="1002",
                archive="DI_CONNECT/UploadedFiles.zip",
                member_name="folder/bike.tcx",
                extension=".tcx",
                size_bytes=len(
                    tcx_data
                ),
                quality="GOOD",
            ),
            _match_row(
                activity_id="1003",
                archive="DI_CONNECT/UploadedFiles.zip",
                member_name="folder/review.gpx",
                extension=".gpx",
                size_bytes=len(
                    gpx_data
                ),
                quality="POSSIBLE",
            ),
        ],
    )

    extractor = GarminRawFileExtractor(
        export_root=str(
            export_root
        ),
        raw_matches_csv=str(
            matches_csv
        ),
        output_directory=str(
            output_directory
        ),
    )

    result = extractor.extract()

    assert result.requested == 2
    assert result.extracted == 2
    assert result.skipped_existing == 0
    assert result.skipped_quality == 1
    assert result.missing_archives == 0
    assert result.missing_members == 0
    assert result.errors == 0

    run_output = (
        output_directory
        / "1001.fit"
    )

    bike_output = (
        output_directory
        / "1002.tcx"
    )

    assert run_output.read_bytes() == fit_data
    assert bike_output.read_bytes() == tcx_data

    assert not (
        output_directory
        / "1003.gpx"
    ).exists()

    manifest_path = Path(
        result.manifest_path
    )

    assert manifest_path.exists()

    with manifest_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as source:
        rows = list(
            csv.DictReader(
                source
            )
        )

    assert len(rows) == 3

    by_id = {
        row[
            "activity_id"
        ]: row
        for row in rows
    }

    assert by_id["1001"]["status"] == "EXTRACTED"
    assert by_id["1001"]["sha256"] == _sha256(
        fit_data
    )
    assert by_id["1002"]["status"] == "EXTRACTED"
    assert by_id["1003"]["status"] == "SKIPPED_QUALITY"


def test_existing_file_with_valid_size_is_skipped(
    tmp_path: Path,
) -> None:
    export_root = (
        tmp_path
        / "export"
    )

    output_directory = (
        tmp_path
        / "extracted"
    )

    matches_csv = (
        tmp_path
        / "garmin_raw_matches.csv"
    )

    data = b"existing-fit"

    _write_zip(
        export_root
        / "archive.zip",
        {
            "activity.fit": data,
        },
    )

    _write_matches_csv(
        matches_csv,
        [
            _match_row(
                activity_id="2001",
                archive="archive.zip",
                member_name="activity.fit",
                extension=".fit",
                size_bytes=len(
                    data
                ),
                quality="EXCELLENT",
            )
        ],
    )

    output_directory.mkdir(
        parents=True,
    )

    existing_path = (
        output_directory
        / "2001.fit"
    )

    existing_path.write_bytes(
        data
    )

    result = GarminRawFileExtractor(
        export_root=str(
            export_root
        ),
        raw_matches_csv=str(
            matches_csv
        ),
        output_directory=str(
            output_directory
        ),
    ).extract()

    assert result.requested == 1
    assert result.extracted == 0
    assert result.skipped_existing == 1
    assert result.errors == 0


def test_existing_file_with_wrong_size_records_error(
    tmp_path: Path,
) -> None:
    export_root = (
        tmp_path
        / "export"
    )

    output_directory = (
        tmp_path
        / "extracted"
    )

    matches_csv = (
        tmp_path
        / "garmin_raw_matches.csv"
    )

    expected_data = b"correct-data"

    _write_zip(
        export_root
        / "archive.zip",
        {
            "activity.fit": expected_data,
        },
    )

    _write_matches_csv(
        matches_csv,
        [
            _match_row(
                activity_id="2002",
                archive="archive.zip",
                member_name="activity.fit",
                extension=".fit",
                size_bytes=len(
                    expected_data
                ),
                quality="EXCELLENT",
            )
        ],
    )

    output_directory.mkdir(
        parents=True,
    )

    (
        output_directory
        / "2002.fit"
    ).write_bytes(
        b"wrong"
    )

    result = GarminRawFileExtractor(
        export_root=str(
            export_root
        ),
        raw_matches_csv=str(
            matches_csv
        ),
        output_directory=str(
            output_directory
        ),
    ).extract()

    assert result.errors == 1
    assert result.extracted == 0


def test_missing_archive_is_reported(
    tmp_path: Path,
) -> None:
    export_root = (
        tmp_path
        / "export"
    )

    export_root.mkdir()

    matches_csv = (
        tmp_path
        / "garmin_raw_matches.csv"
    )

    _write_matches_csv(
        matches_csv,
        [
            _match_row(
                activity_id="3001",
                archive="missing.zip",
                member_name="activity.fit",
                extension=".fit",
                size_bytes=10,
                quality="EXCELLENT",
            )
        ],
    )

    result = GarminRawFileExtractor(
        export_root=str(
            export_root
        ),
        raw_matches_csv=str(
            matches_csv
        ),
        output_directory=str(
            tmp_path
            / "output"
        ),
    ).extract()

    assert result.requested == 1
    assert result.missing_archives == 1
    assert result.extracted == 0


def test_missing_member_is_reported(
    tmp_path: Path,
) -> None:
    export_root = (
        tmp_path
        / "export"
    )

    _write_zip(
        export_root
        / "archive.zip",
        {
            "other.fit": b"data",
        },
    )

    matches_csv = (
        tmp_path
        / "garmin_raw_matches.csv"
    )

    _write_matches_csv(
        matches_csv,
        [
            _match_row(
                activity_id="3002",
                archive="archive.zip",
                member_name="missing.fit",
                extension=".fit",
                size_bytes=10,
                quality="EXCELLENT",
            )
        ],
    )

    result = GarminRawFileExtractor(
        export_root=str(
            export_root
        ),
        raw_matches_csv=str(
            matches_csv
        ),
        output_directory=str(
            tmp_path
            / "output"
        ),
    ).extract()

    assert result.missing_members == 1
    assert result.extracted == 0


def test_custom_quality_filter_can_extract_possible(
    tmp_path: Path,
) -> None:
    export_root = (
        tmp_path
        / "export"
    )

    data = b"<gpx/>"

    _write_zip(
        export_root
        / "archive.zip",
        {
            "activity.gpx": data,
        },
    )

    matches_csv = (
        tmp_path
        / "garmin_raw_matches.csv"
    )

    _write_matches_csv(
        matches_csv,
        [
            _match_row(
                activity_id="4001",
                archive="archive.zip",
                member_name="activity.gpx",
                extension=".gpx",
                size_bytes=len(
                    data
                ),
                quality="POSSIBLE",
            )
        ],
    )

    result = GarminRawFileExtractor(
        export_root=str(
            export_root
        ),
        raw_matches_csv=str(
            matches_csv
        ),
        output_directory=str(
            tmp_path
            / "output"
        ),
        allowed_qualities={
            "POSSIBLE"
        },
    ).extract()

    assert result.requested == 1
    assert result.extracted == 1
    assert result.skipped_quality == 0


def test_missing_required_columns_raises_error(
    tmp_path: Path,
) -> None:
    export_root = (
        tmp_path
        / "export"
    )

    export_root.mkdir()

    matches_csv = (
        tmp_path
        / "garmin_raw_matches.csv"
    )

    matches_csv.write_text(
        "activity_id,match_quality\n"
        "5001,EXCELLENT\n",
        encoding="utf-8",
    )

    extractor = GarminRawFileExtractor(
        export_root=str(
            export_root
        ),
        raw_matches_csv=str(
            matches_csv
        ),
        output_directory=str(
            tmp_path
            / "output"
        ),
    )

    with pytest.raises(
        GarminRawExtractionError,
        match="colonne richieste",
    ):
        extractor.extract()


def test_duplicate_activity_id_raises_error(
    tmp_path: Path,
) -> None:
    export_root = (
        tmp_path
        / "export"
    )

    export_root.mkdir()

    matches_csv = (
        tmp_path
        / "garmin_raw_matches.csv"
    )

    first = _match_row(
        activity_id="5002",
        archive="archive.zip",
        member_name="activity.fit",
        extension=".fit",
        size_bytes=10,
        quality="EXCELLENT",
    )

    second = dict(
        first
    )

    _write_matches_csv(
        matches_csv,
        [
            first,
            second,
        ],
    )

    extractor = GarminRawFileExtractor(
        export_root=str(
            export_root
        ),
        raw_matches_csv=str(
            matches_csv
        ),
        output_directory=str(
            tmp_path
            / "output"
        ),
    )

    with pytest.raises(
        GarminRawExtractionError,
        match="duplicato",
    ):
        extractor.extract()


def test_incoherent_extension_raises_error(
    tmp_path: Path,
) -> None:
    export_root = (
        tmp_path
        / "export"
    )

    export_root.mkdir()

    matches_csv = (
        tmp_path
        / "garmin_raw_matches.csv"
    )

    _write_matches_csv(
        matches_csv,
        [
            _match_row(
                activity_id="5003",
                archive="archive.zip",
                member_name="activity.fit",
                extension=".tcx",
                size_bytes=10,
                quality="EXCELLENT",
            )
        ],
    )

    extractor = GarminRawFileExtractor(
        export_root=str(
            export_root
        ),
        raw_matches_csv=str(
            matches_csv
        ),
        output_directory=str(
            tmp_path
            / "output"
        ),
    )

    with pytest.raises(
        GarminRawExtractionError,
        match="Estensione incoerente",
    ):
        extractor.extract()


def test_missing_paths_raise_file_not_found(
    tmp_path: Path,
) -> None:
    extractor = GarminRawFileExtractor(
        export_root=str(
            tmp_path
            / "missing_export"
        ),
        raw_matches_csv=str(
            tmp_path
            / "missing.csv"
        ),
        output_directory=str(
            tmp_path
            / "output"
        ),
    )

    with pytest.raises(
        FileNotFoundError
    ):
        extractor.extract()