"""
IronCoach - Airtable Client

Gestisce lettura e scrittura verso Airtable.
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

    def _get_first_record(
        self,
        table_name,
    ):
        table = self.base.table(
            table_name
        )

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
        table = self.base.table(
            table_name
        )

        records = table.all()

        if not records:
            return {}

        if date_field:
            record = max(
                records,
                key=lambda item: (
                    str(
                        item.get(
                            "fields",
                            {},
                        ).get(
                            date_field,
                            "",
                        )
                        or ""
                    ),
                    item.get(
                        "createdTime",
                        "",
                    ),
                ),
            )
        else:
            record = max(
                records,
                key=lambda item: item.get(
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
        table = self.base.table(
            table_name
        )

        records = table.all()

        if not records:
            return []

        data = [
            record.get(
                "fields",
                {},
            )
            for record in records
        ]

        if date_field:
            data.sort(
                key=lambda item: str(
                    item.get(
                        date_field,
                        "",
                    )
                    or ""
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
            "Recovery Log",
            "Data",
        )

    def get_latest_training(self):
        return self._get_latest_record(
            "Training Log",
            "Data allenamento",
        )

    def get_latest_nutrition(self):
        return self._get_latest_record(
            "Nutrition Log",
            "Data",
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
        Legge lo storico verticale dalla tabella Performance Log.

        Ignora record vuoti o incompleti. Se la tabella è vuota,
        mantiene il fallback sul profilo atleta.
        """

        table = self.base.table(
            "Performance Log"
        )

        records = table.all() or []
        performance = []

        for record in records:
            fields = record.get(
                "fields",
                {},
            )

            date = fields.get(
                "Data"
            )
            metric = fields.get(
                "Metrica"
            )
            value = fields.get(
                "Valore"
            )

            if (
                date in (None, "")
                or metric in (None, "")
                or value in (None, "")
            ):
                continue

            item = {
                "date": date,
                "metric": metric,
                "value": value,
            }

            note = fields.get(
                "Note"
            )

            if note not in (None, ""):
                item["note"] = note

            performance.append(
                item
            )

        performance.sort(
            key=lambda item: str(
                item.get(
                    "date"
                )
                or ""
            )
        )

        if performance:
            return performance

        athlete = self.get_athlete_profile()

        if not athlete:
            return []

        return [
            {
                "ftp": athlete.get(
                    "FTP"
                ),
                "vo2max_run": athlete.get(
                    "VO₂max corsa"
                ),
                "vo2max_bike": athlete.get(
                    "VO₂max bici"
                ),
                "css": athlete.get(
                    "CSS"
                ),
            }
        ]

    # -------------------------------------------------
    # DUPLICATE PROTECTION
    # -------------------------------------------------

    def _find_duplicate_decision(
        self,
        table,
        fields,
    ):
        """
        Cerca una decisione identica già salvata nello stesso giorno.
        """

        records = table.all() or []

        comparison_fields = (
            "Data",
            "Decisione IronCoach",
            "Motivazione",
            "Confidenza",
            "Azione consigliata",
            "Priorità",
            "Priorità allenante",
            "Strategia",
            "Allenamento modificato",
        )

        expected = {
            key: fields.get(key)
            for key in comparison_fields
        }

        for record in records:
            record_fields = record.get(
                "fields",
                {},
            )

            current = {
                key: record_fields.get(key)
                for key in comparison_fields
            }

            if current == expected:
                return record

        return None

    # -------------------------------------------------
    # WRITE
    # -------------------------------------------------

    def save_decision(
        self,
        fields,
    ):
        fields = fields or {}

        table = self.base.table(
            "Decision Log"
        )

        duplicate = self._find_duplicate_decision(
            table,
            fields,
        )

        if duplicate:
            print("\n")
            print("=" * 60)
            print("ℹ️ DECISIONE GIÀ PRESENTE SU AIRTABLE")
            print("=" * 60)
            print(
                f"Record ID: {duplicate.get('id')}"
            )
            print("=" * 60)

            return duplicate

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