from backend.normalization.activity_normalizer import ActivityNormalizer


normalizer = ActivityNormalizer()


garmin_activity = {

    "id": "garmin_001",

    "start_date": "2026-08-01",

    "activity_type": "running",

    "distance": 10500,

    "duration": 3600,

    "average_hr": 145,

    "max_hr": 172,

    "training_load": 180,

    "rpe": 7,

    "notes": "Corsa aerobica facile"

}


result = normalizer.normalize(
    garmin_activity,
    source="garmin",
)


print(result)
