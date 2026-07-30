"""
IronCoach - Context Builder v0.2

Costruisce il contesto completo dell'atleta
leggendo i dati da Airtable.

Integra il primo livello intelligence:

- AthleteProfileEngine

Il profilo atleta viene aggiunto al contesto,
senza modificare ancora la logica decisionale.
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


        }



        context["athlete_profile"] = (
            self.profile_engine.analyze(
                {
                    "athlete": context["athlete"]
                }
            )
        )



        return context