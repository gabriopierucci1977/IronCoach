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

        Args:
            table_name (str): Nome della tabella Airtable.

        Returns:
            dict: Campi del record oppure dizionario vuoto.
        """

        table = self.base.table(table_name)
        records = table.all()

        if not records:
            return {}

        return records[0].get("fields", {})

    def get_athlete_profile(self):
        """
        Restituisce il profilo dell'atleta.
        """

        return self._get_first_record("Athlete Profile")

    def get_latest_recovery(self):
        """
        Restituisce l'ultimo record disponibile
        della tabella Recovery Log.
        """

        return self._get_first_record("Recovery Log")

    def get_latest_training(self):
        """
        Restituisce l'ultimo record disponibile
        della tabella Training Log.
        """

        return self._get_first_record("Training Log")

    def get_latest_nutrition(self):
        """
        Restituisce l'ultimo record disponibile
        della tabella Nutrition Log.
        """

        return self._get_first_record("Nutrition Log")

    def get_latest_decision(self):
        """
        Restituisce l'ultimo record disponibile
        della tabella Decision Log.
        """

        return self._get_first_record("Decision Log")

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