"""
IronCoach Injury Analyzer v0.4

Analizzatore dedicato alla valutazione del rischio fisico.

Supporta:

- dati della seduta;
- profilo atleta normalizzato;
- storico problematiche fisiche.

Responsabilità:

- identificare rischio fisico;
- classificare livello attenzione;
- fornire informazioni al CoachEngine.

Non contiene logica decisionale.
"""




class InjuryAnalyzer:



    LEVEL_LOW = "LOW"

    LEVEL_MODERATE = "MODERATE"

    LEVEL_HIGH = "HIGH"

    LEVEL_CRITICAL = "CRITICAL"

    LEVEL_UNKNOWN = "UNKNOWN"




    def analyze(
        self,
        context,
    ):


        context = context or {}



        # ==================================================
        # INPUT SUPPORTATI
        # ==================================================


        if "training" in context:


            training = context.get(
                "training",
                {},
            ) or {}


            athlete_profile = context.get(
                "athlete_profile",
                {},
            ) or {}


        else:


            # compatibilità vecchio utilizzo

            training = context

            athlete_profile = {}




        constraints = athlete_profile.get(
            "constraints",
            {},
        ) or {}



        # Safety-relevant values use the canonical normalized activity
        # contract first.  The raw fallback keeps compatibility with legacy
        # contexts and direct analyzer use.
        current_problem = self._normalized_text(
            self._training_value(
                training,
                (
                    "current_problem",
                    "pain_notes",
                    "injury_notes",
                    "Dolori/problematiche",
                    "dolori_problematiche",
                    "Dolori",
                ),
            )
        ).lower()

        historical_problem = self._normalized_text(
            constraints.get(
                "injury_history"
            )
            or athlete_profile.get(
                "injury_history"
            )
        ).lower()

        physical_limitations = self._normalized_text(
            constraints.get(
                "physical_limitations"
            )
            or athlete_profile.get(
                "physical_limitations"
            )
            or athlete_profile.get(
                "limitations"
            )
        ).lower()

        pain_score = self._number(
            self._training_value(
                training,
                (
                    "pain_score",
                    "Pain Score",
                    "Dolore",
                ),
            )
        )


        combined_text = " ".join(

            value

            for value in (

                current_problem,

                historical_problem,

                physical_limitations,

            )

            if value

        )



        reasons = []

        patterns = []

        # ==================================================
        # DATI INSUFFICIENTI
        # ==================================================


        if not combined_text and pain_score is None:


            return {


                "level":

                    self.LEVEL_UNKNOWN,



                "current_problem":

                    "",



                "history":

                    "",



                "patterns":

                    [],



                "pain_score":

                    pain_score,



                "risk":

                    False,



                "reasons":

                    [
                        "Nessuna informazione disponibile "
                        "su dolori o problematiche"
                    ],

            }




        # ==================================================
        # NESSUN PROBLEMA ATTUALE
        # ==================================================


        no_problem = (

            "nessun dolore",

            "nessun problema",

            "nessuna problematica",

            "nessun fastidio",

            "nessuno",

            "no dolore",

            "no problemi",

        )



        if self._contains_any(
            current_problem,
            no_problem,
        ):


            current_problem = ""




        # ==================================================
        # SEGNALI CRITICI
        # ==================================================


        critical_signs = (

            "forte",

            "acuto",

            "zoppia",

            "gonfiore",

            "blocco",

            "lesione",

            "impossibile",

            "peggioramento",

        )



        if self._contains_any(
            combined_text,
            critical_signs,
        ):


            reasons.append(

                "Segnali fisici critici rilevati"

            )



            return self._result(

                level=self.LEVEL_CRITICAL,

                current_problem=current_problem,

                history=historical_problem,

                patterns=patterns,

                pain_score=pain_score,

                reasons=reasons,

            )




        # ==================================================
        # PATTERN INFORTUNIO
        # ==================================================


        injury_patterns = (

            (
                "tendine",
                "Tendine / problema tendineo",
            ),

            (
                "achille",
                "Achilles tendon history",
            ),

            (
                "infiammazione",
                "Infiammazione",
            ),

            (
                "strappo",
                "Problema muscolare",
            ),

            (
                "lesione",
                "Lesione",
            ),

        )



        for keyword, label in injury_patterns:


            if keyword in combined_text:


                patterns.append(
                    label
                )




        if patterns:


            reasons.append(

                "Storico o pattern fisico rilevante: "

                + ", ".join(patterns)

            )



            if current_problem:


                reasons.append(

                    "Problematica attuale: "

                    + current_problem

                )



            return self._result(

                level=self.LEVEL_HIGH,

                current_problem=current_problem,

                history=historical_problem,

                patterns=patterns,

                pain_score=pain_score,

                reasons=reasons,

            )




        # ==================================================
        # PAIN SCORE
        # ==================================================


        if pain_score is not None:


            if pain_score >= 5:


                reasons.append(

                    f"Pain Score elevato: {pain_score}"

                )


                return self._result(

                    level=self.LEVEL_HIGH,

                    current_problem=current_problem,

                    history=historical_problem,

                    patterns=patterns,

                    pain_score=pain_score,

                    reasons=reasons,

                )



            if pain_score >= 2:


                reasons.append(

                    f"Fastidio fisico presente: {pain_score}/10"

                )


                return self._result(

                    level=self.LEVEL_MODERATE,

                    current_problem=current_problem,

                    history=historical_problem,

                    patterns=patterns,

                    pain_score=pain_score,

                    reasons=reasons,

                )




        # ==================================================
        # DEFAULT
        # ==================================================


        if current_problem:


            reasons.append(

                "Problematica fisica segnalata: "

                + current_problem

            )



            return self._result(

                level=self.LEVEL_MODERATE,

                current_problem=current_problem,

                history=historical_problem,

                patterns=patterns,

                pain_score=pain_score,

                reasons=reasons,

            )




        return self._result(

            level=self.LEVEL_LOW,

            current_problem="",

            history=historical_problem,

            patterns=patterns,

            pain_score=pain_score,

            reasons=[

                "Nessun rischio fisico rilevante rilevato"

            ],

        )




    # ==================================================
    # RESULT
    # ==================================================


    def _result(
        self,
        level,
        current_problem,
        history,
        patterns,
        pain_score,
        reasons,
    ):


        return {


            "level":

                level,



            "risk":

                level in (

                    self.LEVEL_HIGH,

                    self.LEVEL_CRITICAL,

                ),



            "current_problem":

                current_problem,



            "history":

                history,



            "patterns":

                patterns,



            "pain_score":

                pain_score,



            "reasons":

                reasons,

        }




    # ==================================================
    # HELPERS
    # ==================================================


    def _training_value(
        self,
        training,
        keys,
    ):
        """Read canonical training values with a legacy ``raw`` fallback."""

        for data in (
            training,
            training.get("raw", {})
            if isinstance(training, dict)
            else {},
        ):
            if not isinstance(data, dict):
                continue

            for key in keys:
                if key not in data:
                    continue

                value = data.get(key)

                if value not in (
                    None,
                    "",
                ):
                    return value

        return None


    def _number(
        self,
        value,
    ):


        if value is None:

            return None



        if isinstance(
            value,
            str,
        ):


            value = (

                value
                .strip()
                .replace(
                    ",",
                    ".",
                )

            )



        try:

            return float(
                value
            )


        except (
            TypeError,
            ValueError,
        ):

            return None




    def _normalized_text(
        self,
        value,
    ):


        if value is None:

            return ""



        if isinstance(
            value,
            dict,
        ):


            value = value.get(
                "value",
                "",
            )



        return str(
            value
        ).strip()




    def _contains_any(
        self,
        text,
        expressions,
    ):


        if not text:

            return False



        return any(

            expression in text

            for expression in expressions

        )
