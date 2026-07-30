"""
IronCoach Training History v0.1

Modello neutro dello storico allenamenti.

Non conosce:
- Garmin
- Strava
- Airtable

Riceve dati già normalizzati.
"""


class TrainingHistory:


    def __init__(
        self,
        sessions=None,
    ):

        self.sessions = sessions or []



    def add_session(
        self,
        session,
    ):

        self.sessions.append(
            session
        )



    def get_sessions(self):

        return self.sessions



    def count(self):

        return len(
            self.sessions
        )