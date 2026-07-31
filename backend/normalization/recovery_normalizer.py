"""
IronCoach Recovery Normalizer

Normalizza dati di recupero provenienti da:

- Garmin
- Whoop
- Oura
- input manuale

in formato interno IronCoach.

Il modulo NON interpreta il recupero.
La valutazione rimane agli analyzer.
"""


class RecoveryNormalizer:
    """
    Normalizzatore dati recovery.
    """



    def normalize(
        self,
        recovery,
        source="manual",
    ):
        """
        Converte dati grezzi recovery
        nel formato IronCoach.
        """

        recovery = recovery or {}


        return {

            # origine dato

            "source":
                source,


            "source_id":

                self._get_value(
                    recovery,
                    [
                        "id",
                        "recovery_id",
                        "source_id",
                    ],
                ),



            "date":

                self._get_value(
                    recovery,
                    [
                        "date",
                        "timestamp",
                        "day",
                    ],
                ),



            # sonno

            "sleep":

                {

                    "score":

                        self._get_value(
                            recovery,
                            [
                                "sleep_score",
                                "sleepScore",
                            ],
                        ),


                    "hours":

                        self._get_value(
                            recovery,
                            [
                                "sleep_hours",
                                "hours_sleep",
                                "duration",
                            ],
                        ),


                    "quality":

                        self._get_value(
                            recovery,
                            [
                                "sleep_quality",
                            ],
                        ),

                },



            # recupero fisiologico

            "readiness":

                self._get_value(
                    recovery,
                    [
                        "readiness",
                        "recovery_score",
                        "body_battery",
                    ],
                ),



            "hrv":

                self._get_value(
                    recovery,
                    [
                        "hrv",
                        "hrv_score",
                        "heart_rate_variability",
                    ],
                ),



            "resting_hr":

                self._get_value(
                    recovery,
                    [
                        "resting_hr",
                        "resting_heart_rate",
                        "rhr",
                    ],
                ),



            "stress":

                self._get_value(
                    recovery,
                    [
                        "stress",
                        "stress_score",
                    ],
                ),



            # percezione atleta

            "fatigue":

                self._get_value(
                    recovery,
                    [
                        "fatigue",
                        "fatigue_score",
                    ],
                ),



            "soreness":

                self._get_value(
                    recovery,
                    [
                        "soreness",
                        "muscle_soreness",
                        "pain",
                    ],
                ),



            "energy":

                self._get_value(
                    recovery,
                    [
                        "energy",
                        "morning_energy",
                    ],
                ),



            "notes":

                self._get_value(
                    recovery,
                    [
                        "notes",
                        "comment",
                    ],
                ),



            # dato originale

            "raw":

                recovery,

        }



    # ==================================================
    # HELPERS
    # ==================================================


    def _get_value(
        self,
        data,
        keys,
        default=None,
    ):

        for key in keys:

            value = data.get(key)


            if value not in (
                None,
                "",
            ):
                return value


        return default