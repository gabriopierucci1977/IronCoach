"""
IronCoach Context Builder v2

Costruisce il contesto completo atleta.

Responsabilità:

- recuperare dati dalle sorgenti;
- normalizzare i dati;
- costruire il modello IronCoach;
- preparare gli storici per gli analyzer.
"""


from backend.history.training_history import TrainingHistory
from backend.history.recovery_history import RecoveryHistory
from backend.history.performance_history import PerformanceHistory


from backend.normalization.activity_normalizer import (
    ActivityNormalizer,
)

from backend.normalization.recovery_normalizer import (
    RecoveryNormalizer,
)

from backend.normalization.athlete_normalizer import (
    AthleteNormalizer,
)



class ContextBuilder:



    def __init__(
        self,
        airtable_client,
    ):

        self.client = airtable_client


        self.activity_normalizer = (
            ActivityNormalizer()
        )


        self.recovery_normalizer = (
            RecoveryNormalizer()
        )


        self.athlete_normalizer = (
            AthleteNormalizer()
        )



    def build(self):


        # ==================================================
        # RAW DATA
        # ==================================================


        raw_athlete = (
            self.client.get_athlete_profile()
        )


        raw_recovery = (
            self.client.get_latest_recovery()
        )


        raw_training = (
            self.client.get_latest_training()
        )


        nutrition = (
            self.client.get_latest_nutrition()
        )


        decision = (
            self.client.get_latest_decision()
        )



        # ==================================================
        # NORMALIZATION
        # ==================================================


        athlete = (
            self.athlete_normalizer.normalize(
                raw_athlete,
                source="airtable",
            )
        )


        recovery = (
            self.recovery_normalizer.normalize(
                raw_recovery,
                source="airtable",
            )
        )


        training = (
            self.activity_normalizer.normalize(
                raw_training,
                source="airtable",
            )
        )



        # ==================================================
        # HISTORY
        # ==================================================


        training_history = TrainingHistory()

        recovery_history = RecoveryHistory()

        performance_history = PerformanceHistory()



        # --------------------------------------------------
        # TRAINING HISTORY
        # --------------------------------------------------


        try:

            sessions = (
                self.client.get_training_history()
            )


            for session in sessions:


                normalized = (
                    self.activity_normalizer.normalize(
                        session,
                        source="airtable",
                    )
                )


                training_history.add_session(
                    normalized
                )


        except Exception:

            pass



        # --------------------------------------------------
        # RECOVERY HISTORY
        # --------------------------------------------------


        try:

            records = (
                self.client.get_recovery_history()
            )


            for record in records:


                normalized = (
                    self.recovery_normalizer.normalize(
                        record,
                        source="airtable",
                    )
                )


                recovery_history.add_record(
                    normalized
                )


        except Exception:

            pass



        # --------------------------------------------------
        # PERFORMANCE HISTORY
        # --------------------------------------------------


        try:

            metrics = (
                self.client.get_performance_history()
            )


            for metric in metrics:

                performance_history.add_record(
                    metric
                )


        except Exception:

            pass



        # ==================================================
        # FINAL IRONCOACH CONTEXT
        # ==================================================


        return {


            "athlete":
                athlete,


            "athlete_profile":
                athlete,


            "recovery":
                recovery,


            "training":
                training,


            "nutrition":
                nutrition,


            "decision":
                decision,



            "training_history":
                training_history.sessions
                if hasattr(
                    training_history,
                    "sessions",
                )
                else [],



            "recovery_history":
                recovery_history.records
                if hasattr(
                    recovery_history,
                    "records",
                )
                else [],



            "performance_history":
                performance_history.records
                if hasattr(
                    performance_history,
                    "records",
                )
                else [],



            "history":

                {

                    "training":
                        training_history,


                    "recovery":
                        recovery_history,


                    "performance":
                        performance_history,

                }

        }