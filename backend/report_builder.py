"""
IronCoach Report Builder v0.2

Costruisce un report leggibile a partire
dal Context Builder e dal Coach Engine.

Include una sezione dedicata alla nuova
intelligence dell'atleta.
"""


class ReportBuilder:
    """
    Converte il contesto IronCoach e la decisione finale
    in un report testuale leggibile.
    """

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
        report.append("ULTIMA DECISIONE REGISTRATA")
        report.append("-" * 60)

        if last_decision:

            self._append_fields(
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

        self._append_fields(
            report,
            decision,
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
        data,
    ):

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

    # -------------------------------------------------
    # CAMPI
    # -------------------------------------------------

    def _append_fields(
        self,
        report,
        data,
    ):

        if not isinstance(
            data,
            dict,
        ):
            return

        modified_workout = None

        for key, value in data.items():

            normalized = (
                str(key)
                .lower()
                .replace("_", " ")
                .strip()
            )

            if normalized in (
                "allenamento modificato",
                "modified workout",
            ):

                modified_workout = value
                continue

            if normalized == "intelligence":
                continue

            report.append(
                f"{self._label(key)}: "
                f"{self._format_value(value)}"
            )

        if modified_workout:

            self._append_modified_workout(
                report,
                modified_workout,
            )

    # -------------------------------------------------
    # INTELLIGENCE ATLETA
    # -------------------------------------------------

    def _append_intelligence(
        self,
        report,
        intelligence,
    ):

        if not isinstance(
            intelligence,
            dict,
        ):

            return

        if not intelligence:
            return

        athlete_profile = intelligence.get(
            "athlete_profile",
            {},
        ) or {}

        load_analysis = intelligence.get(
            "load",
            {},
        ) or {}

        adaptation_analysis = intelligence.get(
            "adaptation",
            {},
        ) or {}

        performance_analysis = intelligence.get(
            "performance",
            {},
        ) or {}

        report.append("")
        report.append("INTELLIGENCE ATLETA")
        report.append("-" * 60)

        self._append_athlete_profile(
            report,
            athlete_profile,
        )

        self._append_load_analysis(
            report,
            load_analysis,
        )

        self._append_adaptation_analysis(
            report,
            adaptation_analysis,
        )

        self._append_performance_analysis(
            report,
            performance_analysis,
        )

    def _append_athlete_profile(
        self,
        report,
        profile,
    ):

        report.append("")
        report.append("PROFILO ATLETA")

        if not profile:

            report.append(
                "• Profilo non disponibile"
            )
            return

        athlete_type = profile.get(
            "athlete_type",
            "N/D",
        )

        strengths = profile.get(
            "strengths",
            [],
        )

        limitations = profile.get(
            "limitations",
            [],
        )

        preferences = profile.get(
            "training_preferences",
            [],
        )

        load_tolerance = profile.get(
            "load_tolerance",
            {},
        )

        injury_patterns = profile.get(
            "injury_patterns",
            [],
        )

        report.append(
            "• Tipo atleta: "
            f"{self._format_value(athlete_type)}"
        )

        report.append(
            "• Punti di forza: "
            f"{self._format_value(strengths)}"
        )

        report.append(
            "• Limitazioni note: "
            f"{self._format_value(limitations)}"
        )

        report.append(
            "• Preferenze allenamento: "
            f"{self._format_value(preferences)}"
        )

        report.append(
            "• Tolleranza al carico: "
            f"{self._format_value(load_tolerance)}"
        )

        report.append(
            "• Pattern infortuni: "
            f"{self._format_value(injury_patterns)}"
        )

    def _append_load_analysis(
        self,
        report,
        load_analysis,
    ):

        report.append("")
        report.append("CARICO STORICO")

        if not load_analysis:

            report.append(
                "• Analisi non disponibile"
            )
            return

        level = load_analysis.get(
            "level",
            "UNKNOWN",
        )

        total_load = load_analysis.get(
            "total_load",
            0,
        )

        sessions = load_analysis.get(
            "sessions",
            0,
        )

        distribution = load_analysis.get(
            "sport_distribution",
            {},
        )

        reasons = load_analysis.get(
            "reasons",
            [],
        )

        report.append(
            "• Stato carico: "
            f"{self._format_value(level)}"
        )

        report.append(
            "• Carico totale analizzato: "
            f"{self._format_value(total_load)}"
        )

        report.append(
            "• Sedute analizzate: "
            f"{self._format_value(sessions)}"
        )

        report.append(
            "• Distribuzione per sport: "
            f"{self._format_sport_distribution(distribution)}"
        )

        report.append(
            "• Valutazione: "
            f"{self._format_value(reasons)}"
        )

    def _append_adaptation_analysis(
        self,
        report,
        adaptation_analysis,
    ):

        report.append("")
        report.append("ADATTAMENTO AL CARICO")

        if not adaptation_analysis:

            report.append(
                "• Analisi non disponibile"
            )
            return

        level = adaptation_analysis.get(
            "adaptation_level",
            "UNKNOWN",
        )

        risk_factors = adaptation_analysis.get(
            "risk_factors",
            [],
        )

        positive_factors = adaptation_analysis.get(
            "positive_factors",
            [],
        )

        reasons = adaptation_analysis.get(
            "reasons",
            [],
        )

        report.append(
            "• Capacità di adattamento: "
            f"{self._format_value(level)}"
        )

        report.append(
            "• Fattori positivi: "
            f"{self._format_value(positive_factors)}"
        )

        report.append(
            "• Fattori di rischio: "
            f"{self._format_value(risk_factors)}"
        )

        report.append(
            "• Valutazione: "
            f"{self._format_value(reasons)}"
        )

    def _append_performance_analysis(
        self,
        report,
        performance_analysis,
    ):

        report.append("")
        report.append("TREND PERFORMANCE")

        if not performance_analysis:

            report.append(
                "• Analisi non disponibile"
            )
            return

        trend = performance_analysis.get(
            "trend",
            "UNKNOWN",
        )

        metrics = performance_analysis.get(
            "metrics",
            {},
        )

        strengths = performance_analysis.get(
            "strengths",
            [],
        )

        concerns = performance_analysis.get(
            "concerns",
            [],
        )

        reasons = performance_analysis.get(
            "reasons",
            [],
        )

        report.append(
            "• Trend complessivo: "
            f"{self._format_value(trend)}"
        )

        report.append(
            "• Variazioni metriche: "
            f"{self._format_performance_metrics(metrics)}"
        )

        report.append(
            "• Segnali positivi: "
            f"{self._format_value(strengths)}"
        )

        report.append(
            "• Aspetti da monitorare: "
            f"{self._format_value(concerns)}"
        )

        report.append(
            "• Valutazione: "
            f"{self._format_value(reasons)}"
        )

    # -------------------------------------------------
    # ALLENAMENTO MODIFICATO
    # -------------------------------------------------

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
                self._label(key),
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
        report.append(
            "-" * 60
        )

        recovery_state = recovery.get(
            "Stato Recovery",
            recovery.get(
                "recovery_state",
                "N/D",
            ),
        )

        recovery_score = recovery.get(
            "Recovery Score",
            recovery.get(
                "recovery_score",
                "N/D",
            ),
        )

        sleep = recovery.get(
            "Sleep Score",
            "N/D",
        )

        sleep_hours = recovery.get(
            "Ore sonno",
            "N/D",
        )

        workout = training.get(
            "Nome seduta",
            "N/D",
        )

        rpe = training.get(
            "RPE percepito",
            training.get(
                "Rpe percepito",
                "N/D",
            ),
        )

        nutrition_state = nutrition.get(
            "Stato recupero nutrizionale",
            "N/D",
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
                "N/D",
            ),
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
        value,
    ):

        return (
            str(value)
            .replace("_", " ")
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

            if not value:
                return "N/D"

            if "value" in value:

                return self._format_value(
                    value.get("value")
                )

            return ", ".join(
                f"{self._label(key)}: "
                f"{self._format_value(item)}"
                for key, item in value.items()
            )

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):

            if not value:
                return "N/D"

            return "; ".join(
                self._format_value(item)
                for item in value
            )

        if isinstance(
            value,
            str,
        ):

            value = value.strip()

            if not value:
                return "N/D"

            return value

        if isinstance(
            value,
            float,
        ):

            if value.is_integer():
                return str(
                    int(value)
                )

            return str(
                round(
                    value,
                    2,
                )
            )

        return str(value)

    def _format_sport_distribution(
        self,
        distribution,
    ):

        if not isinstance(
            distribution,
            dict,
        ):

            return "N/D"

        if not distribution:
            return "N/D"

        labels = {
            "run": "Corsa",
            "running": "Corsa",
            "bike": "Bici",
            "cycling": "Bici",
            "swim": "Nuoto",
            "swimming": "Nuoto",
            "strength": "Forza",
            "unknown": "Altro",
        }

        values = []

        for sport, load in distribution.items():

            label = labels.get(
                str(sport).lower(),
                self._label(sport),
            )

            values.append(
                f"{label}: "
                f"{self._format_value(load)}"
            )

        return "; ".join(values)

    def _format_performance_metrics(
        self,
        metrics,
    ):

        if not isinstance(
            metrics,
            dict,
        ):

            return "N/D"

        if not metrics:
            return "N/D"

        labels = {
            "vo2max_run": "VO₂max corsa",
            "vo2max_bike": "VO₂max bici",
            "ftp": "FTP",
            "css": "CSS",
        }

        values = []

        for metric, change in metrics.items():

            label = labels.get(
                metric,
                self._label(metric),
            )

            numeric_change = self._number(
                change
            )

            if numeric_change is None:

                formatted_change = (
                    self._format_value(change)
                )

            elif numeric_change > 0:

                formatted_change = (
                    f"+{numeric_change:g}%"
                )

            else:

                formatted_change = (
                    f"{numeric_change:g}%"
                )

            values.append(
                f"{label}: {formatted_change}"
            )

        return "; ".join(values)

    def _number(
        self,
        value,
    ):

        if value is None:
            return None

        try:

            return float(value)

        except (
            TypeError,
            ValueError,
        ):

            return None