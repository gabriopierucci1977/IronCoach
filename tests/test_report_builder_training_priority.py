"""
Test della training priority nel report finale.
"""

from backend.report_builder import ReportBuilder


def test_report_shows_training_priority_in_decision() -> None:
    report = ReportBuilder().build(
        context={
            "athlete_profile": {},
            "recovery": {},
            "training": {},
            "nutrition": {},
        },
        decision={
            "strategy": "ADAPT",
            "training_priority": "SPECIFICITA_GARA",
            "reason": "Test",
            "recommended_action": "Test",
        },
    )

    assert "DECISIONE DEL COACH" in report
    assert "Priorità allenante: SPECIFICITA_GARA" in report


def test_report_shows_priority_metadata_in_modified_workout() -> None:
    report = ReportBuilder().build(
        context={
            "athlete_profile": {},
            "recovery": {},
            "training": {},
            "nutrition": {},
        },
        decision={
            "strategy": "ADAPT",
            "training_priority": "SVILUPPO_PRESTAZIONE",
            "modified_workout": {
                "strategy": "ADAPT",
                "training_priority": "SVILUPPO_PRESTAZIONE",
                "planned_zone": "Z3-Z4",
                "stimulus_adjustment": {
                    "type": "QUALITY",
                    "focus": "Qualità dello stimolo allenante.",
                },
                "goal_adjustment": {
                    "goal_type": "PERFORMANCE",
                },
                "intensity_adjustment": {
                    "goal_type": "PERFORMANCE",
                },
            },
        },
    )

    assert "ALLENAMENTO MODIFICATO" in report
    assert "Priorità allenante: SVILUPPO_PRESTAZIONE" in report
    assert "Zona pianificata: Z3-Z4" in report
    assert "Adattamento stimolo:" in report
    assert "Type: QUALITY" in report
    assert "Adattamento obiettivo:" in report
    assert "Adattamento intensità:" in report