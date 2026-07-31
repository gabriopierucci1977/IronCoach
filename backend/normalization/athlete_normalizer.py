"""
IronCoach Athlete Normalizer

Normalizza il profilo atleta proveniente da:

- Airtable
- database esterni
- input manuale

in formato interno IronCoach.

Non contiene logica coaching.
La valutazione rimane negli analyzer.
"""


class AthleteNormalizer:
    """
    Normalizzatore profilo atleta.
    """



    def normalize(
        self,
        athlete,
        source="manual",
    ):
        """
        Trasforma il profilo atleta
        nel formato IronCoach.
        """

        athlete = athlete or {}


        return {

            "source":
                source,


            "source_id":

                self._get_value(
                    athlete,
                    [
                        "id",
                        "record_id",
                        "source_id",
                    ],
                ),



            "identity":

                {

                    "name":

                        self._get_value(
                            athlete,
                            [
                                "Nome atleta",
                                "name",
                                "athlete_name",
                            ],
                        ),


                    "level":

                        self._get_value(
                            athlete,
                            [
                                "Livello atleta",
                                "level",
                                "athlete_level",
                            ],
                        ),

                },



            "goals":

                {

                    "primary":

                        self._get_value(
                            athlete,
                            [
                                "Obiettivo principale",
                                "primary_goal",
                                "goal",
                            ],
                        ),


                    "race_targets":

                        self._get_value(
                            athlete,
                            [
                                "Gare obiettivo",
                                "race_targets",
                                "target_races",
                            ],
                        ),

                },



            "physiology":

                {

                    "weight":

                        self._get_value(
                            athlete,
                            [
                                "Peso attuale kg",
                                "weight",
                            ],
                        ),


                    "height":

                        self._get_value(
                            athlete,
                            [
                                "Altezza cm",
                                "height",
                            ],
                        ),


                    "ftp":

                        self._get_value(
                            athlete,
                            [
                                "Ftp",
                                "FTP",
                                "ftp",
                            ],
                        ),


                    "css":

                        self._get_value(
                            athlete,
                            [
                                "Css",
                                "CSS",
                                "css",
                            ],
                        ),


                    "vo2max_run":

                        self._get_value(
                            athlete,
                            [
                                "Vo₂max corsa",
                                "vo2max_run",
                            ],
                        ),


                    "vo2max_bike":

                        self._get_value(
                            athlete,
                            [
                                "Vo₂max bici",
                                "vo2max_bike",
                            ],
                        ),

                },



            "constraints":

                {

                    "physical_limitations":

                        self._get_value(
                            athlete,
                            [
                                "Limitazioni fisiche",
                                "limitations",
                            ],
                        ),


                    "injury_history":

                        self._get_value(
                            athlete,
                            [
                                "Storico infortuni",
                                "injury_history",
                            ],
                        ),

                },



            "preferences":

                {

                    "availability":

                        self._get_value(
                            athlete,
                            [
                                "Disponibilità allenamento",
                                "availability",
                            ],
                        ),


                    "session_preferences":

                        self._get_value(
                            athlete,
                            [
                                "Preferenza",
                                "training_preferences",
                            ],
                        ),

                },



            "equipment":

                self._get_value(
                    athlete,
                    [
                        "Attrezzatura disponibile",
                        "equipment",
                    ],
                ),



            "raw":

                athlete,

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