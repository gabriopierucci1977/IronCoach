"""
IronCoach Coach Engine v6

Motore di orchestrazione.

Responsabilità:

- ricevere il contesto atleta;
- chiamare gli analyzer dedicati;
- passare gli assessment al DecisionEngine;
- restituire la decisione finale.

La logica di valutazione è contenuta nei moduli:

backend/analyzers/

"""



from backend.engines.decision_engine import DecisionEngine


from backend.analyzers.recovery_analyzer import RecoveryAnalyzer
from backend.analyzers.training_analyzer import TrainingAnalyzer
from backend.analyzers.injury_analyzer import InjuryAnalyzer
from backend.analyzers.nutrition_analyzer import NutritionAnalyzer




class CoachEngine:


    """
    Orchestratore principale IronCoach.

    Non contiene logica decisionale.
    """


    def __init__(self):


        self.recovery_analyzer = RecoveryAnalyzer()

        self.training_analyzer = TrainingAnalyzer()

        self.injury_analyzer = InjuryAnalyzer()

        self.nutrition_analyzer = NutritionAnalyzer()


        self.decision_engine = DecisionEngine()




    def evaluate(
        self,
        context,
    ):

        """
        Valuta il contesto completo atleta.

        Input:

            {
                "recovery": {},
                "training": {},
                "nutrition": {}
            }


        Output:

            decision generata dal DecisionEngine
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
