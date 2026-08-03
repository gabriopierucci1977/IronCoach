"""
Test Garmin Historical Import CLI

Verifica:
- costruzione del report;
- conteggi per stato, sport, tipo e anno;
- scrittura del report JSON;
- dry-run senza estrazione;
- esecuzione con estrazione;
- qualità predefinite e REVIEW;
- validazione degli argomenti;
- codici di uscita per errori di configurazione;
- codice di uscita per estrazioni incomplete.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.importers import garmin_historical_cli
from backend.importers.garmin_historical_cli import (
    EXIT_CONFIGURATION_ERROR,
    EXIT_EXECUTION_ERROR,
    EXIT_SUCCESS,
    build_report,
    extraction_qualities,
    run,
    validate_execution_arguments,
    write_json_report,
)
from backend.importers.garmin_raw_extractor import (
    GarminRawExtractionResult,
)


def _activity(
    *,
    sport: str,
    activity_type: str,
    start_time: str,
    status: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        sport=sport,
        activity_type=activity_type,
        start_time=start_time,
        metadata={
            "garmin_historical": {
                "import_status": status,
            }
        },
    )


def test_build_report_counts_status_sport_type_and_year(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    activities = [
        _activity(
            sport="RUN",
            activity_type="RUNNING",
            start_time="2024-01-02T10:00:00Z",
            status="SAFE",
        ),
        _activity(
            sport="RUN",
            activity_type="TRAIL_RUNNING",
            start_time="2024-03-04T10:00:00Z",
            status="REVIEW",
        ),
        _activity(
            sport="BIKE",
            activity_type="CYCLING",
            start_time="2025-05-06T10:00:00Z",
            status="JSON_ONLY",
        ),
    ]

    monkeypatch.setattr(
        garmin_historical_cli,
        "activity_status",
        lambda activity: activity.metadata[
            "garmin_historical"
        ][
            "import_status"
        ],
    )

    report = build_report(
        activities=activities,
        dry_run=True,
    )

    assert report["mode"] == "DRY_RUN"
    assert report["activities_total"] == 3

    assert report["status_counts"] == {
        "SAFE": 1,
        "REVIEW": 1,
        "JSON_ONLY": 1,
    }

    assert report["sport_counts"] == {
        "BIKE": 1,
        "RUN": 2,
    }

    assert report["activity_type_counts"] == {
        "CYCLING": 1,
        "RUNNING": 1,
        "TRAIL_RUNNING": 1,
    }

    assert report["year_counts"] == {
        "2024": 2,
        "2025": 1,
    }

    assert report["extraction"] is None


def test_build_report_includes_extraction_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    activity = _activity(
        sport="SWIM",
        activity_type="POOL_SWIM",
        start_time="2023-01-01T00:00:00Z",
        status="SAFE",
    )

    monkeypatch.setattr(
        garmin_historical_cli,
        "activity_status",
        lambda item: item.metadata[
            "garmin_historical"
        ][
            "import_status"
        ],
    )

    extraction_result = GarminRawExtractionResult(
        requested=1,
        extracted=1,
        skipped_existing=0,
        skipped_quality=0,
        missing_archives=0,
        missing_members=0,
        errors=0,
        manifest_path="manifest.csv",
    )

    report = build_report(
        activities=[
            activity
        ],
        extraction_result=extraction_result,
        dry_run=False,
    )

    assert report["mode"] == "EXECUTE"
    assert report["extraction"] == {
        "requested": 1,
        "extracted": 1,
        "skipped_existing": 0,
        "skipped_quality": 0,
        "missing_archives": 0,
        "missing_members": 0,
        "errors": 0,
        "manifest_path": "manifest.csv",
    }


def test_write_json_report_creates_parent_directories(
    tmp_path: Path,
) -> None:
    report_path = (
        tmp_path
        / "nested"
        / "report.json"
    )

    report = {
        "mode": "DRY_RUN",
        "activities_total": 3,
    }

    write_json_report(
        report_path,
        report,
    )

    assert report_path.exists()

    loaded = json.loads(
        report_path.read_text(
            encoding="utf-8"
        )
    )

    assert loaded == report


def test_extraction_qualities_default_and_review() -> None:
    assert set(
        extraction_qualities(
            False
        )
    ) == {
        "EXCELLENT",
        "GOOD",
    }

    assert set(
        extraction_qualities(
            True
        )
    ) == {
        "EXCELLENT",
        "GOOD",
        "POSSIBLE",
        "WEAK",
    }


def test_validate_execution_arguments_requires_paths() -> None:
    args = SimpleNamespace(
        execute=True,
        export_root=None,
        extract_to=None,
    )

    with pytest.raises(
        ValueError,
        match="--export-root",
    ):
        validate_execution_arguments(
            args
        )


def test_run_dry_run_does_not_extract(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    activities = [
        _activity(
            sport="RUN",
            activity_type="RUNNING",
            start_time="2025-01-01T10:00:00Z",
            status="SAFE",
        )
    ]

    class FakeImporter:
        def __init__(
            self,
            summary_source: str,
            raw_matches_csv: str,
        ):
            assert summary_source == "summary"
            assert raw_matches_csv == "matches.csv"

        def import_activities(
            self,
        ) -> list[SimpleNamespace]:
            return activities

        @staticmethod
        def import_status(
            activity: SimpleNamespace,
        ) -> str:
            return activity.metadata[
                "garmin_historical"
            ][
                "import_status"
            ]

    class FailingExtractor:
        def __init__(
            self,
            *args: object,
            **kwargs: object,
        ):
            raise AssertionError(
                "L'estrattore non deve essere creato in dry-run."
            )

    monkeypatch.setattr(
        garmin_historical_cli,
        "GarminHistoricalImporter",
        FakeImporter,
    )

    monkeypatch.setattr(
        garmin_historical_cli,
        "GarminRawFileExtractor",
        FailingExtractor,
    )

    result = run(
        [
            "--summary-source",
            "summary",
            "--matches-csv",
            "matches.csv",
        ]
    )

    output = capsys.readouterr()

    assert result == EXIT_SUCCESS
    assert "Modalità: DRY_RUN" in output.out
    assert "Attività totali: 1" in output.out
    assert "SAFE: 1" in output.out


def test_run_execute_extracts_and_writes_report(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report_path = (
        tmp_path
        / "report.json"
    )

    activities = [
        _activity(
            sport="BIKE",
            activity_type="CYCLING",
            start_time="2026-02-03T10:00:00Z",
            status="SAFE",
        )
    ]

    class FakeImporter:
        def __init__(
            self,
            summary_source: str,
            raw_matches_csv: str,
        ):
            assert summary_source == "summary"
            assert raw_matches_csv == "matches.csv"

        def import_activities(
            self,
        ) -> list[SimpleNamespace]:
            return activities

        @staticmethod
        def import_status(
            activity: SimpleNamespace,
        ) -> str:
            return activity.metadata[
                "garmin_historical"
            ][
                "import_status"
            ]

    class FakeExtractor:
        def __init__(
            self,
            export_root: str,
            raw_matches_csv: str,
            output_directory: str,
            allowed_qualities: set[str],
        ):
            assert export_root == "export"
            assert raw_matches_csv == "matches.csv"
            assert output_directory == "output"
            assert set(
                allowed_qualities
            ) == {
                "EXCELLENT",
                "GOOD",
            }

        def extract(
            self,
        ) -> GarminRawExtractionResult:
            return GarminRawExtractionResult(
                requested=1,
                extracted=1,
                skipped_existing=0,
                skipped_quality=0,
                missing_archives=0,
                missing_members=0,
                errors=0,
                manifest_path="output/manifest.csv",
            )

    monkeypatch.setattr(
        garmin_historical_cli,
        "GarminHistoricalImporter",
        FakeImporter,
    )

    monkeypatch.setattr(
        garmin_historical_cli,
        "GarminRawFileExtractor",
        FakeExtractor,
    )

    result = run(
        [
            "--summary-source",
            "summary",
            "--matches-csv",
            "matches.csv",
            "--export-root",
            "export",
            "--extract-to",
            "output",
            "--report-json",
            str(
                report_path
            ),
            "--execute",
        ]
    )

    output = capsys.readouterr()

    assert result == EXIT_SUCCESS
    assert "Modalità: EXECUTE" in output.out
    assert "extracted: 1" in output.out
    assert report_path.exists()

    report = json.loads(
        report_path.read_text(
            encoding="utf-8"
        )
    )

    assert report["mode"] == "EXECUTE"
    assert report["extraction"]["extracted"] == 1


def test_run_execute_without_required_paths_returns_configuration_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = run(
        [
            "--summary-source",
            "summary",
            "--matches-csv",
            "matches.csv",
            "--execute",
        ]
    )

    output = capsys.readouterr()

    assert result == EXIT_CONFIGURATION_ERROR
    assert "--export-root" in output.err
    assert "--extract-to" in output.err


def test_run_returns_execution_error_for_incomplete_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeImporter:
        def __init__(
            self,
            summary_source: str,
            raw_matches_csv: str,
        ):
            pass

        def import_activities(
            self,
        ) -> list[SimpleNamespace]:
            return []

        @staticmethod
        def import_status(
            activity: SimpleNamespace,
        ) -> str:
            return "SAFE"

    class FakeExtractor:
        def __init__(
            self,
            *args: object,
            **kwargs: object,
        ):
            pass

        def extract(
            self,
        ) -> GarminRawExtractionResult:
            return GarminRawExtractionResult(
                requested=1,
                extracted=0,
                skipped_existing=0,
                skipped_quality=0,
                missing_archives=1,
                missing_members=0,
                errors=0,
                manifest_path="manifest.csv",
            )

    monkeypatch.setattr(
        garmin_historical_cli,
        "GarminHistoricalImporter",
        FakeImporter,
    )

    monkeypatch.setattr(
        garmin_historical_cli,
        "GarminRawFileExtractor",
        FakeExtractor,
    )

    result = run(
        [
            "--summary-source",
            "summary",
            "--matches-csv",
            "matches.csv",
            "--export-root",
            "export",
            "--extract-to",
            "output",
            "--execute",
        ]
    )

    assert result == EXIT_EXECUTION_ERROR


def test_run_file_not_found_returns_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class MissingImporter:
        def __init__(
            self,
            summary_source: str,
            raw_matches_csv: str,
        ):
            pass

        def import_activities(
            self,
        ) -> list[SimpleNamespace]:
            raise FileNotFoundError(
                "summary missing"
            )

    monkeypatch.setattr(
        garmin_historical_cli,
        "GarminHistoricalImporter",
        MissingImporter,
    )

    result = run(
        [
            "--summary-source",
            "missing",
            "--matches-csv",
            "missing.csv",
        ]
    )

    output = capsys.readouterr()

    assert result == EXIT_CONFIGURATION_ERROR
    assert "summary missing" in output.err