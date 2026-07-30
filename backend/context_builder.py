"""
IronCoach - Context Builder

Costruisce il contesto completo dell'atleta
leggendo dati da Airtable e preparando
gli storici per gli analyzer.
"""


from backend.history.training_history import TrainingHistory
from backend.history.recovery_history import RecoveryHistory
from backend.history.performance_history import PerformanceHistory



class ContextBuilder:


    def __init__(self, airtable_client):

        self.client = airtable_client



    def build(self):


        athlete = self.client.get_athlete_profile()

        recovery = self.client.get_latest_recovery()

        training = self.client.get_latest_training()

        nutrition = self.client.get_latest_nutrition()

        decision = self.client.get_latest_decision()



        training_history = TrainingHistory()

        recovery_history = RecoveryHistory()

        performance_history = PerformanceHistory()



        # -----------------------------------------
        # TRAINING HISTORY
        # -----------------------------------------

        try:

            sessions = self.client.get_training_history()

            for session in sessions:

                training_history.add_session(session)


        except Exception:

            pass



        # -----------------------------------------
        # RECOVERY HISTORY
        # -----------------------------------------

        try:

            records = self.client.get_recovery_history()

            for record in records:

                recovery_history.add_record(record)


        except Exception:

            pass



        # -----------------------------------------
        # PERFORMANCE HISTORY
        # -----------------------------------------

        try:

            metrics = self.client.get_performance_history()

            for metric in metrics:

                performance_history.add_record(metric)


        except Exception:

            pass



        return {


            "athlete": athlete,

            "recovery": recovery,

            "training": training,

            "nutrition": nutrition,

            "decision": decision,


            # dati grezzi per analyzer
            "training_history":
                training_history.sessions
                if hasattr(training_history, "sessions")
                else [],


            "recovery_history":
                recovery_history.records
                if hasattr(recovery_history, "records")
                else [],


            "performance_history":
                performance_history.records
                if hasattr(performance_history, "records")
                else [],



            "history": {

                "training":
                    training_history,

                "recovery":
                    recovery_history,

                "performance":
                    performance_history

            }

        }