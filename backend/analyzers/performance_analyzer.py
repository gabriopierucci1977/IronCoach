"""
IronCoach Performance Analyzer v0.1

Analizza l'evoluzione prestativa dell'atleta.

Non decide.
Non modifica allenamenti.

Produce informazioni utilizzabili
dal livello intelligence.
"""


class PerformanceAnalyzer:


    TREND_IMPROVING = "IMPROVING"
    TREND_STABLE = "STABLE"
    TREND_DECLINING = "DECLINING"
    TREND_UNKNOWN = "UNKNOWN"



    def analyze(
        self,
        history,
    ):

        history = history or {}


        records = history.get(
            "performance_history",
            []
        )


        if len(records) < 2:

            return {

                "trend": self.TREND_UNKNOWN,

                "metrics": {},

                "strengths": [],

                "concerns": [],

                "reasons": [
                    "Storico performance insufficiente"
                ]

            }



        first = records[0]

        last = records[-1]


        metrics = {}

        improvements = 0

        declines = 0



        for key in (
            "vo2max_run",
            "vo2max_bike",
            "ftp",
            "css",
        ):

            old = self._number(
                first.get(key)
            )

            new = self._number(
                last.get(key)
            )


            if old is None or new is None:

                continue


            change = (
                (new - old)
                /
                old
                *
                100
            )


            metrics[key] = round(
                change,
                1
            )


            if change > 2:

                improvements += 1


            elif change < -2:

                declines += 1



        if improvements > declines:

            trend = self.TREND_IMPROVING


        elif declines > improvements:

            trend = self.TREND_DECLINING


        else:

            trend = self.TREND_STABLE



        strengths = []

        concerns = []


        if trend == self.TREND_IMPROVING:

            strengths.append(
                "Performance in crescita"
            )


        elif trend == self.TREND_DECLINING:

            concerns.append(
                "Performance in calo"
            )



        return {

            "trend": trend,

            "metrics": metrics,

            "strengths": strengths,

            "concerns": concerns,

            "reasons": [
                f"Trend performance: {trend}"
            ]

        }



    def _number(
        self,
        value,
    ):

        if value is None:

            return None


        try:

            return float(value)


        except (
            TypeError,
            ValueError,
        ):

            return None