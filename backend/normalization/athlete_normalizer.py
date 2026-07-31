"""
IronCoach Athlete Normalizer v0.2.3

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
                        "Record ID",
                    ],
                ),



            "identity":

                {

                    "name":

                        self._get_value(
                            athlete,
                            [
                                "Nome atleta",
                                "Nome Atleta",
                                "name",
                                "athlete_name",
                            ],
                        ),



                    "level":

                        self._get_value(
                            athlete,
                            [
                                "Livello atleta",
                                "Livello Atleta",
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
                                "Obiettivo Principale",
                                "Obiettivi principali",
                                "Obiettivi Principali",
                                "primary_goal",
                                "goal",
                            ],
                        ),



                    "race_targets":

                        self._get_value(
                            athlete,
                            [
                                "Gare obiettivo",
                                "Gare Obiettivo",
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
                                "Peso Attuale kg",
                                "weight",
                            ],
                        ),



                    "height":

                        self._get_value(
                            athlete,
                            [
                                "Altezza cm",
                                "Altezza Cm",
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
                                "VO₂max corsa",
                                "Vo2max corsa",
                                "VO2max corsa",
                                "vo2max_run",
                            ],
                        ),



                    "vo2max_bike":

                        self._get_value(
                            athlete,
                            [
                                "Vo₂max bici",
                                "VO₂max bici",
                                "Vo2max bici",
                                "VO2max bici",
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
                                "Limitazioni Fisiche",
                                "limitations",
                            ],
                        ),



                    "injury_history":

                        self._get_value(
                            athlete,
                            [
                                "Storico infortuni",
                                "Storico Infortuni",
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
                                "Disponibilita allenamento",
                                "availability",
                            ],
                        ),



                    "session_preferences":

                        self._get_value(
                            athlete,
                            [
                                "Preferenza",
                                "Preferenze allenamento",
                                "training_preferences",
                            ],
                        ),



                    "training_distribution":

                        self._get_value(
                            athlete,
                            [
                                "Allenamento distribuito tra",
                                "Allenamento distribuito",
                                "training_distribution",
                            ],
                        ),

                },
            # ==================================================
            # CAMPO ESPOSTO AL LIVELLO PRINCIPALE
            # ==================================================


            "training_distribution":

                self._get_value(
                    athlete,
                    [
                        "Allenamento distribuito tra",
                        "Allenamento distribuito",
                        "training_distribution",
                    ],
                ),



            "equipment":

                self._get_value(
                    athlete,
                    [
                        "Attrezzatura disponibile",
                        "Attrezzatura Disponibile",
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

        if not isinstance(
            data,
            dict,
        ):

            return default



        # -------------------------------------------------
        # MATCH ESATTO
        # -------------------------------------------------


        for key in keys:

            value = data.get(
                key
            )


            if value not in (
                None,
                "",
            ):

                return value



        # -------------------------------------------------
        # MATCH NORMALIZZATO
        # -------------------------------------------------


        normalized_fields = {}


        for original_key in data.keys():


            if original_key is None:

                continue



            normalized_key = (

                str(original_key)
                .strip()
                .lower()
                .replace(" ", "")
                .replace("_", "")

            )


            normalized_fields[
                normalized_key
            ] = original_key




        for key in keys:


            normalized_key = (

                str(key)
                .strip()
                .lower()
                .replace(" ", "")
                .replace("_", "")

            )



            real_key = normalized_fields.get(
                normalized_key
            )



            if real_key:


                value = data.get(
                    real_key
                )


                if value not in (
                    None,
                    "",
                ):

                    return value



        return default
