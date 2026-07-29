"""
IronCoach Decision Writer

TEST 5
Aggiunge il campo "Strategia".
"""

from datetime import datetime


class DecisionWriter:

    def __init__(self, airtable_client):
        self.client = airtable_client

    def save(self, decision):

        fields = {
            "Data": datetime.now().strftime("%Y-%m-%d"),
            "Decisione IronCoach": decision.get("decision"),
            "Motivazione": decision.get("reason"),
            "Confidenza": decision.get("confidence"),
            "Azione consigliata": decision.get("recommended_action"),
            "Allenamento modificato": (
                str(decision.get("modified_workout"))
                if decision.get("modified_workout")
                else ""
            ),
            "Priorità": decision.get("priority"),
            "Strategia": decision.get("strategy"),
        }

        print("\n" + "=" * 60)
        print("TEST AIRTABLE - STRATEGIA")
        print("=" * 60)

        for key, value in fields.items():
            print(f"{key}: {repr(value)}")

        print("=" * 60)

        return self.client.save_decision(fields)