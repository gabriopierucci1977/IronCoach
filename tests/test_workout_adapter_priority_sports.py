"""
Test multisport della training priority nel WorkoutAdapter.
"""

from backend.workout_adapter import WorkoutAdapter


def _context(sport: str) -> dict:
    return {
        "training": {
            "sport": sport,
            "Nome seduta": "Seduta programmata",
            "Tipo seduta": "Intervalli",
            "Zona prevista": "Z4",
            "Durata minuti": 60,
        },
    }


def _decision(
    training_priority: str,
    strategy: str = "ADAPT",
) -> dict:
    return {
        "strategy": strategy,
        "training_priority": training_priority,
    }


def test_specificity_priority_changes_swim_content() -> None:
    workout = WorkoutAdapter().adapt(
        context=_context("SWIM"),
        decision=_decision("SPECIFICITA_GARA"),
    )

    assert workout["sport_category"] == "SWIM"
    assert workout["intensity"] == "Z2-Z4 controllata"
    assert "passo gara" in workout["main_set"]
    assert "regolarità della bracciata" in workout["technical_focus"]


def test_performance_priority_changes_generic_content() -> None:
    workout = WorkoutAdapter().adapt(
        context=_context("ROWING"),
        decision=_decision("SVILUPPO_PRESTAZIONE"),
    )

    assert workout["sport_category"] == "GENERIC"
    assert workout["intensity"] == "Z3-Z4 controllata"
    assert "lavoro qualitativo controllato" in workout["main_set"]
    assert "Qualità del gesto" in workout["technical_focus"]


def test_continuity_priority_changes_bike_content() -> None:
    workout = WorkoutAdapter().adapt(
        context=_context("BIKE"),
        decision=_decision("CONTINUITA"),
    )

    assert workout["sport_category"] == "BIKE"
    assert workout["intensity"] == "Z1-Z2 controllata"
    assert "VO2max" in workout["removed_elements"]
    assert "Continuità aerobica" in workout["technical_focus"]


def test_keep_plan_preserves_priority_metadata() -> None:
    workout = WorkoutAdapter().adapt(
        context=_context("RUN"),
        decision=_decision(
            "SPECIFICITA_GARA",
            strategy="KEEP_PLAN",
        ),
    )

    assert workout == {
        "training_priority": "SPECIFICITA_GARA",
        "strategy": "KEEP_PLAN",
    }