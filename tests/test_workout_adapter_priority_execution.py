"""
Test dell'applicazione operativa della training priority
nel WorkoutAdapter.
"""

from backend.workout_adapter import WorkoutAdapter


def _context(
    sport: str = "RUN",
    duration: int = 60,
) -> dict:
    return {
        "training": {
            "sport": sport,
            "Nome seduta": "Seduta qualità",
            "Tipo seduta": "Intervalli",
            "Zona prevista": "Z4",
            "Durata minuti": duration,
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


def test_event_priority_changes_run_content() -> None:
    workout = WorkoutAdapter().adapt(
        context=_context("RUN"),
        decision=_decision("SPECIFICITA_GARA"),
    )

    assert workout["strategy"] == "ADAPT"
    assert workout["training_priority"] == "SPECIFICITA_GARA"
    assert workout["intensity"] == "Z2-Z4 controllata"
    assert "ritmo gara" in workout["main_set"]
    assert "Economia di corsa" in workout["technical_focus"]


def test_performance_priority_changes_bike_content() -> None:
    workout = WorkoutAdapter().adapt(
        context=_context("BIKE"),
        decision=_decision("SVILUPPO_PRESTAZIONE"),
    )

    assert workout["strategy"] == "ADAPT"
    assert workout["training_priority"] == "SVILUPPO_PRESTAZIONE"
    assert workout["intensity"] == "Z3-Z4 controllata"
    assert "intervalli controllati" in workout["main_set"]
    assert "Qualità della potenza" in workout["technical_focus"]


def test_wellness_priority_limits_intensity() -> None:
    workout = WorkoutAdapter().adapt(
        context=_context("RUN"),
        decision=_decision("CONTINUITA"),
    )

    assert workout["strategy"] == "ADAPT"
    assert workout["training_priority"] == "CONTINUITA"
    assert workout["intensity"] == "Z1-Z2 controllata"
    assert "VO2max" in workout["removed_elements"]
    assert "Continuità aerobica" in workout["technical_focus"]


def test_recovery_priority_changes_adapted_content() -> None:
    workout = WorkoutAdapter().adapt(
        context=_context("RUN"),
        decision=_decision("RIPRISTINO"),
    )

    assert workout["strategy"] == "ADAPT"
    assert workout["training_priority"] == "RIPRISTINO"
    assert workout["intensity"] == "Z1 molto facile"
    assert "recupero attivo" in workout["main_set"]
    assert "Qualsiasi lavoro di qualità" in workout["removed_elements"]


def test_reduce_load_keeps_safety_precedence() -> None:
    workout = WorkoutAdapter().adapt(
        context=_context("RUN"),
        decision=_decision(
            "SVILUPPO_PRESTAZIONE",
            strategy="REDUCE_LOAD",
        ),
    )

    assert workout["strategy"] == "REDUCE_LOAD"
    assert workout["intensity"] == "Z1-Z2 facile"
    assert "soglia" in workout["removed_elements"].lower()
    assert "Z3-Z4 controllata" not in workout["main_set"]


def test_recovery_strategy_keeps_safety_precedence() -> None:
    workout = WorkoutAdapter().adapt(
        context=_context("BIKE"),
        decision=_decision(
            "SPECIFICITA_GARA",
            strategy="RECOVERY",
        ),
    )

    assert workout["strategy"] == "RECOVERY"
    assert workout["intensity"] == "Z1 molto facile"
    assert "rigeneranti" in workout["main_set"]
    assert "potenza gara" not in workout["main_set"]