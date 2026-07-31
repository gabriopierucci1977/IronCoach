"""
IronCoach Recovery Normalizer

Normalizza dati di recupero provenienti da:

- Garmin
- Whoop
- Oura
- Airtable
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


            "source":
                source,



            "source_id":

                self._get_value(
                    recovery,
                    [
                        "id",
                        "recovery_id",
                        "source_id",
                        "Record ID",
                    ],
                ),



            "date":

                self._get_value(
                    recovery,
                    [
                        "date",
                        "Data",
                        "timestamp",
                        "day",
                    ],
                ),



            # ==================================================
            # SONNO
            # ==================================================

            "sleep":

                {

                    "score":

                        self._get_value(
                            recovery,
                            [

                                "sleep_score",
                                "sleepScore",
                                "Sleep Score",

                            ],
                        ),



                    "hours":

                        self._get_value(
                            recovery,
                            [

                                "sleep_hours",
                                "hours_sleep",
                                "duration",
                                "Ore sonno",

                            ],
                        ),



                    "quality":

                        self._get_value(
                            recovery,
                            [

                                "sleep_quality",
                                "Qualità sonno",

                            ],
                        ),

                },



            # ==================================================
            # RECUPERO FISIOLOGICO
            # ==================================================

            "readiness":

                self._get_value(
                    recovery,
                    [

                        "readiness",
                        "recovery_score",
                        "Recovery Score",
                        "body_battery",

                    ],
                ),



            "hrv":

                self._get_value(
                    recovery,
                    [

                        "hrv",
                        "HRV",
                        "hrv_score",
                        "heart_rate_variability",

                    ],
                ),



            "resting_hr":

                self._get_value(
                    recovery,
                    [

                        "resting_hr",
                        "Resting HR",
                        "resting_heart_rate",
                        "rhr",

                    ],
                ),



            "stress":

                self._get_value(
                    recovery,
                    [

                        "stress",
                        "Stress",
                        "stress_score",

                    ],
                ),



            # ==================================================
            # PERCEZIONE ATLETA
            # ==================================================

            "fatigue":

                self._get_value(
                    recovery,
                    [

                        "fatigue",
                        "fatigue_score",
                        "Fatica",

                    ],
                ),



            "soreness":

                self._get_value(
                    recovery,
                    [

                        "soreness",
                        "muscle_soreness",
                        "pain",
                        "Dolore generale",
                        "Pain Score",

                    ],
                ),



            "energy":

                self._get_value(
                    recovery,
                    [

                        "energy",
                        "morning_energy",
                        "Energia mattutina",

                    ],
                ),



            "notes":

                self._get_value(
                    recovery,
                    [

                        "notes",
                        "Note dell'atleta",
                        "comment",
                        "Commento alla decisione Coachh",

                    ],
                ),



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