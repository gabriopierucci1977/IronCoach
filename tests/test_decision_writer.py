"""
Test DecisionWriter sullo schema Airtable reale.

Verifica che:
- la decisione venga convertita correttamente;
- i campi presenti in Decision Log vengano salvati;
- i campi interni non presenti in Airtable non vengano inviati.
"""

from backend.decision_writer import DecisionWriter


class FakeAirtableClient:

    def __init__(self):
        self.saved_fields = None

    def save_decision(
        self,
        fields,
    ):
        self.saved_fields = fields

        return {
            "id": "rec_test",
            "fields": fields,
        }


def _decision():

    return {
        "decision": "ADATTA",
        "reason": "Performance da monitorare.",
        "confidence": 90,
        "recommended_action": "Riduci volume.",
        "priority": "Performance",
        "training_priority": "SVILUPPO_PRESTAZIONE",
        "strategy": "ADAPT",
        "modified_workout": {
            "strategy": "ADAPT",
            "training_priority": "SVILUPPO_PRESTAZIONE",
        },
        "risk_level": "CAUTION",
        "reasoning": [
            "Performance: in calo",
            "Adattamento: moderato",
        ],
        "intelligence": {
            "performance": {
                "trend": "DECLINING",
            },
        },
    }


def test_writer_saves_main_decision_fields():

    client = FakeAirtableClient()

    writer = DecisionWriter(
        client
    )

    writer.save(
        _decision()
    )

    fields = client.saved_fields

    assert fields[
        "Decisione IronCoach"
    ] == "ADATTA"

    assert fields[
        "Motivazione"
    ] == "Performance da monitorare."

    assert fields[
        "Confidenza"
    ] == 90

    assert fields[
        "Azione consigliata"
    ] == "Riduci volume."

    assert fields[
        "Priorità"
    ] == "Performance"

    assert fields[
        "Priorità allenante"
    ] == "SVILUPPO_PRESTAZIONE"

    assert fields[
        "Strategia"
    ] == "ADAPT"


def test_writer_normalizes_legacy_decisions():

    client = FakeAirtableClient()

    writer = DecisionWriter(
        client
    )

    assert writer._normalize_decision(
        "RECOVERY"
    ) == "RECUPERA"

    assert writer._normalize_decision(
        "RIDUZIONE"
    ) == "RIDUCI"


def test_writer_serializes_modified_workout():

    client = FakeAirtableClient()

    writer = DecisionWriter(
        client
    )

    writer.save(
        _decision()
    )

    saved_workout = client.saved_fields[
        "Allenamento modificato"
    ]

    assert "SVILUPPO_PRESTAZIONE" in saved_workout
    assert "ADAPT" in saved_workout


def test_writer_excludes_unsupported_airtable_fields():

    client = FakeAirtableClient()

    writer = DecisionWriter(
        client
    )

    writer.save(
        _decision()
    )

    fields = client.saved_fields

    assert "Risk level" not in fields
    assert "Reasoning" not in fields
    assert "Intelligence" not in fields