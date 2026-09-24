"""Integration coverage for the documented real-data MAINTAIN_PLAN path."""

from datetime import datetime, timezone

from backend.config import RuntimeConfig
from backend.maintain_plan.coach_review import review_database
from backend.maintain_plan.runtime_actual_session_capture import (
    RuntimeActualSessionCapture,
)
from backend.maintain_plan.runtime_matching_decision import DecisionStatus
from backend.maintain_plan.runtime_prescription_capture import (
    RuntimePrescriptionCapture,
)


def test_runtime_captures_plan_and_garmin_activity_for_coach_review(tmp_path):
    database = tmp_path / "maintain-plan.db"
    config = RuntimeConfig(
        maintain_plan_snapshot_enabled=True,
        maintain_plan_actual_session_enabled=True,
        maintain_plan_database_path=str(database),
        maintain_plan_timezone="Europe/Rome",
    )
    athlete = {"source_id": "recAthleteReal"}

    RuntimePrescriptionCapture(
        clock=lambda: datetime(2026, 9, 14, 10, tzinfo=timezone.utc),
    ).capture(
        runtime_config=config,
        athlete=athlete,
        training={
            "source": "airtable",
            "source_id": "recTrainingReal",
            "date": "2026-09-15",
            "sport": "RUN",
            "workout_name": "Corsa aerobica",
            "session_type": "continuous",
            "duration_minutes": 60,
            "intensity": 140,
            "intensity_method": "HR",
            "intensity_unit": "bpm",
            "environment": "OUTDOOR",
            "mode": "ROAD",
            "raw": {},
        },
        decision={
            "decision_id": "decision-real",
            "primary_intent": "MAINTAIN_PLAN",
            "strategy": "KEEP_PLAN",
            "modified_workout": {},
        },
    )
    RuntimeActualSessionCapture().capture(
        runtime_config=config,
        athlete=athlete,
        garmin_training_history=[{
            "activity_id": "garmin:activity-real",
            "source_id": "activity-real",
            "date": "2026-09-15T08:00:00Z",
            "sport": "RUN",
            "duration_minutes": 60,
            "distance_km": 10,
            "heart_rate": {},
            "power": {},
            "segments": [],
            "metadata": {},
            "raw": {"activity_type": "running", "distance_km": 10},
        }],
        normalized_at=datetime(2026, 9, 16, tzinfo=timezone.utc),
    )

    review = review_database(str(database), "recAthleteReal")

    assert review.decision.status is DecisionStatus.MATCHED
    assert len(review.decision.candidates) == 1
    assert review.candidate_details[0]["source"] == "garmin"
