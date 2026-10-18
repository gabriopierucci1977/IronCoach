#!/usr/bin/env python3
"""Import one Garmin FIT file into the MAINTAIN_PLAN runtime database."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.importers.garmin_fit_importer import GarminFitImporter
from backend.importers.garmin_fit_runtime_bridge import (
    source_activity_to_runtime_payload,
)
from backend.maintain_plan.runtime_actual_session_capture import (
    RuntimeActualSessionCapture,
)


class CaptureConfig:
    maintain_plan_actual_session_enabled = True

    def __init__(self, database_path: str):
        self.maintain_plan_database_path = database_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Import one Garmin FIT file into MAINTAIN_PLAN."
    )
    parser.add_argument("fit_file")
    parser.add_argument("--athlete-source-id", required=True)
    parser.add_argument(
        "--database",
        default="data/ironcoach_maintain_plan.db",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    fit_path = Path(args.fit_file)
    importer = GarminFitImporter(str(fit_path))
    file_hash = importer.file_hash()
    activity = importer.import_activity()

    payload = source_activity_to_runtime_payload(
        activity,
        file_hash,
    )

    if args.dry_run:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print("MANUAL_FIT_DRY_RUN_COMPLETATO")
        return 0

    result = RuntimeActualSessionCapture().capture(
        runtime_config=CaptureConfig(args.database),
        athlete={"source_id": args.athlete_source_id},
        garmin_training_history=[payload],
        normalized_at=datetime.now(timezone.utc),
    )

    print("FILE_HASH =", file_hash)
    print("CREATED =", result.created)
    print("REUSED =", result.reused)
    print("UNSUPPORTED =", result.unsupported)
    print("MANUAL_FIT_IMPORT_COMPLETATO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
