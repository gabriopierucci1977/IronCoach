"""
IronCoach Coach Engine

Valuta il contesto dell'atleta e restituisce
una Decision ufficiale.
"""

from backend.decision import Decision


class CoachEngine:

    def evaluate(self, context):

        recovery = context.get("recovery", {})

        recovery_state = (
            recovery.get("Stato Recovery")
            or recovery.get("stato_recovery")
            or recovery.get("Recovery Status")
            or ""
        )

        recovery_state = str(recovery_state).upper()

        if recovery_state == "ROSSO":

            decision = Decision(
                decision="RECUPERA",
                reason="Recovery in stato ROSSO.",
                priority="Recovery",
                confidence=98,
                strategy="RECOVERY",
                recommended_action="Riposo oppure 30' Z1"
            )

        elif recovery_state == "GIALLO":

            decision = Decision(
                decision="RIDUZIONE",
                reason="Recovery in stato GIALLO.",
                priority="Recovery",
                confidence=90,
                strategy="REDUCE_LOAD",
                recommended_action="Riduci volume del 30%"
            )

        else:

            decision = Decision(
                decision="CONFERMA",
                reason="Recovery in stato VERDE.",
                priority="Performance",
                confidence=95,
                strategy="KEEP_PLAN",
                recommended_action="Allenamento confermato"
            )

        # Compatibilità con il resto del progetto
        return decision.to_dict()