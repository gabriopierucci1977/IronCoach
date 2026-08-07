"""
Test CLI export incrementale Garmin.

Verifica:

- opzione --incremental;
- incompatibilità con --force;
- uso dei source_id già presenti per filtrare il merger;
- chiamata a export_incremental;
- report operativo con existing, added e skipped.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import pytest

import backend.importers.garmin_activity_export_cli as cli
from backend.importers.garmin_activity_export_cli import (
    GarminActivityExportCliError,
)
from backend.models.activity import IronCoachActivity


def _activity(
    source_id: str,
) -> IronCoachActivity:
    return IronCoachActivity(
        activity_id=f"garmin:{source_id}",
        source="garmin",
        source_id=source_id,
        file_hash=f"hash-{source_id}",
        start_time="2025-01-01T08:00:00Z",
        end_time=None,
        sport="RUN",
        activity_type="running",
        duration_seconds=3600,
        distance_meters=10000.0,
        elevation_gain=None,
        elevation_loss=None,
        calories=None,
        avg_speed=None,
        max_speed=None,
        avg_hr=None,
        max_hr=None,
        avg_cadence=None,
        max_cadence=None,
        avg_power=None,
        normalized_power=None,
        training_load=None,
        training_effect=None,
        segments=[],
        metadata={},
    )


def _args(
    tmp_path: Path,
    *,
    incremental: bool = True,
    force: bool = False,
) -> argparse.Namespace:
    return argparse.Namespace(
        summary_source=str(tmp_path),
        raw_matches_csv=str(tmp_path / "matches.csv"),
        extracted_directory=str(tmp_path / "extracted"),
        output=str(tmp_path / "activities.jsonl.gz"),
        manifest=None,
        report=str(tmp_path / "report.json"),
        include_review=False,
        strict=False,
        force=force,
        incremental=incremental,
    )


def test_parser_accepts_incremental_flag() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(
        [
            "--incremental",
        ]
    )

    assert args.incremental is True


def test_incremental_and_force_are_incompatible(
    tmp_path: Path,
    monkeypatch,
) -> None:
    args = _args(
        tmp_path,
        incremental=True,
        force=True,
    )

    monkeypatch.setattr(
        cli,
        "_validate_inputs",
        lambda **kwargs: None,
    )

    with pytest.raises(
        GarminActivityExportCliError,
        match="incremental.*force",
    ):
        cli.run_export(args)


def test_incremental_uses_existing_source_ids_and_exports_only_new(
    tmp_path: Path,
    monkeypatch,
) -> None:
    args = _args(tmp_path)

    monkeypatch.setattr(
        cli,
        "_validate_inputs",
        lambda **kwargs: None,
    )

    existing = [
        _activity("1001"),
        _activity("1002"),
    ]
    merged_new = [
        _activity("1003"),
    ]

    captured: dict[str, object] = {}

    class FakeExporter:
        def __init__(
            self,
            output_path: str,
            manifest_path: str | None = None,
        ):
            self.output_path = Path(output_path)
            self.manifest_path = (
                Path(manifest_path)
                if manifest_path
                else Path(str(output_path) + ".manifest.json")
            )

        def load(
            self,
            validate_manifest: bool = True,
        ):
            assert validate_manifest is True
            return existing

        def export_incremental(
            self,
            activities,
        ):
            captured["exported"] = list(activities)

            return SimpleNamespace(
                output_path=str(self.output_path),
                manifest_path=str(self.manifest_path),
                activity_count=3,
                segment_count=0,
                byte_count=123,
                sha256="abc",
                compressed=True,
                existing_count=2,
                added_count=1,
                skipped_existing=0,
            )

    class FakeMerger:
        def __init__(
            self,
            *,
            summary_source: str,
            raw_matches_csv: str,
            extracted_directory: str,
            include_review: bool,
            strict: bool,
            excluded_source_ids,
        ):
            captured["excluded_source_ids"] = set(
                excluded_source_ids
            )

        def merge_all(self):
            return SimpleNamespace(
                activities=merged_new,
                total=1,
                merged=1,
                json_only=0,
                skipped_review=0,
                missing_raw_files=0,
                parse_errors=0,
                excluded_existing=2,
            )

    monkeypatch.setattr(
        cli,
        "GarminActivityExporter",
        FakeExporter,
    )
    monkeypatch.setattr(
        cli,
        "GarminActivityMerger",
        FakeMerger,
    )

    report = cli.run_export(args)

    assert captured["excluded_source_ids"] == {
        "1001",
        "1002",
    }
    assert captured["exported"] == merged_new

    assert report["status"] == "UPDATED"
    assert report["incremental"] is True
    assert report["existing_count"] == 2
    assert report["added_count"] == 1
    assert report["skipped_existing"] == 0
    assert report["excluded_existing"] == 2


def test_incremental_requires_existing_valid_archive(
    tmp_path: Path,
    monkeypatch,
) -> None:
    args = _args(tmp_path)

    monkeypatch.setattr(
        cli,
        "_validate_inputs",
        lambda **kwargs: None,
    )

    class FakeExporter:
        def __init__(
            self,
            output_path: str,
            manifest_path: str | None = None,
        ):
            self.output_path = Path(output_path)
            self.manifest_path = Path(
                str(output_path) + ".manifest.json"
            )

        def load(
            self,
            validate_manifest: bool = True,
        ):
            raise FileNotFoundError("missing archive")

    monkeypatch.setattr(
        cli,
        "GarminActivityExporter",
        FakeExporter,
    )

    with pytest.raises(FileNotFoundError):
        cli.run_export(args)
