"""
IronCoach Activity Normalizer

Trasforma attività grezze provenienti da:

- Garmin
- Strava
- Airtable
- input manuale

in formato standard IronCoach.

Il normalizzatore NON interpreta
il dato dal punto di vista coaching.

La valutazione rimane agli analyzer.
"""


class ActivityNormalizer:
    """
    Normalizzatore attività IronCoach.
    """



    def normalize(
        self,
        activity,
        source="manual",
    ):
        """
        Converte un'attività grezza
        nel formato IronCoach.
        """

        activity = activity or {}



        return {

            "source":
                source,



            "source_id":

                self._get_value(
                    activity,
                    [
                        "id",
                        "activity_id",
                        "source_id",
                        "Record ID",
                    ],
                ),



            "date":

                self._get_value(
                    activity,
                    [
                        "date",
                        "Date",
                        "start_date",
                        "timestamp",
                        "Data allenamento",
                    ],
                ),



            "sport":

                self._normalize_sport(

                    self._get_value(
                        activity,
                        [

                            "sport",
                            "Sport",
                            "activity_type",
                            "type",

                        ],
                    )

                ),



            "duration_minutes":

                self._normalize_duration(

                    self._get_value(
                        activity,
                        [

                            "duration_minutes",
                            "Durata minuti",
                            "duration",
                            "moving_time",

                        ],
                    )

                ),



            "distance_km":

                self._normalize_distance(

                    self._get_value(
                        activity,
                        [

                            "distance_km",
                            "Distanza km",
                            "distance",

                        ],
                    )

                ),



            "training_load":

                self._get_value(
                    activity,
                    [

                        "training_load",
                        "Carico interno",
                        "load",
                        "tss",
                        "icu_training_load",

                    ],
                    0,
                ),



            "intensity":

                self._get_value(
                    activity,
                    [

                        "intensity",
                        "zone",
                        "Zona prevista",

                    ],
                    None,
                ),



            "heart_rate":

                {

                    "average":

                        self._get_value(
                            activity,
                            [

                                "average_hr",
                                "heart_rate_average",
                                "FC media",

                            ],
                        ),



                    "max":

                        self._get_value(
                            activity,
                            [

                                "max_hr",
                                "heart_rate_max",
                                "FC massima",

                            ],
                        ),

                },



            "power":

                {

                    "average":

                        self._get_value(
                            activity,
                            [

                                "average_power",
                                "power_average",
                                "Potenza media",

                            ],
                        ),



                    "normalized":

                        self._get_value(
                            activity,
                            [

                                "normalized_power",
                                "Potenza normalizzata",

                            ],
                        ),

                },



            "rpe":

                self._get_value(
                    activity,
                    [

                        "rpe",
                        "RPE percepito",
                        "perceived_exertion",

                    ],
                ),



            "notes":

                self._get_value(
                    activity,
                    [

                        "notes",
                        "Note personali",
                        "comment",

                    ],
                ),



            "raw":

                activity,

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



    def _normalize_distance(
        self,
        value,
    ):

        if value is None:
            return 0


        try:

            value = float(value)


            if value > 1000:

                return round(
                    value / 1000,
                    2,
                )


            return round(
                value,
                2,
            )


        except Exception:

            return 0



    def _normalize_duration(
        self,
        value,
    ):

        if value is None:
            return 0


        try:

            value = float(value)


            if value > 300:

                return round(
                    value / 60,
                    2,
                )


            return value


        except Exception:

            return 0



    def _normalize_sport(
        self,
        sport,
    ):

        if not sport:
            return "UNKNOWN"



        sport = str(
            sport
        ).lower()



        mapping = {

            "run":
                "RUN",

            "running":
                "RUN",

            "corsa":
                "RUN",



            "bike":
                "BIKE",

            "cycling":
                "BIKE",

            "bici":
                "BIKE",



            "swim":
                "SWIM",

            "nuoto":
                "SWIM",



            "strength":
                "STRENGTH",

            "forza":
                "STRENGTH",

        }



        return mapping.get(
            sport,
            sport.upper(),
        )