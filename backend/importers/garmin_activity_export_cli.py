"""
Garmin Merged Activity Export CLI

Esegue la fusione tra riepiloghi Garmin e file grezzi,
quindi salva un archivio persistente JSON Lines compresso.

Uso standard:

    python -m backend.importers.garmin_activity_export_cli

Output predefiniti:

    data/garmin/garmin_activities_merged.jsonl.gz
    data/garmin/garmin_activities_merged.jsonl.gz.manifest.json
    data/garmin/garmin_activity_export_report.json

Il comando non scrive nel database.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from backend.importers.garmin_activity_exporter import (
    GarminActivityExportError,
    GarminActivityExporter,
)
from backend.importers.garmin_activity_merger import (
    GarminActivityMerger,
)


DEFAULT_SUMMARY_SOURCE = Path("data/garmin")
DEFAULT_RAW_MATCHES_CSV = Path(
    "data/garmin/garmin_raw_matches.csv"
)
DEFAULT_EXTRACTED_DIRECTORY = Path(
    "data/garmin_extracted"
)
DEFAULT_OUTPUT_PATH = Path(
    "data/garmin/garmin_activities_merged.jsonl.gz"
)
DEFAULT_REPORT_PATH = Path(
    "data/garmin/garmin_activity_export_report.json"
)


class GarminActivityExportCliError(Exception):
    """
    Errore di configurazione o di esecuzione CLI.
    """


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fonde lo storico Garmin e crea un export "
            "persistente JSON Lines."
        )
    )

    parser.add_argument(
        "--summary-source",
        default=str(
            DEFAULT_SUMMARY_SOURCE
        ),
        help=(
            "File o directory contenente "
            "*_summarizedActivities.json."
        ),
    )

    parser.add_argument(
        "--raw-matches-csv",
        default=str(
            DEFAULT_RAW_MATCHES_CSV
        ),
        help=(
            "CSV prodotto dal collegamento tra attività "
            "Garmin e file grezzi."
        ),
    )

    parser.add_argument(
        "--extracted-directory",
        default=str(
            DEFAULT_EXTRACTED_DIRECTORY
        ),
        help=(
            "Directory contenente i file FIT, TCX e GPX "
            "estratti."
        ),
    )

    parser.add_argument(
        "--output",
        default=str(
            DEFAULT_OUTPUT_PATH
        ),
        help=(
            "Percorso dell'export .jsonl oppure .jsonl.gz."
        ),
    )

    parser.add_argument(
        "--manifest",
        default=None,
        help=(
            "Percorso manifest. Se omesso viene usato "
            "<output>.manifest.json."
        ),
    )

    parser.add_argument(
        "--report",
        default=str(
            DEFAULT_REPORT_PATH
        ),
        help=(
            "Percorso del report riepilogativo JSON."
        ),
    )

    parser.add_argument(
        "--include-review",
        action="store_true",
        help=(
            "Include anche i collegamenti classificati REVIEW."
        ),
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Interrompe la fusione al primo errore di parsing."
        ),
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Rigenera l'export anche se esiste già "
            "ed è valido."
        ),
    )

    parser.add_argument(
        "--incremental",
        action="store_true",
        help=(
            "Aggiorna un export esistente aggiungendo soltanto "
            "le attività Garmin non ancora archiviate."
        ),
    )

    return parser


def _validate_inputs(
    *,
    summary_source: Path,
    raw_matches_csv: Path,
    extracted_directory: Path,
) -> None:
    if not summary_source.exists():
        raise GarminActivityExportCliError(
            "Sorgente riepiloghi Garmin non trovata: "
            f"{summary_source}"
        )

    if not raw_matches_csv.is_file():
        raise GarminActivityExportCliError(
            "CSV collegamenti Garmin non trovato: "
            f"{raw_matches_csv}"
        )

    if not extracted_directory.is_dir():
        raise GarminActivityExportCliError(
            "Directory file Garmin estratti non trovata: "
            f"{extracted_directory}"
        )


def _write_json_atomic(
    path: Path,
    payload: Dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = path.with_name(
        path.name + ".tmp"
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
        path
    )


def _existing_export_report(
    *,
    exporter: GarminActivityExporter,
    report_path: Path,
) -> Dict[str, Any]:
    manifest = exporter.validate_manifest()

    report = {
        "status": "ALREADY_VALID",
        "output_path": str(
            exporter.output_path
        ),
        "manifest_path": str(
            exporter.manifest_path
        ),
        "report_path": str(
            report_path
        ),
        "activity_count": manifest.get(
            "activity_count"
        ),
        "segment_count": manifest.get(
            "segment_count"
        ),
        "byte_count": manifest.get(
            "byte_count"
        ),
        "sha256": manifest.get(
            "sha256"
        ),
        "compressed": manifest.get(
            "compressed"
        ),
        "merge_status_counts": manifest.get(
            "merge_status_counts",
            {},
        ),
        "raw_format_counts": manifest.get(
            "raw_format_counts",
            {},
        ),
        "sport_counts": manifest.get(
            "sport_counts",
            {},
        ),
    }

    _write_json_atomic(
        report_path,
        report,
    )

    return report


def _run_incremental_export(
    *,
    args: argparse.Namespace,
    exporter: GarminActivityExporter,
    summary_source: Path,
    raw_matches_csv: Path,
    extracted_directory: Path,
    report_path: Path,
) -> Dict[str, Any]:
    """
    Aggiorna l'archivio esistente senza ripetere il parsing
    delle attività già identificate tramite source_id.
    """

    print(
        "Avvio aggiornamento incrementale Garmin.",
        flush=True,
    )

    started_at = time.monotonic()

    existing_activities = exporter.load(
        validate_manifest=True
    )

    existing_source_ids = {
        str(activity.source_id).strip()
        for activity in existing_activities
        if str(activity.source_id or "").strip()
    }

    merger = GarminActivityMerger(
        summary_source=str(summary_source),
        raw_matches_csv=str(raw_matches_csv),
        extracted_directory=str(extracted_directory),
        include_review=bool(args.include_review),
        strict=bool(args.strict),
        excluded_source_ids=existing_source_ids,
    )

    merge_result = merger.merge_all()

    merge_elapsed_seconds = round(
        time.monotonic() - started_at,
        3,
    )

    export_started_at = time.monotonic()

    export_result = exporter.export_incremental(
        merge_result.activities
    )

    export_elapsed_seconds = round(
        time.monotonic() - export_started_at,
        3,
    )

    total_elapsed_seconds = round(
        time.monotonic() - started_at,
        3,
    )

    report = {
        "status": (
            "UPDATED"
            if export_result.added_count > 0
            else "ALREADY_CURRENT"
        ),
        "incremental": True,
        "existing_count": export_result.existing_count,
        "added_count": export_result.added_count,
        "skipped_existing": export_result.skipped_existing,
        "excluded_existing": merge_result.excluded_existing,
        "activity_count": export_result.activity_count,
        "segment_count": export_result.segment_count,
        "byte_count": export_result.byte_count,
        "sha256": export_result.sha256,
        "compressed": export_result.compressed,
        "output_path": export_result.output_path,
        "manifest_path": export_result.manifest_path,
        "report_path": str(report_path),
        "merge_elapsed_seconds": merge_elapsed_seconds,
        "export_elapsed_seconds": export_elapsed_seconds,
        "total_elapsed_seconds": total_elapsed_seconds,
        "merge": {
            "total": merge_result.total,
            "merged": merge_result.merged,
            "json_only": merge_result.json_only,
            "skipped_review": merge_result.skipped_review,
            "missing_raw_files": merge_result.missing_raw_files,
            "parse_errors": merge_result.parse_errors,
            "excluded_existing": merge_result.excluded_existing,
        },
        "inputs": {
            "summary_source": str(summary_source),
            "raw_matches_csv": str(raw_matches_csv),
            "extracted_directory": str(extracted_directory),
            "include_review": bool(args.include_review),
            "strict": bool(args.strict),
        },
    }

    _write_json_atomic(
        report_path,
        report,
    )

    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )

    return report


def run_export(
    args: argparse.Namespace,
) -> Dict[str, Any]:
    summary_source = Path(
        args.summary_source
    )

    raw_matches_csv = Path(
        args.raw_matches_csv
    )

    extracted_directory = Path(
        args.extracted_directory
    )

    output_path = Path(
        args.output
    )

    manifest_path = (
        Path(
            args.manifest
        )
        if args.manifest
        else None
    )

    report_path = Path(
        args.report
    )

    incremental = bool(
        getattr(
            args,
            "incremental",
            False,
        )
    )
    force = bool(
        getattr(
            args,
            "force",
            False,
        )
    )

    if incremental and force:
        raise GarminActivityExportCliError(
            "Le opzioni --incremental e --force "
            "non possono essere usate insieme."
        )

    _validate_inputs(
        summary_source=summary_source,
        raw_matches_csv=raw_matches_csv,
        extracted_directory=extracted_directory,
    )

    exporter = GarminActivityExporter(
        output_path=str(
            output_path
        ),
        manifest_path=(
            str(
                manifest_path
            )
            if manifest_path
            else None
        ),
    )

    if incremental:
        return _run_incremental_export(
            args=args,
            exporter=exporter,
            summary_source=summary_source,
            raw_matches_csv=raw_matches_csv,
            extracted_directory=extracted_directory,
            report_path=report_path,
        )

    if (
        not force
        and exporter.output_path.exists()
        and exporter.manifest_path.exists()
    ):
        print(
            "Export esistente trovato: verifica integrità...",
            flush=True,
        )

        report = _existing_export_report(
            exporter=exporter,
            report_path=report_path,
        )

        print(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            flush=True,
        )

        return report

    print(
        "Avvio fusione storico Garmin.",
        flush=True,
    )

    print(
        f"Riepiloghi: {summary_source}",
        flush=True,
    )

    print(
        f"Collegamenti raw: {raw_matches_csv}",
        flush=True,
    )

    print(
        f"File estratti: {extracted_directory}",
        flush=True,
    )

    print(
        "Il parsing completo può richiedere circa 30-40 minuti.",
        flush=True,
    )

    started_at = time.monotonic()

    merger = GarminActivityMerger(
        summary_source=str(
            summary_source
        ),
        raw_matches_csv=str(
            raw_matches_csv
        ),
        extracted_directory=str(
            extracted_directory
        ),
        include_review=bool(
            args.include_review
        ),
        strict=bool(
            args.strict
        ),
    )

    merge_result = merger.merge_all()

    merge_elapsed_seconds = round(
        time.monotonic() - started_at,
        3,
    )

    print(
        "Fusione completata. Avvio export persistente.",
        flush=True,
    )

    export_started_at = time.monotonic()

    export_result = exporter.export(
        merge_result.activities
    )

    export_elapsed_seconds = round(
        time.monotonic() - export_started_at,
        3,
    )

    total_elapsed_seconds = round(
        time.monotonic() - started_at,
        3,
    )

    report = {
        "status": "CREATED",
        "merge_elapsed_seconds": merge_elapsed_seconds,
        "export_elapsed_seconds": export_elapsed_seconds,
        "total_elapsed_seconds": total_elapsed_seconds,
        "merge": {
            "total": merge_result.total,
            "merged": merge_result.merged,
            "json_only": merge_result.json_only,
            "skipped_review": merge_result.skipped_review,
            "missing_raw_files": (
                merge_result.missing_raw_files
            ),
            "parse_errors": merge_result.parse_errors,
        },
        "export": asdict(
            export_result
        ),
        "inputs": {
            "summary_source": str(
                summary_source
            ),
            "raw_matches_csv": str(
                raw_matches_csv
            ),
            "extracted_directory": str(
                extracted_directory
            ),
            "include_review": bool(
                args.include_review
            ),
            "strict": bool(
                args.strict
            ),
        },
        "report_path": str(
            report_path
        ),
    }

    _write_json_atomic(
        report_path,
        report,
    )

    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )

    print(
        f"Export salvato in: {export_result.output_path}",
        flush=True,
    )

    print(
        f"Manifest salvato in: {export_result.manifest_path}",
        flush=True,
    )

    print(
        f"Report salvato in: {report_path}",
        flush=True,
    )

    return report


def main(
    argv: Optional[Sequence[str]] = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(
        argv
    )

    try:
        run_export(
            args
        )
    except (
        FileNotFoundError,
        GarminActivityExportError,
        GarminActivityExportCliError,
        OSError,
        ValueError,
    ) as exc:
        print(
            f"ERRORE: {exc}",
            file=sys.stderr,
            flush=True,
        )

        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )