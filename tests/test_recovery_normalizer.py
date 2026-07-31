from backend.normalization.recovery_normalizer import RecoveryNormalizer


normalizer = RecoveryNormalizer()


garmin_recovery = {

    "id": "recovery_001",

    "date": "2026-08-01",

    "sleep_score": 82,

    "sleep_hours": 7.5,

    "body_battery": 65,

    "hrv": 58,

    "resting_hr": 46,

    "stress": 22,

    "fatigue": 3,

    "soreness": 1,

    "morning_energy": 8,

    "notes": "Buona sensazione generale"

}


result = normalizer.normalize(
    garmin_recovery,
    source="garmin",
)


print(result)
