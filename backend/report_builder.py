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



        # ----------------------------------------------
        # PROFILO ATLETA
        # ----------------------------------------------

        athlete_profile = intelligence.get(
            "athlete_profile",
            {},
        ) or {}


        if athlete_profile:


            if isinstance(
                athlete_profile,
                dict,
            ):


                profile_summary = {

                    "tipo atleta":
                        athlete_profile.get(
                            "tipo_atleta",
                            athlete_profile.get(
                                "athlete_type",
                                "N/D",
                            ),
                        ),


                    "punti di forza":
                        athlete_profile.get(
                            "strengths",
                            "N/D",
                        ),


                    "limitazioni note":
                        athlete_profile.get(
                            "limitations",
                            "N/D",
                        ),


                    "preferenze allenamento":
                        athlete_profile.get(
                            "training_preferences",
                            "N/D",
                        ),


                    "tolleranza al carico":
                        athlete_profile.get(
                            "load_tolerance",
                            "N/D",
                        ),


                    "pattern infortuni":
                        athlete_profile.get(
                            "injury_patterns",
                            "N/D",
                        ),

                }


                self._append_block(
                    report,
                    "PROFILO ATLETA",
                    profile_summary,
                )


        # ----------------------------------------------
        # LOAD
        # ----------------------------------------------

        self._append_block(
            report,
            "CARICO STORICO",
            intelligence.get(
                "load",
                {},
            ),
        )


        # ----------------------------------------------
        # ADAPTATION
        # ----------------------------------------------

        self._append_block(
            report,
            "ADATTAMENTO AL CARICO",
            intelligence.get(
                "adaptation",
                {},
            ),
        )


        # ----------------------------------------------
        # RECOVERY TREND
        # ----------------------------------------------

        self._append_block(
            report,
            "TREND RECOVERY",
            intelligence.get(
                "recovery_trend",
                {},
            ),
        )


        # ----------------------------------------------
        # PERFORMANCE
        # ----------------------------------------------

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
    # MODIFIED WORKOUT
    # ==================================================

    def _append_modified_workout(
        self,
        report,
        workout,
    ):

        if not isinstance(
            workout,
            dict,
        ):
            return


        report.append("")
        report.append(
            "ALLENAMENTO MODIFICATO"
        )
        report.append("-" * 60)


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

            "alternative":
                "Alternativa",

            "notes":
                "Note",

        }


        for key, value in workout.items():

            report.append(
                f"{mapping.get(key,key)}: "
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


        recovery_state = (
            recovery.get("Stato recovery")
            or recovery.get("stato_recovery")
            or recovery.get("recovery_state")
            or "N/D"
        )


        recovery_score = (
            recovery.get("Recovery score")
            or recovery.get("Recovery Score")
            or recovery.get("recovery_score")
            or "N/D"
        )


        sleep = (
            recovery.get("Sleep score")
            or recovery.get("Sleep Score")
            or "N/D"
        )


        sleep_hours = (
            recovery.get("Ore sonno")
            or "N/D"
        )


        workout = (
            training.get("Nome seduta")
            or "N/D"
        )


        nutrition_state = (
            nutrition.get(
                "Stato recupero nutrizionale"
            )
            or "N/D"
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



    # ==================================================
    # GENERIC HELPERS
    # ==================================================

    def _append_section(
        self,
        report,
        title,
        data,
    ):

        report.append("")
        report.append(title)
        report.append("-" * 60)

        self._append_fields(
            report,
            data,
        )



    def _append_fields(
        self,
        report,
        data,
        skip_keys=None,
    ):

        if not isinstance(
            data,
            dict,
        ):
            return


        skip_keys = skip_keys or []


        for key, value in data.items():

            if key in skip_keys:
                continue


            report.append(
                f"{self._label(key)}: "
                f"{self._format_value(value)}"
            )



    def _label(
        self,
        key,
    ):

        return (
            str(key)
            .replace("_"," ")
            .capitalize()
        )



    def _format_value(
        self,
        value,
    ):

        if isinstance(
            value,
            dict,
        ):

            return "; ".join(
                [
                    f"{k}={v}"
                    for k,v in value.items()
                ]
            )


        if isinstance(
            value,
            list,
        ):

            return ", ".join(
                [
                    str(v)
                    for v in value
                ]
            )


        return str(value)