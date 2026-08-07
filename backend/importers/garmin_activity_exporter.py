"""
Garmin Activity Exporter

Serializza in JSON Lines le attività Garmin fuse,
così il parsing dei file FIT/TCX/GPX non deve essere
ripetuto a ogni utilizzo.

Caratteristiche:
- una attività per riga;
- serializzazione completa dei segmenti;
- scrittura atomica;
- SHA-256 del file esportato;
- manifest JSON con conteggi e metadati;
- lettura e validazione dell'export;
- supporto opzionale gzip;
- nessuna scrittura nel database.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
from collections import Counter
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, TextIO

from backend.models.activity import IronCoachActivity
from backend.models.activity_segment import IronCoachActivitySegment


class GarminActivityExportError(Exception):
    """Errore durante esportazione o lettura delle attività Garmin fuse."""


@dataclass(frozen=True)
class GarminActivityExportResult:
    """Riepilogo dell'esportazione JSON Lines."""

    output_path: str
    manifest_path: str
    activity_count: int
    segment_count: int
    byte_count: int
    sha256: str
    compressed: bool


@dataclass(frozen=True)
class GarminActivityIncrementalExportResult:
    """Riepilogo dell'aggiornamento incrementale."""

    output_path: str
    manifest_path: str
    activity_count: int
    segment_count: int
    byte_count: int
    sha256: str
    compressed: bool
    existing_count: int
    added_count: int
    skipped_existing: int


