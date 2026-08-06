"""
Test del riepilogo leggibile dell'allenamento modificato
salvato nel Decision Log.
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


def test_writer_formats_modified_workout_as_readable_summary() -> None:
    client = FakeAirtableClient()

    DecisionWriter(client).save(
        {
            "decision": "RECUPERA",
            "training_priority": "RIPRISTINO",
            "strategy": "RECOVERY",
            "modified_workout": {
                "strategy": "RECOVERY",
                "original_workout": "6x1000 pista",
                "sport": "RUN",
                "original_type": "Qualità",
                "original_zone": "Z5",
                "original_duration_minutes": 58,
                "duration_minutes": 29,
                "training_priority": "RIPRISTINO",
                "intensity": "Z1 molto facile",
                "warmup": "5' corsa facile",
                "main_set": "19' corsa rigenerante",
                "cooldown": "5' camminata",
                "technical_focus": "Rilassamento",
                "alternative": "Riposo completo",
                "removed_elements": "VO2max e sprint",
                "notes": "Seduta rigenerante.",
            },
        }
    )

    summary = client.saved_fields[
        "Allenamento modificato"
    ]

    assert "Strategia: RECOVERY" in summary
    assert "Seduta originale: 6x1000 pista" in summary
    assert "Durata originale: 58 min" in summary
    assert "Nuova durata: 29 min" in summary
    assert "Priorità allenante: RIPRISTINO" in summary
    assert "Parte centrale: 19' corsa rigenerante" in summary
    assert "Elementi rimossi: VO2max e sprint" in summary
    assert "{'" not in summary


def test_writer_omits_empty_workout_fields() -> None:
    client = FakeAirtableClient()

    DecisionWriter(client).save(
        {
            "decision": "ADATTA",
            "modified_workout": {
                "strategy": "ADAPT",
                "alternative": "",
                "notes": None,
            },
        }
    )

    summary = client.saved_fields[
        "Allenamento modificato"
    ]

    assert summary == "Strategia: ADAPT"


def test_writer_preserves_existing_workout_text() -> None:
    client = FakeAirtableClient()

    DecisionWriter(client).save(
        {
            "decision": "ADATTA",
            "modified_workout": "Testo già formattato",
        }
    )

    assert (
        client.saved_fields["Allenamento modificato"]
        == "Testo già formattato"
    )