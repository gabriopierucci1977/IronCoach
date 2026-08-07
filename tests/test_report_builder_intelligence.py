"""
Test ReportBuilder per intelligence e decisione finale.

Verifica che il report esponga senza perdere informazioni:

- carico recente;
- adattamento;
- trend recovery;
- trend performance;
- dettagli metriche performance;
- reasoning decisionale;
- rischio e azione consigliata;
- warning di freschezza strutturati con priorità;
- fallback ai warning legacy;
- assenza della sezione warning quando non necessaria.
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
                "details": {
                    "ftp": {
                        "start": 280,
                        "end": 267.4,
                        "change_percent": -4.5,
                    },
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


def test_report_contains_performance_metric_history_details() -> None:
    report = ReportBuilder().build(
        _context(),
        _decision(),
    )

    assert "Start: 280" in report
    assert "End: 267.4" in report
    assert "Change percent: -4.5" in report


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


def test_coach_summary_reads_recovery_state_from_raw_data() -> None:
    context = _context()

    context["recovery"] = {
        "readiness": 69,
        "sleep": {
            "score": 70,
            "hours": 6,
        },
        "raw": {
            "Stato recovery": "GIALLO",
            "Recovery score": 69,
        },
    }

    report = ReportBuilder().build(
        context,
        _decision(),
    )

    assert (
        "• Stato recovery: GIALLO, "
        "Recovery Score 69"
    ) in report


def test_report_contains_improving_performance_details() -> None:
    decision = _decision()

    decision["intelligence"]["performance"] = {
        "trend": "IMPROVING",
        "metrics": {
            "ftp": 3.9,
        },
        "details": {
            "ftp": {
                "start": 255,
                "end": 265,
                "change_percent": 3.9,
            },
        },
        "strengths": [
            "Performance in crescita",
        ],
        "concerns": [],
    }

    report = ReportBuilder().build(
        _context(),
        decision,
    )

    assert "Trend: IMPROVING" in report
    assert "FTP: 3.9" in report
    assert "Performance in crescita" in report
    assert "Start: 255" in report
    assert "End: 265" in report


def test_structured_freshness_reasons_have_priority() -> None:
    context = _context()
    context["data_freshness"] = {
        "level": "MODERATE",
        "reasons": [
            (
                "Allenamento: dato obsoleto di 8 giorni "
                "(data 2026-07-30, soglia 7 giorni)"
            ),
        ],
    }
    context["context_warnings"] = [
        "Recovery: warning legacy da ignorare",
    ]

    report = ReportBuilder().build(
        context,
        _decision(),
    )

    assert "ATTENZIONE DATI" in report
    assert (
        "• Allenamento: dato obsoleto di 8 giorni "
        "(data 2026-07-30, soglia 7 giorni)"
    ) in report
    assert "warning legacy da ignorare" not in report


def test_context_warnings_are_used_as_fallback() -> None:
    context = _context()
    context["context_warnings"] = [
        "Archivio Garmin non disponibile",
    ]

    report = ReportBuilder().build(
        context,
        _decision(),
    )

    assert "ATTENZIONE DATI" in report
    assert "• Archivio Garmin non disponibile" in report


def test_report_omits_warning_section_without_reasons() -> None:
    context = _context()
    context["data_freshness"] = {
        "level": "LOW",
        "reasons": [],
    }
    context["context_warnings"] = []

    report = ReportBuilder().build(
        context,
        _decision(),
    )

    assert "ATTENZIONE DATI" not in report