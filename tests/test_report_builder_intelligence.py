"""
Test ReportBuilder per intelligence e decisione finale.

Verifica che il report esponga senza perdere informazioni:
- carico recente;
- adattamento;
- trend recovery;
- trend performance;
- reasoning decisionale;
- rischio e azione consigliata.
"""

from backend.report_builder import ReportBuilder


def _context():
    return {
        "athlete_profile": {
            "identity": {
                "name": "Atleta Test",
            },
        },
        "recovery": {
            "recovery_score": 82,
            "recovery_state": "VERDE",
        },
        "training": {
            "sport": "RUN",
            "distance_km": 10,
            "duration_minutes": 50,
        },
        "nutrition": {
            "nutrition_state": "ADEGUATA",
        },
        "decision": {},
    }


def _decision():
    return {
        "decision": "ADATTA",
        "reason": "La capacità di adattamento è da monitorare.",
        "priority": "Performance",
        "confidence": 90,
        "strategy": "ADAPT",
        "recommended_action": (
            "Riduci moderatamente volume o intensità."
        ),
        "reasoning": [
            "Recovery: basso",
            "Carico: alto",
            "Adattamento: moderato",
            "Performance: in peggioramento",
        ],
        "risk_level": "CAUTION",
        "intelligence": {
            "athlete_profile": {
                "athlete_name": "Atleta Test",
            },
            "load": {
                "level": "HIGH",
                "acute_load_7d": 620.0,
                "chronic_load_28d": 2100.0,
                "acute_chronic_ratio": 1.18,
            },
            "adaptation": {
                "adaptation_level": "MODERATE",
                "risk_factors": [
                    "Carico recente elevato",
                ],
                "positive_factors": [],
                "reasons": [
                    "Adattamento da monitorare",
                ],
            },
            "recovery_trend": {
                "trend": "STABLE",
            },
            "performance": {
                "trend": "DECLINING",
                "metrics": {
                    "ftp": -4.5,
                },
                "concerns": [
                    "Performance in calo",
                ],
            },
        },
    }


def test_report_contains_all_intelligence_sections() -> None:
    report = ReportBuilder().build(
        _context(),
        _decision(),
    )

    assert "INTELLIGENCE ATLETA" in report
    assert "CARICO RECENTE" in report
    assert "ADATTAMENTO AL CARICO" in report
    assert "TREND RECOVERY" in report
    assert "TREND PERFORMANCE" in report


def test_report_contains_recent_load_metrics() -> None:
    report = ReportBuilder().build(
        _context(),
        _decision(),
    )

    assert "Acute load 7d: 620.0" in report
    assert "Chronic load 28d: 2100.0" in report
    assert "Acute chronic ratio: 1.18" in report


def test_report_contains_adaptation_details() -> None:
    report = ReportBuilder().build(
        _context(),
        _decision(),
    )

    assert "Adaptation level: MODERATE" in report
    assert "Carico recente elevato" in report
    assert "Adattamento da monitorare" in report


def test_report_contains_performance_details() -> None:
    report = ReportBuilder().build(
        _context(),
        _decision(),
    )

    assert "Trend: DECLINING" in report
    assert "FTP: -4.5" in report
    assert "Performance in calo" in report


def test_report_contains_decision_reasoning() -> None:
    report = ReportBuilder().build(
        _context(),
        _decision(),
    )

    assert "Reasoning: " in report
    assert "Performance: in peggioramento" in report
    assert "Adattamento: moderato" in report


def test_report_contains_risk_and_recommended_action() -> None:
    report = ReportBuilder().build(
        _context(),
        _decision(),
    )

    assert "Risk level: CAUTION" in report
    assert (
        "Azione consigliata: "
        "Riduci moderatamente volume o intensità."
    ) in report


def test_intelligence_is_not_duplicated_as_raw_decision_field() -> None:
    report = ReportBuilder().build(
        _context(),
        _decision(),
    )

    assert "Intelligence: " not in report