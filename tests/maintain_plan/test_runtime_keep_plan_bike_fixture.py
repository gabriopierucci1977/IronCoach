"""Isolated BIKE KEEP_PLAN runtime comparison fixture."""

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


def test_runtime_keep_plan_matches_bike_activity_fixture(tmp_path):
    database = tmp_path / "maintain-plan-bike.db"

    config = RuntimeConfig(
        maintain_plan_snapshot_enabled=True,
        maintain_plan_actual_session_enabled=True,
        maintain_plan_database_path=str(database),
        maintain_plan_timezone="Europe/Rome",
    )

    athlete = {"source_id": "recAthleteBikeKeep"}

    training = {
        "source": "airtable",
        "source_id": "recBikeKeepPlan",
        "date": "2026-10-14",
        "sport": "BIKE",
        "workout_name": "Bike TEST",
        "session_type": "continuous",
        "duration_minutes": 90,
        "intensity": 140,
        "intensity_method": "HR",
        "intensity_unit": "bpm",
        "environment": "OUTDOOR",
        "mode": "ROAD",
        "raw": {
            "Zona prevista": "Z3 Medio",
            "Tipo seduta": "Qualità",
        },
    }

    decision = {
        "decision_id": "decision-bike-keep-plan",
        "primary_intent": "MAINTAIN_PLAN",
        "strategy": "KEEP_PLAN",
        "modified_workout": {},
    }

    prescription = RuntimePrescriptionCapture(
        clock=lambda: datetime(
            2026,
            10,
            14,
            8,
            tzinfo=timezone.utc,
        ),
    ).capture(
        runtime_config=config,
        athlete=athlete,
        training=training,
        decision=decision,
    )

    assert prescription is not None

    RuntimeActualSessionCapture().capture(
        runtime_config=config,
        athlete=athlete,
        garmin_training_history=[
            {
                "activity_id": "garmin:bike-keep-plan",
                "source_id": "bike-keep-plan",
                "date": "2026-10-14T10:07:02Z",
                "sport": "BIKE",
                "duration_minutes": 90,
                "distance_km": 45,
                "heart_rate": {
                    "average": 140,
                    "max": 160,
                },
                "power": {},
                "segments": [],
                "metadata": {
                    "garmin": {
                        "file_name": "24720297468_ACTIVITY.fit",
                        "sub_sport": "road",
                    },
                },
                "raw": {
                    "activity_type": "road",
                    "distance_km": 45,
                },
            }
        ],
        normalized_at=datetime(
            2026,
            10,
            15,
            tzinfo=timezone.utc,
        ),
    )

    review = review_database(
        str(database),
        "recAthleteBikeKeep",
    )

    assert review.decision.status is DecisionStatus.MATCHED
    assert len(review.decision.candidates) == 1
    assert review.candidate_details[0]["source"] == "garmin"
