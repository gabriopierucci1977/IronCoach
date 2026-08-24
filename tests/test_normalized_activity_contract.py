"""
Regression tests for the normalized activity contract.

These tests intentionally exercise the real boundaries that feed the coaching
pipeline.  They protect against data being available in raw Airtable input but
lost after normalization/history construction.
"""

from backend.analyzers.adaptation_analyzer import AdaptationAnalyzer
from backend.analyzers.injury_analyzer import InjuryAnalyzer
from backend.analyzers.load_analyzer import LoadAnalyzer
from backend.analyzers.recovery_trend_analyzer import RecoveryTrendAnalyzer
from backend.analyzers.training_analyzer import TrainingAnalyzer
from backend.coach_engine import CoachEngine
from backend.history.recovery_history import RecoveryHistory
from backend.history.training_history import TrainingHistory
from backend.normalization.activity_normalizer import ActivityNormalizer
from backend.normalization.athlete_normalizer import AthleteNormalizer


def _stressful_training():
    return {
        "Data allenamento": "2026-08-10",
        "Sport": "Corsa",
        "Nome seduta": "5x5 VO2",
        "Tipo seduta": "Ripetute VO2",
        "Zona prevista": "Z5",
        "Durata minuti": 150,
        "Carico interno": 950,
        "RPE percepito": 8,
    }


def _painful_training():
    return {
        "Data allenamento": "2026-08-10",
        "Sport": "Corsa",
        "Tipo seduta": "Facile",
        "Zona prevista": "Z2",
        "Durata minuti": 60,
        "Carico interno": 300,
        "RPE percepito": 5,
        "Dolori/problematiche": "Dolore acuto al ginocchio con gonfiore",
        "Pain Score": 9,
    }


def test_activity_normalizer_exposes_canonical_coaching_fields() -> None:
    normalized = ActivityNormalizer().normalize(
        {
            **_stressful_training(),
            "Dolori/problematiche": "Fastidio al tendine di Achille",
            "Pain Score": 4,
        },
        source="airtable",
    )

    assert normalized["workout_name"] == "5x5 VO2"
    assert normalized["session_type"] == "Ripetute VO2"
    assert normalized["intensity"] == "Z5"
    assert normalized["duration_minutes"] == 150.0
    assert normalized["training_load"] == 950
    assert normalized["rpe"] == 8
    assert normalized["current_problem"] == "Fastidio al tendine di Achille"
    assert normalized["pain_score"] == 4


def test_training_analyzer_preserves_assessment_after_normalization() -> None:
    raw = _stressful_training()
    normalized = ActivityNormalizer().normalize(
        raw,
        source="airtable",
    )

    direct = TrainingAnalyzer().analyze(raw)
    through_normalizer = TrainingAnalyzer().analyze(normalized)

    assert direct["level"] == "HIGH"
    assert through_normalizer["level"] == direct["level"]
    assert through_normalizer["session_type"] == "ripetute vo2"
    assert through_normalizer["planned_zone"] == "z5"
    assert through_normalizer["duration_minutes"] == 150.0
    assert through_normalizer["internal_load"] == 950.0




def test_empty_normalized_training_remains_unknown() -> None:
    normalized = ActivityNormalizer().normalize(
        {},
        source="airtable",
    )

    result = TrainingAnalyzer().analyze(
        normalized
    )

    assert normalized["duration_minutes"] is None
    assert normalized["training_load"] is None
    assert result["level"] == "UNKNOWN"


def test_injury_analyzer_preserves_critical_signal_after_normalization() -> None:
    raw = _painful_training()
    normalized = ActivityNormalizer().normalize(
        raw,
        source="airtable",
    )

    direct = InjuryAnalyzer().analyze(raw)
    through_normalizer = InjuryAnalyzer().analyze(normalized)

    assert direct["level"] == "CRITICAL"
    assert through_normalizer["level"] == "CRITICAL"
    assert through_normalizer["pain_score"] == 9.0
    assert "ginocchio" in through_normalizer["current_problem"]


