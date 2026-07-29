"""
IronCoach Coach Engine v2

Valuta il contesto complessivo dell'atleta e restituisce
una Decision ufficiale basata su recovery, sonno, stress,
dolore, carico recente, allenamento e nutrizione.
"""

from backend.decision import Decision


class CoachEngine:
    """
    Motore decisionale centrale di IronCoach.

    La valutazione segue due livelli:

    1. Regole di sicurezza prioritarie.
    2. Punteggio di rischio derivato dai dati disponibili.
    """

    def evaluate(self, context):
        """
        Valuta il contesto dell'atleta.

        Args:
            context (dict): Contesto costruito da ContextBuilder.

        Returns:
            dict: Decisione ufficiale IronCoach.
        """

        context = context or {}

        recovery = context.get("recovery", {}) or {}
        training = context.get("training", {}) or {}
        nutrition = context.get("nutrition", {}) or {}

        recovery_state = self._get_text(
            recovery,
            "Stato Recovery",
            "stato_recovery",
            "Recovery Status",
        ).upper()

        recovery_score = self._get_number(
            recovery,
            "Recovery Score",
            "recovery_score",
        )

        sleep_score = self._get_number(
            recovery,
            "Sleep Score",
            "sleep_score",
        )

        stress = self._get_number(
            recovery,
            "Stress",
            "stress",
        )

        general_pain = self._get_number(
            recovery,
            "Dolore generale",
            "dolore_generale",
        )

        load_ratio = self._get_number(
            recovery,
            "Rapporto Carico 7/28 giorni",
            "rapporto_carico_7_28",
        )

        session_rpe = self._get_number(
            training,
            "RPE percepito",
            "rpe",
            "RPE",
        )

        training_issues = self._get_text(
            training,
            "Dolori/problematiche",
            "dolori_problematiche",
        )

        hydration_status = self._get_text(
            nutrition,
            "Stato idratazione",
            "stato_idratazione",
        ).upper()

        carbohydrate_status = self._get_text(
            nutrition,
            "Stato carboidrati",
            "stato_carboidrati",
        ).upper()

        nutrition_recovery_status = self._get_text(
            nutrition,
            "Stato recupero nutrizionale",
            "stato_recupero_nutrizionale",
        ).upper()

        # -------------------------------------------------
        # LIVELLO 1 - REGOLE DI SICUREZZA
        # -------------------------------------------------

        if recovery_state == "ROSSO":
            return Decision(
                decision="RECUPERA",
                reason="Recovery in stato ROSSO: il recupero ha priorità.",
                priority="Recovery",
                confidence=98,
                strategy="RECOVERY",
                recommended_action="Riposo completo oppure massimo 30' in Z1.",
            ).to_dict()

        if general_pain is not None and general_pain >= 7:
            return Decision(
                decision="RECUPERA",
                reason=(
                    f"Dolore generale elevato "
                    f"({self._format_number(general_pain)}/10): "
                    "evitare ulteriore carico."
                ),
                priority="Recovery",
                confidence=98,
                strategy="RECOVERY",
                recommended_action=(
                    "Sospendi l'allenamento intenso e valuta il dolore "
                    "prima di riprendere."
                ),
            ).to_dict()

        if recovery_score is not None and recovery_score < 40:
            return Decision(
                decision="RECUPERA",
                reason=(
                    "Recovery Score molto basso "
                    f"({self._format_number(recovery_score)})."
                ),
                priority="Recovery",
                confidence=96,
                strategy="RECOVERY",
                recommended_action=(
                    "Riposo oppure attività rigenerante molto leggera."
                ),
            ).to_dict()

        # -------------------------------------------------
        # LIVELLO 2 - PUNTEGGIO DI RISCHIO
        # -------------------------------------------------

        risk_score = 0
        reasons = []

        if recovery_state == "GIALLO":
            risk_score += 3
            reasons.append("recovery in stato GIALLO")

        elif recovery_state == "VERDE":
            reasons.append("recovery in stato VERDE")

        elif not recovery_state:
            risk_score += 1
            reasons.append("stato recovery non disponibile")

        else:
            risk_score += 1
            reasons.append(f"stato recovery {recovery_state}")

        if recovery_score is not None:
            if recovery_score < 55:
                risk_score += 3
                reasons.append(
                    "Recovery Score basso "
                    f"({self._format_number(recovery_score)})"
                )

            elif recovery_score < 70:
                risk_score += 1
                reasons.append(
                    "Recovery Score moderato "
                    f"({self._format_number(recovery_score)})"
                )

        if sleep_score is not None:
            if sleep_score < 50:
                risk_score += 3
                reasons.append(
                    "Sleep Score molto basso "
                    f"({self._format_number(sleep_score)})"
                )

            elif sleep_score < 70:
                risk_score += 1
                reasons.append(
                    "Sleep Score da migliorare "
                    f"({self._format_number(sleep_score)})"
                )

        if stress is not None:
            if stress >= 8:
                risk_score += 2
                reasons.append(
                    f"stress elevato "
                    f"({self._format_number(stress)}/10)"
                )

            elif stress >= 6:
                risk_score += 1
                reasons.append(
                    f"stress moderato "
                    f"({self._format_number(stress)}/10)"
                )

        if general_pain is not None:
            if general_pain >= 4:
                risk_score += 3
                reasons.append(
                    "dolore generale significativo "
                    f"({self._format_number(general_pain)}/10)"
                )

            elif general_pain >= 2:
                risk_score += 1
                reasons.append(
                    "dolore generale presente "
                    f"({self._format_number(general_pain)}/10)"
                )

        if load_ratio is not None:
            if load_ratio > 1.5:
                risk_score += 3
                reasons.append(
                    "rapporto carico 7/28 elevato "
                    f"({self._format_number(load_ratio)})"
                )

            elif load_ratio > 1.2:
                risk_score += 1
                reasons.append(
                    "rapporto carico 7/28 in crescita "
                    f"({self._format_number(load_ratio)})"
                )

        if session_rpe is not None:
            if session_rpe >= 9:
                risk_score += 1
                reasons.append(
                    "ultima seduta molto impegnativa "
                    f"(RPE {self._format_number(session_rpe)}/10)"
                )

            elif session_rpe >= 8:
                reasons.append(
                    "ultima seduta impegnativa "
                    f"(RPE {self._format_number(session_rpe)}/10)"
                )

        if self._contains_relevant_issue(training_issues):
            risk_score += 1
            reasons.append(
                "problematica segnalata nell'ultima seduta: "
                f"{training_issues}"
            )

        nutrition_warning_count = self._count_nutrition_warnings(
            hydration_status,
            carbohydrate_status,
            nutrition_recovery_status,
        )

        if nutrition_warning_count >= 2:
            risk_score += 1
            reasons.append("recupero nutrizionale da migliorare")

        reason = self._build_reason(reasons)

        # -------------------------------------------------
        # DECISIONE FINALE
        # -------------------------------------------------

        if risk_score >= 6:
            decision = Decision(
                decision="RECUPERA",
                reason=reason,
                priority="Recovery",
                confidence=self._calculate_confidence(90, risk_score),
                strategy="RECOVERY",
                recommended_action=(
                    "Riposo oppure attività rigenerante in Z1, "
                    "senza lavori di qualità."
                ),
            )

        elif risk_score >= 4:
            decision = Decision(
                decision="RIDUZIONE",
                reason=reason,
                priority="Recovery",
                confidence=self._calculate_confidence(88, risk_score),
                strategy="REDUCE_LOAD",
                recommended_action=(
                    "Riduci il volume del 30-40% ed elimina "
                    "gli intervalli ad alta intensità."
                ),
            )

        elif risk_score >= 2:
            decision = Decision(
                decision="ADATTA",
                reason=reason,
                priority="Recovery",
                confidence=self._calculate_confidence(85, risk_score),
                strategy="ADAPT",
                recommended_action=(
                    "Mantieni la seduta ma riduci intensità o durata; "
                    "privilegia lavoro aerobico controllato."
                ),
            )

        else:
            decision = Decision(
                decision="CONFERMA",
                reason=reason,
                priority="Performance",
                confidence=self._calculate_confidence(92, risk_score),
                strategy="KEEP_PLAN",
                recommended_action=(
                    "Allenamento confermato come programmato."
                ),
            )

        return decision.to_dict()

    # -------------------------------------------------
    # ESTRAZIONE DATI
    # -------------------------------------------------

    def _get_value(self, data, *field_names):
        """
        Restituisce il primo valore disponibile tra i campi indicati.
        """

        if not isinstance(data, dict):
            return None

        for field_name in field_names:
            value = data.get(field_name)

            if value is not None and value != "":
                return value

        return None

    def _get_text(self, data, *field_names):
        """
        Restituisce un valore testuale normalizzato.
        """

        value = self._get_value(data, *field_names)

        if value is None:
            return ""

        if isinstance(value, dict):
            value = value.get("value", "")

        return str(value).strip()

    def _get_number(self, data, *field_names):
        """
        Converte un campo Airtable in numero.

        Returns:
            float | None: Numero convertito oppure None.
        """

        value = self._get_value(data, *field_names)

        if value is None or isinstance(value, bool):
            return None

        if isinstance(value, dict):
            value = value.get("value")

        if isinstance(value, (int, float)):
            return float(value)

        try:
            normalized_value = str(value).strip().replace(",", ".")
            return float(normalized_value)

        except (TypeError, ValueError):
            return None

    # -------------------------------------------------
    # ANALISI
    # -------------------------------------------------

    def _contains_relevant_issue(self, issue_text):
        """
        Determina se il testo segnala dolore o affaticamento.

        Le descrizioni esplicitamente negative, come
        'nessun dolore', non vengono considerate criticità.
        """

        if not issue_text:
            return False

        normalized_text = issue_text.lower().strip()

        safe_expressions = (
            "nessun dolore",
            "nessun problema",
            "nessuna problematica",
            "nessun fastidio",
        )

        if any(
            expression in normalized_text
            for expression in safe_expressions
        ):
            return False

        issue_keywords = (
            "dolore",
            "fastidio",
            "affaticamento",
            "infiammazione",
            "rigidità",
            "contrattura",
            "tensione",
        )

        return any(
            keyword in normalized_text
            for keyword in issue_keywords
        )

    def _count_nutrition_warnings(self, *statuses):
        """
        Conta gli stati nutrizionali negativi.
        """

        warning_labels = (
            "DA MIGLIORARE",
            "INSUFFICIENTE",
            "BASSO",
            "INADEGUATO",
            "ROSSO",
        )

        warning_count = 0

        for status in statuses:
            if status and any(
                label in status
                for label in warning_labels
            ):
                warning_count += 1

        return warning_count

    def _build_reason(self, reasons):
        """
        Costruisce una motivazione leggibile.
        """

        if not reasons:
            return "Dati disponibili compatibili con il piano previsto."

        first_reason = reasons[0]
        remaining_reasons = reasons[1:]

        if not remaining_reasons:
            return f"Valutazione basata su {first_reason}."

        return (
            f"Valutazione basata su {first_reason}; "
            + "; ".join(remaining_reasons)
            + "."
        )

    def _calculate_confidence(self, base_confidence, risk_score):
        """
        Calcola la confidenza mantenendola tra 75 e 98.
        """

        confidence = base_confidence + min(risk_score, 5)

        return max(75, min(98, confidence))

    def _format_number(self, value):
        """
        Formatta un numero eliminando decimali inutili.
        """

        if value is None:
            return "N/D"

        if float(value).is_integer():
            return str(int(value))

        return f"{value:.1f}"