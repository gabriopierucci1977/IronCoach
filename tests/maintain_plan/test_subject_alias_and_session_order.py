from datetime import datetime, timezone
from types import SimpleNamespace

from backend.maintain_plan.coach_web import _resolve_subject_alias
from backend.maintain_plan.session_flow import list_sessions


def _session(identifier, start):
    return SimpleNamespace(
        session_id=identifier,
        start=start,
        components=(SimpleNamespace(discipline="BIKE"),),
    )


def test_known_subject_aliases_resolve_to_one_canonical_owner():
    environment = {
        "IRONCOACH_SUBJECT_REF": "recO4aHGKSTexpXUC",
        "IRONCOACH_SUBJECT_ALIASES": "gabrio-pierucci,gabrio_pierucci",
    }

    assert _resolve_subject_alias(
        "gabrio-pierucci", environment
    ) == "recO4aHGKSTexpXUC"
    assert _resolve_subject_alias(
        "gabrio_pierucci", environment
    ) == "recO4aHGKSTexpXUC"


def test_sessions_are_listed_newest_first():
    old = _session(
        "old",
        datetime(2026, 10, 6, 15, 58, 30, tzinfo=timezone.utc),
    )
    new = _session(
        "new",
        datetime(2026, 10, 17, 8, 10, 23, tzinfo=timezone.utc),
    )

    class Repository:
        def list_actual_sessions(self, subject_ref):
            return (old, new)

    page = list_sessions(Repository(), "recO4aHGKSTexpXUC")

    assert [item.session_id for item in page.items] == ["new", "old"]
