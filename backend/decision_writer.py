"""
IronCoach Decision Writer

Converte una decisione del Coach Engine
nei campi presenti nella tabella Airtable Decision Log.
"""


from datetime import datetime


class DecisionWriter:
    """
    Gestisce la preparazione e il salvataggio
    delle decisioni generate da IronCoach.
    """

    def __init__(
        self,
        airtable_client,
    ):
        self.client = airtable_client

    def save(
        self,
        decision,
    ):
        """
        Prepara i campi Airtable e salva la decisione.
        """

        decision = decision or {}

        modified_workout = decision.get(
            "modified_workout"
        )

        fields = {
            "Data": datetime.now().strftime(
                "%Y-%m-%d"
            ),
            "Decisione IronCoach": self._normalize_decision(
                decision.get(
                    "decision"
                )
            ),
            "Motivazione": decision.get(
                "reason"
            ),
            "Confidenza": decision.get(
                "confidence"
            ),
            "Azione consigliata": decision.get(
                "recommended_action"
            ),
            "Allenamento modificato": (
                str(modified_workout)
                if modified_workout
                else ""
            ),
            "Priorità": decision.get(
                "priority"
            ),
            "Priorità allenante": decision.get(
                "training_priority"
            ),
            "Strategia": decision.get(
                "strategy"
            ),
        }

        return self.client.save_decision(
            fields
        )

    # ==================================================
    # AIRTABLE COMPATIBILITY
    # ==================================================

    def _normalize_decision(
        self,
        value,
    ):
        if not value:
            return None

        mapping = {
            "RIDUZIONE": "RIDUCI",
            "RIDUCI": "RIDUCI",
            "RECOVERY": "RECUPERA",
            "RECUPERA": "RECUPERA",
            "MANTENIMENTO": "MANTIENI",
            "MANTIENI": "MANTIENI",
        }

        return mapping.get(
            value.upper(),
            value,
        )