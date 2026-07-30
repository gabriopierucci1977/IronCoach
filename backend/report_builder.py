"""
IronCoach Report Builder

Costruisce un report leggibile
dal Context Builder e dal Coach Engine.

Versione corretta:
- compatibilità Airtable + analyzer normalizzati
- gestione intelligence atleta
- separazione decisione / workout modificato
- formattazione dizionari sicura
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
            context.get("athlete")
            or context.get("athlete_profile")
            or {}
        )


        recovery = (
            context.get("recovery")
            or {}
        )


        training = (
            context.get("training")
            or {}
        )


        nutrition = (
            context.get("nutrition")
            or {}
        )


        last_decision = (
            context.get("decision")
            or {}
        )


        intelligence = (
            decision.get("intelligence")
            or {}
        )


        report = []


        report.append("=" * 60)
        report.append(
            "IRONCOACH REPORT"
        )
        report.append("=" * 60)



        # --------------------------------------------------
        # ATLETA
        # --------------------------------------------------

        self._append_section(
            report,
            "ATLETA",
            athlete,
        )



        # --------------------------------------------------
        # RECOVERY
        # --------------------------------------------------

        self._append_section(
            report,
            "RECOVERY",
            recovery,
        )



        # --------------------------------------------------
        # TRAINING
        # --------------------------------------------------

        self._append_section(
            report,
            "TRAINING",
            training,
        )



        # --------------------------------------------------
        # NUTRITION
        # --------------------------------------------------

        self._append_section(
            report,
            "NUTRITION",
            nutrition,
        )



        # --------------------------------------------------
        # SUMMARY
        # --------------------------------------------------

        self._append_coach_summary(
            report,
            context,
            decision,
        )



        # --------------------------------------------------
        # INTELLIGENCE
        # --------------------------------------------------

        self._append_intelligence(
            report,
            intelligence,
        )



        # --------------------------------------------------
        # ULTIMA DECISIONE
        # --------------------------------------------------

        report.append("")
        report.append(
            "ULTIMA DECISIONE REGISTRATA"
        )
        report.append("-" * 60)


        self._append_fields(
            report,
            last_decision,
            skip_keys=[
                "modified_workout",
                "allenamento modificato",
            ],
        )



        # --------------------------------------------------
        # DECISIONE COACH
        # --------------------------------------------------

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



        # --------------------------------------------------
        # WORKOUT MODIFICATO
        # --------------------------------------------------

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
        report.append("=" * 60)


        return "\n".join(report)





    # ==================================================
    # GENERIC SECTION
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


        if not data:
            report.append("N/D")
            return



        for key, value in data.items():

            report.append(
                f"{self._label(key)}: "
                f"{self._format_value(value)}"
            )

    # ==================================================
    # INTELLIGENCE ATLETA
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



        self._append_athlete_profile(
            report,
            intelligence.get(
                "athlete_profile",
                {},
            ),
        )


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





    # ==================================================
    # ATHLETE PROFILE INTELLIGENCE
    # ==================================================


    def _append_athlete_profile(
        self,
        report,
        profile,
    ):

        if not profile:
            return



        report.append("")
        report.append(
            "PROFILO ATLETA"
        )



        mapping = {

            "athlete_type":
                "Tipo atleta",

            "type":
                "Tipo atleta",


            "strengths":
                "Punti di forza",


            "limitations":
                "Limitazioni note",


            "training_preferences":
                "Preferenze allenamento",


            "load_tolerance":
                "Tolleranza al carico",


            "injury_patterns":
                "Pattern infortuni",

        }



        for key, value in profile.items():

            label = mapping.get(
                key,
                self._label(key),
            )


            report.append(
                f"• {label}: "
                f"{self._format_value(value)}"
            )





    # ==================================================
    # GENERIC INTELLIGENCE BLOCK
    # ==================================================


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
                f"{mapping.get(key, key)}: "
                f"{self._format_value(value)}"
            )

    # ==================================================
    # COACH SUMMARY
    # ==================================================


    def _append_coach_summary(
        self,
        report,
        context,
        decision,
    ):

        recovery = (
            context.get(
                "recovery",
                {},
            )
            or {}
        )


        training = (
            context.get(
                "training",
                {},
            )
            or {}
        )


        nutrition = (
            context.get(
                "nutrition",
                {},
            )
            or {}
        )


        report.append("")
        report.append(
            "SINTESI DEL COACH"
        )
        report.append("-" * 60)



        recovery_state = (

            recovery.get(
                "Stato recovery"
            )

            or recovery.get(
                "stato_recovery"
            )

            or recovery.get(
                "recovery_state"
            )

            or "N/D"

        )



        recovery_score = (

            recovery.get(
                "Recovery score"
            )

            or recovery.get(
                "Recovery Score"
            )

            or recovery.get(
                "recovery_score"
            )

            or "N/D"

        )



        sleep_score = (

            recovery.get(
                "Sleep score"
            )

            or recovery.get(
                "Sleep Score"
            )

            or recovery.get(
                "sleep_score"
            )

            or "N/D"

        )



        sleep_hours = (

            recovery.get(
                "Ore sonno"
            )

            or recovery.get(
                "ore_sonno"
            )

            or "N/D"

        )



        workout = (

            training.get(
                "Nome seduta"
            )

            or training.get(
                "nome_seduta"
            )

            or "N/D"

        )



        nutrition_state = (

            nutrition.get(
                "Stato recupero nutrizionale"
            )

            or nutrition.get(
                "stato_recupero_nutrizionale"
            )

            or "N/D"

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
            f"• Ultima seduta: "
            f"{workout}"
        )


        report.append(
            f"• Nutrizione: "
            f"{nutrition_state}"
        )



        risk = (

            decision.get(
                "risk_level"
            )

            or "N/D"

        )


        report.append("")
        report.append(
            f"Rischio complessivo: {risk}"
        )





    # ==================================================
    # FIELD WRITER
    # ==================================================


    def _append_fields(
        self,
        report,
        data,
        skip_keys=None,
    ):

        if not data:
            return



        skip_keys = skip_keys or []



        for key, value in data.items():


            if key in skip_keys:
                continue



            report.append(
                f"{self._label(key)}: "
                f"{self._format_value(value)}"
            )





    # ==================================================
    # FORMAT HELPERS
    # ==================================================


    def _label(
        self,
        key,
    ):

        labels = {

            "risk_level":
                "Risk level",

            "recommended_action":
                "Azione consigliata",

            "strategy":
                "Strategia",

            "reason":
                "Motivazione",

            "confidence":
                "Confidenza",

            "priority":
                "Priorità",

            "decision":
                "Decisione ironcoach",

            "reasoning":
                "Reasoning",

            "total_load":
                "Carico totale",

            "sessions_with_load":
                "Sedute con carico",

            "sport_distribution":
                "Distribuzione sport",

            "adaptation_level":
                "Livello adattamento",

            "data_quality":
                "Qualità dati",

        }


        return labels.get(
            key,
            str(key).replace(
                "_",
                " ",
            ).capitalize(),
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

            return "; ".join(
                [
                    f"{self._label(k)}="
                    f"{self._format_value(v)}"
                    for k, v in value.items()
                ]
            )



        if isinstance(
            value,
            list,
        ):

            return ", ".join(
                [
                    self._format_value(item)
                    for item in value
                ]
            )



        return str(value)
