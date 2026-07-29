"""
IronCoach - Context Builder

Costruisce il contesto completo dell'atleta
leggendo i dati da Airtable.
"""


class ContextBuilder:

    def __init__(self, airtable_client):
        self.client = airtable_client

    def build(self):

        context = {

            "athlete": self.client.get_athlete_profile(),

            "recovery": self.client.get_latest_recovery(),

            "training": self.client.get_latest_training(),

            "nutrition": self.client.get_latest_nutrition(),

            "decision": self.client.get_latest_decision()

        }

        return context