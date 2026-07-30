"""
IronCoach Report Builder

Costruisce un report leggibile
dal Context Builder e dal Coach Engine.
"""


class ReportBuilder:


    def build(
        self,
        context,
        decision,
    ):

        context = context or {}
        decision = decision or {}


        athlete = context.get(
            "athlete",
            {},
        ) or {}

        recovery = context.get(
            "recovery",
            {},
        ) or {}

        training = context.get(
            "training",
            {},
        ) or {}

        nutrition = context.get(
            "nutrition",
            {},
        ) or {}

        last_decision = context.get(
            "decision",
            {},
        ) or {}


        intelligence = decision.get(
            "intelligence",
            {},
        ) or {}


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


        self._append_coach_summary(
            report,
            context,
            decision,
        )


        self._append_intelligence(
            report,
            intelligence,
        )


        report.append("")
        report.append(
            "ULTIMA DECISIONE REGISTRATA"
        )
        report.append("-" * 60)


        self._append_fields(
            report,
            last_decision,
        )


        report.append("")
        report.append("=" * 60)
        report.append(
            "DECISIONE DEL COACH"
        )
        report.append("=" * 60)


        self._append_fields(
            report,
            decision,
            skip_keys=[
                "intelligence",
                "modified_workout",
                "allenamento modificato",
            ],
        )


        modified_workout = (
            decision.get(
                "modified_workout",
            )
            or decision.get(
                "allenamento modificato",
            )
        )


        if modified_workout:

            self._append_modified_workout(
                report,
                modified_workout,
            )


        report.append("")
        report.append("=" * 60)


        return "\n".join(report)



    # ==================================================
    # INTELLIGENCE
    # ==================================================

    def _append_intelligence(
        self,
        report,
        intelligence,
    ):

        if not intelligence:
            return


        report.append("")
        report.append(
            "INTELLIGENCE ATLETA"
        )
        report.append("-" * 60)


        # Il profilo atleta è già presente nella sezione ATLETA.
        # Evitiamo duplicazione del report.


        self._append_block(
            report,
            "CARICO STORICO",
            intelligence.get(
                "load",
                {},
            ),
        )


        self._append_block(
            report,
            "ADATTAMENTO AL CARICO",
            intelligence.get(
                "adaptation",
                {},
            ),
        )


        self._append_block(
            report,
            "TREND RECOVERY",
            intelligence.get(
                "recovery_trend",
                {},
            ),
        )


        self._append_block(
            report,
            "TREND PERFORMANCE",
            intelligence.get(
                "performance",
                {},
            ),
        )



    def _append_block(
        self,
        report,
        title,
        data,
    ):

        if not data:
            return


        report.append("")
        report.append(title)


        for key, value in data.items():

            report.append(
                f"• {self._label(key)}: "
                f"{self._format_value(value)}"
            )



    # ==================================================
    # SUMMARY
    # ==================================================

    def _append_coach_summary(
        self,
        report,
        context,
        decision,
    ):

        recovery = context.get(
            "recovery",
            {},
        ) or {}

        training = context.get(
            "training",
            {},
        ) or {}

        nutrition = context.get(
            "nutrition",
            {},
        ) or {}


        report.append("")
        report.append(
            "SINTESI DEL COACH"
        )
        report.append("-" * 60)


        recovery_state = self._first_value(
            recovery,
            [
                "Stato recovery",
                "stato_recovery",
                "recovery_state",
                "Recovery state",
                "Recovery Stato",
            ],
            "N/D",
        )


        recovery_score = self._first_value(
            recovery,
            [
                "Recovery score",
                "Recovery Score",
                "recovery_score",
            ],
            "N/D",
        )


        sleep = self._first_value(
            recovery,
            [
                "Sleep score",
                "Sleep Score",
                "sleep_score",
            ],
            "N/D",
        )


        sleep_hours = self._first_value(
            recovery,
            [
                "Ore sonno",
                "ore_sonno",
                "sleep_hours",
            ],
            "N/D",
        )


        workout = self._first_value(
            training,
            [
                "Nome seduta",
                "nome_seduta",
            ],
            "N/D",
        )


        nutrition_state = self._first_value(
            nutrition,
            [
                "Stato recupero nutrizionale",
                "stato_recupero_nutrizionale",
            ],
            "N/D",
        )


        report.append(
            f"• Stato recovery: "
            f"{recovery_state}, "
            f"Recovery Score {recovery_score}"
        )


        report.append(
            f"• Sonno: Sleep Score {sleep}; "
            f"{sleep_hours} ore registrate"
        )


        report.append(
            f"• Ultima seduta: {workout}"
        )


        report.append(
            f"• Nutrizione: {nutrition_state}"
        )


        risk = decision.get(
            "risk_level",
            "N/D",
        )


        report.append("")
        report.append(
            f"Rischio complessivo: {risk}"
        )



    def _first_value(
        self,
        data,
        keys,
        default="N/D",
    ):

        for key in keys:

            value = data.get(key)

            if value is not None and value != "":
                return value

        return default