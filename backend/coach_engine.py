"""
IronCoach Coach Engine v6.1

Motore di orchestrazione.

Responsabilità:

- ricevere il contesto atleta;
- chiamare gli analyzer;
- arricchire il contesto con informazioni intelligence;
- passare gli assessment al DecisionEngine.

La logica decisionale rimane nel DecisionEngine.
"""


from backend.engines.decision_engine import DecisionEngine


from backend.analyzers.recovery_analyzer import RecoveryAnalyzer
from backend.analyzers.training_analyzer import TrainingAnalyzer
from backend.analyzers.injury_analyzer import InjuryAnalyzer
from backend.analyzers.nutrition_analyzer import NutritionAnalyzer
from backend.analyzers.load_analyzer import LoadAnalyzer
from backend.analyzers.adaptation_analyzer import AdaptationAnalyzer




class CoachEngine:


    def __init__(self):

        self.recovery_analyzer = RecoveryAnalyzer()

        self.training_analyzer = TrainingAnalyzer()

        self.injury_analyzer = InjuryAnalyzer()

        self.nutrition_analyzer = NutritionAnalyzer()


        self.load_analyzer = LoadAnalyzer()

        self.adaptation_analyzer = AdaptationAnalyzer()


        self.decision_engine = DecisionEngine()



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



        athlete_profile = context.get(
            "athlete_profile",
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



        #
        # Intelligence layer
        #


        load_analysis = (
            self.load_analyzer.analyze(
                {
                    "training_history":
                        context.get(
                            "training_history",
                            []
                        )
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



        assessments = {


            "recovery":
                recovery_assessment,


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


        }



        return self.decision_engine.decide(
            assessments
        )