"""
IronCoach - Airtable Client

Gestisce lettura e scrittura
verso Airtable.
"""

from pyairtable import Api

from config.settings import AIRTABLE_API_KEY, AIRTABLE_BASE_ID


class AirtableClient:

    def __init__(self):
        self.api = Api(AIRTABLE_API_KEY)
        self.base = self.api.base(AIRTABLE_BASE_ID)

    # -------------------------------------------------
    # CONNECTION
    # -------------------------------------------------

    def test_connection(self):
        try:
            tables = self.base.tables()

            print("=" * 60)
            print("✅ Connessione ad Airtable riuscita")
            print("=" * 60)

            print("\nTabelle trovate:\n")

            for table in tables:
                print(f"- {table.name}")

            return True

        except Exception as error:
            print(error)
            return False

    # -------------------------------------------------
    # INTERNAL READERS
    # -------------------------------------------------

    def _get_first_record(self, table_name):
        table = self.base.table(table_name)

        record = table.first()

        if not record:
            return {}

        return record.get(
            "fields",
            {},
        )

    def _get_latest_record(
        self,
        table_name,
        date_field=None,
    ):
        table = self.base.table(table_name)

        records = table.all()

        if not records:
            return {}

        if date_field:
            record = max(
                records,
                key=lambda r: (
                    r.get("fields", {}).get(date_field, ""),
                    r.get(
                        "createdTime",
                        "",
                    ),
                ),
            )

        else:
            record = max(
                records,
                key=lambda r: r.get(
                    "createdTime",
                    "",
                ),
            )

        return record.get(
            "fields",
            {},
        )

    def _get_history(
        self,
        table_name,
        limit=100,
        date_field=None,
    ):
        table = self.base.table(table_name)

        records = table.all()

        if not records:
            return []

        data = [
            r.get(
                "fields",
                {},
            )
            for r in records
        ]

        if date_field:
            data.sort(
                key=lambda x: x.get(
                    date_field,
                    "",
                )
            )

        return data[-limit:]

    # -------------------------------------------------
    # PROFILE
    # -------------------------------------------------

    def get_athlete_profile(self):
        return self._get_first_record(
            "Athlete Profile"
        )

    # -------------------------------------------------
    # LATEST DATA
    # -------------------------------------------------

    def get_latest_recovery(self):
        return self._get_latest_record(
            "Recovery Log"
        )

    def get_latest_training(self):
        return self._get_latest_record(
            "Training Log",
            "Data allenamento",
        )

    def get_latest_nutrition(self):
        return self._get_latest_record(
            "Nutrition Log"
        )

    def get_latest_decision(self):
        return self._get_latest_record(
            "Decision Log",
            "Data",
        )

    # -------------------------------------------------
    # HISTORY
    # -------------------------------------------------

    def get_training_history(
        self,
        limit=100,
    ):
        return self._get_history(
            "Training Log",
            limit,
            "Data allenamento",
        )

    def get_recovery_history(
        self,
        limit=100,
    ):
        return self._get_history(
            "Recovery Log",
            limit,
            "Data",
        )

    def get_performance_history(self):
        """
        Restituisce lo stato performance corrente del profilo atleta.

        Questo non rappresenta ancora uno storico temporale: finché non
        saranno disponibili almeno due rilevazioni datate della stessa
        metrica, il PerformanceAnalyzer continuerà correttamente a
        restituire trend UNKNOWN.
        """

        athlete = self.get_athlete_profile()

        if not athlete:
            return []

        return [
            {
                "ftp": athlete.get("FTP"),
                "vo2max_run": athlete.get("VO₂max corsa"),
                "vo2max_bike": athlete.get("VO₂max bici"),
                "css": athlete.get("CSS"),
            }
        ]

    # -------------------------------------------------
    # WRITE
    # -------------------------------------------------

    def save_decision(
        self,
        fields,
    ):
        table = self.base.table(
            "Decision Log"
        )

        record = table.create(
            fields
        )

        print("\n")
        print("=" * 60)
        print("✅ DECISIONE SALVATA SU AIRTABLE")
        print("=" * 60)
        print(
            f"Record ID: {record.get('id')}"
        )
        print("=" * 60)

        return record