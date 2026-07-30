"""
IronCoach - Context Builder v0.4

Costruisce il contesto completo dell'atleta.

Integra:

- AthleteProfileEngine
- HistoryBuilder

Preparato per future sorgenti:

- Garmin Connect
- Strava

La logica decisionale esistente
rimane invariata.
"""


from backend.intelligence.athlete_profile_engine import (
    AthleteProfileEngine,
)

from backend.history.history_builder import (
    HistoryBuilder,
)



class ContextBuilder:



    def __init__(
        self,
        airtable_client,
    ):

        self.client = airtable_client


        self.profile_engine = (
            AthleteProfileEngine()
        )


        self.history_builder = (
            HistoryBuilder()
        )



    def build(self):


        context = {


            "athlete": (
                self.client.get_athlete_profile()
            ),


            "recovery": (
                self.client.get_latest_recovery()
            ),


            "training": (
                self.client.get_latest_training()
            ),


            "nutrition": (
                self.client.get_latest_nutrition()
            ),


            "decision": (
                self.client.get_latest_decision()
            ),


            # Storico predisposto per:
            # Garmin Connect / Strava

            "training_history": [],

            "recovery_history": [],

            "performance_history": [],

        }



        context["athlete_profile"] = (
            self.profile_engine.analyze(
                {
                    "athlete": context["athlete"]
                }
            )
        )



        context["history"] = (
            self.history_builder.build(
                {

                    "training_history":
                        context["training_history"],

                    "recovery_history":
                        context["recovery_history"],

                    "performance_history":
                        context["performance_history"],

                }
            )
        )



        return context