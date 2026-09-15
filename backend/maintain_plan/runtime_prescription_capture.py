"""Opt-in runtime service for persisting communicated prescriptions."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from .prescription_snapshot_service import PrescriptionSnapshotService
from .repository import MaintainPlanRepository
from .runtime_prescription_adapter import build_communicated_prescription


class RuntimePrescriptionCapture:
    """Validate runtime input before opening the isolated SQLite database."""

    def __init__(
        self,
        repository_factory: Callable[[str], object] = MaintainPlanRepository,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._repository_factory = repository_factory
        self._clock = clock

    def capture(self, *, runtime_config, training, decision):
        """Capture an eligible decision, or return ``None`` when not enabled."""
        if getattr(runtime_config, "maintain_plan_snapshot_enabled", None) is not True:
            return None
        if type(decision) is not dict:
            return None
        if (
            decision.get("primary_intent") != "MAINTAIN_PLAN"
            or decision.get("strategy") != "KEEP_PLAN"
        ):
            return None

        # Build (including domain validation) before repository construction;
        # repository construction runs the SQLite migrations.
        communicated = build_communicated_prescription(
            training,
            decision,
            communicated_at=self._clock(),
            timezone_name=runtime_config.maintain_plan_timezone,
        )
        repository = self._repository_factory(
            runtime_config.maintain_plan_database_path
        )
        return PrescriptionSnapshotService(repository).acquire(communicated)