class GarminActivityExporter:
    """Esporta e ricarica IronCoachActivity in formato JSON Lines."""

    FORMAT_NAME = "ironcoach-garmin-activities-jsonl"
    FORMAT_VERSION = 1

    def __init__(
        self,
        output_path: str,
        manifest_path: Optional[str] = None,
    ):
        self.output_path = Path(output_path)
        self.manifest_path = (
            Path(manifest_path)
            if manifest_path
            else self._default_manifest_path(self.output_path)
        )

    def export(
        self,
        activities: Iterable[IronCoachActivity],
    ) -> GarminActivityExportResult:
        """Scrive tutte le attività in modo atomico."""

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

        temporary_output = self._temporary_path(self.output_path)
        temporary_manifest = self._temporary_path(self.manifest_path)

        activity_count = 0
        segment_count = 0
        seen_activity_ids = set()
        seen_source_ids = set()
        status_counts: Counter[str] = Counter()
        sport_counts: Counter[str] = Counter()
        raw_format_counts: Counter[str] = Counter()

        try:
            with self._open_text_writer(temporary_output) as output:
                for activity in activities:
                    self._validate_activity(
                        activity=activity,
                        seen_activity_ids=seen_activity_ids,
                        seen_source_ids=seen_source_ids,
                    )

                    payload = self.activity_to_dict(activity)

                    output.write(
                        json.dumps(
                            payload,
                            ensure_ascii=False,
                            separators=(",", ":"),
                            sort_keys=True,
                            allow_nan=False,
                        )
                    )
                    output.write("\n")

                    activity_count += 1
                    segment_count += len(activity.segments or [])
                    sport_counts[activity.sport or "UNKNOWN"] += 1

                    merge_metadata = activity.metadata.get("garmin_merge", {})
                    merge_status = str(
                        merge_metadata.get("merge_status") or "UNKNOWN"
                    )
                    status_counts[merge_status] += 1

                    raw_format = merge_metadata.get("raw_format")
                    if raw_format:
                        raw_format_counts[str(raw_format)] += 1

            if activity_count == 0:
                raise GarminActivityExportError(
                    "Nessuna attività da esportare."
                )

            temporary_output.replace(self.output_path)

            byte_count = self.output_path.stat().st_size
            file_hash = self._sha256(self.output_path)

            manifest = {
                "format": self.FORMAT_NAME,
                "format_version": self.FORMAT_VERSION,
                "created_at": self._utc_now(),
                "output_file": self.output_path.name,
                "compressed": self._is_gzip_path(self.output_path),
                "activity_count": activity_count,
                "segment_count": segment_count,
                "byte_count": byte_count,
                "sha256": file_hash,
                "merge_status_counts": dict(sorted(status_counts.items())),
                "sport_counts": dict(sorted(sport_counts.items())),
                "raw_format_counts": dict(sorted(raw_format_counts.items())),
            }

            temporary_manifest.write_text(
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                )
                + "\n",
                encoding="utf-8",
            )
            temporary_manifest.replace(self.manifest_path)

            return GarminActivityExportResult(
                output_path=str(self.output_path),
                manifest_path=str(self.manifest_path),
                activity_count=activity_count,
                segment_count=segment_count,
                byte_count=byte_count,
                sha256=file_hash,
                compressed=self._is_gzip_path(self.output_path),
            )

        except (
            OSError,
            TypeError,
            ValueError,
            GarminActivityExportError,
        ):
            temporary_output.unlink(missing_ok=True)
            temporary_manifest.unlink(missing_ok=True)
            raise

    def export_incremental(
        self,
        activities: Iterable[IronCoachActivity],
    ) -> GarminActivityIncrementalExportResult:
        """
        Aggiunge attività nuove a un export esistente validato.

        Le attività con la stessa coppia activity_id/source_id già presente
        vengono ignorate. I conflitti di identità interrompono l'operazione
        senza riscrivere archivio o manifest.
        """

        existing = self.load(validate_manifest=True)
        existing_by_activity_id = {
            str(activity.activity_id).strip(): activity
            for activity in existing
        }
        existing_by_source_id = {
            str(activity.source_id).strip(): activity
            for activity in existing
        }

        pending: List[IronCoachActivity] = []
        pending_by_activity_id: Dict[str, IronCoachActivity] = {}
        pending_by_source_id: Dict[str, IronCoachActivity] = {}
        skipped_existing = 0

        for activity in activities:
            self._validate_incremental_activity(activity)

            activity_id = str(activity.activity_id).strip()
            source_id = str(activity.source_id).strip()

            existing_activity = existing_by_activity_id.get(activity_id)
            existing_source = existing_by_source_id.get(source_id)

            if existing_activity is not None:
                if str(existing_activity.source_id).strip() != source_id:
                    raise GarminActivityExportError(
                        "activity_id in conflitto con un source_id diverso: "
                        f"{activity_id}"
                    )

                skipped_existing += 1
                continue

            if existing_source is not None:
                if str(existing_source.activity_id).strip() != activity_id:
                    raise GarminActivityExportError(
                        "source_id in conflitto con un activity_id diverso: "
                        f"{source_id}"
                    )

                skipped_existing += 1
                continue

            pending_activity = pending_by_activity_id.get(activity_id)
            if pending_activity is not None:
                if str(pending_activity.source_id).strip() != source_id:
                    raise GarminActivityExportError(
                        "activity_id in conflitto tra le nuove attività: "
                        f"{activity_id}"
                    )

                skipped_existing += 1
                continue

            pending_source = pending_by_source_id.get(source_id)
            if pending_source is not None:
                if str(pending_source.activity_id).strip() != activity_id:
                    raise GarminActivityExportError(
                        "source_id in conflitto tra le nuove attività: "
                        f"{source_id}"
                    )

                skipped_existing += 1
                continue

            pending.append(activity)
            pending_by_activity_id[activity_id] = activity
            pending_by_source_id[source_id] = activity

        if not pending:
            manifest = self.validate_manifest()

            return GarminActivityIncrementalExportResult(
                output_path=str(self.output_path),
                manifest_path=str(self.manifest_path),
                activity_count=int(manifest["activity_count"]),
                segment_count=int(manifest["segment_count"]),
                byte_count=int(manifest["byte_count"]),
                sha256=str(manifest["sha256"]),
                compressed=bool(manifest["compressed"]),
                existing_count=len(existing),
                added_count=0,
                skipped_existing=skipped_existing,
            )

        combined = existing + pending
        combined.sort(key=self._activity_sort_key)

        export_result = self.export(combined)

        return GarminActivityIncrementalExportResult(
            output_path=export_result.output_path,
            manifest_path=export_result.manifest_path,
            activity_count=export_result.activity_count,
            segment_count=export_result.segment_count,
            byte_count=export_result.byte_count,
            sha256=export_result.sha256,
            compressed=export_result.compressed,
            existing_count=len(existing),
            added_count=len(pending),
            skipped_existing=skipped_existing,
        )

    def load(
        self,
        validate_manifest: bool = True,
    ) -> List[IronCoachActivity]:
        """Carica l'intero export in memoria."""

        return list(
            self.iter_activities(
                validate_manifest=validate_manifest
            )
        )

    def iter_activities(
        self,
        validate_manifest: bool = True,
    ) -> Iterator[IronCoachActivity]:
        """Legge le attività una alla volta."""

        if not self.output_path.exists():
            raise FileNotFoundError(
                "Garmin merged export not found: "
                f"{self.output_path}"
            )

        if validate_manifest:
            self.validate_manifest()

        seen_activity_ids = set()
        seen_source_ids = set()

        try:
            with self._open_text_reader(self.output_path) as source:
                for line_number, line in enumerate(source, start=1):
                    text = line.strip()
                    if not text:
                        continue

                    try:
                        payload = json.loads(text)
                    except json.JSONDecodeError as exc:
                        raise GarminActivityExportError(
                            "JSON Lines non valido "
                            f"alla riga {line_number}."
                        ) from exc

                    activity = self.activity_from_dict(payload)
                    self._validate_activity(
                        activity=activity,
                        seen_activity_ids=seen_activity_ids,
                        seen_source_ids=seen_source_ids,
                    )
                    yield activity

        except OSError as exc:
            raise GarminActivityExportError(
                "Impossibile leggere l'export Garmin: "
                f"{self.output_path}"
            ) from exc

    def validate_manifest(self) -> Dict[str, Any]:
        """Verifica formato, dimensione e SHA-256."""

        if not self.output_path.exists():
            raise FileNotFoundError(
                "Garmin merged export not found: "
                f"{self.output_path}"
            )

        if not self.manifest_path.exists():
            raise FileNotFoundError(
                "Garmin merged export manifest not found: "
                f"{self.manifest_path}"
            )

        try:
            manifest = json.loads(
                self.manifest_path.read_text(encoding="utf-8")
            )
        except OSError as exc:
            raise GarminActivityExportError(
                "Impossibile leggere il manifest Garmin: "
                f"{self.manifest_path}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise GarminActivityExportError(
                "Manifest Garmin non valido: "
                f"{self.manifest_path}"
            ) from exc

        if not isinstance(manifest, dict):
            raise GarminActivityExportError(
                "Il manifest Garmin deve essere un oggetto JSON."
            )

        if manifest.get("format") != self.FORMAT_NAME:
            raise GarminActivityExportError(
                "Formato manifest Garmin non supportato."
            )

        if manifest.get("format_version") != self.FORMAT_VERSION:
            raise GarminActivityExportError(
                "Versione manifest Garmin non supportata: "
                f"{manifest.get('format_version')}"
            )

        expected_size = manifest.get("byte_count")
        actual_size = self.output_path.stat().st_size

        if expected_size != actual_size:
            raise GarminActivityExportError(
                "Dimensione export Garmin non valida: "
                f"{actual_size} != {expected_size}"
            )

        expected_hash = manifest.get("sha256")
        actual_hash = self._sha256(self.output_path)

        if expected_hash != actual_hash:
            raise GarminActivityExportError(
                "SHA-256 export Garmin non valido."
            )

        return manifest

    @staticmethod
    def activity_to_dict(
        activity: IronCoachActivity,
    ) -> Dict[str, Any]:
        """Converte attività e segmenti in tipi JSON."""

        if not isinstance(activity, IronCoachActivity):
            raise GarminActivityExportError(
                "Oggetto non compatibile con IronCoachActivity."
            )

        payload = asdict(activity)
        GarminActivityExporter._validate_json_value(payload)
        return payload

    @staticmethod
    def activity_from_dict(
        payload: Dict[str, Any],
    ) -> IronCoachActivity:
        """Ricostruisce IronCoachActivity da un record JSON."""

        if not isinstance(payload, dict):
            raise GarminActivityExportError(
                "Record attività Garmin non valido."
            )

        activity_field_names = {
            field.name for field in fields(IronCoachActivity)
        }
        unknown_fields = set(payload) - activity_field_names

        if unknown_fields:
            raise GarminActivityExportError(
                "Campi attività non supportati: "
                + ", ".join(sorted(unknown_fields))
            )

        activity_data = dict(payload)
        raw_segments = activity_data.get("segments")

        if raw_segments is None:
            raw_segments = []

        if not isinstance(raw_segments, list):
            raise GarminActivityExportError(
                "Il campo segments deve essere una lista."
            )

        activity_data["segments"] = [
            GarminActivityExporter.segment_from_dict(segment)
            for segment in raw_segments
        ]

        metadata = activity_data.get("metadata")
        if metadata is None:
            activity_data["metadata"] = {}
        elif not isinstance(metadata, dict):
            raise GarminActivityExportError(
                "Il campo metadata deve essere un oggetto."
            )

        try:
            return IronCoachActivity(**activity_data)
        except TypeError as exc:
            raise GarminActivityExportError(
                "Record IronCoachActivity incompleto o non valido."
            ) from exc

    @staticmethod
    def segment_from_dict(
        payload: Dict[str, Any],
    ) -> IronCoachActivitySegment:
        """Ricostruisce un segmento da un record JSON."""

        if not isinstance(payload, dict):
            raise GarminActivityExportError(
                "Record segmento Garmin non valido."
            )

        segment_field_names = {
            field.name for field in fields(IronCoachActivitySegment)
        }
        unknown_fields = set(payload) - segment_field_names

        if unknown_fields:
            raise GarminActivityExportError(
                "Campi segmento non supportati: "
                + ", ".join(sorted(unknown_fields))
            )

        segment_data = dict(payload)
        metadata = segment_data.get("metadata")

        if metadata is None:
            segment_data["metadata"] = {}
        elif not isinstance(metadata, dict):
            raise GarminActivityExportError(
                "Il metadata del segmento deve essere un oggetto."
            )

        try:
            return IronCoachActivitySegment(**segment_data)
        except TypeError as exc:
            raise GarminActivityExportError(
                "Record IronCoachActivitySegment incompleto o non valido."
            ) from exc

    @staticmethod
    def _validate_incremental_activity(
        activity: IronCoachActivity,
    ) -> None:
        GarminActivityExporter._validate_activity(
            activity=activity,
            seen_activity_ids=set(),
            seen_source_ids=set(),
        )

    @staticmethod
    def _activity_sort_key(
        activity: IronCoachActivity,
    ) -> tuple:
        start_time = str(activity.start_time or "").strip()

        if start_time.endswith("Z"):
            start_time = start_time[:-1] + "+00:00"

        try:
            parsed = datetime.fromisoformat(start_time)
        except ValueError:
            parsed = datetime.min.replace(tzinfo=timezone.utc)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.astimezone(timezone.utc)

        return (
            parsed,
            str(activity.source_id or ""),
        )

    @staticmethod
    def _validate_activity(
        activity: IronCoachActivity,
        seen_activity_ids: set,
        seen_source_ids: set,
    ) -> None:
        if not isinstance(activity, IronCoachActivity):
            raise GarminActivityExportError(
                "Oggetto non compatibile con IronCoachActivity."
            )

        activity_id = str(activity.activity_id or "").strip()
        source_id = str(activity.source_id or "").strip()

        if not activity_id:
            raise GarminActivityExportError(
                "Attività senza activity_id."
            )

        if not source_id:
            raise GarminActivityExportError(
                f"Attività senza source_id: {activity_id}"
            )

        if activity_id in seen_activity_ids:
            raise GarminActivityExportError(
                "activity_id duplicato nell'export: "
                f"{activity_id}"
            )

        if source_id in seen_source_ids:
            raise GarminActivityExportError(
                "source_id duplicato nell'export: "
                f"{source_id}"
            )

        seen_activity_ids.add(activity_id)
        seen_source_ids.add(source_id)

    @staticmethod
    def _validate_json_value(
        value: Any,
        path: str = "$",
    ) -> None:
        if value is None or isinstance(value, (str, bool, int)):
            return

        if isinstance(value, float):
            if not math.isfinite(value):
                raise GarminActivityExportError(
                    f"Valore numerico non finito in {path}."
                )
            return

        if isinstance(value, list):
            for index, item in enumerate(value):
                GarminActivityExporter._validate_json_value(
                    item,
                    f"{path}[{index}]",
                )
            return

        if isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str):
                    raise GarminActivityExportError(
                        f"Chiave metadata non testuale in {path}."
                    )
                GarminActivityExporter._validate_json_value(
                    item,
                    f"{path}.{key}",
                )
            return

        raise GarminActivityExportError(
            "Valore non serializzabile in "
            f"{path}: {type(value).__name__}"
        )

    def _open_text_writer(self, path: Path) -> TextIO:
        if self._is_gzip_path(self.output_path):
            return gzip.open(
                path,
                mode="wt",
                encoding="utf-8",
                newline="\n",
            )

        return path.open(
            mode="w",
            encoding="utf-8",
            newline="\n",
        )

    @staticmethod
    def _open_text_reader(path: Path) -> TextIO:
        if GarminActivityExporter._is_gzip_path(path):
            return gzip.open(
                path,
                mode="rt",
                encoding="utf-8",
                newline="",
            )

        return path.open(
            mode="r",
            encoding="utf-8",
            newline="",
        )

    @staticmethod
    def _is_gzip_path(path: Path) -> bool:
        return path.suffix.lower() == ".gz"

    @staticmethod
    def _default_manifest_path(output_path: Path) -> Path:
        return Path(str(output_path) + ".manifest.json")

    @staticmethod
    def _temporary_path(path: Path) -> Path:
        return path.with_name(path.name + f".{os.getpid()}.tmp")

    @staticmethod
    def _sha256(path: Path) -> str:
        sha = hashlib.sha256()

        with path.open("rb") as source:
            for chunk in iter(
                lambda: source.read(1024 * 1024),
                b"",
            ):
                sha.update(chunk)

        return sha.hexdigest()

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat().replace(
            "+00:00",
            "Z",
        )