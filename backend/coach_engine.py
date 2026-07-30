"""
IronCoach Coach Engine v6.5

Motore centrale di orchestrazione.

Responsabilità:

- ricevere il contesto atleta;
- eseguire gli analyzer dello stato attuale;
- analizzare carico, adattamento e performance;
- analizzare il trend storico del recupero;
- passare gli assessment al DecisionEngine;
- allegare l'intelligence alla decisione finale.

La logica decisionale rimane nel DecisionEngine.
"""


from backend.engines.decision_engine import DecisionEngine

from backend.analyzers.recovery_analyzer import RecoveryAnalyzer
from backend.analyzers.recovery_trend_analyzer import RecoveryTrendAnalyzer
from backend.analyzers.training_analyzer import TrainingAnalyzer
from backend.analyzers.injury_analyzer import InjuryAnalyzer
from backend.analyzers.nutrition_analyzer import NutritionAnalyzer
from backend.analyzers.load_analyzer import LoadAnalyzer
from backend.analyzers.adaptation_analyzer import AdaptationAnalyzer
from backend.analyzers.performance_analyzer import PerformanceAnalyzer



class CoachEngine:
    """
    Orchestratore principale IronCoach.
    """



    def __init__(self):

        self.recovery_analyzer = RecoveryAnalyzer()

        self.recovery_trend_analyzer = (
            RecoveryTrendAnalyzer()
        )

        self.training_analyzer = TrainingAnalyzer()
        self.injury_analyzer = InjuryAnalyzer()
        self.nutrition_analyzer = NutritionAnalyzer()

        self.load_analyzer = LoadAnalyzer()
        self.adaptation_analyzer = AdaptationAnalyzer()
        self.performance_analyzer = PerformanceAnalyzer()

        self.decision_engine = DecisionEngine()



    # ==================================================
    # HELPERS
    # ==================================================

    def _first_value(
        self,
        data,
        keys,
        default="N/D",
    ):

        for key in keys:

            value = data.get(key)

            if value not in (
                None,
                "",
                [],
            ):
                return value

        return default



    def _build_athlete_intelligence(
        self,
        athlete_profile,
    ):
        """
        Normalizzazione profilo atleta
        per Intelligence Report.
        """

        athlete_profile = athlete_profile or {}


        return {

            "athlete_type":
                self._first_value(
                    athlete_profile,
                    [
                        "Tipo atleta",
                        "Livello atleta",
                        "athlete_type",
                    ],
                ),


            "strengths":
                self._first_value(
                    athlete_profile,
                    [
                        "Punti di forza",
                        "Note coach",
                        "strengths",
                    ],
                ),


            "limitations":
                self._first_value(
                    athlete_profile,
                    [
                        "Limitazioni note",
                        "Limitazioni fisiche",
                        "limitations",
                    ],
                ),


            "training_preferences":
                self._first_value(
                    athlete_profile,
                    [
                        "Preferenza",
                        "Preferenze allenamento",
                        "Disponibilità allenamento",
                        "training_preferences",
                    ],
                ),


            "training_distribution":
                self._first_value(
                    athlete_profile,
                    [
                        "Allenamento distribuito tra",
                        "training_distribution",
                    ],
                ),


            "load_tolerance":
                self._first_value(
                    athlete_profile,
                    [
                        "Tolleranza al carico",
                        "Disponibilità allenamento",
                        "load_tolerance",
                    ],
                ),


            "injury_patterns":
                self._first_value(
                    athlete_profile,
                    [
                        "Pattern infortuni",
                        "Storico infortuni",
                        "injury_patterns",
                    ],
                ),


            "sport_profile":
                self._first_value(
                    athlete_profile,
                    [
                        "Sport principale",
                        "sport_profile",
                    ],
                ),


            "experience_years":
                self._first_value(
                    athlete_profile,
                    [
                        "Anni di attività sportiva",
                        "experience_years",
                    ],
                ),


            "vo2max_run":
                self._first_value(
                    athlete_profile,
                    [
                        "Vo₂max corsa",
                        "VO₂max corsa",
                        "VO2max corsa",
                        "vo2max_run",
                    ],
                ),


            "vo2max_bike":
                self._first_value(
                    athlete_profile,
                    [
                        "Vo₂max bici",
                        "VO₂max bici",
                        "VO2max bici",
                        "vo2max_bike",
                    ],
                ),
        }



    # ==================================================
    # EVALUATION
    # ==================================================

    def evaluate(
        self,
        context,
    ):

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


        athlete_profile = (
            context.get("athlete_profile")
            or context.get("athlete")
            or {}
        )


        training_history = context.get(
            "training_history",
            [],
        ) or []


        recovery_history = context.get(
            "recovery_history",
            [],
        ) or []


        performance_history = context.get(
            "performance_history",
            [],
        ) or []



        recovery_assessment = (
            self.recovery_analyzer.analyze(
                recovery
            )
        )


        recovery_trend_analysis = (
            self.recovery_trend_analyzer.analyze(
                {
                    "recovery_history":
                        recovery_history,
                }
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


        load_analysis = (
            self.load_analyzer.analyze(
                {
                    "training_history":
                        training_history,
                }
            )
        )


        adaptation_analysis = (
            self.adaptation_analyzer.analyze(
                {
                    "athlete_profile":
                        athlete_profile,

                    "load_analysis":
                        load_analysis,
                }
            )
        )


        performance_analysis = (
            self.performance_analyzer.analyze(
                {
                    "performance_history":
                        performance_history,
                }
            )
        )



        assessments = {

            "recovery":
                recovery_assessment,

            "recovery_trend":
                recovery_trend_analysis,

            "training":
                training_assessment,

            "injury":
                injury_assessment,

            "nutrition":
                nutrition_assessment,

            "load":
                load_analysis,

            "adaptation":
                adaptation_analysis,

            "performance":
                performance_analysis,
        }



        decision = self.decision_engine.decide(
            assessments
        )



        decision["intelligence"] = {

            "athlete_profile":
                self._build_athlete_intelligence(
                    athlete_profile
                ),


            "load":
                load_analysis,


            "adaptation":
                adaptation_analysis,


            "recovery_trend":
                recovery_trend_analysis,


            "performance":
                performance_analysis,
        }



        return decision