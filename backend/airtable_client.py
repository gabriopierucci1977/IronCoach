"""
IronCoach - Airtable Client

Gestisce la connessione con Airtable.
"""

from pyairtable import Api
from config.settings import AIRTABLE_API_KEY, AIRTABLE_BASE_ID


class AirtableClient:

    def __init__(self):
        self.api = Api(AIRTABLE_API_KEY)
        self.base = self.api.base(AIRTABLE_BASE_ID)

    def test_connection(self):
        """
        Verifica la connessione alla base Airtable.
        """

        try:
            tables = self.base.tables()

            print("===================================")
            print("✅ Connessione ad Airtable riuscita")
            print("===================================")

            print("\nTabelle trovate:\n")

            for table in tables:
                print("-", table.name)

            return True

        except Exception as e:

            print("===================================")
            print("❌ Errore di connessione")
            print("===================================")

            print(e)

            return False