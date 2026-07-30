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
            athlete
        )

        self._append_section(
            report,
            "RECOVERY",
            recovery
        )

        self._append_section(
            report,
            "TRAINING",
            training
        )

        self._append_section(
            report,
            "NUTRITION",
            nutrition
        )

        self._append_coach_summary(
            report,
            context,
            decision
        )

        self._append_intelligence(
            report,
            decision
        )

        report.append("")
        report.append("ULTIMA DECISIONE REGISTRATA")
        report.append("-" * 60)

        if last_decision:
            self._append_fields(
                report,
                last_decision
            )
        else:
            report.append(
                "Nessuna decisione precedente."
            )

        report.append("")
        report.append("=" * 60)
        report.append("DECISIONE DEL COACH")
        report.append("=" * 60)

        self._append_fields(
            report,
            decision
        )

        report.append("")
        report.append("=" * 60)

        return "\n".join(report)


    # -------------------------------------------------
    # SEZIONI STANDARD
    # -------------------------------------------------

    def _append_section(
        self,
        report,
        title,
        data
    ):

        report.append("")
        report.append(title)
        report.append("-" * 60)

        if data:

            self._append_fields(
                report,
                data
            )

        else:

            report.append(
                "Nessun dato disponibile."
            )


    # -------------------------------------------------
    # CAMPI
    # -------------------------------------------------

    def _append_fields(
        self,
        report,
        data
    ):

        if not isinstance(data, dict):
            return

        modified_workout = None

        for key, value in data.items():

            # Intelligence viene mostrata
            # nella sezione dedicata
            if key == "intelligence":
                continue

            normalized = (
                str(key)
                .lower()
                .replace("_", " ")
                .strip()
            )

            if normalized in (
                "allenamento modificato",
                "modified workout"
            ):

                modified_workout = value
                continue

            report.append(
                f"{self._label(key)}: "
                f"{self._format_value(value)}"
            )


        if modified_workout:

            self._append_modified_workout(
                report,
                modified_workout
            )


    # -------------------------------------------------
    # INTELLIGENCE
    # -------------------------------------------------

    def _append_intelligence(
        self,
        report,
        decision
    ):

        intelligence = decision.get(
            "intelligence"
        )

        if not intelligence:
            return

        report.append("")
        report.append(
            "INTELLIGENCE ATLETA"
        )
        report.append(
            "-" * 60
        )

        if isinstance(intelligence, dict):

            for key, value in intelligence.items():

                report.append(
                    f"{self._label(key)}: "
                    f"{self._format_value(value)}"
                )

        else:

            report.append(
                self._format_value(intelligence)
            )


    # -------------------------------------------------
    # ALLENAMENTO MODIFICATO
    # -------------------------------------------------

    def _append_modified_workout(
        self,
        report,
        workout
    ):

        if not isinstance(workout, dict):
            return

        report.append("")
        report.append(
            "ALLENAMENTO MODIFICATO"
        )
        report.append(
            "-" * 60
        )

        mapping = {

            "strategy":
                "Strategia",

            "original_workout":
                "Seduta originale",

            "sport":
                "Sport",

            "sport_category":
                "Categoria sport",

            "original_type":
                "Tipo originale",

            "original_zone":
                "Zona originale",

            "original_duration_minutes":
                "Durata originale",

            "duration_minutes":
                "Nuova durata",

            "intensity":
                "Intensità",

            "warmup":
                "Riscaldamento",

            "main_set":
                "Parte centrale",

            "cooldown":
                "Defaticamento",

            "technical_focus":
                "Focus tecnico",

            "removed_elements":
                "Elementi rimossi",

            "alternative":
                "Alternativa",

            "notes":
                "Note",
        }


        for key, value in workout.items():

            label = mapping.get(
                key,
                self._label(key)
            )

            report.append(
                f"{label}: "
                f"{self._format_value(value)}"
            )


    # -------------------------------------------------
    # SINTESI COACH
    # -------------------------------------------------

    def _append_coach_summary(
        self,
        report,
        context,
        decision
    ):

        recovery = context.get(
            "recovery",
            {}
        ) or {}

        training = context.get(
            "training",
            {}
        ) or {}

        nutrition = context.get(
            "nutrition",
            {}
        ) or {}


        report.append("")
        report.append(
            "SINTESI DEL COACH"
        )
        report.append(
            "-" * 60
        )


        recovery_state = recovery.get(
            "Stato Recovery",
            recovery.get(
                "recovery_state",
                "N/D"
            )
        )

        recovery_score = recovery.get(
            "Recovery Score",
            recovery.get(
                "recovery_score",
                "N/D"
            )
        )

        sleep = recovery.get(
            "Sleep Score",
            "N/D"
        )

        sleep_hours = recovery.get(
            "Ore sonno",
            "N/D"
        )

        workout = training.get(
            "Nome seduta",
            "N/D"
        )

        rpe = training.get(
            "RPE percepito",
            "N/D"
        )

        nutrition_state = nutrition.get(
            "Stato recupero nutrizionale",
            "N/D"
        )


        report.append(
            f"• Stato recovery: {recovery_state}, "
            f"Recovery Score {recovery_score}"
        )

        report.append(
            f"• Sonno: Sleep Score {sleep}; "
            f"{sleep_hours} ore registrate"
        )

        report.append(
            f"• Ultima seduta: {workout} "
            f"(RPE {rpe}/10)"
        )

        report.append(
            f"• Nutrizione: {nutrition_state}"
        )


        risk = decision.get(
            "risk_level",
            decision.get(
                "risk",
                "N/D"
            )
        )

        report.append("")
        report.append(
            f"Rischio complessivo: {risk}"
        )


    # -------------------------------------------------
    # FORMATTAZIONE
    # -------------------------------------------------

    def _label(
        self,
        value
    ):

        return (
            str(value)
            .replace("_", " ")
            .capitalize()
        )


    def _format_value(
        self,
        value
    ):

        if value is None:
            return "N/D"


        if isinstance(value, dict):

            if "value" in value:

                return self._format_value(
                    value.get("value")
                )

            return ", ".join(
                f"{k}={self._format_value(v)}"
                for k, v in value.items()
            )


        if isinstance(value, list):

            if not value:
                return "N/D"

            return ", ".join(
                self._format_value(item)
                for item in value
            )


        if isinstance(value, str):

            value = value.strip()

            if not value:
                return "N/D"

            return value


        return str(value)