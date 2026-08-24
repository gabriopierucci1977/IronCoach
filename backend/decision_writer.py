"""
IronCoach Decision Writer

Converte una decisione del Coach Engine
nei campi presenti nella tabella Airtable Decision Log.

Il Decision Model contiene anche ``risk_level``, ``reasoning`` e
``intelligence``.  Questi campi rimangono disponibili nel report/runtime ma
non vengono inviati ad Airtable finché la tabella Decision Log non espone
colonne dedicate.  Inviare campi non presenti nello schema Airtable rende il
salvataggio fragile, quindi il writer mantiene intenzionalmente un contratto
esplicito e conservativo.
"""

from datetime import datetime


class DecisionWriter:
    """
    Gestisce la preparazione e il salvataggio
    delle decisioni generate da IronCoach.
    """

    AIRTABLE_FIELDS = (
        "Data",
        "Decisione IronCoach",
        "Motivazione",
        "Confidenza",
        "Azione consigliata",
        "Allenamento modificato",
        "Priorità",
        "Priorità allenante",
        "Strategia",
    )

    RICH_RUNTIME_FIELDS = (
        "risk_level",
        "reasoning",
        "intelligence",
    )

    def __init__(
        self,
        airtable_client,
    ):
        self.client = airtable_client

    def save(
        self,
        decision,
    ):
        decision = decision or {}

        fields = {
            "Data": datetime.now().strftime(
                "%Y-%m-%d"
            ),
            "Decisione IronCoach": self._normalize_decision(
                decision.get("decision")
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
            "Allenamento modificato": self._format_modified_workout(
                decision.get("modified_workout")
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

    def _format_modified_workout(
        self,
        workout,
    ):
        """
        Crea un riepilogo leggibile per Airtable.
        """

        if not workout:
            return ""

        if isinstance(workout, str):
            return workout

        labels = (
            ("strategy", "Strategia"),
            ("original_workout", "Seduta originale"),
            ("sport", "Sport"),
            ("original_type", "Tipo originale"),
            ("original_zone", "Zona originale"),
            ("original_duration_minutes", "Durata originale"),
            ("duration_minutes", "Nuova durata"),
            ("training_priority", "Priorità allenante"),
            ("intensity", "Intensità"),
            ("warmup", "Riscaldamento"),
            ("main_set", "Parte centrale"),
            ("cooldown", "Defaticamento"),
            ("technical_focus", "Focus tecnico"),
            ("alternative", "Alternativa"),
            ("removed_elements", "Elementi rimossi"),
            ("notes", "Note"),
        )

        lines = []

        for key, label in labels:
            value = workout.get(key)

            if value in (
                None,
                "",
                [],
                {},
            ):
                continue

            if key in (
                "original_duration_minutes",
                "duration_minutes",
            ):
                value = f"{value} min"

            lines.append(
                f"{label}: {value}"
            )

        return "\n".join(lines)

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