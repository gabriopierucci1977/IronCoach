"""
Test di persistenza della training priority nel DecisionWriter.
"""

from backend.decision_writer import DecisionWriter


class FakeAirtableClient:
    def __init__(self):
        self.saved_fields = None

    def save_decision(self, fields):
        self.saved_fields = fields
        return {
            "id": "rec-test",
            "fields": fields,
        }


def test_writer_persists_training_priority() -> None:
    client = FakeAirtableClient()

    result = DecisionWriter(client).save(
        {
            "decision": "ADATTA",
            "reason": "Test",
            "confidence": 91,
            "recommended_action": "Riduci il carico.",
            "priority": "Performance",
            "training_priority": "SVILUPPO_PRESTAZIONE",
            "strategy": "ADAPT",
            "risk_level": "MEDIUM",
            "reasoning": ["Test"],
            "intelligence": {},
            "modified_workout": {
                "strategy": "ADAPT",
            },
        }
    )

    assert result["id"] == "rec-test"
    assert (
        client.saved_fields["Priorità allenante"]
        == "SVILUPPO_PRESTAZIONE"
    )
    assert client.saved_fields["Priorità"] == "Performance"
    assert client.saved_fields["Strategia"] == "ADAPT"


def test_writer_allows_missing_training_priority() -> None:
    client = FakeAirtableClient()

    DecisionWriter(client).save(
        {
            "decision": "MANTIENI",
            "strategy": "KEEP_PLAN",
        }
    )

    assert "Priorità allenante" in client.saved_fields
    assert client.saved_fields["Priorità allenante"] is None


def test_writer_serializes_modified_workout() -> None:
    client = FakeAirtableClient()

    DecisionWriter(client).save(
        {
            "decision": "ADATTA",
            "training_priority": "CONTINUITA",
            "modified_workout": {
                "training_priority": "CONTINUITA",
                "strategy": "ADAPT",
            },
        }
    )

    saved_workout = client.saved_fields[
        "Allenamento modificato"
    ]

    assert "CONTINUITA" in saved_workout
    assert "ADAPT" in saved_workout