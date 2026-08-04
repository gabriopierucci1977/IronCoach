"""
Test di orchestrazione del CoachEngine.

Verifica che:
- recovery, load e performance vengano analizzati prima dell'adattamento;
- AdaptationAnalyzer riceva athlete_profile, load_analysis,
  performance_analysis e recovery_analysis;
- gli assessment finali contengano gli stessi risultati;
- evaluate non richieda servizi esterni o scritture;
- la performance intelligence venga mantenuta nella decisione finale.
"""

from backend.coach_engine import CoachEngine


class RecordingAnalyzer:
    def __init__(
        self,
        name,
        result,
        events,
    ):
        self.name = name
        self.result = result
        self.events = events
        self.inputs = []

    def analyze(
        self,
        payload,
    ):
        self.events.append(
            self.name
        )
        self.inputs.append(
            payload
        )
        return self.result


class RecordingDecisionEngine:
    def __init__(
        self,
    ):
        self.assessments = None

    def decide(
        self,
        assessments,
    ):
        self.assessments = assessments
        return {
            "decision": "MAINTAIN",
        }


def _build_engine():
    events = []

    engine = CoachEngine.__new__(
        CoachEngine
    )

    engine.recovery_analyzer = RecordingAnalyzer(
        "recovery",
        {
            "state": "VERDE",
            "level": "LOW",
            "score": 82,
            "sleep_score": 78,
            "reasons": [
                "Recovery favorevole"
            ],
        },
        events,
    )

    engine.recovery_trend_analyzer = RecordingAnalyzer(
        "recovery_trend",
        {
            "trend": "STABLE",
        },
        events,
    )

    engine.training_analyzer = RecordingAnalyzer(
        "training",
        {
            "status": "AVAILABLE",
        },
        events,
    )

    engine.injury_analyzer = RecordingAnalyzer(
        "injury",
        {
            "risk": "LOW",
        },
        events,
    )

    engine.nutrition_analyzer = RecordingAnalyzer(
        "nutrition",
        {
            "status": "ADEQUATE",
        },
        events,
    )

    engine.load_analyzer = RecordingAnalyzer(
        "load",
        {
            "level": "NORMAL",
            "total_load": 900,
            "acute_chronic_ratio": 1.0,
            "sessions_with_load": 12,
        },
        events,
    )

    engine.performance_analyzer = RecordingAnalyzer(
        "performance",
        {
            "trend": "IMPROVING",
            "metrics": {
                "ftp": 5.0,
            },
            "details": {
                "ftp": {
                    "start": 280,
                    "end": 294,
                    "change_percent": 5.0,
                }
            },
            "strengths": [
                "Performance in crescita",
            ],
            "concerns": [],
        },
        events,
    )

    engine.adaptation_analyzer = RecordingAnalyzer(
        "adaptation",
        {
            "adaptation_level": "GOOD",
            "risk_factors": [],
            "positive_factors": [
                "Performance in crescita"
            ],
            "reasons": [
                "Adattamento favorevole"
            ],
        },
        events,
    )

    engine.decision_engine = RecordingDecisionEngine()

    engine._build_athlete_intelligence = (
        lambda profile: profile
    )

    return engine, events


def _context():
    return {
        "recovery": {
            "recovery_score": 82,
        },
        "training": {
            "planned": True,
        },
        "nutrition": {
            "status": "ok",
        },
        "athlete_profile": {
            "limitations": [],
            "experience": "advanced",
        },
        "training_history": [
            {
                "date": "2025-01-01",
                "training_load": 100,
            }
        ],
        "recovery_history": [
            {
                "date": "2025-01-01",
                "recovery_score": 80,
            }
        ],
        "performance_history": [
            {
                "date": "2025-01-01",
                "metric": "ftp",
                "value": 280,
            },
            {
                "date": "2025-02-01",
                "metric": "ftp",
                "value": 294,
            },
        ],
    }


def test_performance_is_analyzed_before_adaptation() -> None:
    engine, events = _build_engine()

    engine.evaluate(
        _context()
    )

    assert events.index(
        "performance"
    ) < events.index(
        "adaptation"
    )


def test_adaptation_receives_all_required_analyses() -> None:
    engine, _ = _build_engine()

    engine.evaluate(
        _context()
    )

    payload = (
        engine
        .adaptation_analyzer
        .inputs[0]
    )

    assert payload == {
        "athlete_profile": {
            "limitations": [],
            "experience": "advanced",
        },
        "load_analysis": {
            "level": "NORMAL",
            "total_load": 900,
            "acute_chronic_ratio": 1.0,
            "sessions_with_load": 12,
        },
        "performance_analysis": {
            "trend": "IMPROVING",
            "metrics": {
                "ftp": 5.0,
            },
            "details": {
                "ftp": {
                    "start": 280,
                    "end": 294,
                    "change_percent": 5.0,
                }
            },
            "strengths": [
                "Performance in crescita",
            ],
            "concerns": [],
        },
        "recovery_analysis": {
            "state": "VERDE",
            "level": "LOW",
            "score": 82,
            "sleep_score": 78,
            "reasons": [
                "Recovery favorevole"
            ],
        },
    }


def test_decision_engine_receives_enriched_adaptation() -> None:
    engine, _ = _build_engine()

    decision = engine.evaluate(
        _context()
    )

    assessments = (
        engine
        .decision_engine
        .assessments
    )

    assert assessments[
        "adaptation"
    ][
        "adaptation_level"
    ] == "GOOD"

    assert assessments[
        "performance"
    ][
        "trend"
    ] == "IMPROVING"

    assert assessments[
        "recovery"
    ][
        "state"
    ] == "VERDE"

    assert decision[
        "intelligence"
    ][
        "adaptation"
    ][
        "adaptation_level"
    ] == "GOOD"


def test_performance_intelligence_is_preserved_in_final_decision() -> None:
    engine, _ = _build_engine()

    decision = engine.evaluate(
        _context()
    )

    performance = decision[
        "intelligence"
    ][
        "performance"
    ]

    assert performance[
        "trend"
    ] == "IMPROVING"

    assert performance[
        "metrics"
    ][
        "ftp"
    ] == 5.0

    assert performance[
        "details"
    ][
        "ftp"
    ][
        "change_percent"
    ] == 5.0


def test_analyzer_inputs_use_context_histories() -> None:
    engine, _ = _build_engine()
    context = _context()

    engine.evaluate(
        context
    )

    assert (
        engine
        .load_analyzer
        .inputs[0]
    ) == {
        "training_history":
            context[
                "training_history"
            ],
    }

    assert (
        engine
        .performance_analyzer
        .inputs[0]
    ) == {
        "performance_history":
            context[
                "performance_history"
            ],
    }

    assert (
        engine
        .recovery_trend_analyzer
        .inputs[0]
    ) == {
        "recovery_history":
            context[
                "recovery_history"
            ],
    }