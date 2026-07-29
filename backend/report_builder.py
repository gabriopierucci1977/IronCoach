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
    # SEZIONI
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
                formatted_value = (
                    self._append_unit(
                        formatted_value,
                        "min",
                    )
                )

            if source == "Distanza km":
                formatted_value = (
                    self._append_unit(
                        formatted_value,
                        "km",
                    )
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

            parsed_value = (
                self._parse_serialized_workout(
                    value
                )
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
                formatted_value = (
                    self._append_unit(
                        formatted_value,
                        "min",
                    )
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