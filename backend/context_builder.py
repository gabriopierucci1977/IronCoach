"""
IronCoach - Context Builder v0.3

Costruisce il contesto completo dell'atleta
leggendo i dati da Airtable.

Integra:

- AthleteProfileEngine
- Performance History placeholder

Il livello storico è predisposto per future integrazioni:
- Garmin Connect
- Strava

La logica decisionale non viene modificata.
"""


from backend.intelligence.athlete_profile_engine import (
    AthleteProfileEngine,
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


            # Placeholder storico performance.
            # In futuro alimentato da:
            # Garmin Connect / Strava

            "performance_history": [],


            # Placeholder storico allenamenti.
            # In futuro alimentato da:
            # Garmin Connect / Strava

            "training_history": [],

        }



        context["athlete_profile"] = (
            self.profile_engine.analyze(
                {
                    "athlete": context["athlete"]
                }
            )
        )



        return context