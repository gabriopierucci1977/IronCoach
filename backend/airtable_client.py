"""
IronCoach - Airtable Client

Gestisce le operazioni di lettura e scrittura
verso Airtable.
"""

from pyairtable import Api

from config.settings import AIRTABLE_API_KEY, AIRTABLE_BASE_ID


class AirtableClient:
    """
    Client centralizzato per l'accesso alla base Airtable
    utilizzata da IronCoach.
    """

    def __init__(self):
        self.api = Api(AIRTABLE_API_KEY)
        self.base = self.api.base(AIRTABLE_BASE_ID)

    # -------------------------------------------------
    # TEST CONNESSIONE
    # -------------------------------------------------

    def test_connection(self):
        """
        Verifica la connessione alla base Airtable.

        Returns:
            bool: True se la connessione riesce, False altrimenti.
        """

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
            print("=" * 60)
            print("❌ Errore di connessione ad Airtable")
            print("=" * 60)
            print(error)

            return False

    # -------------------------------------------------
    # LETTURA DATI
    # -------------------------------------------------

    def _get_first_record(self, table_name):
        """
        Restituisce i campi del primo record disponibile
        nella tabella indicata.

        Questo metodo viene utilizzato solo per tabelle
        che contengono un singolo record principale,
        come Athlete Profile.

        Args:
            table_name (str): Nome della tabella Airtable.

        Returns:
            dict: Campi del record oppure dizionario vuoto.
        """

        table = self.base.table(table_name)
        record = table.first()

        if not record:
            return {}

        return record.get("fields", {})

    def _get_latest_record(self, table_name, date_field=None):
        """
        Restituisce il record più recente di una tabella.

        Se viene indicato un campo data, Airtable ordina
        i record in ordine decrescente usando quel campo.

        Se non viene indicato un campo data, i record
        vengono ordinati localmente in base a createdTime.

        Args:
            table_name (str): Nome della tabella Airtable.
            date_field (str | None): Campo data da usare
                per determinare il record più recente.

        Returns:
            dict: Campi del record più recente oppure
                dizionario vuoto.
        """

        table = self.base.table(table_name)

        if date_field:
            record = table.first(sort=[f"-{date_field}"])

            if not record:
                return {}

            return record.get("fields", {})

        records = table.all()

        if not records:
            return {}

        latest_record = max(
            records,
            key=lambda record: record.get("createdTime", ""),
        )

        return latest_record.get("fields", {})

    def get_athlete_profile(self):
        """
        Restituisce il profilo principale dell'atleta.
        """

        return self._get_first_record("Athlete Profile")

    def get_latest_recovery(self):
        """
        Restituisce l'ultimo record creato
        nella tabella Recovery Log.
        """

        return self._get_latest_record("Recovery Log")

    def get_latest_training(self):
        """
        Restituisce l'allenamento con la data più recente.
        """

        return self._get_latest_record(
            "Training Log",
            date_field="Data allenamento",
        )

    def get_latest_nutrition(self):
        """
        Restituisce l'ultimo record creato
        nella tabella Nutrition Log.
        """

        return self._get_latest_record("Nutrition Log")

    def get_latest_decision(self):
        """
        Restituisce la decisione con la data più recente.
        """

        return self._get_latest_record(
            "Decision Log",
            date_field="Data",
        )

    # -------------------------------------------------
    # SCRITTURA DATI
    # -------------------------------------------------

    def save_decision(self, fields):
        """
        Salva una nuova decisione nella tabella Decision Log.

        Args:
            fields (dict): Campi da inviare ad Airtable.

        Returns:
            dict: Record creato da Airtable.
        """

        table = self.base.table("Decision Log")

        try:
            record = table.create(fields)

        except Exception as error:
            print("\n" + "=" * 60)
            print("❌ ERRORE DURANTE IL SALVATAGGIO SU AIRTABLE")
            print("=" * 60)
            print(f"Tipo errore: {type(error).__name__}")
            print(error)
            print("=" * 60)

            raise

        print("\n" + "=" * 60)
        print("✅ DECISIONE SALVATA SU AIRTABLE")
        print("=" * 60)
        print(f"Record ID: {record.get('id', 'N/D')}")
        print("=" * 60)

        return record