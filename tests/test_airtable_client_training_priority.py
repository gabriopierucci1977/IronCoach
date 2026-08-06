"""
Test AirtableClient per Decision Log e training priority.
"""

from backend.airtable_client import AirtableClient


class FakeTable:
    def __init__(self, records=None):
        self.records = records or []
        self.created_fields = None

    def all(self):
        return self.records

    def create(self, fields):
        self.created_fields = fields
        return {
            "id": "rec-decision",
            "fields": fields,
        }


class FakeBase:
    def __init__(self, table):
        self._table = table
        self.requested_table = None

    def table(self, table_name):
        self.requested_table = table_name
        return self._table


def _client_with_table(table):
    client = AirtableClient.__new__(
        AirtableClient
    )
    client.base = FakeBase(table)
    return client


def test_save_decision_writes_training_priority_to_decision_log() -> None:
    table = FakeTable()
    client = _client_with_table(table)

    fields = {
        "Decisione IronCoach": "ADATTA",
        "Priorità allenante": "SPECIFICITA_GARA",
        "Strategia": "ADAPT",
    }

    result = client.save_decision(fields)

    assert client.base.requested_table == "Decision Log"
    assert table.created_fields is fields
    assert (
        result["fields"]["Priorità allenante"]
        == "SPECIFICITA_GARA"
    )


def test_latest_decision_preserves_training_priority() -> None:
    table = FakeTable(
        records=[
            {
                "createdTime": "2026-08-05T08:00:00.000Z",
                "fields": {
                    "Data": "2026-08-05",
                    "Priorità allenante": "CONTINUITA",
                },
            },
            {
                "createdTime": "2026-08-06T08:00:00.000Z",
                "fields": {
                    "Data": "2026-08-06",
                    "Priorità allenante": "RIPRISTINO",
                },
            },
        ]
    )
    client = _client_with_table(table)

    decision = client.get_latest_decision()

    assert client.base.requested_table == "Decision Log"
    assert decision["Data"] == "2026-08-06"
    assert (
        decision["Priorità allenante"]
        == "RIPRISTINO"
    )