"""
IronCoach Coach Engine v5

Motore di orchestrazione.

Responsabilità:
- raccogliere le valutazioni dai diversi analyzer;
- inviare gli assessment al DecisionEngine;
- mantenere invariata l'interfaccia pubblica:

    CoachEngine().evaluate(context)

Il metodo restituisce sempre un dizionario generato da Decision.
"""

from backend.engines.decision_engine import DecisionEngine

from backend.analyzers.recovery_analyzer import RecoveryAnalyzer
from backend.analyzers.training_analyzer import TrainingAnalyzer
from backend.analyzers.injury_analyzer import InjuryAnalyzer
from backend.analyzers.nutrition_analyzer import NutritionAnalyzer



class CoachEngine:

    """
    Motore centrale di IronCoach.

    Gli analyzer producono valutazioni separate:

    - recovery readiness
    - training stress
    - injury risk
    - nutrition status

    Il DecisionEngine combina successivamente
    gli assessment e genera la decisione finale.
    """


    RECOVERY_GREEN = "VERDE"
    RECOVERY_YELLOW = "GIALLO"
    RECOVERY_RED = "ROSSO"


    LEVEL_LOW = "LOW"
    LEVEL_MODERATE = "MODERATE"
    LEVEL_HIGH = "HIGH"
    LEVEL_CRITICAL = "CRITICAL"
    LEVEL_UNKNOWN = "UNKNOWN"



    def __init__(self):

        self.recovery_analyzer = RecoveryAnalyzer()

        self.training_analyzer = TrainingAnalyzer()

        self.injury_analyzer = InjuryAnalyzer()

        self.nutrition_analyzer = NutritionAnalyzer()


        self.decision_engine = DecisionEngine()



    def evaluate(self, context):

        """
        Valuta il contesto completo dell'atleta.
        """

        context = context or {}


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



        recovery_assessment = (
            self.recovery_analyzer.analyze(
                recovery
            )
        )


        training_assessment = (
            self.training_analyzer.analyze(
                training
            )
        )


        injury_assessment = (
            self.injury_analyzer.analyze(
                training
            )
        )


        nutrition_assessment = (
            self.nutrition_analyzer.analyze(
                nutrition
            )
        )



        assessments = {

            "recovery": recovery_assessment,

            "training": training_assessment,

            "injury": injury_assessment,

            "nutrition": nutrition_assessment,

        }



        return self.decision_engine.decide(
            assessments
        )

    def _assess_recovery(self, recovery):

        """
        BACKUP TEMPORANEO

        La logica è stata spostata in:
            backend.analyzers.recovery_analyzer

        Questo metodo rimane solo durante la fase
        di migrazione per confronto e rollback.
        """

        recovery_state = self._normalized_text(
            recovery.get("Stato Recovery")
            or recovery.get("stato_recovery")
        ).upper()


        recovery_score = self._number(
            recovery.get("Recovery Score")
            or recovery.get("recovery_score")
        )


        sleep_score = self._number(
            recovery.get("Sleep Score")
            or recovery.get("sleep_score")
        )


        reasons = []


        if recovery_state == self.RECOVERY_RED:

            reasons.append(
                "Recovery in stato ROSSO"
            )


            if recovery_score is not None:

                reasons.append(
                    f"Recovery Score pari a "
                    f"{self._format_number(recovery_score)}"
                )


            if sleep_score is not None and sleep_score < 60:

                reasons.append(
                    f"Sleep Score basso: "
                    f"{self._format_number(sleep_score)}"
                )


            return {
                "state": recovery_state,
                "level": self.LEVEL_CRITICAL,
                "score": recovery_score,
                "sleep_score": sleep_score,
                "reasons": reasons,
            }



        if recovery_state == self.RECOVERY_YELLOW:

            reasons.append(
                "Recovery in stato GIALLO"
            )


            if recovery_score is not None:

                reasons.append(
                    f"Recovery Score pari a "
                    f"{self._format_number(recovery_score)}"
                )


            if sleep_score is not None and sleep_score < 65:

                reasons.append(
                    f"Sleep Score ridotto: "
                    f"{self._format_number(sleep_score)}"
                )


            return {
                "state": recovery_state,
                "level": self.LEVEL_MODERATE,
                "score": recovery_score,
                "sleep_score": sleep_score,
                "reasons": reasons,
            }



        if recovery_state == self.RECOVERY_GREEN:

            reasons.append(
                "Recovery in stato VERDE"
            )


            if recovery_score is not None:

                reasons.append(
                    f"Recovery Score pari a "
                    f"{self._format_number(recovery_score)}"
                )


            if sleep_score is not None and sleep_score < 60:

                reasons.append(
                    "Sleep Score basso nonostante "
                    "recovery VERDE: "
                    f"{self._format_number(sleep_score)}"
                )


                return {
                    "state": recovery_state,
                    "level": self.LEVEL_MODERATE,
                    "score": recovery_score,
                    "sleep_score": sleep_score,
                    "reasons": reasons,
                }


            return {
                "state": recovery_state,
                "level": self.LEVEL_LOW,
                "score": recovery_score,
                "sleep_score": sleep_score,
                "reasons": reasons,
            }



        return {
            "state": recovery_state,
            "level": self.LEVEL_UNKNOWN,
            "score": recovery_score,
            "sleep_score": sleep_score,
            "reasons": reasons,
        }

    def _assess_training(self, training):

        """
        BACKUP TEMPORANEO

        La logica è stata spostata in:
            backend.analyzers.training_analyzer

        Metodo mantenuto solo per rollback.
        """

        rpe = self._number(
            training.get("RPE percepito")
            or training.get("RPE")
            or training.get("rpe")
        )


        session_type = self._normalized_text(
            training.get("Tipo seduta")
            or training.get("tipo_seduta")
        ).lower()


        planned_zone = self._normalized_text(
            training.get("Zona prevista")
            or training.get("zona_prevista")
        ).lower()


        duration_minutes = self._number(
            training.get("Durata minuti")
            or training.get("durata_minuti")
        )


        internal_load = self._number(
            training.get("Carico interno")
            or training.get("carico_interno")
        )


        reasons = []


        if rpe is not None:

            reasons.append(
                f"RPE ultima seduta: "
                f"{self._format_number(rpe)}"
            )


        if (
            "qualità" in session_type
            or "vo2" in session_type
            or "ripetute" in session_type
            or "intervalli" in session_type
        ):

            reasons.append(
                "Ultima seduta classificata ad alta intensità"
            )


        if (
            "z4" in planned_zone
            or "z5" in planned_zone
            or "vo2" in planned_zone
        ):

            reasons.append(
                "Zona prevista ad alta intensità"
            )


        if (
            rpe is not None
            and rpe >= 9
        ):

            return {

                "level": self.LEVEL_HIGH,

                "rpe": rpe,

                "session_type": session_type,

                "planned_zone": planned_zone,

                "duration_minutes": duration_minutes,

                "internal_load": internal_load,

                "reasons": reasons,

            }


        return {

            "level": self.LEVEL_LOW,

            "rpe": rpe,

            "session_type": session_type,

            "planned_zone": planned_zone,

            "duration_minutes": duration_minutes,

            "internal_load": internal_load,

            "reasons": reasons,

        }



    def _assess_injury(self, training):

        """
        BACKUP TEMPORANEO

        La logica è stata spostata in:
            backend.analyzers.injury_analyzer
        """

        problem = self._normalized_text(
            training.get("Dolori/problematiche")
            or training.get("dolori_problematiche")
            or training.get("Dolori")
        ).lower()


        if not problem:

            return {

                "level": self.LEVEL_UNKNOWN,

                "problem": "",

                "reasons": [
                    "Nessuna informazione disponibile "
                    "su dolori o problemi"
                ],

            }


        return {

            "level": self.LEVEL_MODERATE,

            "problem": problem,

            "reasons": [
                f"Segnalazione fisica da monitorare: {problem}"
            ],

        }

    def _assess_nutrition(self, nutrition):

        """
        BACKUP TEMPORANEO

        La logica è stata spostata in:
            backend.analyzers.nutrition_analyzer
        """

        recovery_status = self._normalized_text(
            nutrition.get("Stato recupero nutrizionale")
            or nutrition.get("stato_recupero_nutrizionale")
        ).lower()


        hydration_status = self._normalized_text(
            nutrition.get("Stato idratazione")
            or nutrition.get("stato_idratazione")
        ).lower()


        carbohydrate_status = self._normalized_text(
            nutrition.get("Stato carboidrati")
            or nutrition.get("stato_carboidrati")
        ).lower()


        reasons = []


        if recovery_status:

            reasons.append(
                f"Recupero nutrizionale: "
                f"{recovery_status.upper()}"
            )


        if hydration_status:

            reasons.append(
                f"Idratazione: "
                f"{hydration_status.upper()}"
            )


        if carbohydrate_status:

            reasons.append(
                f"Disponibilità carboidrati: "
                f"{carbohydrate_status.upper()}"
            )


        return {

            "level": self.LEVEL_LOW,

            "recovery_status": recovery_status,

            "hydration_status": hydration_status,

            "carbohydrate_status": carbohydrate_status,

            "reasons": reasons,

        }



    def _number(self, value):

        """
        Converte un valore numerico in float.
        """

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

        """
        Normalizza testo proveniente da Airtable.
        """

        if value is None:

            return ""


        if isinstance(value, dict):

            generated_value = value.get(
                "value"
            )

            if generated_value is not None:

                return str(
                    generated_value
                ).strip()


        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):

            return " ".join(
                str(item).strip()
                for item in value
                if item is not None
            ).strip()


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



    def _format_number(self, value):

        if value is None:

            return "N/D"


        if float(value).is_integer():

            return str(
                int(value)
            )


        return f"{value:.1f}"

