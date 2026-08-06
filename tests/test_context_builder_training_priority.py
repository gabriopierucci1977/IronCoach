"""
Test ContextBuilder con training priority dall'ultima decisione.
"""

from backend.context_builder import ContextBuilder


class FakeClient:
    def get_athlete_profile(self):
        return {}

    def get_latest_recovery(self):
        return {}

    def get_latest_training(self):
        return {}

    def get_latest_nutrition(self):
        return {}

    def get_latest_decision(self):
        return {
            "Data": "2026-08-06",
            "Decisione IronCoach": "ADATTA",
            "Priorità allenante": "SPECIFICITA_GARA",
            "Strategia": "ADAPT",
        }

    def get_training_history(self):
        return []

    def get_recovery_history(self):
        return []

    def get_performance_history(self):
        return []


class EmptyGarminArchive:
    def iter_all(self):
        return iter(())


def test_context_preserves_latest_training_priority() -> None:
    context = ContextBuilder(
        FakeClient(),
        include_garmin=True,
        garmin_archive=EmptyGarminArchive(),
    ).build()

    assert context["decision"]["Data"] == "2026-08-06"
    assert (
        context["decision"]["Priorità allenante"]
        == "SPECIFICITA_GARA"
    )
    assert context["decision"]["Strategia"] == "ADAPT"


def test_context_exposes_complete_latest_decision() -> None:
    context = ContextBuilder(
        FakeClient(),
        include_garmin=False,
        garmin_archive=EmptyGarminArchive(),
    ).build()

    assert context["decision"] == {
        "Data": "2026-08-06",
        "Decisione IronCoach": "ADATTA",
        "Priorità allenante": "SPECIFICITA_GARA",
        "Strategia": "ADAPT",
    }