"""
IronCoach - Training History v0.3

Gestisce lo storico degli allenamenti.

Supporta:

- dati normalizzati IronCoach
- vecchio formato Airtable
- attività Garmin/Strava già normalizzate

Non contiene logica coaching.
"""



class TrainingHistory:


    def __init__(self):

        self.sessions = []



    # -------------------------------------------------
    # ADD SESSION
    # -------------------------------------------------


    def add_session(
        self,
        session,
    ):

        if not isinstance(
            session,
            dict,
        ):

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
        sessions,
    ):

        if not isinstance(
            sessions,
            list,
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
        session,
    ):


        sport = self._first_value(
            session,
            [
                "sport",
                "Sport",
                "Categoria sport",
                "Tipo sport",
            ],
            "",
        )



        sport = self._normalize_sport(
            sport
        )



        training_load = self._first_value(
            session,
            [
                "training_load",
                "load",
                "Load",
                "Carico interno",
                "Carico",
            ],
            None,
        )



        duration = self._first_value(
            session,
            [
                "duration_minutes",
                "duration",
                "Durata minuti",
            ],
            0,
        )



        distance = self._first_value(
            session,
            [
                "distance_km",
                "distance",
                "Distanza km",
            ],
            0,
        )



        rpe = self._first_value(
            session,
            [
                "rpe",
                "RPE percepito",
                "perceived_exertion",
            ],
            0,
        )



        date = self._first_value(
            session,
            [
                "date",
                "Data allenamento",
                "start_date",
            ],
            "",
        )

        heart_rate = self._first_value(
            session,
            [
                "heart_rate",
                "Heart rate",
                "fc",
            ],
            {},
        )



        power = self._first_value(
            session,
            [
                "power",
                "Power",
            ],
            {},
        )



        return {


            "sport":

                sport,



            # compatibilità analyzer esistenti

            "load":

                self._to_optional_float(
                    training_load
                ),



            # formato normalizzato IronCoach

            "training_load":

                self._to_optional_float(
                    training_load
                ),



            "duration":

                self._to_float(
                    duration
                ),



            "duration_minutes":

                self._to_float(
                    duration
                ),



            "distance_km":

                self._to_float(
                    distance
                ),



            "rpe":

                self._to_float(
                    rpe
                ),



            "heart_rate":

                heart_rate,



            "power":

                power,



            "date":

                date,



            "raw":

                session,

        }




    # -------------------------------------------------
    # SPORT NORMALIZER
    # -------------------------------------------------


    def _normalize_sport(
        self,
        sport,
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


    def get_metrics(
        self,
    ):

        return self.sessions




    def get_sessions(
        self,
    ):

        return self.sessions




    def count(
        self,
    ):

        return len(
            self.sessions
        )




    # -------------------------------------------------
    # HELPERS
    # -------------------------------------------------


    def _first_value(
        self,
        data,
        keys,
        default=None,
    ):

        data = data or {}



        for key in keys:


            value = data.get(
                key
            )



            if value not in (
                None,
                "",
            ):

                return value



        return default




    def _to_optional_float(
        self,
        value,
    ):
        """Convert an observed numeric value while preserving missingness."""

        if value in (
            None,
            "",
        ):
            return None

        if isinstance(
            value,
            str,
        ):
            value = (
                value
                .strip()
                .replace(
                    ",",
                    ".",
                )
            )

            if not value:
                return None

        try:
            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            return None


    def _to_float(
        self,
        value,
    ):


        if value is None:

            return 0.0



        if isinstance(
            value,
            str,
        ):

            value = (

                value
                .strip()
                .replace(
                    ",",
                    ".",
                )

            )



            if not value:

                return 0.0



        try:

            return float(
                value
            )


        except (
            TypeError,
            ValueError,
        ):

            return 0.0
