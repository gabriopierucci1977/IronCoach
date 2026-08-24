"""
Test DecisionEpisode model.

DecisionEpisode rappresenta il ciclo di vita completo
di una decisione IronCoach nella Decision Memory.
"""

from datetime import datetime
from uuid import UUID

from backend.models.decision_episode import DecisionEpisode


def _episode():
    return DecisionEpisode(
        athlete_id="athlete-123",
        decision_timestamp="2026-08-24T09:00:00Z",
        decision_action="CONFERMA",
        rule_id="DEFAULT_CONFIRM",
        primary_intent="MAINTAIN_PLAN",
        pre_decision_state={
            "recovery": {
                "level": "LOW",
            },
        },
        athlete_state={
            "goal_type": "PERFORMANCE",
        },
    )


def test_decision_episode_generates_uuid4_episode_id():
    episode = _episode()

    parsed = UUID(
        episode.episode_id
    )

    assert parsed.version == 4


def test_decision_episode_starts_open():
    episode = _episode()

    assert episode.status == "OPEN"


def test_decision_episode_uses_schema_version_one():
    episode = _episode()

    assert episode.schema_version == "1"


def test_decision_episode_audit_timestamps_are_utc_iso():
    episode = _episode()

    created_at = datetime.fromisoformat(
        episode.created_at.replace(
            "Z",
            "+00:00",
        )
    )

    updated_at = datetime.fromisoformat(
        episode.updated_at.replace(
            "Z",
            "+00:00",
        )
    )

    assert episode.created_at.endswith("Z")
    assert episode.updated_at.endswith("Z")
    assert created_at.utcoffset().total_seconds() == 0
    assert updated_at.utcoffset().total_seconds() == 0


def test_decision_episode_optional_collections_are_not_shared():
    first = _episode()
    second = _episode()

    first.supporting_intents.append(
        "REDUCE_LOAD"
    )

    first.adherence_evidence[
        "duration"
    ] = "matched"

    assert second.supporting_intents == []
    assert second.adherence_evidence == {}


def test_decision_episode_keeps_decision_identity_separate():
    episode = DecisionEpisode(
        athlete_id="athlete-123",
        decision_id="decision-456",
        decision_timestamp="2026-08-24T09:00:00Z",
        decision_action="ADATTA",
        rule_id="PERFORMANCE_DECLINING_LOAD_HIGH",
        primary_intent="PROTECT_PERFORMANCE",
        supporting_intents=[
            "REDUCE_LOAD",
        ],
        pre_decision_state={},
        athlete_state={},
    )

    assert episode.episode_id != episode.decision_id
    assert episode.decision_id == "decision-456"


def test_decision_episode_outcomes_start_unevaluated():
    episode = _episode()

    assert episode.adherence_status is None

    assert episode.outcome_24h_status is None
    assert episode.outcome_72h_status is None
    assert episode.outcome_7d_status is None

    assert episode.overall_outcome_status is None
    assert episode.overall_outcome_confidence is None