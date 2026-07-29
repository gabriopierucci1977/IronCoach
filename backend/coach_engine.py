"""
IronCoach Coach Engine

Decisione adattiva basata su:
- stato recovery
- carico recente
- qualità ultima seduta
- problematiche
- nutrizione
"""

from backend.decision import Decision


class CoachEngine:

    def evaluate(self, context):

        recovery = context.get("recovery", {}) or {}
        training = context.get("training", {}) or {}
        nutrition = context.get("nutrition", {}) or {}

        recovery_state = str(
            recovery.get("Stato Recovery")
            or recovery.get("stato_recovery")
            or ""
        ).upper()

        recovery_score = self._number(
            recovery.get("Recovery Score")
        )

        rpe = self._number(
            training.get("RPE percepito")
            or training.get("RPE")
        )

        session_type = str(
            training.get("Tipo seduta")
            or ""
        ).lower()

        problem = str(
            training.get("Dolori/problematiche")
            or ""
        ).lower()

        nutrition_status = str(
            nutrition.get("Stato recupero nutrizionale")
            or ""
        ).lower()


        reasoning = []

        high_risk = False


        # -----------------------------
        # ROSSO
        # -----------------------------

        if recovery_state == "ROSSO":

            reasoning.append(
                "Recovery in stato ROSSO"
            )

            return Decision(
                decision="RECUPERA",
                reason=(
                    "Recovery in stato ROSSO: "
                    "il recupero ha priorità."
                ),
                priority="Recovery",
                confidence=98,
                strategy="RECOVERY",
                recommended_action=(
                    "Riposo completo oppure massimo 30' in Z1."
                ),
                reasoning=reasoning,
                risk_level="HIGH_ALERT",
            ).to_dict()


        # -----------------------------
        # FATTORI DI RISCHIO
        # -----------------------------

        if rpe and rpe >= 8:
            high_risk = True
            reasoning.append(
                "RPE seduta precedente elevato"
            )

        if "qualità" in session_type:
            high_risk = True
            reasoning.append(
                "Seduta precedente ad alta intensità"
            )

        if problem and "nessun" not in problem:
            high_risk = True
            reasoning.append(
                "Problematica muscolare segnalata"
            )

        if "migliorare" in nutrition_status:
            high_risk = True
            reasoning.append(
                "Recupero nutrizionale insufficiente"
            )


        # -----------------------------
        # GIALLO
        # -----------------------------

        if recovery_state == "GIALLO":

            if high_risk:

                reasoning.insert(
                    0,
                    "Recovery GIALLO con fattori di rischio aggiuntivi"
                )

                return Decision(
                    decision="RECUPERA",
                    reason=(
                        "Recovery GIALLO con fattori di rischio "
                        "multipli: meglio una giornata rigenerante."
                    ),
                    priority="Recovery",
                    confidence=95,
                    strategy="RECOVERY",
                    recommended_action=(
                        "Riposo oppure attività rigenerante in Z1, "
                        "senza lavori di qualità."
                    ),
                    reasoning=reasoning,
                    risk_level="HIGH_ALERT",
                ).to_dict()


            return Decision(
                decision="RIDUZIONE",
                reason=(
                    "Recovery in stato GIALLO: "
                    "riduzione del carico consigliata."
                ),
                priority="Recovery",
                confidence=90,
                strategy="REDUCE_LOAD",
                recommended_action=(
                    "Riduci volume e mantieni solo lavoro aerobico."
                ),
                reasoning=reasoning,
                risk_level="CAUTION",
            ).to_dict()


        # -----------------------------
        # VERDE
        # -----------------------------

        if high_risk:

            return Decision(
                decision="ADATTA",
                reason=(
                    "Recovery VERDE ma presenza di fattori "
                    "di rischio: adattare lo stimolo."
                ),
                priority="Recovery",
                confidence=88,
                strategy="ADAPT",
                recommended_action=(
                    "Riduci intensità o durata mantenendo "
                    "lo stimolo aerobico."
                ),
                reasoning=reasoning,
                risk_level="CAUTION",
            ).to_dict()


        return Decision(
            decision="CONFERMA",
            reason=(
                "Recovery VERDE e nessun fattore critico."
            ),
            priority="Performance",
            confidence=95,
            strategy="KEEP_PLAN",
            recommended_action=(
                "Allenamento confermato."
            ),
            reasoning=reasoning,
            risk_level="NORMAL",
        ).to_dict()


    def _number(self, value):

        try:
            return float(value)

        except (TypeError, ValueError):
            return None