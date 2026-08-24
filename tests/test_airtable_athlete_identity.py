from backend.airtable_client import AirtableClient


class FakeTable:
    def __init__(self, record):
        self._record = record

    def first(self):
        return self._record


class FakeBase:
    def __init__(self, record):
        self._record = record

    def table(self, name):
        assert name == "Athlete Profile"
        return FakeTable(self._record)


def test_get_athlete_profile_preserves_airtable_record_id():
    client = AirtableClient.__new__(AirtableClient)
    client.base = FakeBase(
        {
            "id": "recAthlete123",
            "fields": {
                "Nome atleta": "Gabrio",
                "Livello atleta": "Age Group competitivo",
            },
        }
    )

    athlete = client.get_athlete_profile()

    assert athlete["record_id"] == "recAthlete123"
    assert athlete["Nome atleta"] == "Gabrio"
    assert athlete["Livello atleta"] == "Age Group competitivo"