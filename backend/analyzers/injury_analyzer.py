"""
IronCoach Injury Analyzer v0.3.2

Analizzatore dedicato alla valutazione del rischio fisico.

Obiettivi:

- mantenere il comportamento decisionale precedente;
- separare la logica dal CoachEngine;
- mantenere compatibilità con DecisionEngine.
"""


class InjuryAnalyzer:


    LEVEL_LOW = "LOW"
    LEVEL_MODERATE = "MODERATE"
    LEVEL_HIGH = "HIGH"
    LEVEL_CRITICAL = "CRITICAL"
    LEVEL_UNKNOWN = "UNKNOWN"



    def analyze(self, training):

        """
        Valuta il rischio fisico della seduta.
        """

        problem = self._normalized_text(
            training.get("Dolori/problematiche")
            or training.get("dolori_problematiche")
            or training.get("Dolori")
        ).lower()


        pain_score = self._number(
            training.get("Pain Score")
            or training.get("pain_score")
            or training.get("Dolore")
        )


        reasons = []


        if not problem:

            return {

                "level": self.LEVEL_UNKNOWN,

                "problem": "",

                "pain_score": pain_score,

                "reasons": [
                    "Nessuna informazione disponibile "
                    "su dolori o problemi"
                ],

            }



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
            problem,
            no_problem,
        ):

            return {

                "level": self.LEVEL_LOW,

                "problem": problem,

                "pain_score": pain_score,

                "reasons": [
                    "Nessun dolore o problema segnalato"
                ],

            }



        severe_signs = (

            "forte",
            "acuto",
            "zoppia",
            "gonfiore",
            "blocco",
            "lesione",
            "peggioramento",
            "impossibile",

        )


        if self._contains_any(
            problem,
            severe_signs,
        ):

            reasons.append(
                f"Problematica critica segnalata: {problem}"
            )


            return {

                "level": self.LEVEL_CRITICAL,

                "problem": problem,

                "pain_score": pain_score,

                "reasons": reasons,

            }



        injury_signs = (

            "tendine",
            "tendineo",
            "infiammazione",
            "strappo",
            "lesione",

        )


        if self._contains_any(
            problem,
            injury_signs,
        ):

            reasons.append(
                f"Problematica fisica segnalata: {problem}"
            )


            return {

                "level": self.LEVEL_HIGH,

                "problem": problem,

                "pain_score": pain_score,

                "reasons": reasons,

            }



        if pain_score is not None:

            if pain_score >= 5:

                reasons.append(
                    f"Pain Score elevato: {pain_score}"
                )


                return {

                    "level": self.LEVEL_HIGH,

                    "problem": problem,

                    "pain_score": pain_score,

                    "reasons": reasons,

                }



            if pain_score >= 2:

                reasons.append(
                    f"Problematica fisica segnalata: {problem}"
                )


                return {

                    "level": self.LEVEL_HIGH,

                    "problem": problem,

                    "pain_score": pain_score,

                    "reasons": reasons,

                }



        # Compatibilità con il vecchio comportamento:
        # qualsiasi problematica descritta durante una seduta
        # viene mantenuta come fattore di rischio.

        reasons.append(
            f"Problematica fisica segnalata: {problem}"
        )


        return {

            "level": self.LEVEL_HIGH,

            "problem": problem,

            "pain_score": pain_score,

            "reasons": reasons,

        }



    def _number(self, value):

        if value is None:

            return None


        if isinstance(value, str):

            value = (
                value
                .strip()
                .replace(",", ".")
            )


        try:

            return float(value)


        except (
            TypeError,
            ValueError,
        ):

            return None



    def _normalized_text(self, value):

        if value is None:

            return ""


        if isinstance(value, dict):

            value = value.get(
                "value",
                "",
            )


        return str(value).strip()



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