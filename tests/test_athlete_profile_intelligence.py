from backend.context_builder import ContextBuilder


class FakeClient:

    def get_athlete_profile(self):
        return {
            "Livello atleta": "Age Group",
            "Sport principale": "Triathlon",
            "Obiettivi principali": "Ironman",
            "Gare obiettivo": "Ironman Italia",
            "Disponibilità allenamento": "Quotidianamente",
            "Anni di attività sportiva": 10,
        }

    def get_latest_recovery(self):
        return {}

    def get_latest_training(self):
        return {}

    def get_latest_nutrition(self):
        return {}

    def get_latest_decision(self):
        return {}

    def get_training_history(self):
        return []

    def get_recovery_history(self):
        return []

    def get_performance_history(self):
        return []


def test_context_contains_athlete_profile_intelligence():

    context = ContextBuilder(
        FakeClient(),
        include_garmin=False,
    ).build()

    assert (
        "athlete_profile_intelligence"
        in context
    )

    assert (
        context["athlete_profile_intelligence"]
        ["athlete_type"]
        ==
        "Triatleta Age Group endurance multidisciplinare"
    )