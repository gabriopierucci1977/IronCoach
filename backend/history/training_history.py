"""
IronCoach - Training History

Gestisce lo storico degli allenamenti
e normalizza i dati provenienti da Airtable.
"""


class TrainingHistory:


    def __init__(self):

        self.sessions = []



    # -------------------------------------------------
    # ADD SESSION
    # -------------------------------------------------

    def add_session(
        self,
        session
    ):

        if not isinstance(session, dict):
            return


        normalized = self._normalize_session(
            session
        )


        self.sessions.append(
            normalized
        )



    # -------------------------------------------------
    # BULK LOAD
    # -------------------------------------------------

    def load(
        self,
        sessions
    ):

        if not isinstance(
            sessions,
            list
        ):
            return


        for session in sessions:

            self.add_session(
                session
            )



    # -------------------------------------------------
    # NORMALIZATION
    # -------------------------------------------------

    def _normalize_session(
        self,
        session
    ):


        sport = (

            session.get(
                "sport"
            )

            or session.get(
                "Sport"
            )

            or session.get(
                "Categoria sport"
            )

            or session.get(
                "Tipo sport"
            )

            or ""

        )


        sport = self._normalize_sport(
            sport
        )


        load = (

            session.get(
                "load"
            )

            or session.get(
                "Load"
            )

            or session.get(
                "Carico interno"
            )

            or session.get(
                "Carico"
            )

            or 0

        )


        duration = (

            session.get(
                "duration"
            )

            or session.get(
                "Durata minuti"
            )

            or 0

        )


        rpe = (

            session.get(
                "rpe"
            )

            or session.get(
                "RPE percepito"
            )

            or 0

        )


        date = (

            session.get(
                "date"
            )

            or session.get(
                "Data allenamento"
            )

            or ""

        )


        return {

            "sport": sport,

            "load": self._to_float(
                load
            ),

            "duration": self._to_float(
                duration
            ),

            "rpe": self._to_float(
                rpe
            ),

            "date": date,

        }



    # -------------------------------------------------
    # SPORT NORMALIZER
    # -------------------------------------------------

    def _normalize_sport(
        self,
        sport
    ):

        value = str(
            sport
        ).lower()


        if "cors" in value:
            return "run"


        if (
            "bici" in value
            or "bike" in value
            or "cicl" in value
        ):
            return "bike"


        if (
            "nuot" in value
            or "swim" in value
        ):
            return "swim"


        if (
            "forza" in value
            or "strength" in value
        ):
            return "strength"


        return value or "unknown"



    # -------------------------------------------------
    # OUTPUT
    # -------------------------------------------------

    def get_metrics(self):

        return self.sessions



    def get_sessions(self):

        return self.sessions



    def count(self):

        return len(
            self.sessions
        )



    # -------------------------------------------------
    # HELPERS
    # -------------------------------------------------

    def _to_float(
        self,
        value
    ):

        try:

            return float(
                value
            )

        except:

            return 0.0