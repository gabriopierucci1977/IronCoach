"""
IronCoach Report Builder

Costruisce un report leggibile orientato al coaching
a partire dal Context Builder e dal Coach Engine.
"""

import ast
import json


class ReportBuilder:
    """
    Genera un report professionale eliminando il rumore
    tecnico proveniente da Airtable.
    """

    def build(self, context, decision):
        """
        Costruisce il report completo.

        Args:
            context (dict): Contesto prodotto dal Context Builder.
            decision (dict): Decisione prodotta dal Coach Engine.

        Returns:
            str: Report testuale completo.
        """

        context = context or {}
        decision = decision or {}

        athlete = context.get("athlete", {}) or {}
        recovery = context.get("recovery", {}) or {}
        training = context.get("training", {}) or {}
        nutrition = context.get("nutrition", {}) or {}
        last_decision = context.get("decision", {}) or {}

        report = []

        report.append("=" * 60)
        report.append("IRONCOACH REPORT")
        report.append("=" * 60)

        self._add_athlete(
            report,
            athlete,
        )

        self._add_section(
            report,
            "RECOVERY",
            recovery,
            [
                "Stato Recovery",
                "Recovery Score",
                "Sleep Score",
                "Stress",
                "Dolore generale",
                "Pain Score",
                "Coach Comment",
                "Coach Confidence",
            ],
        )

        self._add_training(
            report,
            training,
        )

        self._add_section(
            report,
            "NUTRITION",
            nutrition,
            [
                "Stato recupero nutrizionale",
                "Stato carboidrati",
                "Stato idratazione",
                "Commento Coach nutrizione",
            ],
        )

        self._add_coach_summary(
            report=report,
            recovery=recovery,
            training=training,
            nutrition=nutrition,
            decision=decision,
        )

        report.append("")
        report.append("ULTIMA DECISIONE")
        report.append("-" * 60)

        if last_decision:
            self._append_decision(
                report,
                last_decision,
            )
        else:
            report.append(
                "Nessuna decisione precedente."
            )

        report.append("")
        report.append("=" * 60)
        report.append("DECISIONE DEL COACH")
        report.append("=" * 60)

        self._append_decision(
            report,
            decision,
        )

        report.append("")
        report.append("=" * 60)

        return "\n".join(report)

    # -------------------------------------------------
    # SEZIONI PRINCIPALI
    # -------------------------------------------------

    def _add_athlete(
        self,
        report,
        athlete,
    ):
        """
        Aggiunge al report i dati essenziali dell'atleta.
        """

        report.append("")
        report.append("ATLETA")
        report.append("-" * 60)

        fields = [
            ("Nome Atleta", "Nome"),
            ("Livello Atleta", "Livello"),
            ("Sport Principale", "Sport principale"),
            ("Peso attuale kg", "Peso"),
            ("FTP", "FTP"),
            ("VO₂max corsa", "VO2max corsa"),
            ("VO₂max bici", "VO2max bici"),
            ("CSS", "CSS"),
            ("Limitazioni fisiche", "Limitazioni"),
        ]

        printed_fields = 0

        for source, label in fields:
            value = self._find_value(
                athlete,
                source,
            )

            if not self._has_value(value):
                continue

            report.append(
                f"{label}: {self._format_value(value)}"
            )
            printed_fields += 1

        if printed_fields == 0:
            report.append(
                "Nessun dato atleta disponibile."
            )

    def _add_training(
        self,
        report,
        training,
    ):
        """
        Aggiunge al report i dati essenziali
        dell'ultima seduta.
        """

        report.append("")
        report.append("TRAINING")
        report.append("-" * 60)

        fields = [
            ("Nome seduta", "Seduta"),
            ("Sport", "Sport"),
            ("Tipo seduta", "Tipo"),
            ("Zona prevista", "Zona"),
            ("Durata minuti", "Durata"),
            ("Distanza km", "Distanza"),
            ("RPE percepito", "RPE"),
            ("Sensazioni", "Sensazioni"),
            ("Dolori/problematiche", "Problematiche"),
        ]

        printed_fields = 0

        for source, label in fields:
            value = self._find_value(
                training,
                source,
            )

            if not self._has_value(value):
                continue

            formatted_value = self._format_value(
                value
            )

            if source == "Durata minuti":
                formatted_value = self._append_unit(
                    formatted_value,
                    "min",
                )

            if source == "Distanza km":
                formatted_value = self._append_unit(
                    formatted_value,
                    "km",
                )

            report.append(
                f"{label}: {formatted_value}"
            )
            printed_fields += 1

        if printed_fields == 0:
            report.append(
                "Nessun dato allenamento disponibile."
            )

    def _add_section(
        self,
        report,
        title,
        data,
        fields,
    ):
        """
        Aggiunge una sezione composta soltanto
        dai campi selezionati.
        """

        report.append("")
        report.append(title)
        report.append("-" * 60)

        printed_fields = 0

        for field in fields:
            value = self._find_value(
                data,
                field,
            )

            if not self._has_value(value):
                continue

            report.append(
                f"{field}: {self._format_value(value)}"
            )
            printed_fields += 1

        if printed_fields == 0:
            report.append(
                "Nessun dato disponibile."
            )

    # -------------------------------------------------
    # SINTESI DEL COACH
    # -------------------------------------------------

    def _add_coach_summary(
        self,
        report,
        recovery,
        training,
        nutrition,
        decision,
    ):
        """
        Costruisce una sintesi immediata dei fattori
        principali che hanno influenzato la decisione.

        La sintesi non sostituisce il Coach Engine:
        traduce in forma leggibile i dati già disponibili.
        """

        report.append("")
        report.append("=" * 60)
        report.append("SINTESI DEL COACH")
        report.append("=" * 60)

        summary_items = []

        recovery_summary = self._build_recovery_summary(
            recovery
        )

        if recovery_summary:
            summary_items.append(
                recovery_summary
            )

        sleep_summary = self._build_sleep_summary(
            recovery
        )

        if sleep_summary:
            summary_items.append(
                sleep_summary
            )

        training_summary = self._build_training_summary(
            training
        )

        if training_summary:
            summary_items.append(
                training_summary
            )

        pain_summary = self._build_pain_summary(
            recovery=recovery,
            training=training,
        )

        if pain_summary:
            summary_items.append(
                pain_summary
            )

        nutrition_summary = self._build_nutrition_summary(
            nutrition
        )

        if nutrition_summary:
            summary_items.append(
                nutrition_summary
            )

        if summary_items:
            for item in summary_items:
                report.append(
                    f"• {item}"
                )
        else:
            report.append(
                "• Dati insufficienti per costruire "
                "una sintesi completa."
            )

        risk_level = self._get_risk_level(
            decision
        )

        decision_name = self._get_decision_name(
            decision
        )

        report.append("")
        report.append(
            f"Rischio complessivo: {risk_level}"
        )

        if decision_name:
            report.append(
                f"Decisione suggerita: {decision_name}"
            )

    def _build_recovery_summary(
        self,
        recovery,
    ):
        """
        Genera la frase sintetica sul recupero.
        """

        recovery_status = self._find_value(
            recovery,
            "Stato Recovery",
        )

        recovery_score = self._to_float(
            self._find_value(
                recovery,
                "Recovery Score",
            )
        )

        status_text = ""

        if self._has_value(recovery_status):
            status_text = str(
                recovery_status
            ).strip().upper()

        if recovery_score is not None:
            score_text = self._format_number(
                recovery_score
            )

            if recovery_score >= 80:
                description = "Recupero molto buono"
            elif recovery_score >= 65:
                description = "Recupero buono"
            elif recovery_score >= 50:
                description = "Recupero intermedio"
            elif recovery_score >= 40:
                description = "Recupero ridotto"
            else:
                description = "Recupero critico"

            if status_text:
                return (
                    f"{description}: stato {status_text}, "
                    f"Recovery Score {score_text}"
                )

            return (
                f"{description}: "
                f"Recovery Score {score_text}"
            )

        if status_text:
            return (
                f"Stato recovery: {status_text}"
            )

        return None

    def _build_sleep_summary(
        self,
        recovery,
    ):
        """
        Genera la frase sintetica sul sonno.
        """

        sleep_score = self._to_float(
            self._find_value(
                recovery,
                "Sleep Score",
            )
        )

        sleep_hours = self._to_float(
            self._find_value(
                recovery,
                "Ore sonno",
            )
        )

        if sleep_score is None and sleep_hours is None:
            return None

        parts = []

        if sleep_score is not None:
            score_text = self._format_number(
                sleep_score
            )

            if sleep_score >= 80:
                quality = "buona"
            elif sleep_score >= 65:
                quality = "discreta"
            else:
                quality = "da migliorare"

            parts.append(
                f"qualità del sonno {quality} "
                f"(Sleep Score {score_text})"
            )

        if sleep_hours is not None:
            hours_text = self._format_number(
                sleep_hours
            )

            parts.append(
                f"{hours_text} ore registrate"
            )

        return (
            "Sonno: "
            + "; ".join(parts)
        )

    def _build_training_summary(
        self,
        training,
    ):
        """
        Genera la frase sintetica sul carico percepito
        nell'ultima seduta.
        """

        rpe = self._to_float(
            self._find_value(
                training,
                "RPE percepito",
            )
        )

        workout_name = self._find_value(
            training,
            "Nome seduta",
        )

        if rpe is None:
            return None

        rpe_text = self._format_number(
            rpe
        )

        if rpe >= 9:
            intensity = "Ultima seduta molto impegnativa"
        elif rpe >= 7:
            intensity = "Ultima seduta impegnativa"
        elif rpe >= 5:
            intensity = "Ultima seduta di impegno moderato"
        else:
            intensity = "Ultima seduta a basso impegno"

        result = (
            f"{intensity} (RPE {rpe_text}/10)"
        )

        if self._has_value(workout_name):
            result += (
                f": {self._format_value(workout_name)}"
            )

        return result

    def _build_pain_summary(
        self,
        recovery,
        training,
    ):
        """
        Genera la frase sintetica relativa a dolore
        o problematiche muscolari.
        """

        general_pain = self._to_float(
            self._find_value(
                recovery,
                "Dolore generale",
            )
        )

        training_problem = self._find_value(
            training,
            "Dolori/problematiche",
        )

        if self._has_value(training_problem):
            problem_text = self._format_value(
                training_problem
            )

            if general_pain is not None:
                pain_text = self._format_number(
                    general_pain
                )

                return (
                    f"Problematiche segnalate: {problem_text}; "
                    f"dolore generale {pain_text}/10"
                )

            return (
                f"Problematiche segnalate: {problem_text}"
            )

        if general_pain is None:
            return None

        pain_text = self._format_number(
            general_pain
        )

        if general_pain >= 7:
            description = "Dolore elevato"
        elif general_pain >= 4:
            description = "Dolore moderato"
        elif general_pain > 0:
            description = "Dolore lieve"
        else:
            description = "Nessun dolore generale segnalato"

        if general_pain > 0:
            return (
                f"{description} ({pain_text}/10)"
            )

        return description

    def _build_nutrition_summary(
        self,
        nutrition,
    ):
        """
        Genera la frase sintetica sul recupero
        nutrizionale.
        """

        nutrition_fields = [
            (
                "Stato recupero nutrizionale",
                "recupero nutrizionale",
            ),
            (
                "Stato carboidrati",
                "carboidrati",
            ),
            (
                "Stato idratazione",
                "idratazione",
            ),
        ]

        critical_items = []
        positive_items = []

        for field, label in nutrition_fields:
            value = self._find_value(
                nutrition,
                field,
            )

            if not self._has_value(value):
                continue

            normalized_value = str(
                value
            ).strip().upper()

            if normalized_value in {
                "DA MIGLIORARE",
                "INSUFFICIENTE",
                "BASSO",
                "ROSSO",
                "CRITICO",
            }:
                critical_items.append(
                    label
                )
            elif normalized_value in {
                "OK",
                "BUONO",
                "ADEGUATO",
                "VERDE",
            }:
                positive_items.append(
                    label
                )

        if critical_items:
            return (
                "Nutrizione da migliorare: "
                + ", ".join(critical_items)
            )

        if positive_items:
            return (
                "Recupero nutrizionale adeguato: "
                + ", ".join(positive_items)
            )

        return None

    def _get_risk_level(
        self,
        decision,
    ):
        """
        Traduce la decisione del Coach Engine
        in un livello di rischio leggibile.
        """

        decision_name = self._get_decision_name(
            decision
        )

        strategy = self._get_first_value(
            decision,
            (
                "strategy",
                "Strategia",
            ),
        )

        decision_upper = str(
            decision_name or ""
        ).strip().upper()

        strategy_upper = str(
            strategy or ""
        ).strip().upper()

        if (
            decision_upper == "RECUPERA"
            or strategy_upper == "RECOVERY"
        ):
            return "ALTO"

        if (
            decision_upper == "RIDUZIONE"
            or strategy_upper == "REDUCE_LOAD"
        ):
            return "MEDIO-ALTO"

        if (
            decision_upper == "ADATTA"
            or strategy_upper == "ADAPT"
        ):
            return "MODERATO"

        if (
            decision_upper == "CONFERMA"
            or strategy_upper == "KEEP_PLAN"
        ):
            return "BASSO"

        return "NON DETERMINATO"

    def _get_decision_name(
        self,
        decision,
    ):
        """
        Recupera il nome della decisione usando
        le chiavi Python o Airtable.
        """

        value = self._get_first_value(
            decision,
            (
                "decision",
                "Decisione IronCoach",
            ),
        )

        if not self._has_value(value):
            return None

        return self._format_value(
            value
        )

    # -------------------------------------------------
    # DECISIONI
    # -------------------------------------------------

    def _append_decision(
        self,
        report,
        decision,
    ):
        """
        Aggiunge una decisione al report.

        Gestisce sia le chiavi interne Python sia
        i nomi dei campi salvati su Airtable.
        """

        if not isinstance(decision, dict):
            report.append(
                self._format_value(decision)
            )
            return

        mapping = [
            ("Decisione IronCoach", "Decisione"),
            ("decision", "Decisione"),
            ("Motivazione", "Motivazione"),
            ("reason", "Motivazione"),
            ("Priorità", "Priorità"),
            ("priority", "Priorità"),
            ("Confidenza", "Confidenza"),
            ("confidence", "Confidenza"),
            ("Strategia", "Strategia"),
            ("strategy", "Strategia"),
            ("Azione consigliata", "Azione"),
            ("recommended_action", "Azione"),
        ]

        printed_labels = set()

        for source, label in mapping:
            if label in printed_labels:
                continue

            value = decision.get(source)

            if not self._has_value(value):
                continue

            report.append(
                f"{label}: {self._format_value(value)}"
            )

            printed_labels.add(label)

        if not printed_labels:
            report.append(
                "Nessun dettaglio disponibile."
            )

        workout = self._extract_modified_workout(
            decision
        )

        if workout:
            report.append("")
            report.append("ALLENAMENTO MODIFICATO")
            report.append("-" * 60)

            self._append_workout(
                report,
                workout,
            )

    def _extract_modified_workout(
        self,
        decision,
    ):
        """
        Estrae l'allenamento modificato dalla decisione.

        Il Coach Engine utilizza la chiave:
            modified_workout

        Airtable utilizza la chiave:
            Allenamento modificato
        """

        workout_keys = (
            "modified_workout",
            "Allenamento modificato",
        )

        for key in workout_keys:
            if key not in decision:
                continue

            value = decision.get(key)

            if (
                isinstance(value, dict)
                and "value" in value
            ):
                value = value.get("value")

            parsed_value = self._parse_serialized_workout(
                value
            )

            if self._has_value(parsed_value):
                return parsed_value

        return None

    def _parse_serialized_workout(
        self,
        workout,
    ):
        """
        Converte in dizionario un allenamento che Airtable
        restituisce sotto forma di stringa.

        Sono supportati:

        JSON:
            {"strategy": "ADAPT"}

        Rappresentazione Python:
            {'strategy': 'ADAPT'}
        """

        if not isinstance(workout, str):
            return workout

        cleaned_workout = workout.strip()

        if not cleaned_workout:
            return None

        if not (
            cleaned_workout.startswith("{")
            and cleaned_workout.endswith("}")
        ):
            return cleaned_workout

        try:
            parsed_workout = json.loads(
                cleaned_workout
            )

            if isinstance(parsed_workout, dict):
                return parsed_workout

        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            pass

        try:
            parsed_workout = ast.literal_eval(
                cleaned_workout
            )

            if isinstance(parsed_workout, dict):
                return parsed_workout

        except (
            SyntaxError,
            ValueError,
        ):
            pass

        return cleaned_workout

    # -------------------------------------------------
    # ALLENAMENTO MODIFICATO
    # -------------------------------------------------

    def _append_workout(
        self,
        report,
        workout,
    ):
        """
        Mostra l'allenamento modificato in formato
        multilinea leggibile.
        """

        if not isinstance(workout, dict):
            report.append(
                self._format_value(workout)
            )
            return

        fields = [
            ("strategy", "Strategia"),
            ("original_workout", "Seduta originale"),
            ("sport", "Sport"),
            ("sport_category", "Categoria sport"),
            ("original_type", "Tipo originale"),
            ("original_zone", "Zona originale"),
            (
                "original_duration_minutes",
                "Durata originale",
            ),
            ("duration_minutes", "Nuova durata"),
            ("intensity", "Intensità"),
            ("warmup", "Riscaldamento"),
            ("main_set", "Parte centrale"),
            ("cooldown", "Defaticamento"),
            ("technical_focus", "Focus tecnico"),
            ("removed_elements", "Elementi rimossi"),
            ("alternative", "Alternativa"),
            ("notes", "Note"),
        ]

        printed_fields = 0

        for key, label in fields:
            value = workout.get(key)

            if not self._has_value(value):
                continue

            formatted_value = self._format_value(
                value
            )

            if key in {
                "original_duration_minutes",
                "duration_minutes",
            }:
                formatted_value = self._append_unit(
                    formatted_value,
                    "min",
                )

            report.append(
                f"{label}: {formatted_value}"
            )
            printed_fields += 1

        if printed_fields == 0:
            report.append(
                "Allenamento modificato disponibile, "
                "ma privo di dettagli leggibili."
            )

    # -------------------------------------------------
    # UTILITÀ
    # -------------------------------------------------

    def _find_value(
        self,
        data,
        key,
    ):
        """
        Recupera un valore da un dizionario.
        """

        if not isinstance(data, dict):
            return None

        return data.get(key)

    def _get_first_value(
        self,
        data,
        keys,
    ):
        """
        Restituisce il primo valore disponibile
        tra più possibili chiavi.
        """

        if not isinstance(data, dict):
            return None

        for key in keys:
            value = data.get(key)

            if self._has_value(value):
                return value

        return None

    def _has_value(
        self,
        value,
    ):
        """
        Verifica se un valore contiene dati utili.

        Il valore numerico zero è considerato valido.
        """

        if value is None:
            return False

        if isinstance(value, str):
            return bool(value.strip())

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
                dict,
            ),
        ):
            return bool(value)

        return True

    def _to_float(
        self,
        value,
    ):
        """
        Converte un valore numerico in float.

        Restituisce None quando la conversione
        non è possibile.
        """

        if value is None:
            return None

        if isinstance(value, dict) and "value" in value:
            value = value.get("value")

        if isinstance(value, str):
            cleaned_value = value.strip().replace(
                ",",
                ".",
            )

            if not cleaned_value:
                return None

            try:
                return float(
                    cleaned_value
                )
            except ValueError:
                return None

        if isinstance(
            value,
            (
                int,
                float,
            ),
        ):
            return float(value)

        return None

    def _format_number(
        self,
        value,
    ):
        """
        Evita la visualizzazione di decimali inutili.
        """

        if value is None:
            return "N/D"

        numeric_value = self._to_float(
            value
        )

        if numeric_value is None:
            return self._format_value(
                value
            )

        if numeric_value.is_integer():
            return str(
                int(numeric_value)
            )

        return str(
            round(numeric_value, 2)
        )

    def _append_unit(
        self,
        value,
        unit,
    ):
        """
        Aggiunge un'unità di misura evitando duplicazioni.
        """

        if value == "N/D":
            return value

        value_text = str(value).strip()

        if value_text.lower().endswith(
            unit.lower()
        ):
            return value_text

        return f"{value_text} {unit}"

    def _format_value(
        self,
        value,
    ):
        """
        Converte i valori Python e Airtable
        in testo leggibile.

        Gestisce:
        - valori None;
        - campi AI Airtable con chiave value;
        - liste;
        - dizionari;
        - stringhe vuote.
        """

        if value is None:
            return "N/D"

        if isinstance(value, dict):
            if "value" in value:
                generated_value = value.get(
                    "value"
                )

                if not self._has_value(
                    generated_value
                ):
                    return "N/D"

                return self._format_value(
                    generated_value
                )

            if not value:
                return "N/D"

            formatted_items = []

            for key, nested_value in value.items():
                formatted_items.append(
                    f"{key}: "
                    f"{self._format_value(nested_value)}"
                )

            return ", ".join(
                formatted_items
            )

        if isinstance(value, list):
            if not value:
                return "N/D"

            return ", ".join(
                self._format_value(item)
                for item in value
            )

        if isinstance(value, str):
            cleaned_value = value.strip()

            if not cleaned_value:
                return "N/D"

            return cleaned_value

        return str(value)