"""
IronCoach Activity Normalizer

Trasforma attività grezze provenienti da:

- Garmin
- Strava
- input manuale

in formato standard IronCoach.

Il normalizzatore NON interpreta
il dato dal punto di vista coaching.

La valutazione rimane agli analyzer.
"""


from datetime import datetime



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

            # identificazione

            "source":
                source,


            "source_id":
                self._get_value(
                    activity,
                    [
                        "id",
                        "activity_id",
                        "source_id",
                    ],
                ),



            "date":
                self._get_value(
                    activity,
                    [
                        "date",
                        "start_date",
                        "timestamp",
                    ],
                ),



            # disciplina

            "sport":
                self._normalize_sport(
                    self._get_value(
                        activity,
                        [
                            "sport",
                            "activity_type",
                            "type",
                        ],
                    )
                ),



            # durata

            "duration_minutes":
                self._normalize_duration(
                    self._get_value(
                        activity,
                        [
                            "duration_minutes",
                            "duration",
                            "moving_time",
                        ],
                    )
                ),



            # distanza

            "distance_km":
                self._normalize_distance(
                    self._get_value(
                        activity,
                        [
                            "distance_km",
                            "distance",
                        ],
                    )
                ),



            # carico

            "training_load":
                self._get_value(
                    activity,
                    [
                        "training_load",
                        "load",
                        "tss",
                        "icu_training_load",
                    ],
                    0,
                ),



            # intensità

            "intensity":

                self._get_value(
                    activity,
                    [
                        "intensity",
                        "zone",
                    ],
                    None,
                ),



            # frequenza cardiaca

            "heart_rate":

                {

                    "average":
                        self._get_value(
                            activity,
                            [
                                "average_hr",
                                "heart_rate_average",
                            ],
                        ),


                    "max":
                        self._get_value(
                            activity,
                            [
                                "max_hr",
                                "heart_rate_max",
                            ],
                        ),

                },



            # potenza

            "power":

                {

                    "average":
                        self._get_value(
                            activity,
                            [
                                "average_power",
                                "power_average",
                            ],
                        ),


                    "normalized":
                        self._get_value(
                            activity,
                            [
                                "normalized_power",
                            ],
                        ),

                },



            # percezione atleta

            "rpe":

                self._get_value(
                    activity,
                    [
                        "rpe",
                        "perceived_exertion",
                    ],
                ),



            "notes":

                self._get_value(
                    activity,
                    [
                        "notes",
                        "comment",
                    ],
                ),



            # metadati

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


            # Garmin / Strava spesso usano metri

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


            # secondi

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