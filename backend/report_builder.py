"""
IronCoach Report Builder v0.3.1

Costruisce il report leggibile
dal Context Builder e dal Coach Engine.

Supporta:

- dati normalizzati IronCoach
- vecchio formato Airtable compatibile
- output intelligence Coach Engine
"""


class ReportBuilder:


    def build(
        self,
        context,
        decision,
    ):

        context = context or {}

        decision = decision or {}



        athlete = (

            context.get(
                "athlete"
            )

            or context.get(
                "athlete_profile"
            )

            or {}

        )



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



        report.append(
            "=" * 60
        )


        report.append(
            "IRONCOACH REPORT"
        )


        report.append(
            "=" * 60
        )



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

        self._append_context_warnings(
            report,
            self._resolve_context_warnings(
                context
            ),
        )

        self._append_coach_summary(
            report,
            context,
            decision,
        )



        self._append_intelligence(
            report,
            intelligence,
            decision,
        )



        report.append("")

        report.append(
            "ULTIMA DECISIONE REGISTRATA"
        )

        report.append(
            "-" * 60
        )



        self._append_decision_history(
            report,
            last_decision,
        )



        report.append("")

        report.append(
            "=" * 60
        )



        report.append(
            "DECISIONE DEL COACH"
        )



        report.append(
            "=" * 60
        )



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
                "modified_workout"
            )

            or decision.get(
                "allenamento modificato"
            )

        )



        if modified_workout:


            self._append_modified_workout(
                report,
                modified_workout,
            )



        report.append("")



        report.append(
            "=" * 60
        )



        return "\n".join(
            report
        )




    # ==================================================
    # DECISION HISTORY
    # ==================================================


    def _append_decision_history(
        self,
        report,
        decision,
    ):


        if not decision:

            return



        blocked = {


            "modified_workout",


            "allenamento modificato",


            "allenamento_modificato",

        }



        for key, value in decision.items():


            if str(key).lower() in blocked:

                continue



            report.append(

                f"{self._label(key)}: "
                f"{self._format_value(value)}"

            )
    # ==================================================
    # INTELLIGENCE
    # ==================================================


    def _append_intelligence(
        self,
        report,
        intelligence,
        decision=None,
    ):

        if not intelligence:

            return



        report.append("")



        report.append(
            "INTELLIGENCE ATLETA"
        )



        report.append(
            "-" * 60
        )



        athlete_profile = dict(
            intelligence.get(
                "athlete_profile",
                {},
            )
            or {}
        )

        goal_profile = dict(
            athlete_profile.get(
                "goal_profile",
                {},
            )
            or {}
        )

        resolved_goal_type = self._resolve_goal_type(
            intelligence=intelligence,
            decision=decision or {},
            current_goal_profile=goal_profile,
        )

        if resolved_goal_type:
            goal_profile["goal_type"] = resolved_goal_type
            athlete_profile["goal_profile"] = goal_profile

        self._append_block(
            report,
            "PROFILO ATLETA",
            athlete_profile,
        )



        self._append_block(
            report,
            "CARICO RECENTE",
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

        self._append_block(
            report,
            "FRESCHEZZA DATI",
            intelligence.get(
                "data_freshness",
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



        report.append(
            title
        )



        for key, value in data.items():


            report.append(

                f"• {self._label(key)}: "
                f"{self._format_value(value)}"

            )
    def _resolve_goal_type(
        self,
        intelligence,
        decision,
        current_goal_profile,
    ):
        """
        Recupera goal_type dalle diverse posizioni compatibili
        senza sovrascrivere un valore già presente.
        """

        current = self._first_value(
            current_goal_profile,
            [
                "goal_type",
                "Goal type",
                "tipo_obiettivo",
            ],
            default=None,
        )

        if current:
            return current

        candidates = [
            intelligence.get(
                "goal_profile"
            ),
            decision.get(
                "goal_profile"
            ),
            (
                decision.get(
                    "modified_workout",
                    {},
                )
                or {}
            ).get(
                "goal_profile"
            ),
            (
                decision.get(
                    "allenamento modificato",
                    {},
                )
                or {}
            ).get(
                "goal_profile"
            ),
        ]

        for candidate in candidates:
            if not isinstance(
                candidate,
                dict,
            ):
                continue

            value = self._first_value(
                candidate,
                [
                    "goal_type",
                    "Goal type",
                    "tipo_obiettivo",
                ],
                default=None,
            )

            if value:
                return value

        return None


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



        report.append(
            "-" * 60
        )



        mapping = {


            "strategy":

                "Strategia",



            "training_priority":

                "Priorità allenante",



            "stimulus_adjustment":

                "Adattamento stimolo",



            "goal_adjustment":

                "Adattamento obiettivo",



            "intensity_adjustment":

                "Adattamento intensità",



            "planned_zone":

                "Zona pianificata",



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
    # CONTEXT WARNINGS
    # ==================================================

    def _resolve_context_warnings(
        self,
        context,
    ):
        context = context or {}

        data_freshness = context.get(
            "data_freshness",
            {},
        ) or {}

        structured_reasons = (
            data_freshness.get(
                "reasons",
                [],
            )
            if isinstance(
                data_freshness,
                dict,
            )
            else []
        )

        legacy_warnings = context.get(
            "context_warnings",
            [],
        )

        merged = []
        seen = set()

        for item in [
            *(structured_reasons or []),
            *(legacy_warnings or []),
        ]:
            warning = str(item).strip()

            if not warning or warning in seen:
                continue

            seen.add(warning)
            merged.append(warning)

        return merged

    def _append_context_warnings(
        self,
        report,
        warnings,
    ):
        warnings = [
            str(item).strip()
            for item in (warnings or [])
            if str(item).strip()
        ]

        if not warnings:
            return

        report.append("")
        report.append(
            "ATTENZIONE DATI"
        )
        report.append(
            "-" * 60
        )

        for warning in warnings:
            report.append(
                f"• {warning}"
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

        fueling_history = context.get(
            "garmin_fueling_demand_history",
            [],
        ) or []

        latest_fueling = {}

        for item in reversed(
            fueling_history
        ):
            if isinstance(item, dict):
                latest_fueling = item
                break

        report.append("")



        report.append(
            "SINTESI DEL COACH"
        )



        report.append(
            "-" * 60
        )



        # ----------------------------------------------
        # RECOVERY NORMALIZZATO
        # ----------------------------------------------


        recovery_state = self._first_value(
            recovery,
            [
                "Stato recovery",
                "Stato Recovery",
                "stato_recovery",
                "recovery_state",
                "Recovery state",
            ],
        )



        if recovery_state == "N/D":


            recovery_state = self._first_value(
                recovery.get(
                    "raw",
                    {},
                ) or {},
                [
                    "Stato recovery",
                    "Stato Recovery",
                    "stato_recovery",
                    "recovery_state",
                    "Recovery state",
                ],
            )



        recovery_score = self._first_value(
            recovery,
            [
                "Recovery score",
                "Recovery Score",
                "recovery_score",
                "readiness",
            ],
        )



        if recovery_score == "N/D":


            recovery_score = self._first_value(
                recovery.get(
                    "raw",
                    {},
                ) or {},
                [
                    "Recovery score",
                    "Recovery Score",
                    "recovery_score",
                    "readiness",
                ],
            )



        sleep_data = recovery.get(
            "sleep",
            {},
        ) or {}



        sleep_score = self._first_value(
            recovery,
            [
                "Sleep score",
                "Sleep Score",
                "sleep_score",
            ],
        )



        if sleep_score == "N/D":


            sleep_score = self._first_value(
                sleep_data,
                [
                    "score",
                    "sleep_score",
                ],
            )



        sleep_hours = self._first_value(
            recovery,
            [
                "Ore sonno",
                "ore_sonno",
                "sleep_hours",
            ],
        )



        if sleep_hours == "N/D":


            sleep_hours = self._first_value(
                sleep_data,
                [
                    "hours",
                    "sleep_hours",
                ],
            )



        # ----------------------------------------------
        # TRAINING NORMALIZZATO
        # ----------------------------------------------


        workout = self._first_value(
            training,
            [
                "Nome seduta",
                "nome_seduta",
                "workout_name",
                "name",
                "notes",
            ],
        )



        if workout == "N/D":


            sport = self._first_value(
                training,
                [
                    "sport",
                ],
            )



            distance = self._first_value(
                training,
                [
                    "distance_km",
                ],
            )



            duration = self._first_value(
                training,
                [
                    "duration_minutes",
                ],
            )



            if sport != "N/D":

                workout = (

                    f"{sport} "
                    f"{distance} km "
                    f"({duration} min)"

                )



        # ----------------------------------------------
        # NUTRITION
        # ----------------------------------------------


        nutrition_state = self._first_value(
            nutrition,
            [
                "Stato recupero nutrizionale",
                "stato_recupero_nutrizionale",
                "nutrition_state",
            ],
        )

        calories_burned = latest_fueling.get(
            "calories_burned"
        )

        estimated_water_ml = latest_fueling.get(
            "estimated_water_ml"
        )



        report.append(

            f"• Stato recovery: "
            f"{recovery_state}, "
            f"Recovery Score {recovery_score}"

        )



        report.append(

            f"• Sonno: Sleep Score {sleep_score}; "
            f"{sleep_hours} ore registrate"

        )



        report.append(

            f"• Ultima seduta: {workout}"

        )



        report.append(

            f"• Nutrizione: {nutrition_state}"

        )



        if calories_burned not in (
            None,
            "",
        ):

            report.append(

                "• Costo energetico seduta Garmin: "
                f"{float(calories_burned):g} kcal"

            )



        if estimated_water_ml not in (
            None,
            "",
        ):

            report.append(

                "• Liquidi stimati dalla seduta Garmin: "
                f"{float(estimated_water_ml):g} ml"

            )



        report.append("")



        report.append(

            "Rischio complessivo: "
            +
            str(
                decision.get(
                    "risk_level",
                    "N/D",
                )
            )

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

        report.append(
            title
        )

        report.append(
            "-" * 60
        )


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


        if not data:

            return



        blocked = {

            str(item).lower()

            for item in (
                skip_keys
                or []
            )

        }



        for key, value in data.items():


            if str(key).lower() in blocked:

                continue



            report.append(

                f"{self._label(key)}: "
                f"{self._format_value(value)}"

            )




    def _first_value(
        self,
        data,
        keys,
        default="N/D",
    ):

        data = data or {}



        for key in keys:


            value = data.get(key)



            if value not in (
                None,
                "",
                [],
            ):

                return value



        return default




    def _label(
        self,
        key,
    ):


        labels = {


            "decision":

                "Decisione ironcoach",



            "reason":

                "Motivazione",



            "priority":

                "Priorità",



            "confidence":

                "Confidenza",



            "strategy":

                "Strategia",



            "training_priority":

                "Priorità allenante",



            "recommended_action":

                "Azione consigliata",



            "risk_level":

                "Risk level",



            "athlete_type":

                "Tipo atleta",



            "athlete_name":

                "Nome atleta",



            "athlete_level":

                "Livello atleta",



            "strengths":

                "Punti di forza",



            "limitations":

                "Limitazioni note",



            "training_preferences":

                "Preferenze allenamento",



            "training_distribution":

                "Training distribution",



            "sport_profile":

                "Sport principale",



            "experience_years":

                "Anni esperienza",



            "vo2max_run":

                "Vo2max corsa",



            "vo2max_bike":

                "Vo2max bici",



            "ftp":

                "FTP",



            "css":

                "CSS",



            "weight":

                "Peso",



            "height":

                "Altezza",

        }



        return labels.get(

            key,

            str(key)
            .replace(
                "_",
                " ",
            )
            .capitalize()

        )




    def _format_value(
        self,
        value,
    ):


        if value is None:

            return "N/D"



        if isinstance(
            value,
            dict,
        ):


            if "value" in value:

                return self._format_value(
                    value.get("value")
                )



            return "; ".join(

                f"{self._label(key)}: "
                f"{self._format_value(val)}"

                for key, val in value.items()

            )



        if isinstance(
            value,
            float,
        ):


            return round(
                value,
                2,
            )



        if isinstance(
            value,
            list,
        ):


            return ", ".join(

                str(item)

                for item in value

            )



        return value