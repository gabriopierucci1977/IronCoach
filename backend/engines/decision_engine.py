"""
IronCoach Decision Engine v6.8

Responsabilità:

- combinare le valutazioni prodotte dagli analyzer;
- generare la decisione finale;
- utilizzare intelligence storica atleta;
- mantenere compatibilità con Decision.to_dict();
- normalizzare gli output decisionali.
"""


from backend.decision import Decision




class DecisionEngine:


    LEVEL_LOW = "LOW"
    LEVEL_MODERATE = "MODERATE"
    LEVEL_HIGH = "HIGH"
    LEVEL_CRITICAL = "CRITICAL"
    LEVEL_UNKNOWN = "UNKNOWN"



    # ======================================================
    # DECISION VOCABULARY
    # ======================================================


    DECISION_RECOVER = "RECUPERA"

    DECISION_ADAPT = "ADATTA"

    DECISION_CONFIRM = "CONFERMA"



    STRATEGY_RECOVERY = "RECOVERY"

    STRATEGY_ADAPT = "ADAPT"

    STRATEGY_KEEP_PLAN = "KEEP_PLAN"




    def decide(
        self,
        assessments,
    ):


        assessments = assessments or {}



        self._athlete_profile = assessments.get(
            "athlete_profile",
            {},
        ) or {}



        self._goal_profile = assessments.get(
            "goal_profile",
            {},
        ) or {}



        recovery = assessments.get(
            "recovery",
            {},
        )



        training = assessments.get(
            "training",
            {},
        )



        injury = assessments.get(
            "injury",
            {},
        )



        nutrition = assessments.get(
            "nutrition",
            {},
        )



        load = assessments.get(
            "load",
            {},
        )



        recovery_trend = assessments.get(
            "recovery_trend",
            {},
        )



        adaptation = assessments.get(
            "adaptation",
            {},
        )



        performance = assessments.get(
            "performance",
            {},
        )



        recovery_level = recovery.get(
            "level",
            self.LEVEL_UNKNOWN,
        )



        training_level = training.get(
            "level",
            self.LEVEL_UNKNOWN,
        )



        injury_level = injury.get(
            "level",
            self.LEVEL_UNKNOWN,
        )



        nutrition_level = nutrition.get(
            "level",
            self.LEVEL_UNKNOWN,
        )



        load_level = load.get(
            "level",
            self.LEVEL_UNKNOWN,
        )



        recovery_trend_status = recovery_trend.get(
            "trend",
            "UNKNOWN",
        )



        adaptation_level = adaptation.get(
            "adaptation_level",
            "UNKNOWN",
        )



        performance_trend_status = performance.get(
            "trend",
            "UNKNOWN",
        )



        reasoning = self._build_reasoning(
            assessments
        )

        self._intelligence = self._build_intelligence(
            assessments
        )

        # ======================================================
        # RISCHIO FISICO CRITICO
        # ======================================================


        if injury_level == self.LEVEL_CRITICAL:


            return self._decision(

                decision=self.DECISION_RECOVER,

                reason=(

                    "È stata segnalata una problematica fisica critica. "
                    "La priorità è interrompere il carico e favorire il recupero."

                ),

                priority="Recovery",

                confidence=99,

                strategy=self.STRATEGY_RECOVERY,

                recommended_action=(

                    "Sospendi i lavori allenanti. Valuta riposo e verifica "
                    "l'evoluzione della problematica prima di riprendere."

                ),

                reasoning=reasoning,

                risk_level="HIGH_ALERT",

            )




        # ======================================================
        # RECOVERY CRITICO
        # ======================================================


        if recovery_level == self.LEVEL_CRITICAL:


            return self._decision(

                decision=self.DECISION_RECOVER,

                reason=(

                    "La disponibilità fisiologica è critica: "
                    "il recupero deve avere priorità sullo stimolo allenante."

                ),

                priority="Recovery",

                confidence=98,

                strategy=self.STRATEGY_RECOVERY,

                recommended_action=(

                    "Riposo completo oppure massimo 30 minuti in Z1, "
                    "solo in assenza di dolore."

                ),

                reasoning=reasoning,

                risk_level="HIGH_ALERT",

            )




        # ======================================================
        # INTELLIGENCE:
        # CARICO ALTO + TREND RECOVERY NEGATIVO
        # ======================================================


        if (

            recovery_level == self.LEVEL_MODERATE

            and load_level == self.LEVEL_HIGH

            and recovery_trend_status == "DECLINING"

        ):


            return self._decision(

                decision=self.DECISION_RECOVER,

                reason=(

                    "Il carico recente è elevato e il trend del recupero "
                    "è in peggioramento. Aumentare lo stress allenante "
                    "potrebbe compromettere l'adattamento."

                ),

                priority="Recovery",

                confidence=96,

                strategy=self.STRATEGY_RECOVERY,

                recommended_action=(

                    "Ridurre il carico. Preferire recupero attivo, "
                    "zona aerobica facile e nessun lavoro ad alta intensità."

                ),

                reasoning=reasoning,

                risk_level="HIGH_ALERT",

            )




        # ======================================================
        # RECOVERY MODERATO + RISCHIO FISICO
        # ======================================================


        if (

            recovery_level == self.LEVEL_MODERATE

            and injury_level == self.LEVEL_HIGH

        ):


            return self._decision(

                decision=self.DECISION_RECOVER,

                reason=(

                    "Il recovery è limitato e sono presenti problematiche "
                    "fisiche: aggiungere carico aumenterebbe il rischio."

                ),

                priority="Recovery",

                confidence=97,

                strategy=self.STRATEGY_RECOVERY,

                recommended_action=(

                    "Riposo oppure attività rigenerante molto leggera, "
                    "senza corsa e senza lavori di qualità."

                ),

                reasoning=reasoning,

                risk_level="HIGH_ALERT",

            )




        # ======================================================
        # RECOVERY GIALLO + CARICO + NUTRIZIONE
        # ======================================================


        if (

            recovery_level == self.LEVEL_MODERATE

            and training_level == self.LEVEL_HIGH

            and nutrition_level == self.LEVEL_HIGH

        ):


            return self._decision(

                decision=self.DECISION_RECOVER,

                reason=(

                    "Recovery moderato, stress allenante elevato e recupero "
                    "nutrizionale insufficiente indicano la necessità di "
                    "una giornata rigenerante."

                ),

                priority="Recovery",

                confidence=96,

                strategy=self.STRATEGY_RECOVERY,

                recommended_action=(

                    "Riposo oppure attività rigenerante in Z1. "
                    "Ripristina carboidrati, liquidi e proteine."

                ),

                reasoning=reasoning,

                risk_level="HIGH_ALERT",

            )

        # ======================================================
        # RECOVERY VERDE + CARICO ELEVATO
        # ======================================================


        if (

            recovery_level == self.LEVEL_LOW

            and training_level == self.LEVEL_HIGH

            and load_level == self.LEVEL_HIGH

        ):


            return self._decision(

                decision=self.DECISION_ADAPT,

                reason=(

                    "Il recovery è favorevole ma il carico recente è elevato. "
                    "È necessario mantenere lo stimolo riducendo il rischio."

                ),

                priority="Performance",

                confidence=90,

                strategy=self.STRATEGY_ADAPT,

                recommended_action=(

                    "Mantieni la seduta modificando volume o intensità "
                    "in base alle sensazioni."

                ),

                reasoning=reasoning,

                risk_level="CAUTION",

            )




        # ======================================================
        # RECOVERY VERDE + NUTRIZIONE CARENTE
        # ======================================================


        if (

            recovery_level == self.LEVEL_LOW

            and nutrition_level == self.LEVEL_HIGH

        ):


            return self._decision(

                decision=self.DECISION_ADAPT,

                reason=(

                    "Il recovery è favorevole, ma il recupero nutrizionale "
                    "non è adeguato al carico completo."

                ),

                priority="Recovery",

                confidence=87,

                strategy=self.STRATEGY_ADAPT,

                recommended_action=(

                    "Riduci leggermente la seduta e completa il reintegro "
                    "di carboidrati, proteine e liquidi."

                ),

                reasoning=reasoning,

                risk_level="CAUTION",

            )




        # ======================================================
        # ADATTAMENTO LIMITATO
        # ======================================================


        if adaptation_level == "LIMITED":


            return self._decision(

                decision=self.DECISION_RECOVER,

                reason=(

                    "La capacità di adattamento risulta limitata. "
                    "È necessario ridurre lo stress allenante e "
                    "favorire il recupero."

                ),

                priority="Recovery",

                confidence=96,

                strategy=self.STRATEGY_RECOVERY,

                recommended_action=(

                    "Riduci nettamente il carico. Preferisci riposo, "
                    "recupero attivo o lavoro aerobico molto facile."

                ),

                reasoning=reasoning,

                risk_level="HIGH_ALERT",

            )




        # ======================================================
        # ADATTAMENTO MODERATO
        # ======================================================


        if adaptation_level == "MODERATE":


            return self._decision(

                decision=self.DECISION_ADAPT,

                reason=(

                    "La capacità di adattamento è da monitorare. "
                    "Il piano va mantenuto con una riduzione prudente "
                    "di volume o intensità."

                ),

                priority="Performance",

                confidence=90,

                strategy=self.STRATEGY_ADAPT,

                recommended_action=(

                    "Mantieni l'obiettivo della seduta riducendo "
                    "volume, intensità o densità del lavoro."

                ),

                reasoning=reasoning,

                risk_level="CAUTION",

            )




        # ======================================================
        # PERFORMANCE IN CALO + CARICO ALTO
        # ======================================================


        if (

            performance_trend_status == "DECLINING"

            and load_level == self.LEVEL_HIGH

        ):


            return self._decision(

                decision=self.DECISION_ADAPT,

                reason=(

                    "Il trend prestativo è in calo mentre il carico "
                    "recente è elevato. È opportuno adattare il piano "
                    "prima di aumentare ulteriormente lo stress."

                ),

                priority="Performance",

                confidence=89,

                strategy=self.STRATEGY_ADAPT,

                recommended_action=(

                    "Riduci moderatamente volume o intensità e "
                    "mantieni solo lo stimolo principale della seduta."

                ),

                reasoning=reasoning,

                risk_level="CAUTION",

            )




        # ======================================================
        # DATI RECOVERY NON DISPONIBILI
        # ======================================================


        if recovery_level == self.LEVEL_UNKNOWN:


            if (

                injury_level in (

                    self.LEVEL_HIGH,

                    self.LEVEL_CRITICAL,

                )

                or training_level == self.LEVEL_HIGH

                or nutrition_level == self.LEVEL_HIGH

            ):


                return self._decision(

                    decision=self.DECISION_RECOVER,

                    reason=(

                        "I dati recovery sono insufficienti e sono presenti "
                        "segnali di stress. È prudente ridurre il carico."

                    ),

                    priority="Recovery",

                    confidence=78,

                    strategy=self.STRATEGY_RECOVERY,

                    recommended_action=(

                        "Esegui solo lavoro aerobico facile e raccogli "
                        "nuovi dati recovery prima di una seduta intensa."

                    ),

                    reasoning=reasoning,

                    risk_level="CAUTION",

                )



            return self._decision(

                decision=self.DECISION_ADAPT,

                reason=(

                    "I dati recovery non sono sufficienti per confermare "
                    "con piena affidabilità il piano originale."

                ),

                priority="Recovery",

                confidence=72,

                strategy=self.STRATEGY_ADAPT,

                recommended_action=(

                    "Mantieni una versione prudente della seduta e valuta "
                    "le sensazioni durante il riscaldamento."

                ),

                reasoning=reasoning,

                risk_level="CAUTION",

            )




        # ======================================================
        # FATTORI MODERATI
        # ======================================================


        moderate_factors = self._count_levels(

            (

                training_level,

                injury_level,

                nutrition_level,

            ),

            (

                self.LEVEL_MODERATE,

            ),

        )



        if moderate_factors >= 2:


            return self._decision(

                decision=self.DECISION_ADAPT,

                reason=(

                    "Il recovery è favorevole, ma più fattori secondari "
                    "suggeriscono un adattamento prudente della seduta."

                ),

                priority="Performance",

                confidence=86,

                strategy=self.STRATEGY_ADAPT,

                recommended_action=(

                    "Mantieni l'obiettivo principale riducendo leggermente "
                    "volume o intensità."

                ),

                reasoning=reasoning,

                risk_level="CAUTION",

            )

        # ======================================================
        # CONFERMA PIANO
        # ======================================================


        return self._decision(

            decision=self.DECISION_CONFIRM,

            reason=(

                "Il recovery è favorevole e non emergono fattori critici "
                "che richiedano modifiche al piano."

            ),

            priority="Performance",

            confidence=95,

            strategy=self.STRATEGY_KEEP_PLAN,

            recommended_action="Allenamento confermato.",

            reasoning=reasoning,

            risk_level="NORMAL",

        )




    # ======================================================
    # REASONING
    # ======================================================


    def _build_reasoning(
        self,
        assessments,
    ):


        reasoning = []



        labels = (

            (
                "Recovery",
                assessments.get(
                    "recovery",
                    {},
                ),
            ),

            (
                "Carico",
                assessments.get(
                    "load",
                    {},
                ),
            ),

            (
                "Trend recovery",
                assessments.get(
                    "recovery_trend",
                    {},
                ),
            ),

            (
                "Adattamento",
                assessments.get(
                    "adaptation",
                    {},
                ),
            ),

            (
                "Performance",
                assessments.get(
                    "performance",
                    {},
                ),
            ),

            (
                "Allenamento",
                assessments.get(
                    "training",
                    {},
                ),
            ),

            (
                "Rischio fisico",
                assessments.get(
                    "injury",
                    {},
                ),
            ),

            (
                "Nutrizione",
                assessments.get(
                    "nutrition",
                    {},
                ),
            ),

        )



        for label, assessment in labels:


            level = (

                assessment.get(
                    "level"
                )

                or assessment.get(
                    "adaptation_level"
                )

                or assessment.get(
                    "trend"
                )

                or self.LEVEL_UNKNOWN

            )



            item = (

                f"{label}: "
                f"{self._level_label(level)}"

            )



            if item not in reasoning:

                reasoning.append(
                    item
                )



            for reason in assessment.get(
                "reasons",
                [],
            ):


                if (

                    reason

                    and reason not in reasoning

                ):

                    reasoning.append(
                        reason
                    )


        # --------------------------------------------------
        # PERFORMANCE DETAILS
        # --------------------------------------------------

        performance = assessments.get(
            "performance",
            {},
        ) or {}

        details = performance.get(
            "details",
            {},
        ) or {}

        for metric, data in details.items():

            if not isinstance(
                data,
                dict,
            ):
                continue

            start = data.get(
                "start"
            )

            end = data.get(
                "end"
            )

            change = data.get(
                "change_percent"
            )

            if (
                start is None
                or end is None
                or change is None
            ):
                continue

            detail = (
                f"{str(metric).upper()}: "
                f"{start} -> {end} "
                f"({change}%)"
            )

            if detail not in reasoning:
                reasoning.append(
                    detail
                )


        # --------------------------------------------------
        # ATHLETE PROFILE DETAILS
        # --------------------------------------------------

        athlete_profile = assessments.get(
            "athlete_profile",
            {},
        ) or {}

        athlete_type = athlete_profile.get(
            "athlete_type"
        )

        if self._meaningful_profile_value(
            athlete_type
        ):

            self._append_unique_reasoning(
                reasoning,
                (
                    "Profilo atleta: "
                    f"{athlete_type}"
                ),
            )

        for strength in self._profile_items(
            athlete_profile.get(
                "strengths"
            )
        ):

            self._append_unique_reasoning(
                reasoning,
                (
                    "Punto di forza atleta: "
                    f"{strength}"
                ),
            )

        for limitation in self._profile_items(
            athlete_profile.get(
                "limitations"
            )
        ):

            self._append_unique_reasoning(
                reasoning,
                (
                    "Limitazione atleta: "
                    f"{limitation}"
                ),
            )

        for preference in self._profile_items(
            athlete_profile.get(
                "training_preferences"
            )
        ):

            self._append_unique_reasoning(
                reasoning,
                (
                    "Preferenza allenante: "
                    f"{preference}"
                ),
            )

        for pattern in self._profile_items(
            athlete_profile.get(
                "injury_patterns"
            )
        ):

            self._append_unique_reasoning(
                reasoning,
                (
                    "Pattern infortunio: "
                    f"{pattern}"
                ),
            )



        # --------------------------------------------------
        # GOAL PROFILE DETAILS
        # --------------------------------------------------

        goal_profile = assessments.get(
            "goal_profile",
            {},
        ) or {}

        goal_type = goal_profile.get(
            "goal_type"
        )

        primary_goal = goal_profile.get(
            "primary_goal"
        )

        race_target = goal_profile.get(
            "race_target"
        )

        if self._meaningful_profile_value(
            primary_goal
        ):

            self._append_unique_reasoning(
                reasoning,
                (
                    "Obiettivo atleta: "
                    f"{primary_goal}"
                ),
            )

        elif self._meaningful_profile_value(
            goal_type
        ) and goal_type != "NON DEFINITO":

            self._append_unique_reasoning(
                reasoning,
                (
                    "Tipo obiettivo atleta: "
                    f"{goal_type}"
                ),
            )

        if (
            goal_type == "EVENTO"
            and self._meaningful_profile_value(
                race_target
            )
        ):

            self._append_unique_reasoning(
                reasoning,
                (
                    "Gara obiettivo: "
                    f"{race_target}"
                ),
            )


        return reasoning



    def _append_unique_reasoning(
        self,
        reasoning,
        item,
    ):

        if (
            item
            and item not in reasoning
        ):

            reasoning.append(
                item
            )



    def _profile_items(
        self,
        value,
    ):

        if value is None:

            return []

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):

            items = value

        else:

            items = [
                value
            ]

        return [
            str(item).strip()
            for item in items
            if self._meaningful_profile_value(
                item
            )
        ]



    def _meaningful_profile_value(
        self,
        value,
    ):

        if value is None:

            return False

        normalized = str(
            value
        ).strip()

        if not normalized:

            return False

        return normalized.upper() not in {
            "N/D",
            "UNKNOWN",
            "NONE",
            "NON DISPONIBILE",
        }




    # ======================================================
    # CREAZIONE DECISIONE
    # ======================================================


    def _decision(
        self,
        decision,
        reason,
        priority,
        confidence,
        strategy,
        recommended_action,
        reasoning,
        risk_level,
    ):


        decision = self._normalize_decision(
            decision
        )


        strategy = self._normalize_strategy(
            strategy
        )



        (
            reason,
            recommended_action,
        ) = self._personalize_decision_text(
            reason=reason,
            recommended_action=recommended_action,
        )



        result = Decision(

            decision=decision,

            reason=reason,

            priority=priority,

            confidence=confidence,

            strategy=strategy,

            recommended_action=recommended_action,

            reasoning=reasoning,

            risk_level=risk_level,

            intelligence=getattr(
                self,
                "_intelligence",
                {},
            ),

        )



        return result.to_dict()






    def _personalize_decision_text(
        self,
        reason,
        recommended_action,
    ):

        athlete_profile = getattr(
            self,
            "_athlete_profile",
            {},
        ) or {}

        athlete_type = athlete_profile.get(
            "athlete_type"
        )

        if self._meaningful_profile_value(
            athlete_type
        ):

            reason = self._append_sentence(
                reason,
                (
                    "La valutazione considera il profilo "
                    f"{str(athlete_type).strip()}."
                ),
            )



        goal_profile = getattr(
            self,
            "_goal_profile",
            {},
        ) or {}

        goal_type = goal_profile.get(
            "goal_type"
        )

        race_target = goal_profile.get(
            "race_target"
        )

        if (
            goal_type == "EVENTO"
            and self._meaningful_profile_value(
                race_target
            )
        ):

            reason = self._append_sentence(
                reason,
                (
                    "La gestione considera la preparazione "
                    f"dell'obiettivo gara {race_target}."
                ),
            )

        elif goal_type == "PERFORMANCE":

            reason = self._append_sentence(
                reason,
                (
                    "La strategia considera l'obiettivo "
                    "di miglioramento prestativo."
                ),
            )

        limitation = self._first_profile_item(
            athlete_profile.get(
                "limitations"
            )
        )

        injury_pattern = self._first_profile_item(
            athlete_profile.get(
                "injury_patterns"
            )
        )

        preference = self._first_profile_item(
            athlete_profile.get(
                "training_preferences"
            )
        )

        if limitation:

            recommended_action = self._append_sentence(
                recommended_action,
                (
                    "Considera la limitazione individuale: "
                    f"{limitation}."
                ),
            )

        elif injury_pattern:

            recommended_action = self._append_sentence(
                recommended_action,
                (
                    "Monitoraggio individuale: "
                    f"{injury_pattern}."
                ),
            )

        elif preference:

            recommended_action = self._append_sentence(
                recommended_action,
                (
                    "Compatibilmente con la strategia, "
                    "considera la preferenza allenante: "
                    f"{preference}."
                ),
            )

        return (
            reason,
            recommended_action,
        )



    def _first_profile_item(
        self,
        value,
    ):

        items = self._profile_items(
            value
        )

        if not items:

            return ""

        return items[0]



    def _append_sentence(
        self,
        text,
        sentence,
    ):

        base = str(
            text or ""
        ).strip()

        addition = str(
            sentence or ""
        ).strip()

        if not addition:

            return base

        if addition in base:

            return base

        if not base:

            return addition

        return (
            f"{base} {addition}"
        )



    def _build_intelligence(
        self,
        assessments,
    ):

        return {
            "recovery": assessments.get(
                "recovery",
                {},
            ),
            "load": assessments.get(
                "load",
                {},
            ),
            "adaptation": assessments.get(
                "adaptation",
                {},
            ),
            "recovery_trend": assessments.get(
                "recovery_trend",
                {},
            ),
            "performance": assessments.get(
                "performance",
                {},
            ),
        }

    # ======================================================
    # NORMALIZATION OUTPUT
    # ======================================================


    def _normalize_decision(
        self,
        value,
    ):


        if value is None:

            return self.DECISION_CONFIRM



        mapping = {


            "RIDUZIONE":

                self.DECISION_RECOVER,


            "RIDUCI":

                self.DECISION_RECOVER,


            "REDUCE":

                self.DECISION_RECOVER,


            "RECOVERY":

                self.DECISION_RECOVER,


            "RECUPERA":

                self.DECISION_RECOVER,



            "ADAPT":

                self.DECISION_ADAPT,


            "ADATTA":

                self.DECISION_ADAPT,



            "KEEP_PLAN":

                self.DECISION_CONFIRM,


            "CONFERMA":

                self.DECISION_CONFIRM,

        }



        normalized = str(
            value
        ).upper()



        return mapping.get(
            normalized,
            self.DECISION_CONFIRM,
        )




    def _normalize_strategy(
        self,
        value,
    ):


        if value is None:

            return self.STRATEGY_KEEP_PLAN



        mapping = {


            "REDUCE_LOAD":

                self.STRATEGY_RECOVERY,


            "RECOVERY":

                self.STRATEGY_RECOVERY,



            "ADAPT":

                self.STRATEGY_ADAPT,



            "KEEP_PLAN":

                self.STRATEGY_KEEP_PLAN,

        }



        normalized = str(
            value
        ).upper()



        return mapping.get(
            normalized,
            self.STRATEGY_KEEP_PLAN,
        )




    # ======================================================
    # UTILITY
    # ======================================================


    def _count_levels(
        self,
        values,
        levels,
    ):


        return sum(

            1

            for value in values

            if value in levels

        )




    def _level_label(
        self,
        level,
    ):


        mapping = {


            self.LEVEL_LOW:

                "basso",


            self.LEVEL_MODERATE:

                "moderato",


            self.LEVEL_HIGH:

                "alto",


            self.LEVEL_CRITICAL:

                "critico",


            self.LEVEL_UNKNOWN:

                "non disponibile",



            "DECLINING":

                "in peggioramento",



            "IMPROVING":

                "in miglioramento",


            "MODERATE":

                "moderato",

        }



        return mapping.get(
            level,
            level,
        )