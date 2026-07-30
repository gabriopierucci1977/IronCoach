"""
IronCoach Load Analyzer v0.1

Analizzatore del carico storico allenante.

Non conosce:
- Garmin
- Strava
- Airtable

Riceve dati già normalizzati.
"""


class LoadAnalyzer:


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
            []
        )


        total_load = 0

        sport_distribution = {}


        for session in sessions:

            load = self._number(
                session.get(
                    "load"
                )
            )


            sport = str(
                session.get(
                    "sport",
                    "unknown"
                )
            ).lower()


            if load:

                total_load += load


                sport_distribution[sport] = (
                    sport_distribution.get(
                        sport,
                        0
                    )
                    + load
                )



        level = self._classify(
            total_load
        )


        reasons = []


        if level == self.LEVEL_HIGH:

            reasons.append(
                "Carico storico elevato"
            )


        elif level == self.LEVEL_LOW:

            reasons.append(
                "Carico storico contenuto"
            )


        else:

            reasons.append(
                "Carico storico nella norma"
            )



        return {

            "level": level,

            "total_load": total_load,

            "sessions": len(
                sessions
            ),

            "sport_distribution": (
                sport_distribution
            ),

            "reasons": reasons,

        }



    def _classify(
        self,
        total_load,
    ):

        if total_load >= 2000:

            return self.LEVEL_HIGH


        if total_load < 500:

            return self.LEVEL_LOW


        return self.LEVEL_NORMAL



    def _number(
        self,
        value,
    ):

        if value is None:

            return 0


        try:

            return float(value)


        except (
            TypeError,
            ValueError,
        ):

            return 0