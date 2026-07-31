"""
IronCoach Load Analyzer v0.3

Analizza il carico storico allenante.

Non conosce:
- Garmin
- Strava
- Airtable

Riceve esclusivamente dati già normalizzati.
"""


class LoadAnalyzer:

    LEVEL_UNKNOWN = "UNKNOWN"
    LEVEL_LOW = "LOW"
    LEVEL_NORMAL = "NORMAL"
    LEVEL_HIGH = "HIGH"



    def analyze(
        self,
        history,
    ):

        history = history or {}

        sessions = history.get(
            "training_history",
            [],
        ) or []


        total_load = 0.0

        valid_load_sessions = 0

        sport_distribution = {}



        for session in sessions:


            if not isinstance(
                session,
                dict,
            ):
                continue



            load = self._number(

                self._first_value(
                    session,
                    [
                        "training_load",
                        "load",
                        "Carico interno",
                    ],
                )

            )



            if load is None:

                continue



            sport = self._normalized_text(

                self._first_value(
                    session,
                    [
                        "sport",
                        "Sport",
                    ],
                    "unknown",
                )

            ).lower()



            if not sport:

                sport = "unknown"



            total_load += load

            valid_load_sessions += 1



            sport_distribution[sport] = (

                sport_distribution.get(
                    sport,
                    0.0,
                )
                + load

            )



        level = self._classify(
            sessions=sessions,
            valid_load_sessions=valid_load_sessions,
            total_load=total_load,
        )



        reasons = self._build_reasons(
            level=level,
            sessions=sessions,
            valid_load_sessions=valid_load_sessions,
        )



        return {


            "level":
                level,


            "total_load":
                round(
                    total_load,
                    2,
                ),


            "sessions":
                len(sessions),


            "sessions_with_load":
                valid_load_sessions,


            "sport_distribution":
                sport_distribution,


            "reasons":
                reasons,

        }




    def _first_value(
        self,
        data,
        keys,
        default=None,
    ):

        data = data or {}


        for key in keys:

            value = data.get(key)


            if value not in (
                None,
                "",
            ):
                return value


        return default




    def _classify(
        self,
        sessions,
        valid_load_sessions,
        total_load,
    ):


        if not sessions:

            return self.LEVEL_UNKNOWN



        if valid_load_sessions == 0:

            return self.LEVEL_UNKNOWN



        if total_load >= 2000:

            return self.LEVEL_HIGH



        if total_load < 500:

            return self.LEVEL_LOW



        return self.LEVEL_NORMAL




    def _build_reasons(
        self,
        level,
        sessions,
        valid_load_sessions,
    ):


        if not sessions:

            return [
                "Storico allenamenti non disponibile"
            ]



        if valid_load_sessions == 0:

            return [
                "Dati di carico storico insufficienti"
            ]



        if level == self.LEVEL_HIGH:

            return [
                "Carico storico elevato"
            ]



        if level == self.LEVEL_LOW:

            return [
                "Carico storico contenuto"
            ]



        return [
            "Carico storico nella norma"
        ]




    def _number(
        self,
        value,
    ):


        if value is None:

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

            return float(value)


        except (
            TypeError,
            ValueError,
        ):

            return None




    def _normalized_text(
        self,
        value,
    ):


        if value is None:

            return ""



        if isinstance(
            value,
            dict,
        ):

            value = value.get(
                "value",
                "",
            )



        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):

            return " ".join(

                str(item).strip()

                for item in value

                if item is not None

            ).strip()



        return str(value).strip()