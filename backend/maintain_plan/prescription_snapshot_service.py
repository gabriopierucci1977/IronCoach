"""Explicit acquisition boundary for communicated prescription snapshots.

This module is deliberately not imported by any application runtime.  Callers
must present a complete canonical prescription wrapped as an explicit
communication event; this boundary never looks up or infers prescription data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import PrescriptionSnapshot
from .serialization import deserialize_contract, serialize_contract
from .validators import validate_prescription


class PrescriptionSnapshotRepository(Protocol):
    """The insert-only repository operations used by the acquisition boundary."""

    def create_prescription_snapshot(self, value: PrescriptionSnapshot) -> None: ...

    def get_prescription_snapshot(self, identifier: str) -> PrescriptionSnapshot | None: ...


@dataclass(frozen=True)
class CommunicatedPrescription:
    """A caller's explicit declaration that this exact prescription was communicated."""

    snapshot: PrescriptionSnapshot


class PrescriptionSnapshotService:
    """Validate, defensively copy, and insert a communicated prescription."""

    def __init__(self, repository: PrescriptionSnapshotRepository):
        self._repository = repository

    def acquire(self, communicated: CommunicatedPrescription) -> PrescriptionSnapshot:
        """Persist one immutable snapshot and return its canonical stored value.

        No legacy workout, training context, observed activity, matching result,
        or evaluation is accepted by this API.  Every authored value, identifier,
        and timestamp therefore comes solely from ``communicated.snapshot``.
        """
        if not isinstance(communicated, CommunicatedPrescription):
            raise TypeError("acquire requires an explicitly CommunicatedPrescription")

        # Codec round-tripping is the canonical defensive copy.  It recursively
        # rebuilds every contract container and freezes nested mappings/sets.
        snapshot = deserialize_contract(
            serialize_contract(communicated.snapshot), PrescriptionSnapshot
        )
        errors = validate_prescription(snapshot)
        if errors:
            raise ValueError("; ".join(errors))

        # The repository operation is one SQLite INSERT transaction.  A duplicate
        # ID or any write failure rolls it back rather than replacing prior state.
        self._repository.create_prescription_snapshot(snapshot)
        stored = self._repository.get_prescription_snapshot(
            snapshot.prescription_snapshot_id
        )
        if stored is None or stored != snapshot:
            raise RuntimeError("persisted prescription snapshot failed canonical round-trip")
        return stored
