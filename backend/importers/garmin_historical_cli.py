"""
Garmin Historical Import CLI

Coordina da terminale:
- lettura dei summarizedActivities JSON;
- lettura del CSV garmin_raw_matches.csv;
- classificazione SAFE / REVIEW / JSON_ONLY;
- dry-run con report finale;
- estrazione controllata opzionale dei file FIT/TCX/GPX sicuri.

Non scrive nel database.

Esempi:

Dry-run:
    python -m backend.importers.garmin_historical_cli \
        --summary-source data/garmin/DI_CONNECT/DI-Connect-Fitness \
        --matches-csv data/garmin/garmin_raw_matches.csv

Dry-run con report JSON:
    python -m backend.importers.garmin_historical_cli \
        --summary-source data/garmin/DI_CONNECT/DI-Connect-Fitness \
        --matches-csv data/garmin/garmin_raw_matches.csv \
        --report-json data/garmin/garmin_historical_report.json

Estrazione dei soli match EXCELLENT e GOOD:
    python -m backend.importers.garmin_historical_cli \
        --summary-source data/garmin/DI_CONNECT/DI-Connect-Fitness \
        --matches-csv data/garmin/garmin_raw_matches.csv \
        --export-root data/garmin \
        --extract-to data/garmin_extracted \
        --execute
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from backend.importers.garmin_historical_importer import (
    GarminHistoricalImportError,
    GarminHistoricalImporter,
)
from backend.importers.garmin_raw_extractor import (
    GarminRawExtractionError,
    GarminRawExtractionResult,
    GarminRawFileExtractor,
)
from backend.models.activity import IronCoachActivity


EXIT_SUCCESS = 0
EXIT_CONFIGURATION_ERROR = 2
EXIT_EXECUTION_ERROR = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="garmin-historical-import",
        description=(
            "Analizza lo storico Garmin e, opzionalmente, "
            "estrae i file grezzi sicuri senza scrivere nel database."
        ),
    )

    parser.add_argument(
        "--summary-source",
        required=True,
        help=(
            "File summarizedActivities JSON oppure cartella "
            "che contiene i file *_summarizedActivities.json."
        ),
    )

    parser.add_argument(
        "--matches-csv",
        required=True,
        help="Percorso del file garmin_raw_matches.csv.",
    )

    parser.add_argument(
        "--report-json",
        help=(
            "Percorso opzionale in cui scrivere "
            "il report completo in formato JSON."
        ),
    )

    parser.add_argument(
        "--export-root",
        help=(
            "Radice dell'export Garmin. "
            "Obbligatoria quando si usa --execute."
        ),
    )

    parser.add_argument(
        "--extract-to",
        help=(
            "Cartella di destinazione dei file FIT/TCX/GPX. "
            "Obbligatoria quando si usa --execute."
        ),
    )

    parser.add_argument(
        "--include-review",
        action="store_true",
        help=(
            "Include anche i match POSSIBLE e WEAK "
            "nell'estrazione. Per impostazione predefinita "
            "estrae solo EXCELLENT e GOOD."
        ),
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Esegue realmente l'estrazione. "
            "Senza questa opzione il comando resta in dry-run."
        ),
    )

    return parser


def activity_status(
    activity: IronCoachActivity,
) -> str:
    return GarminHistoricalImporter.import_status(
        activity
    )


def build_report(
    activities: Sequence[IronCoachActivity],
    extraction_result: Optional[
        GarminRawExtractionResult
    ] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    status_counts = Counter(
        activity_status(activity)
        for activity in activities
    )

    sport_counts = Counter(
        activity.sport or "UNKNOWN"
        for activity in activities
    )

    activity_type_counts = Counter(
        activity.activity_type or "UNKNOWN"
        for activity in activities
    )

    years = Counter()

    for activity in activities:
        start_time = activity.start_time or ""

        if len(start_time) >= 4:
            year = start_time[:4]

            if year.isdigit():
                years[year] += 1

    report: Dict[str, Any] = {
        "mode": (
            "DRY_RUN"
            if dry_run
            else "EXECUTE"
        ),
        "activities_total": len(
            activities
        ),
        "status_counts": {
            "SAFE": status_counts.get(
                "SAFE",
                0,
            ),
            "REVIEW": status_counts.get(
                "REVIEW",
                0,
            ),
            "JSON_ONLY": status_counts.get(
                "JSON_ONLY",
                0,
            ),
        },
        "sport_counts": dict(
            sorted(
                sport_counts.items()
            )
        ),
        "activity_type_counts": dict(
            sorted(
                activity_type_counts.items()
            )
        ),
        "year_counts": dict(
            sorted(
                years.items()
            )
        ),
        "extraction": (
            asdict(
                extraction_result
            )
            if extraction_result
            else None
        ),
    }

    return report


def print_report(
    report: Dict[str, Any],
) -> None:
    status_counts = report[
        "status_counts"
    ]

    print(
        "IRONCOACH GARMIN HISTORICAL IMPORT"
    )
    print("=" * 72)
    print(
        f"Modalità: {report['mode']}"
    )
    print(
        f"Attività totali: "
        f"{report['activities_total']}"
    )
    print()
    print("STATI")
    print("-" * 72)
    print(
        f"SAFE: "
        f"{status_counts['SAFE']}"
    )
    print(
        f"REVIEW: "
        f"{status_counts['REVIEW']}"
    )
    print(
        f"JSON_ONLY: "
        f"{status_counts['JSON_ONLY']}"
    )
    print()
    print("SPORT")
    print("-" * 72)

    for sport, count in report[
        "sport_counts"
    ].items():
        print(
            f"{sport}: {count}"
        )

    print()
    print("ANNI")
    print("-" * 72)

    for year, count in report[
        "year_counts"
    ].items():
        print(
            f"{year}: {count}"
        )

    extraction = report.get(
        "extraction"
    )

    if extraction is not None:
        print()
        print("ESTRAZIONE")
        print("-" * 72)

        for key in (
            "requested",
            "extracted",
            "skipped_existing",
            "skipped_quality",
            "missing_archives",
            "missing_members",
            "errors",
            "manifest_path",
        ):
            print(
                f"{key}: "
                f"{extraction[key]}"
            )

    print()
    print("=" * 72)


def write_json_report(
    path: Path,
    report: Dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def extraction_qualities(
    include_review: bool,
) -> Iterable[str]:
    qualities = {
        "EXCELLENT",
        "GOOD",
    }

    if include_review:
        qualities.update(
            {
                "POSSIBLE",
                "WEAK",
            }
        )

    return qualities


def validate_execution_arguments(
    args: argparse.Namespace,
) -> None:
    if not args.execute:
        return

    missing: List[str] = []

    if not args.export_root:
        missing.append(
            "--export-root"
        )

    if not args.extract_to:
        missing.append(
            "--extract-to"
        )

    if missing:
        raise ValueError(
            "Con --execute sono obbligatorie: "
            + ", ".join(
                missing
            )
        )


def run(
    argv: Optional[
        Sequence[str]
    ] = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(
        argv
    )

    try:
        validate_execution_arguments(
            args
        )

        importer = GarminHistoricalImporter(
            summary_source=args.summary_source,
            raw_matches_csv=args.matches_csv,
        )

        activities = (
            importer.import_activities()
        )

        extraction_result = None

        if args.execute:
            extractor = GarminRawFileExtractor(
                export_root=args.export_root,
                raw_matches_csv=args.matches_csv,
                output_directory=args.extract_to,
                allowed_qualities=extraction_qualities(
                    args.include_review
                ),
            )

            extraction_result = (
                extractor.extract()
            )

        report = build_report(
            activities=activities,
            extraction_result=extraction_result,
            dry_run=not args.execute,
        )

        print_report(
            report
        )

        if args.report_json:
            report_path = Path(
                args.report_json
            )

            write_json_report(
                report_path,
                report,
            )

            print(
                "Report JSON: "
                f"{report_path}"
            )

        if (
            extraction_result is not None
            and (
                extraction_result.errors > 0
                or extraction_result.missing_archives > 0
                or extraction_result.missing_members > 0
            )
        ):
            return EXIT_EXECUTION_ERROR

        return EXIT_SUCCESS

    except (
        FileNotFoundError,
        ValueError,
        GarminHistoricalImportError,
        GarminRawExtractionError,
    ) as exc:
        print(
            f"ERRORE: {exc}",
            file=sys.stderr,
        )

        return EXIT_CONFIGURATION_ERROR


def main() -> None:
    raise SystemExit(
        run()
    )


if __name__ == "__main__":
    main()