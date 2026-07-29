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

        athlete = context.get("athlete", {})
        recovery = context.get("recovery", {})
        training = context.get("training", {})
        nutrition = context.get("nutrition", {})
        last_decision = context.get("decision", {})

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
    # COACH SUMMARY
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
        )

        training = context.get(
            "training",
            {}
        )


        report.append("")
        report.append(
            "SINTESI DEL COACH"
        )

        report.append(
            "-" * 60
        )


        recovery_state = self._get_text(
            recovery,
            "Stato Recovery",
            "stato_recovery"
        )

        recovery_score = self._get_value(
            recovery,
            "Recovery Score",
            "recovery_score"
        )

        sleep_score = self._get_value(
            recovery,
            "Sleep Score",
            "sleep_score"
        )

        rpe = self._get_value(
            training,
            "RPE percepito",
            "rpe"
        )

        workout = self._get_text(
            training,
            "Nome seduta",
            "nome_seduta"
        )


        if recovery_state:
            report.append(
                f"• Stato recovery: {recovery_state}, "
                f"Recovery Score {recovery_score}"
            )


        if sleep_score:
            hours = self._get_value(
                recovery,
                "Ore sonno",
                "ore_sonno"
            )

            if hours:
                report.append(
                    f"• Sonno: Sleep Score {sleep_score}; "
                    f"{hours} ore registrate"
                )


        if workout:
            report.append(
                f"• Ultima seduta: {workout} "
                f"(RPE {rpe}/10)"
            )


        nutrition = context.get(
            "nutrition",
            {}
        )

        nutrition_state = self._get_text(
            nutrition,
            "Stato recupero nutrizionale"
        )

        if nutrition_state:
            report.append(
                f"• Nutrizione: {nutrition_state}"
            )


        risk = decision.get(
            "risk_level"
        )

        if risk:
            report.append(
                ""
            )
            report.append(
                f"Rischio complessivo: {risk}"
            )



    # -------------------------------------------------
    # SECTIONS
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
    # FIELD FORMATTER
    # -------------------------------------------------

    def _append_fields(
        self,
        report,
        data
    ):

        if not isinstance(data, dict):
            return


        for key, value in data.items():


            normalized = str(
                key
            ).lower().strip()


            if normalized in (
                "modified_workout",
                "allenamento modificato",
                "allenamento_modificato",
            ):

                workout = self._parse_workout(
                    value
                )

                if workout:

                    self._append_modified_workout(
                        report,
                        workout
                    )

                else:

                    report.append(
                        "Allenamento modificato: "
                        + self._format_value(value)
                    )

                continue



            label = self._label(
                key
            )


            report.append(
                f"{label}: "
                f"{self._format_value(value)}"
            )



    # -------------------------------------------------
    # WORKOUT FORMAT
    # -------------------------------------------------

    def _append_modified_workout(
        self,
        report,
        workout
    ):

        report.append("")
        report.append(
            "ALLENAMENTO MODIFICATO"
        )

        report.append(
            "-" * 60
        )


        labels = {

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

            label = labels.get(
                key,
                key
            )


            report.append(
                f"{label}: "
                f"{self._format_value(value)}"
            )



    # -------------------------------------------------
    # WORKOUT PARSER
    # -------------------------------------------------

    def _parse_workout(
        self,
        value
    ):

        if isinstance(value, dict):
            return value


        return None



    # -------------------------------------------------
    # UTILITY
    # -------------------------------------------------

    def _get_value(
        self,
        data,
        *names
    ):

        if not isinstance(data, dict):
            return None


        for name in names:

            if name in data:

                value = data[name]

                if value not in (
                    None,
                    ""
                ):
                    return value


        return None



    def _get_text(
        self,
        data,
        *names
    ):

        value = self._get_value(
            data,
            *names
        )


        if value is None:
            return ""


        return str(value).strip()



    def _label(
        self,
        key
    ):

        labels = {

            "reason":
                "Motivazione",

            "confidence":
                "Confidenza",

            "strategy":
                "Strategia",

            "recommended_action":
                "Azione",

            "priority":
                "Priorità",

            "risk_level":
                "Livello rischio",

            "reasoning":
                "Ragionamento",

        }


        return labels.get(
            key,
            key
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
                [
                    f"{k}: {self._format_value(v)}"
                    for k, v in value.items()
                ]
            )


        if isinstance(value, list):

            return ", ".join(
                self._format_value(v)
                for v in value
            )


        return str(value).strip()