"""
IronCoach - Workout Adapter

Trasforma la decisione del Coach Engine in una proposta
concreta di allenamento modificato.

Il modulo non decide se confermare, adattare, ridurre
o recuperare: applica operativamente la strategia già
stabilita dal Coach Engine.

Le proposte vengono generate in modo specifico per:

- corsa;
- ciclismo;
- nuoto;
- attività generica.
"""

import unicodedata


class WorkoutAdapter:
    """
    Genera un allenamento modificato sulla base della
    strategia prodotta dal Coach Engine.
    """

    def adapt(
        self,
        context,
        decision,
    ):
        """
        Costruisce l'eventuale allenamento modificato.
        """

        context = context or {}
        decision = decision or {}

        training = context.get(
            "training",
            {},
        ) or {}

        strategy = self._normalize_text(
            decision.get(
                "strategy",
                "",
            )
        ).upper()

        if strategy == "KEEP_PLAN":
            return None

        decision_context = (
            self._build_decision_context(
                decision
            )
        )



        goal_profile = self._get_goal_profile(
            context,
            decision,
        )

        sport = self._get_text(
            training,
            "Sport",
            "sport",
        ) or "Attività aerobica"

        sport_category = self._classify_sport(
            sport
        )

        workout_name = self._get_text(
            training,
            "Nome seduta",
            "nome_seduta",
        ) or "Allenamento programmato"

        session_type = self._get_text(
            training,
            "Tipo seduta",
            "tipo_seduta",
        ) or "Allenamento"

        planned_zone = self._get_text(
            training,
            "Zona prevista",
            "zona_prevista",
        ) or "N/D"

        original_duration = self._get_number(
            training,
            "Durata minuti",
            "durata_minuti",
            "duration",
        )

        goal_adjustment = self._build_goal_adjustment(
            goal_profile,
            strategy,
        )

        workout_data = {
            "sport": sport,
            "sport_category": sport_category,
            "workout_name": workout_name,
            "session_type": session_type,
            "planned_zone": planned_zone,
            "original_duration": original_duration,
            "decision_context": decision_context,
            "goal_profile": goal_profile,
            "goal_adjustment": goal_adjustment,
        }

        if strategy == "ADAPT":
            return self._build_adapted_workout(
                **workout_data
            )

        if strategy == "REDUCE_LOAD":
            return self._build_reduced_workout(
                **workout_data
            )

        if strategy == "RECOVERY":
            return self._build_recovery_workout(
                **workout_data
            )

        return None


    # -------------------------------------------------
    # DISTRIBUZIONE DELLE STRATEGIE
    # -------------------------------------------------

    def _build_adapted_workout(
        self,
        sport,
        sport_category,
        workout_name,
        session_type,
        planned_zone,
        original_duration,
        decision_context,
        goal_profile,
        goal_adjustment,
    ):
        """
        Mantiene parte dello stimolo allenante riducendo
        intensità, volume o complessità della seduta.
        """

        duration = self._calculate_duration(
            original_duration=original_duration,
            percentage=self._adapt_duration_percentage(
                goal_adjustment,
            ),
            default_duration=45,
            minimum_duration=30,
        )

        common_data = self._build_common_data(
            strategy="ADAPT",
            sport=sport,
            sport_category=sport_category,
            workout_name=workout_name,
            session_type=session_type,
            planned_zone=planned_zone,
            original_duration=original_duration,
            duration=duration,
            decision_context=decision_context,
            goal_profile=goal_profile,
            goal_adjustment=goal_adjustment,
        )

        if sport_category == "RUN":
            workout = self._build_run_adapted(
                duration
            )

        elif sport_category == "BIKE":
            workout = self._build_bike_adapted(
                duration
            )

        elif sport_category == "SWIM":
            workout = self._build_swim_adapted(
                duration
            )

        else:
            workout = self._build_generic_adapted(
                duration
            )

        return {
            **common_data,
            **workout,
        }


    def _build_reduced_workout(
        self,
        sport,
        sport_category,
        workout_name,
        session_type,
        planned_zone,
        original_duration,
        decision_context,
        goal_profile,
        goal_adjustment,
    ):
        """
        Riduce in modo significativo il carico previsto,
        mantenendo soltanto lavoro facile e controllato.
        """

        duration = self._calculate_duration(
            original_duration=original_duration,
            percentage=0.65,
            default_duration=40,
            minimum_duration=25,
        )

        common_data = self._build_common_data(
            strategy="REDUCE_LOAD",
            sport=sport,
            sport_category=sport_category,
            workout_name=workout_name,
            session_type=session_type,
            planned_zone=planned_zone,
            original_duration=original_duration,
            duration=duration,
            decision_context=decision_context,
            goal_profile=goal_profile,
            goal_adjustment=goal_adjustment,
        )
        if sport_category == "RUN":
            workout = self._build_run_reduced(
                duration
            )

        elif sport_category == "BIKE":
            workout = self._build_bike_reduced(
                duration
            )

        elif sport_category == "SWIM":
            workout = self._build_swim_reduced(
                duration
            )

        else:
            workout = self._build_generic_reduced(
                duration
            )

        return {
            **common_data,
            **workout,
        }


    def _build_recovery_workout(
        self,
        sport,
        sport_category,
        workout_name,
        session_type,
        planned_zone,
        original_duration,
        decision_context,
        goal_profile,
        goal_adjustment,
    ):
        """
        Genera una proposta esclusivamente rigenerante,
        specifica per lo sport rilevato.
        """

        duration = self._calculate_recovery_duration(
            original_duration
        )

        common_data = self._build_common_data(
            strategy="RECOVERY",
            sport=sport,
            sport_category=sport_category,
            workout_name=workout_name,
            session_type=session_type,
            planned_zone=planned_zone,
            original_duration=original_duration,
            duration=duration,
            decision_context=decision_context,
            goal_profile=goal_profile,
            goal_adjustment=goal_adjustment,
        )

        if sport_category == "RUN":
            workout = self._build_run_recovery(
                duration
            )

        elif sport_category == "BIKE":
            workout = self._build_bike_recovery(
                duration
            )

        elif sport_category == "SWIM":
            workout = self._build_swim_recovery(
                duration
            )

        else:
            workout = self._build_generic_recovery(
                duration
            )

        return {
            **common_data,
            **workout,
        }


    # -------------------------------------------------
    # CORSA
    # -------------------------------------------------

    def _build_run_adapted(
        self,
        duration,
    ):
        """
        Seduta di corsa adattata.

        Rimuove il lavoro ad alta intensità e mantiene
        una corsa aerobica controllata.
        """

        warmup_duration, main_duration, cooldown_duration = (
            self._split_duration(
                duration=duration,
                warmup_target=10,
                cooldown_target=8,
                minimum_main=12,
            )
        )

        return {
            "intensity": "Z1-Z2",
            "warmup": (
                f"{warmup_duration}' di corsa facile "
                "con progressione graduale da Z1 a Z2"
            ),
            "main_set": (
                f"{main_duration}' di corsa aerobica continua "
                "in Z2 controllata"
            ),
            "cooldown": (
                f"{cooldown_duration}' di corsa molto facile "
                "in Z1"
            ),
            "technical_focus": (
                "Passo regolare, appoggio rilassato e cadenza naturale"
            ),
            "removed_elements": (
                "Ripetute intense, sprint, salite impegnative "
                "e lavoro in Z4-Z5"
            ),
            "notes": (
                "Seduta di corsa adattata: volume ridotto del 20% "
                "circa e intensità limitata al lavoro aerobico. "
                "Non forzare il ritmo in presenza di rigidità o dolore."
            ),
        }


    def _build_run_reduced(
        self,
        duration,
    ):
        """
        Seduta di corsa con carico fortemente ridotto.
        """

        warmup_duration, main_duration, cooldown_duration = (
            self._split_duration(
                duration=duration,
                warmup_target=8,
                cooldown_target=7,
                minimum_main=10,
            )
        )

        return {
            "intensity": "Z1-Z2 facile",
            "warmup": (
                f"{warmup_duration}' alternando camminata attiva "
                "e corsa molto facile"
            ),
            "main_set": (
                f"{main_duration}' di corsa facile in Z1-Z2, "
                "senza variazioni di ritmo"
            ),
            "cooldown": (
                f"{cooldown_duration}' di corsa molto facile "
                "o camminata"
            ),
            "technical_focus": (
                "Movimento fluido, rilassato e senza ricerca della velocità"
            ),
            "removed_elements": (
                "Qualsiasi lavoro di soglia, VO2max, sprint, "
                "progressivo o salita intensa"
            ),
            "notes": (
                "Carico di corsa ridotto del 35% circa. "
                "La seduta deve rimanere completamente controllata. "
                "Interrompere in caso di aumento del dolore."
            ),
        }


    def _build_run_recovery(
        self,
        duration,
    ):
        """
        Proposta rigenerante per la corsa.
        """

        warmup_duration, main_duration, cooldown_duration = (
            self._split_duration(
                duration=duration,
                warmup_target=5,
                cooldown_target=5,
                minimum_main=10,
            )
        )

        return {
            "intensity": "Z1 molto facile",
            "warmup": (
                f"{warmup_duration}' di camminata attiva "
                "o corsa molto lenta"
            ),
            "main_set": (
                f"{main_duration}' di corsa rigenerante in Z1, "
                "eventualmente alternata a camminata"
            ),
            "cooldown": (
                f"{cooldown_duration}' di camminata rilassata"
            ),
            "technical_focus": (
                "Rilassamento muscolare e assenza di tensioni"
            ),
            "alternative": (
                "Riposo completo oppure camminata facile"
            ),
            "notes": (
                "Nessun lavoro di qualità. La corsa è facoltativa "
                "e deve essere sostituita dal riposo completo in presenza "
                "di dolore, zoppia o peggioramento delle sensazioni."
            ),
        }
    # -------------------------------------------------
    # CICLISMO
    # -------------------------------------------------

    def _build_bike_adapted(
        self,
        duration,
    ):
        """
        Seduta di ciclismo adattata.

        Mantiene lavoro aerobico con cadenza fluida,
        eliminando intervalli intensi.
        """

        warmup_duration, main_duration, cooldown_duration = (
            self._split_duration(
                duration=duration,
                warmup_target=12,
                cooldown_target=8,
                minimum_main=15,
            )
        )

        return {
            "intensity": "Z1-Z2",
            "warmup": (
                f"{warmup_duration}' di pedalata progressiva "
                "da Z1 a Z2"
            ),
            "main_set": (
                f"{main_duration}' continui in Z2 bassa, "
                "con cadenza agile e pressione costante sui pedali"
            ),
            "cooldown": (
                f"{cooldown_duration}' di pedalata facile in Z1"
            ),
            "technical_focus": (
                "Cadenza fluida indicativamente tra 85 e 95 rpm"
            ),
            "removed_elements": (
                "Intervalli VO2max, soglia, sprint, forza a bassa cadenza "
                "e salite impegnative"
            ),
            "notes": (
                "Seduta ciclistica adattata: volume ridotto del 20% "
                "circa e intensità limitata al lavoro aerobico controllato."
            ),
        }


    def _build_bike_reduced(
        self,
        duration,
    ):
        """
        Seduta ciclistica con carico fortemente ridotto.
        """

        warmup_duration, main_duration, cooldown_duration = (
            self._split_duration(
                duration=duration,
                warmup_target=10,
                cooldown_target=8,
                minimum_main=10,
            )
        )

        return {
            "intensity": "Z1-Z2 facile",
            "warmup": (
                f"{warmup_duration}' di pedalata molto facile in Z1"
            ),
            "main_set": (
                f"{main_duration}' in Z1-Z2 bassa, "
                "preferibilmente su percorso pianeggiante o rulli"
            ),
            "cooldown": (
                f"{cooldown_duration}' molto facili con cadenza libera"
            ),
            "technical_focus": (
                "Pedalata rotonda, rapporto agile e bassa tensione muscolare"
            ),
            "removed_elements": (
                "Soglia, VO2max, sprint, lavori di forza, "
                "salite e cambi di ritmo"
            ),
            "notes": (
                "Carico ciclistico ridotto del 35% circa. "
                "Mantenere una percezione dello sforzo molto bassa "
                "e non inseguire potenza o velocità."
            ),
        }


    def _build_bike_recovery(
        self,
        duration,
    ):
        """
        Proposta rigenerante per il ciclismo.
        """

        warmup_duration, main_duration, cooldown_duration = (
            self._split_duration(
                duration=duration,
                warmup_target=5,
                cooldown_target=5,
                minimum_main=10,
            )
        )

        return {
            "intensity": "Z1 molto facile",
            "warmup": (
                f"{warmup_duration}' di pedalata estremamente facile"
            ),
            "main_set": (
                f"{main_duration}' rigeneranti in Z1, "
                "con rapporto agile e senza pressione sui pedali"
            ),
            "cooldown": (
                f"{cooldown_duration}' molto facili"
            ),
            "technical_focus": (
                "Cadenza confortevole e completa assenza di affaticamento"
            ),
            "alternative": (
                "Riposo completo oppure mobilità leggera"
            ),
            "notes": (
                "Nessun lavoro di qualità o forza. "
                "La seduta deve favorire il recupero e non produrre "
                "ulteriore fatica."
            ),
        }


    # -------------------------------------------------
    # NUOTO
    # -------------------------------------------------

    def _build_swim_adapted(
        self,
        duration,
    ):
        """
        Seduta nuoto adattata.
        """

        return {
            "intensity": "Tecnica + aerobico facile",
            "warmup": (
                f"{max(5, int(duration * 0.15))}' "
                "riscaldamento tecnico"
            ),
            "main_set": (
                f"{max(15, int(duration * 0.60))}' "
                "nuoto continuo controllato"
            ),
            "cooldown": (
                f"{max(5, int(duration * 0.15))}' "
                "defaticamento"
            ),
            "technical_focus": (
                "Efficienza della bracciata e rilassamento"
            ),
            "removed_elements": (
                "Serie massimali, sprint e lavori lattacidi"
            ),
            "notes": (
                "Seduta nuoto adattata con intensità controllata."
            ),
        }


    def _build_swim_reduced(
        self,
        duration,
    ):
        """
        Seduta nuoto ridotta.
        """

        return {
            "intensity": "Facile",
            "warmup": (
                "Riscaldamento tecnico molto leggero"
            ),
            "main_set": (
                f"{duration}' nuoto facile senza variazioni"
            ),
            "cooldown": (
                "Defaticamento libero"
            ),
            "technical_focus": (
                "Fluidità e controllo del gesto"
            ),
            "removed_elements": (
                "Serie intense e lavori di soglia"
            ),
            "notes": (
                "Volume ridotto e percezione dello sforzo bassa."
            ),
        }


    def _build_swim_recovery(
        self,
        duration,
    ):
        """
        Nuoto rigenerante.
        """

        return {
            "intensity": "Molto facile",
            "warmup": (
                "Mobilità in acqua e nuoto leggero"
            ),
            "main_set": (
                f"{duration}' tecnica e recupero attivo"
            ),
            "cooldown": (
                "Nuoto rilassato"
            ),
            "technical_focus": (
                "Rilassamento e respirazione"
            ),
            "alternative": (
                "Riposo o mobilità fuori acqua"
            ),
            "notes": (
                "Nessun lavoro intenso."
            ),
        }
    # -------------------------------------------------
    # GENERICO
    # -------------------------------------------------

    def _build_generic_adapted(
        self,
        duration,
    ):
        """
        Seduta generica adattata.
        """

        warmup_duration, main_duration, cooldown_duration = (
            self._split_duration(
                duration=duration,
                warmup_target=10,
                cooldown_target=8,
                minimum_main=12,
            )
        )

        return {
            "intensity": "Z1-Z2",
            "warmup": (
                f"{warmup_duration}' riscaldamento facile"
            ),
            "main_set": (
                f"{main_duration}' lavoro aerobico controllato"
            ),
            "cooldown": (
                f"{cooldown_duration}' defaticamento"
            ),
            "technical_focus": (
                "Movimento fluido e controllo dello sforzo"
            ),
            "removed_elements": (
                "Picchi intensi e lavoro ad alta intensità"
            ),
            "notes": (
                "Seduta adattata mantenendo stimolo controllato."
            ),
        }


    def _build_generic_reduced(
        self,
        duration,
    ):
        """
        Seduta generica ridotta.
        """

        return {
            "intensity": "Facile",
            "warmup": (
                "Riscaldamento leggero"
            ),
            "main_set": (
                f"{duration}' lavoro controllato"
            ),
            "cooldown": (
                "Defaticamento"
            ),
            "technical_focus": (
                "Riduzione della fatica percepita"
            ),
            "removed_elements": (
                "Lavori intensi e variazioni impegnative"
            ),
            "notes": (
                "Volume ridotto e intensità mantenuta bassa."
            ),
        }


    def _build_generic_recovery(
        self,
        duration,
    ):
        """
        Recupero generico.
        """

        return {
            "intensity": "Z1 molto facile",
            "warmup": (
                "Movimento leggero progressivo"
            ),
            "main_set": (
                f"{duration}' recupero attivo"
            ),
            "cooldown": (
                "Defaticamento rilassato"
            ),
            "technical_focus": (
                "Rilassamento generale"
            ),
            "alternative": (
                "Riposo completo"
            ),
            "notes": (
                "Nessun lavoro di qualità."
            ),
        }


    # -------------------------------------------------
    # DATI COMUNI
    # -------------------------------------------------

    def _build_common_data(
        self,
        strategy,
        sport,
        sport_category,
        workout_name,
        session_type,
        planned_zone,
        original_duration,
        duration,
        decision_context,
        goal_profile,
        goal_adjustment,
    ):
        """
        Costruisce i dati comuni a tutte le proposte.
        """

        original_duration_value = None

        if original_duration is not None:
            original_duration_value = round(
                original_duration,
                1,
            )

        return {
            "strategy": strategy,
            "original_workout": workout_name,
            "sport": sport,
            "sport_category": sport_category,
            "original_type": session_type,
            "original_zone": planned_zone,
            "original_duration_minutes": original_duration_value,
            "duration_minutes": duration,
            "decision_context": decision_context,
            "goal_profile": goal_profile,
            "goal_adjustment": goal_adjustment,
        }


    def _build_goal_adjustment(
        self,
        goal_profile,
        strategy,
    ):
        """
        Determina il contesto di adattamento
        legato all'obiettivo atleta.
        """

        goal_profile = goal_profile or {}

        goal_type = goal_profile.get(
            "goal_type"
        )

        if goal_type == "EVENTO":
            return {
                "goal_type": "EVENTO",
                "focus": (
                    "Preservare la specificità "
                    "dell'obiettivo gara."
                ),
                "strategy": strategy,
            }

        if goal_type == "PERFORMANCE":
            return {
                "goal_type": "PERFORMANCE",
                "focus": (
                    "Preservare gli stimoli qualitativi "
                    "compatibili con il recupero."
                ),
                "strategy": strategy,
            }

        if goal_type == "BENESSERE":
            return {
                "goal_type": "BENESSERE",
                "focus": (
                    "Privilegiare continuità e gestione "
                    "della fatica."
                ),
                "strategy": strategy,
            }

        return {
            "goal_type": "NON DEFINITO",
            "focus": "Adattamento standard.",
            "strategy": strategy,
        }



    def _get_goal_profile(
        self,
        context,
        decision,
    ):
        """
        Estrae il profilo obiettivo atleta
        disponibile nel contesto o nella decisione.
        """

        context = context or {}
        decision = decision or {}

        if context.get(
            "goal_profile"
        ):

            return context.get(
                "goal_profile",
                {},
            ) or {}

        intelligence = decision.get(
            "intelligence",
            {},
        ) or {}

        return intelligence.get(
            "goal_profile",
            {},
        ) or {}



    def _build_decision_context(
        self,
        decision,
    ):
        """
        Estrae i fattori intelligence dalla decisione
        del Coach Engine.
        """

        decision = decision or {}

        intelligence = decision.get(
            "intelligence",
            {},
        ) or {}

        performance = intelligence.get(
            "performance",
            {},
        ) or {}

        adaptation = intelligence.get(
            "adaptation",
            {},
        ) or {}

        recovery_trend = intelligence.get(
            "recovery_trend",
            {},
        ) or {}

        return {
            "risk_level": decision.get(
                "risk_level"
            ),

            "performance_trend": performance.get(
                "trend"
            ),

            "adaptation_level": adaptation.get(
                "adaptation_level"
            ),

            "recovery_trend": recovery_trend.get(
                "trend"
            ),
        }


    # -------------------------------------------------
    # CLASSIFICAZIONE SPORT
    # -------------------------------------------------

    def _classify_sport(
        self,
        sport,
    ):
        """
        Classifica il valore dello sport.
        """

        normalized_sport = self._normalize_text(
            sport
        ).lower()

        run_keywords = (
            "corsa",
            "run",
            "running",
            "trail",
            "jogging",
        )

        bike_keywords = (
            "bici",
            "bike",
            "cycling",
            "ciclismo",
            "ciclist",
            "mtb",
            "mountain bike",
            "rulli",
            "indoor cycling",
        )

        swim_keywords = (
            "nuoto",
            "swim",
            "swimming",
            "piscina",
            "acque libere",
            "open water",
        )

        if any(
            keyword in normalized_sport
            for keyword in run_keywords
        ):
            return "RUN"

        if any(
            keyword in normalized_sport
            for keyword in bike_keywords
        ):
            return "BIKE"

        if any(
            keyword in normalized_sport
            for keyword in swim_keywords
        ):
            return "SWIM"

        return "GENERIC"
    # -------------------------------------------------
    # DURATE
    # -------------------------------------------------

    def _adapt_duration_percentage(
        self,
        goal_adjustment,
    ):
        """
        Modula la riduzione della durata
        in base all'obiettivo atleta.
        """

        goal_adjustment = goal_adjustment or {}

        goal_type = goal_adjustment.get(
            "goal_type"
        )

        if goal_type == "EVENTO":
            return 0.90

        if goal_type == "PERFORMANCE":
            return 0.85

        if goal_type == "BENESSERE":
            return 0.70

        return 0.80



    def _calculate_duration(
        self,
        original_duration,
        percentage,
        default_duration,
        minimum_duration,
    ):
        """
        Calcola la nuova durata della seduta.
        """

        if (
            original_duration is None
            or original_duration <= 0
        ):
            return int(default_duration)

        calculated_duration = round(
            original_duration * percentage
        )

        return int(
            max(
                minimum_duration,
                calculated_duration,
            )
        )

    def _calculate_recovery_duration(
        self,
        original_duration,
    ):
        """
        Calcola la durata di una seduta rigenerante.

        La durata viene limitata per evitare che una seduta
        di recupero diventi troppo lunga.
        """

        if (
            original_duration is None
            or original_duration <= 0
        ):
            return 30

        calculated_duration = round(
            original_duration * 0.50
        )

        return int(
            min(
                40,
                max(
                    20,
                    calculated_duration,
                ),
            )
        )

    def _split_duration(
        self,
        duration,
        warmup_target,
        cooldown_target,
        minimum_main,
    ):
        """
        Divide la durata totale tra riscaldamento,
        parte centrale e defaticamento.

        Garantisce che la somma delle tre parti sia
        uguale alla durata totale.
        """

        duration = int(
            max(
                1,
                duration,
            )
        )

        warmup_duration = min(
            int(warmup_target),
            max(
                3,
                duration // 4,
            ),
        )

        cooldown_duration = min(
            int(cooldown_target),
            max(
                3,
                duration // 5,
            ),
        )

        main_duration = (
            duration
            - warmup_duration
            - cooldown_duration
        )

        if main_duration < minimum_main:
            missing_minutes = (
                minimum_main
                - main_duration
            )

            reducible_warmup = max(
                0,
                warmup_duration - 3,
            )

            reduction = min(
                missing_minutes,
                reducible_warmup,
            )

            warmup_duration -= reduction
            main_duration += reduction
            missing_minutes -= reduction

            reducible_cooldown = max(
                0,
                cooldown_duration - 3,
            )

            reduction = min(
                missing_minutes,
                reducible_cooldown,
            )

            cooldown_duration -= reduction
            main_duration += reduction

        main_duration = max(
            1,
            duration
            - warmup_duration
            - cooldown_duration,
        )

        return (
            warmup_duration,
            main_duration,
            cooldown_duration,
        )

    # -------------------------------------------------
    # ESTRAZIONE E NORMALIZZAZIONE
    # -------------------------------------------------

    def _get_value(self, data, *field_names):
        """
        Restituisce il primo valore disponibile.
        """

        if not isinstance(data, dict):
            return None

        for field_name in field_names:
            value = data.get(field_name)

            if value is not None and value != "":
                return value

        return None

    def _get_text(self, data, *field_names):
        """
        Estrae e normalizza un valore testuale.
        """

        value = self._get_value(
            data,
            *field_names,
        )

        if value is None:
            return ""

        if isinstance(value, dict):
            value = value.get(
                "value",
                "",
            )

        return str(value).strip()

    def _get_number(self, data, *field_names):
        """
        Estrae e converte un valore numerico.

        Returns:
            float | None: Valore convertito oppure None.
        """

        value = self._get_value(
            data,
            *field_names,
        )

        if value is None or isinstance(value, bool):
            return None

        if isinstance(value, dict):
            value = value.get("value")

        if isinstance(value, (int, float)):
            return float(value)

        try:
            normalized_value = (
                str(value)
                .strip()
                .replace(",", ".")
            )

            return float(normalized_value)

        except (TypeError, ValueError):
            return None

    def _normalize_text(self, value):
        """
        Normalizza il testo rimuovendo spazi superflui
        e segni diacritici.

        Esempio:
            "Ciclismo" -> "Ciclismo"
            "attività" -> "attivita"
        """

        if value is None:
            return ""

        if isinstance(value, dict):
            value = value.get(
                "value",
                "",
            )

        text = str(value).strip()

        normalized_text = unicodedata.normalize(
            "NFKD",
            text,
        )

        normalized_text = "".join(
            character
            for character in normalized_text
            if not unicodedata.combining(character)
        )

        return " ".join(
            normalized_text.split()
        )