def test_critical_injury_reaches_decision_engine_through_normalized_context() -> None:
    training = ActivityNormalizer().normalize(
        _painful_training(),
        source="airtable",
    )
    athlete = AthleteNormalizer().normalize(
        {"Nome": "Atleta test"},
        source="airtable",
    )

    decision = CoachEngine().evaluate(
        {
            "training": training,
            "athlete_profile": athlete,
            "recovery": {},
            "nutrition": {},
            "training_history": [],
            "recovery_history": [],
            "performance_history": [],
            "data_freshness": {
                "level": "HIGH",
                "reasons": [],
            },
        }
    )

    assert decision["decision"] == "RECUPERA"
    assert decision["strategy"] == "RECOVERY"
    assert decision["risk_level"] == "HIGH_ALERT"


def test_missing_training_load_stays_missing_through_training_history() -> None:
    normalized = ActivityNormalizer().normalize(
        {
            "Data allenamento": "2026-08-10",
            "Sport": "Corsa",
            "Durata minuti": 60,
        },
        source="airtable",
    )

    history = TrainingHistory()
    history.load([normalized])

    session = history.sessions[0]
    result = LoadAnalyzer().analyze(
        {
            "training_history": history.sessions,
        }
    )

    assert normalized["training_load"] is None
    assert session["training_load"] is None
    assert session["load"] is None
    assert result["level"] == "UNKNOWN"
    assert result["sessions_with_load"] == 0


def test_real_zero_training_load_is_preserved_as_observed_value() -> None:
    normalized = ActivityNormalizer().normalize(
        {
            "Data allenamento": "2026-08-10",
            "Sport": "Corsa",
            "Carico interno": 0,
        },
        source="airtable",
    )

    history = TrainingHistory()
    history.load([normalized])

    result = LoadAnalyzer().analyze(
        {
            "training_history": history.sessions,
        }
    )

    assert normalized["training_load"] == 0
    assert history.sessions[0]["training_load"] == 0.0
    assert result["sessions_with_load"] == 1
    assert result["level"] == "LOW"


def test_recovery_trend_reads_nested_sleep_score_from_recovery_history() -> None:
    history = RecoveryHistory()

    for date, recovery, sleep in (
        ("2026-08-01", 70, 50),
        ("2026-08-02", 72, 52),
        ("2026-08-03", 80, 65),
        ("2026-08-04", 82, 70),
    ):
        history.add_record(
            {
                "date": date,
                "recovery_score": recovery,
                "sleep_score": sleep,
            }
        )

    result = RecoveryTrendAnalyzer().analyze(
        {
            "recovery_history": history.records,
        }
    )

    assert result["trend"] == "IMPROVING"
    assert result["sleep_trend"] == "IMPROVING"
    assert result["sleep_change"] == 16.5


def test_adaptation_analyzer_reads_normalized_physical_limitations() -> None:
    athlete = AthleteNormalizer().normalize(
        {
            "Limitazioni fisiche": "Tendinopatia achillea",
        },
        source="airtable",
    )

    result = AdaptationAnalyzer().analyze(
        {
            "athlete_profile": athlete,
            "load_analysis": {
                "level": "HIGH",
                "total_load": 2200,
                "acute_chronic_ratio": 1.2,
                "sessions_with_load": 20,
            },
            "performance_analysis": {},
            "recovery_analysis": {},
        }
    )

    assert result["adaptation_level"] == "LIMITED"
    assert "Tendinopatia achillea" in result["risk_factors"]


def test_explicit_long_duration_minutes_are_not_reinterpreted_as_seconds() -> None:
    normalized = ActivityNormalizer().normalize(
        {
            "Sport": "Bici",
            "Durata minuti": 360,
        },
        source="airtable",
    )

    assert normalized["duration_minutes"] == 360.0


def test_source_specific_generic_duration_uses_explicit_unit_contract() -> None:
    garmin = ActivityNormalizer().normalize(
        {
            "activity_type": "running",
            "duration": 3600,
        },
        source="garmin",
    )
    manual = ActivityNormalizer().normalize(
        {
            "sport": "bike",
            "duration": 360,
        },
        source="manual",
    )

    assert garmin["duration_minutes"] == 60.0
    assert manual["duration_minutes"] == 360.0


def test_explicit_duration_seconds_are_converted_even_for_manual_source() -> None:
    normalized = ActivityNormalizer().normalize(
        {
            "sport": "bike",
            "duration_seconds": 21600,
        },
        source="manual",
    )

    assert normalized["duration_minutes"] == 360.0
