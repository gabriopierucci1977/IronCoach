"""
IronCoach Report Builder

Costruisce un report leggibile a partire
dal Context Builder e dal Coach Engine.
"""


class ReportBuilder:
    """
    Converte il contesto IronCoach e la decisione finale
    in un report testuale leggibile.
    """

    WORKOUT_FIELD_LABELS = {
        "strategy": "Strategia",
        "original_workout": "Seduta originale",
        "sport": "Sport",
        "sport_category": "Categoria sport",
        "original_type": "Tipo originale",
        "original_zone": "Zona originale",
        "original_duration_minutes": "Durata originale",
        "duration_minutes": "Nuova durata",
        "intensity": "Intensità",
        "warmup": "Riscaldamento",
        "main_set": "Parte centrale",
        "cooldown": "Defaticamento",
        "technical_focus": "Focus tecnico",
        "removed_elements": "Elementi rimossi",
        "alternative": "Alternativa",
        "notes": "Note",
    }

    DECISION_FIELD_LABELS = {
        "decision": "Decisione",
        "Decisione IronCoach": "Decisione IronCoach",
        "reason": "Motivazione",
        "Motivazione": "Motivazione",
        "priority": "Priorità",
        "Priorità": "Priorità",
        "confidence": "Confidenza",
        "Confidenza": "Confidenza",
        "strategy": "Strategia",
        "Strategia": "Strategia",
        "recommended_action": "Azione consigliata",
        "Azione consigliata": "Azione consigliata",
        "Data": "Data",
    }

    MODIFIED_WORKOUT_KEYS = (
        "modified_workout",
        "Allenamento modificato",
    )

    LAST_DECISION_FIELDS = (
        "Data",
        "Decisione IronCoach",
        "decision",
        "Strategia",
        "strategy",
        "Priorità",
        "priority",
        "Confidenza",
        "confidence",
        "Motivazione",
        "reason",
    )

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

        self._append_section(
            report,
            "ATLETA",
            athlete,
        )

        self._append_section(
            report,
            "RECOVERY",
            recovery,
        )

        self._append_section(
            report,
            "TRAINING",
            training,
        )

        self._append_section(
            report,
            "NUTRITION",
            nutrition,
        )

        report.append("")
        report.append("ULTIMA DECISIONE")
        report.append("-" * 60)

        if last_decision:
            self._append_last_decision_summary(
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
            include_modified_workout=True,
        )

        report.append("")
        report.append("=" * 60)

        return "\n".join(report)

    def _append_section(
        self,
        report,
        title,
        data,
    ):
        """
        Aggiunge una sezione standard al report.
        """

        report.append("")
        report.append(title)
        report.append("-" * 60)

        if data:
            self._append_fields(
                report,
                data,
            )
        else:
            report.append(
                "Nessun dato disponibile."
            )

    def _append_last_decision_summary(
        self,
        report,
        decision,
    ):
        """
        Mostra un riepilogo compatto dell'ultima decisione
        salvata su Airtable.

        L'allenamento modificato precedente non viene
        ristampato integralmente per evitare duplicazioni.
        """

        if not isinstance(decision, dict):
            report.append(
                self._format_value(decision)
            )
            return

        summary_fields = self._select_last_decision_fields(
            decision
        )

        if summary_fields:
            self._append_fields(
                report,
                summary_fields,
                labels=self.DECISION_FIELD_LABELS,
            )
        else:
            report.append(
                "Nessun dettaglio disponibile."
            )

        modified_workout = self._extract_modified_workout(
            decision
        )

        if modified_workout:
            self._append_workout_summary(
                report,
                modified_workout,
            )

    def _select_last_decision_fields(
        self,
        decision,
    ):
        """
        Seleziona soltanto i campi principali
        dell'ultima decisione.
        """

        selected_fields = {}
        selected_concepts = set()

        concept_aliases = {
            "Data": "date",
            "Decisione IronCoach": "decision",
            "decision": "decision",
            "Strategia": "strategy",
            "strategy": "strategy",
            "Priorità": "priority",
            "priority": "priority",
            "Confidenza": "confidence",
            "confidence": "confidence",
            "Motivazione": "reason",
            "reason": "reason",
        }

        for key in self.LAST_DECISION_FIELDS:
            if key not in decision:
                continue

            concept = concept_aliases.get(
                key,
                key,
            )

            if concept in selected_concepts:
                continue

            value = decision.get(key)

            if value in (
                None,
                "",
            ):
                continue

            selected_fields[key] = value
            selected_concepts.add(concept)

        return selected_fields

    def _append_workout_summary(
        self,
        report,
        modified_workout,
    ):
        """
        Mostra un riepilogo sintetico dell'allenamento
        modificato collegato all'ultima decisione.
        """

        report.append("")
        report.append(
            "Riepilogo allenamento precedente:"
        )

        if not isinstance(modified_workout, dict):
            report.append(
                self._format_value(modified_workout)
            )
            return

        summary_keys = (
            "sport",
            "original_workout",
            "duration_minutes",
            "intensity",
        )

        summary_parts = []

        for key in summary_keys:
            value = modified_workout.get(key)

            if value in (
                None,
                "",
            ):
                continue

            label = self.WORKOUT_FIELD_LABELS.get(
                key,
                self._humanize_key(key),
            )

            formatted_value = self._format_value(
                value
            )

            formatted_value = (
                self._format_workout_field_value(
                    key,
                    formatted_value,
                )
            )

            summary_parts.append(
                f"{label}: {formatted_value}"
            )

        if summary_parts:
            report.append(
                " | ".join(summary_parts)
            )
        else:
            report.append(
                "Allenamento modificato disponibile."
            )

    def _append_decision(
        self,
        report,
        decision,
        include_modified_workout=True,
    ):
        """
        Aggiunge una decisione al report separando
        l'eventuale allenamento modificato dagli altri campi.
        """

        if not isinstance(decision, dict):
            report.append(
                self._format_value(decision)
            )
            return

        modified_workout = self._extract_modified_workout(
            decision
        )

        decision_fields = {
            key: value
            for key, value in decision.items()
            if key not in self.MODIFIED_WORKOUT_KEYS
        }

        if decision_fields:
            self._append_fields(
                report,
                decision_fields,
                labels=self.DECISION_FIELD_LABELS,
            )
        else:
            report.append(
                "Nessun dettaglio disponibile."
            )

        if (
            include_modified_workout
            and modified_workout
        ):
            self._append_modified_workout(
                report,
                modified_workout,
            )

    def _append_modified_workout(
        self,
        report,
        modified_workout,
    ):
        """
        Mostra l'allenamento modificato come sezione
        multilinea leggibile.
        """

        report.append("")
        report.append("ALLENAMENTO MODIFICATO")
        report.append("-" * 60)

        if isinstance(modified_workout, dict):
            self._append_fields(
                report,
                modified_workout,
                labels=self.WORKOUT_FIELD_LABELS,
                format_workout_units=True,
            )
            return

        formatted_value = self._format_value(
            modified_workout
        )

        if formatted_value == "N/D":
            report.append(
                "Nessun allenamento modificato."
            )
        else:
            report.append(
                formatted_value
            )

    def _append_fields(
        self,
        report,
        data,
        labels=None,
        format_workout_units=False,
    ):
        """
        Aggiunge al report tutti i campi di un dizionario.

        Args:
            report (list): Righe del report.
            data (dict): Campi da aggiungere.
            labels (dict | None): Etichette leggibili opzionali.
            format_workout_units (bool): Aggiunge unità di misura
                ai campi dell'allenamento modificato.
        """

        if not isinstance(data, dict):
            report.append(
                self._format_value(data)
            )
            return

        labels = labels or {}

        for key, value in data.items():
            label = labels.get(
                key,
                self._humanize_key(key),
            )

            formatted_value = self._format_value(
                value
            )

            if format_workout_units:
                formatted_value = (
                    self._format_workout_field_value(
                        key,
                        formatted_value,
                    )
                )

            report.append(
                f"{label}: {formatted_value}"
            )

    def _extract_modified_workout(
        self,
        decision,
    ):
        """
        Estrae l'allenamento modificato dalla decisione.

        Gestisce sia il nome interno Python sia il nome
        salvato su Airtable.
        """

        for key in self.MODIFIED_WORKOUT_KEYS:
            if key not in decision:
                continue

            value = decision.get(key)

            if (
                isinstance(value, dict)
                and "value" in value
            ):
                value = value.get("value")

            parsed_value = (
                self._parse_dictionary_string(
                    value
                )
            )

            if parsed_value not in (
                None,
                "",
                {},
            ):
                return parsed_value

        return None

    def _parse_dictionary_string(
        self,
        value,
    ):
        """
        Converte in dizionario una rappresentazione testuale
        Python o JSON, quando possibile.

        Airtable può restituire il campo Allenamento modificato
        come stringa anziché come dizionario.
        """

        if not isinstance(value, str):
            return value

        cleaned_value = value.strip()

        if not cleaned_value:
            return None

        if not (
            cleaned_value.startswith("{")
            and cleaned_value.endswith("}")
        ):
            return cleaned_value

        try:
            import json

            parsed_value = json.loads(
                cleaned_value
            )

            if isinstance(parsed_value, dict):
                return parsed_value

        except (
            TypeError,
            ValueError,
        ):
            pass

        try:
            import ast

            parsed_value = ast.literal_eval(
                cleaned_value
            )

            if isinstance(parsed_value, dict):
                return parsed_value

        except (
            SyntaxError,
            ValueError,
        ):
            pass

        return cleaned_value

    def _format_workout_field_value(
        self,
        key,
        formatted_value,
    ):
        """
        Aggiunge unità di misura ai campi temporali
        dell'allenamento modificato.
        """

        duration_keys = {
            "original_duration_minutes",
            "duration_minutes",
        }

        if (
            key in duration_keys
            and formatted_value != "N/D"
        ):
            return f"{formatted_value} min"

        return formatted_value

    def _humanize_key(
        self,
        key,
    ):
        """
        Converte una chiave tecnica in un'etichetta leggibile.

        Esempio:
            original_workout -> Original workout
        """

        text = str(key).replace(
            "_",
            " ",
        ).strip()

        if not text:
            return "Campo"

        return (
            text[:1].upper()
            + text[1:]
        )

    def _format_value(
        self,
        value,
    ):
        """
        Converte i valori Airtable in un formato leggibile.

        Gestisce in particolare:
        - campi AI Airtable con chiavi state/value/isStale;
        - liste di record collegati;
        - valori None;
        - stringhe multilinea;
        - dizionari annidati.
        """

        if value is None:
            return "N/D"

        if isinstance(value, dict):
            if "value" in value:
                generated_value = value.get(
                    "value"
                )

                if generated_value in (
                    None,
                    "",
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
                    f"{key}="
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