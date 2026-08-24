"""
Test ricerca episodi pending nella Decision Memory.

Verifica che il repository restituisca, per un atleta,
solo gli episodi ancora da elaborare e in ordine cronologico.
"""

from backend.decision_memory.repository import (
    DecisionMemoryRepository,
)
from backend.models.decision_episode import (
    DecisionEpisode,
)


def _episode(
    *,
    athlete_id,
    decision_id,
    decision_timestamp,
    status,
):
    return DecisionEpisode(
        athlete_id=athlete_id,
        decision_id=decision_id,
        decision_timestamp=decision_timestamp,
        decision_action="ADATTA",
        strategy="ADAPT",
        rule_id="PERFORMANCE_DECLINING_LOAD_HIGH",
        primary_intent="PROTECT_PERFORMANCE",
        decision_confidence=89,
        supporting_intents=[
            "REDUCE_LOAD",
        ],
        pre_decision_state={},
        athlete_state={},
        status=status,
    )


def test_list_pending_by_athlete_returns_only_pending_episodes(
    tmp_path,
):
    repository = DecisionMemoryRepository(
        tmp_path / "ironcoach_memory.db"
    )

    episodes = [
        _episode(
            athlete_id="athlete-123",
            decision_id="decision-open",
            decision_timestamp="2026-08-24T09:00:00Z",
            status="OPEN",
        ),
        _episode(
            athlete_id="athlete-123",
            decision_id="decision-activity",
            decision_timestamp="2026-08-24T10:00:00Z",
            status="WAITING_FOR_ACTIVITY",
        ),
        _episode(
            athlete_id="athlete-123",
            decision_id="decision-outcome",
            decision_timestamp="2026-08-24T11:00:00Z",
            status="WAITING_FOR_OUTCOME",
        ),
        _episode(
            athlete_id="athlete-123",
            decision_id="decision-complete",
            decision_timestamp="2026-08-24T12:00:00Z",
            status="COMPLETE",
        ),
        _episode(
            athlete_id="athlete-123",
            decision_id="decision-incomplete",
            decision_timestamp="2026-08-24T13:00:00Z",
            status="INCOMPLETE",
        ),
        _episode(
            athlete_id="athlete-other",
            decision_id="decision-other-athlete",
            decision_timestamp="2026-08-24T08:00:00Z",
            status="OPEN",
        ),
    ]

    for episode in episodes:
        repository.create(
            episode
        )

    pending = repository.list_pending_by_athlete(
        "athlete-123"
    )

    assert [
        episode.decision_id
        for episode in pending
    ] == [
        "decision-open",
        "decision-activity",
        "decision-outcome",
    ]

    assert [
        episode.status
        for episode in pending
    ] == [
        "OPEN",
        "WAITING_FOR_ACTIVITY",
        "WAITING_FOR_OUTCOME",
    ]