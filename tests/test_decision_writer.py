"""
Test DecisionWriter.

Verifica che:
- la decisione venga convertita correttamente;
- i campi principali vengano salvati;
- l'intelligence della decisione venga mantenuta.
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
        "reason": (
            "Performance da monitorare."
        ),
        "confidence": 90,
        "recommended_action": (
            "Riduci volume."
        ),
        "priority": "Performance",
        "strategy": "ADAPT",
        "modified_workout": None,
        "risk_level": "CAUTION",
        "reasoning": [
            "Performance: in calo",
            "Adattamento: moderato",
        ],
        "intelligence": {
            "performance": {
                "trend": "DECLINING",
                "metrics": {
                    "ftp": -4.5,
                },
            },
            "load": {
                "level": "HIGH",
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



def test_writer_preserves_intelligence_fields():

    client = FakeAirtableClient()

    writer = DecisionWriter(
        client
    )

    writer.save(
        _decision()
    )

    fields = client.saved_fields

    assert fields[
        "Intelligence"
    ][
        "performance"
    ][
        "trend"
    ] == "DECLINING"

    assert fields[
        "Intelligence"
    ][
        "load"
    ][
        "level"
    ] == "HIGH"



def test_writer_preserves_reasoning_and_risk():

    client = FakeAirtableClient()

    writer = DecisionWriter(
        client
    )

    writer.save(
        _decision()
    )

    fields = client.saved_fields

    assert fields[
        "Risk level"
    ] == "CAUTION"

    assert fields[
        "Reasoning"
    ] == [
        "Performance: in calo",
        "Adattamento: moderato",
    ]