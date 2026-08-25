"""
Test Decision Memory Formatter.
"""

from backend.decision_memory.formatter import (
    DecisionMemoryFormatter,
)


def test_formatter_creates_readable_report():

    formatter = DecisionMemoryFormatter()

    episode = {
        "decision_timestamp": (
            "2026-08-25T08:00:00Z"
        ),
        "decision_action": "ADATTA",
        "strategy": "ADAPT",
        "primary_intent": "REDUCE_LOAD",
        "status": "WAITING_FOR_ACTIVITY",
        "recommended_workout": {
            "sport": "RUN",
            "duration_minutes": 40,
        },
    }

    output = formatter.format(
        episode
    )

    assert "ADATTA" in output
    assert "ADAPT" in output
    assert "REDUCE_LOAD" in output
    assert "RUN" in output
    assert "40" in output