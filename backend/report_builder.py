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

    def build(self, context, decision):
        """
        Costruisce il report completo.

        Args:
            context (dict): Contesto prodotto dal Context Builder.
            decision (dict): Decisione prodotta dal Coach Engine.

        Returns:
            str: Report testuale completo.
        """

        athlete = context.get("athlete", {})
        recovery = context.get("recovery", {})
        training = context.get("training", {})
        nutrition = context.get("nutrition", {})
        last_decision = context.get("decision", {})

        report = []

        report.append("=" * 60)
        report.append("IRONCOACH REPORT")
        report.append("=" * 60)

        self._append_section(report, "ATLETA", athlete)
        self._append_section(report, "RECOVERY", recovery)
        self._append_section(report, "TRAINING", training)
        self._append_section(report, "NUTRITION", nutrition)

        report.append("")
        report.append("ULTIMA DECISIONE")
        report.append("-" * 60)

        if last_decision:
            self._append_fields(report, last_decision)
        else:
            report.append("Nessuna decisione precedente.")

        report.append("")
        report.append("=" * 60)
        report.append("DECISIONE DEL COACH")
        report.append("=" * 60)

        self._append_fields(report, decision)

        report.append("")
        report.append("=" * 60)

        return "\n".join(report)

    def _append_section(self, report, title, data):
        """
        Aggiunge una sezione standard al report.
        """

        report.append("")
        report.append(title)
        report.append("-" * 60)

        if data:
            self._append_fields(report, data)
        else:
            report.append("Nessun dato disponibile.")

    def _append_fields(self, report, data):
        """
        Aggiunge al report tutti i campi di un dizionario.
        """

        for key, value in data.items():
            formatted_value = self._format_value(value)
            report.append(f"{key}: {formatted_value}")

    def _format_value(self, value):
        """
        Converte i valori Airtable in un formato leggibile.

        Gestisce in particolare:
        - campi AI Airtable con chiavi state/value/isStale;
        - liste di record collegati;
        - valori None;
        - stringhe multilinea.
        """

        if value is None:
            return "N/D"

        if isinstance(value, dict):
            if "value" in value:
                generated_value = value.get("value")

                if generated_value in (None, ""):
                    return "N/D"

                return str(generated_value).strip()

            if not value:
                return "N/D"

            formatted_items = []

            for key, nested_value in value.items():
                formatted_items.append(
                    f"{key}={self._format_value(nested_value)}"
                )

            return ", ".join(formatted_items)

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