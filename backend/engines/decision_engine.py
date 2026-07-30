"""
IronCoach Decision Engine

Responsabilità:
- combinare le valutazioni prodotte dagli analyzer;
- generare la decisione finale;
- mantenere compatibilità con Decision.to_dict().

La logica decisionale è estratta da CoachEngine senza
modificare il comportamento originale.
"""

from backend.decision import Decision


class DecisionEngine:
    """
    Decision layer centrale di IronCoach.

    Riceve:
        - recovery assessment
        - training assessment
        - injury assessment
        - nutrition assessment

    Restituisce:
        dizionario serializzato tramite Decision.to_dict()
    """

    LEVEL_LOW = "LOW"
    LEVEL_MODERATE = "MODERATE"
    LEVEL_HIGH = "HIGH"
    LEVEL_CRITICAL = "CRITICAL"
    LEVEL_UNKNOWN = "UNKNOWN"


    def decide(self, assessments):
        """
        Combina le valutazioni e genera la decisione finale.
        """

        recovery = assessments["recovery"]
        training = assessments["training"]
        injury = assessments["injury"]
        nutrition = assessments["nutrition"]

        recovery_level = recovery["level"]
        training_level = training["level"]
        injury_level = injury["level"]
        nutrition_level = nutrition["level"]

        reasoning = self._build_reasoning(assessments)


        # ------------------------------------------------------
        # BLOCCO DI SICUREZZA: RISCHIO FISICO CRITICO
        # ------------------------------------------------------

        if injury_level == self.LEVEL_CRITICAL:

            return self._decision(
                decision="RECUPERA",
                reason=(
                    "È stata segnalata una problematica fisica critica. "
                    "La priorità è interrompere il carico e favorire il recupero."
                ),
                priority="Recovery",
                confidence=99,
                strategy="RECOVERY",
                recommended_action=(
                    "Sospendi i lavori allenanti. Valuta riposo e verifica "
                    "l'evoluzione della problematica prima di riprendere."
                ),
                reasoning=reasoning,
                risk_level="HIGH_ALERT",
            )


        # ------------------------------------------------------
        # RECOVERY ROSSO O CRITICO
        # ------------------------------------------------------

        if recovery_level == self.LEVEL_CRITICAL:

            return self._decision(
                decision="RECUPERA",
                reason=(
                    "La disponibilità fisiologica è critica: "
                    "il recupero deve avere priorità sullo stimolo allenante."
                ),
                priority="Recovery",
                confidence=98,
                strategy="RECOVERY",
                recommended_action=(
                    "Riposo completo oppure massimo 30 minuti in Z1, "
                    "solo in assenza di dolore."
                ),
                reasoning=reasoning,
                risk_level="HIGH_ALERT",
            )


        # ------------------------------------------------------
        # RECOVERY GIALLO + RISCHIO FISICO
        # ------------------------------------------------------

        if (
            recovery_level == self.LEVEL_MODERATE
            and injury_level == self.LEVEL_HIGH
        ):

            return self._decision(
                decision="RECUPERA",
                reason=(
                    "Il recovery è limitato e sono presenti problematiche "
                    "fisiche: aggiungere carico aumenterebbe il rischio."
                ),
                priority="Recovery",
                confidence=97,
                strategy="RECOVERY",
                recommended_action=(
                    "Riposo oppure attività rigenerante molto leggera, "
                    "senza corsa e senza lavori di qualità."
                ),
                reasoning=reasoning,
                risk_level="HIGH_ALERT",
            )

        # ------------------------------------------------------
        # RECOVERY GIALLO + CARICO ALTO + NUTRIZIONE CARENTE
        # ------------------------------------------------------

        if (
            recovery_level == self.LEVEL_MODERATE
            and training_level == self.LEVEL_HIGH
            and nutrition_level == self.LEVEL_HIGH
        ):

            return self._decision(
                decision="RECUPERA",
                reason=(
                    "Recovery moderato, stress allenante elevato e recupero "
                    "nutrizionale insufficiente indicano la necessità di una "
                    "giornata rigenerante."
                ),
                priority="Recovery",
                confidence=96,
                strategy="RECOVERY",
                recommended_action=(
                    "Riposo oppure attività rigenerante in Z1. "
                    "Ripristina carboidrati, liquidi e proteine prima "
                    "del prossimo lavoro di qualità."
                ),
                reasoning=reasoning,
                risk_level="HIGH_ALERT",
            )


        # ------------------------------------------------------
        # RECOVERY GIALLO + DUE FATTORI MODERATI/ALTI
        # ------------------------------------------------------

        if recovery_level == self.LEVEL_MODERATE:

            additional_risk_factors = self._count_levels(
                (
                    training_level,
                    injury_level,
                    nutrition_level,
                ),
                (
                    self.LEVEL_MODERATE,
                    self.LEVEL_HIGH,
                    self.LEVEL_CRITICAL,
                ),
            )

            high_risk_factors = self._count_levels(
                (
                    training_level,
                    injury_level,
                    nutrition_level,
                ),
                (
                    self.LEVEL_HIGH,
                    self.LEVEL_CRITICAL,
                ),
            )


            if high_risk_factors >= 2:

                return self._decision(
                    decision="RECUPERA",
                    reason=(
                        "Il recovery è moderato e sono presenti più fattori "
                        "di rischio elevato. Una seduta allenante non è "
                        "consigliata."
                    ),
                    priority="Recovery",
                    confidence=95,
                    strategy="RECOVERY",
                    recommended_action=(
                        "Giornata di recupero o attività rigenerante in Z1, "
                        "senza intensità."
                    ),
                    reasoning=reasoning,
                    risk_level="HIGH_ALERT",
                )


            if additional_risk_factors >= 1:

                return self._decision(
                    decision="RIDUZIONE",
                    reason=(
                        "Il recovery è moderato e il contesto non supporta "
                        "il carico completo previsto."
                    ),
                    priority="Recovery",
                    confidence=92,
                    strategy="REDUCE_LOAD",
                    recommended_action=(
                        "Riduci volume e intensità. Mantieni solo lavoro "
                        "aerobico facile e interrompi in caso di peggioramento "
                        "delle sensazioni."
                    ),
                    reasoning=reasoning,
                    risk_level="CAUTION",
                )


            return self._decision(
                decision="RIDUZIONE",
                reason=(
                    "Il recovery è moderato: è prudente ridurre il carico "
                    "anche in assenza di altri segnali critici."
                ),
                priority="Recovery",
                confidence=90,
                strategy="REDUCE_LOAD",
                recommended_action=(
                    "Riduci il volume previsto e mantieni intensità "
                    "prevalentemente aerobica."
                ),
                reasoning=reasoning,
                risk_level="CAUTION",
            )


        # ------------------------------------------------------
        # RECOVERY VERDE + PROBLEMATICA FISICA
        # ------------------------------------------------------

        if injury_level == self.LEVEL_HIGH:

            return self._decision(
                decision="ADATTA",
                reason=(
                    "Il recovery generale è favorevole, ma la problematica "
                    "fisica richiede una modifica specifica della seduta."
                ),
                priority="Recovery",
                confidence=94,
                strategy="ADAPT",
                recommended_action=(
                    "Evita il gesto o la disciplina che provoca dolore. "
                    "Sostituisci la seduta con attività a basso impatto."
                ),
                reasoning=reasoning,
                risk_level="CAUTION",
            )

        # ------------------------------------------------------
        # RECOVERY VERDE + CARICO ALTO E NUTRIZIONE CARENTE
        # ------------------------------------------------------

        if (
            recovery_level == self.LEVEL_LOW
            and training_level == self.LEVEL_HIGH
            and nutrition_level == self.LEVEL_HIGH
        ):

            return self._decision(
                decision="ADATTA",
                reason=(
                    "Il recovery è favorevole, ma lo stress dell'ultima "
                    "seduta e il recupero nutrizionale insufficiente "
                    "suggeriscono di adattare lo stimolo."
                ),
                priority="Recovery",
                confidence=91,
                strategy="ADAPT",
                recommended_action=(
                    "Mantieni la seduta, ma riduci intensità o durata. "
                    "Cura il reintegro nutrizionale e l'idratazione."
                ),
                reasoning=reasoning,
                risk_level="CAUTION",
            )


        # ------------------------------------------------------
        # RECOVERY VERDE + CARICO ALTO
        # ------------------------------------------------------

        if (
            recovery_level == self.LEVEL_LOW
            and training_level == self.LEVEL_HIGH
        ):

            return self._decision(
                decision="ADATTA",
                reason=(
                    "Il recovery è favorevole, ma l'ultima seduta ha "
                    "prodotto uno stress elevato. Lo stimolo può essere "
                    "mantenuto in forma ridotta."
                ),
                priority="Performance",
                confidence=89,
                strategy="ADAPT",
                recommended_action=(
                    "Mantieni l'obiettivo della seduta riducendo durata, "
                    "numero di ripetute o intensità."
                ),
                reasoning=reasoning,
                risk_level="CAUTION",
            )


        # ------------------------------------------------------
        # RECOVERY VERDE + NUTRIZIONE CARENTE
        # ------------------------------------------------------

        if (
            recovery_level == self.LEVEL_LOW
            and nutrition_level == self.LEVEL_HIGH
        ):

            return self._decision(
                decision="ADATTA",
                reason=(
                    "Il recovery è favorevole, ma il recupero nutrizionale "
                    "non è adeguato al carico completo."
                ),
                priority="Recovery",
                confidence=87,
                strategy="ADAPT",
                recommended_action=(
                    "Riduci leggermente la seduta e completa il reintegro "
                    "di carboidrati, proteine e liquidi."
                ),
                reasoning=reasoning,
                risk_level="CAUTION",
            )


        # ------------------------------------------------------
        # DATI RECOVERY NON DISPONIBILI
        # ------------------------------------------------------

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
                    decision="RIDUZIONE",
                    reason=(
                        "I dati recovery sono insufficienti e sono presenti "
                        "segnali di stress. È prudente ridurre il carico."
                    ),
                    priority="Recovery",
                    confidence=78,
                    strategy="REDUCE_LOAD",
                    recommended_action=(
                        "Esegui solo lavoro aerobico facile e raccogli nuovi "
                        "dati recovery prima di una seduta intensa."
                    ),
                    reasoning=reasoning,
                    risk_level="CAUTION",
                )


            return self._decision(
                decision="ADATTA",
                reason=(
                    "I dati recovery non sono sufficienti per confermare "
                    "con piena affidabilità il piano originale."
                ),
                priority="Recovery",
                confidence=72,
                strategy="ADAPT",
                recommended_action=(
                    "Mantieni una versione prudente della seduta e valuta "
                    "le sensazioni durante il riscaldamento."
                ),
                reasoning=reasoning,
                risk_level="CAUTION",
            )

        # ------------------------------------------------------
        # RECOVERY VERDE + FATTORI MODERATI
        # ------------------------------------------------------

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
                decision="ADATTA",
                reason=(
                    "Il recovery è favorevole, ma più fattori secondari "
                    "suggeriscono un adattamento prudente della seduta."
                ),
                priority="Performance",
                confidence=86,
                strategy="ADAPT",
                recommended_action=(
                    "Mantieni l'obiettivo principale riducendo leggermente "
                    "volume o intensità."
                ),
                reasoning=reasoning,
                risk_level="CAUTION",
            )


        # ------------------------------------------------------
        # CONFERMA DEL PIANO
        # ------------------------------------------------------

        return self._decision(
            decision="CONFERMA",
            reason=(
                "Il recovery è favorevole e non emergono fattori critici "
                "che richiedano modifiche al piano."
            ),
            priority="Performance",
            confidence=95,
            strategy="KEEP_PLAN",
            recommended_action="Allenamento confermato.",
            reasoning=reasoning,
            risk_level="NORMAL",
        )


    def _build_reasoning(self, assessments):
        """
        Costruisce una lista leggibile e priva di duplicati.
        """

        reasoning = []

        labels = (
            ("Recovery", assessments["recovery"]),
            ("Carico", assessments["training"]),
            ("Rischio fisico", assessments["injury"]),
            ("Nutrizione", assessments["nutrition"]),
        )

        for label, assessment in labels:

            level = assessment.get(
                "level",
                self.LEVEL_UNKNOWN,
            )

            reasoning.append(
                f"{label}: {self._level_label(level)}"
            )

            for reason in assessment.get("reasons", []):

                if reason and reason not in reasoning:
                    reasoning.append(reason)

        return reasoning


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
        """
        Crea e serializza una Decision.
        """

        return Decision(
            decision=decision,
            reason=reason,
            priority=priority,
            confidence=confidence,
            strategy=strategy,
            recommended_action=recommended_action,
            reasoning=reasoning,
            risk_level=risk_level,
        ).to_dict()


    def _count_levels(
        self,
        levels,
        accepted_levels,
    ):
        """
        Conta quanti livelli appartengono all'insieme indicato.
        """

        return sum(
            1
            for level in levels
            if level in accepted_levels
        )


    def _level_label(self, level):
        """
        Converte i livelli interni in etichette leggibili.
        """

        labels = {
            self.LEVEL_LOW: "basso",
            self.LEVEL_MODERATE: "moderato",
            self.LEVEL_HIGH: "alto",
            self.LEVEL_CRITICAL: "critico",
            self.LEVEL_UNKNOWN: "non determinato",
        }

        return labels.get(
            level,
            "non determinato",
        )
