"""
Test Decision Memory Viewer.
"""

from backend.decision_memory.viewer import (
    DecisionMemoryViewer,
)


class FakeRepository:
    def latest(
        self,
        limit=10,
    ):
        return [
            {
                "decision_action": "ADATTA",
                "strategy": "ADAPT",
                "status": "WAITING_FOR_ACTIVITY",
                "decision_timestamp": (
                    "2026-08-25T07:30:25Z"
                ),
                "recommended_workout": {
                    "sport": "RUN",
                    "duration_minutes": 40,
                },
            }
        ]


def test_viewer_returns_latest_decisions():

    viewer = DecisionMemoryViewer(
        repository=FakeRepository(),
    )

    result = viewer.latest()

    assert len(result) == 1

    assert result[0][
        "decision_action"
    ] == "ADATTA"

    assert result[0][
        "strategy"
    ] == "ADAPT"