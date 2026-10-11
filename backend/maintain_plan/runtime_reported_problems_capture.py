"""Opt-in capture and persistence of a canonical reported-problems projection."""

from __future__ import annotations

from .repository import MaintainPlanRepository
from .stability_models import ReportedProblemsProjectionSnapshot
from .stability_validators import validate_projection_structure


class ReportedProblemsProjectionCaptureError(ValueError):
    def __init__(self, errors, *, code="INPUT_INVALID"):
        self.code = code
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


def build_reported_problems_projection_capture(
    value: ReportedProblemsProjectionSnapshot,
) -> ReportedProblemsProjectionSnapshot:
    """Validate one caller-scoped projection without reading events or sources."""
    errors = validate_projection_structure(value)
    if errors:
        raise ReportedProblemsProjectionCaptureError(errors)
    return value


class RuntimeReportedProblemsProjectionCapture:
    def __init__(self, repository_factory=MaintainPlanRepository):
        self._repository_factory = repository_factory

    def capture(
        self, *, value, enabled=False, database_path=None,
    ) -> ReportedProblemsProjectionSnapshot | None:
        """Validate before opening SQLite; disabled calls have no side effects."""
        if enabled is not True:
            return None
        value = build_reported_problems_projection_capture(value)
        if database_path is None:
            raise ReportedProblemsProjectionCaptureError(
                ("database_path is required",), code="INPUT_MISSING",
            )
        repository = self._repository_factory(database_path)
        return repository.acquire_reported_problems_projection(value)
