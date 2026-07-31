"""
IronCoach Recovery History v0.2

Modello dello storico recupero atleta.

Supporta:

- dati normalizzati IronCoach
- vecchio formato Airtable

Non contiene logica coaching.
"""


class RecoveryHistory:



    def __init__(
        self,
        records=None,
    ):

        self.records = records or []



    # -------------------------------------------------
    # ADD RECORD
    # -------------------------------------------------


    def add_record(
        self,
        record,
    ):

        if not isinstance(
            record,
            dict,
        ):

            return



        normalized = self._normalize_record(
            record
        )



        self.records.append(
            normalized
        )



    # -------------------------------------------------
    # NORMALIZATION
    # -------------------------------------------------


    def _normalize_record(
        self,
        record,
    ):


        sleep = record.get(
            "sleep",
            {},
        ) or {}



        return {


            "date":

                self._first_value(
                    record,
                    [
                        "date",
                        "day",
                        "timestamp",
                    ],
                    "",
                ),



            # campo standard per trend analyzer

            "recovery_score":

                self._first_value(
                    record,
                    [
                        "readiness",
                        "recovery_score",
                        "Recovery Score",
                        "Recovery score",
                    ],
                    None,
                ),



            "readiness":

                self._first_value(
                    record,
                    [
                        "readiness",
                        "recovery_score",
                    ],
                    None,
                ),



            "sleep": {


                "score":

                    self._first_value(
                        sleep,
                        [
                            "score",
                            "sleep_score",
                        ],
                        self._first_value(
                            record,
                            [
                                "sleep_score",
                                "Sleep Score",
                            ],
                            None,
                        ),
                    ),



                "hours":

                    self._first_value(
                        sleep,
                        [
                            "hours",
                            "sleep_hours",
                        ],
                        self._first_value(
                            record,
                            [
                                "sleep_hours",
                                "Ore sonno",
                            ],
                            None,
                        ),
                    ),

            },



            "stress":

                self._first_value(
                    record,
                    [
                        "stress",
                        "Stress",
                    ],
                    None,
                ),



            "energy":

                self._first_value(
                    record,
                    [
                        "energy",
                        "morning_energy",
                        "Energia mattutina",
                    ],
                    None,
                ),



            "soreness":

                self._first_value(
                    record,
                    [
                        "soreness",
                        "pain",
                        "Dolore generale",
                    ],
                    None,
                ),



            "raw":

                record,

        }



    # -------------------------------------------------
    # OUTPUT
    # -------------------------------------------------


    def get_records(
        self,
    ):

        return self.records



    def count(
        self,
    ):

        return len(
            self.records
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