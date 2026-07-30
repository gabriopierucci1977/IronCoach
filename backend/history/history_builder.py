"""
IronCoach History Builder v0.1

Costruisce gli oggetti storico atleta.

Responsabilità:

- ricevere dati grezzi normalizzati;
- trasformarli in strutture History;
- preparare il sistema per future integrazioni:

    - Garmin Connect
    - Strava
    - altre sorgenti

Non esegue analisi.
"""


from backend.history.training_history import TrainingHistory
from backend.history.recovery_history import RecoveryHistory
from backend.history.performance_history import PerformanceHistory



class HistoryBuilder:



    def build(
        self,
        data=None,
    ):


        data = data or {}



        training_history = TrainingHistory(
            data.get(
                "training_history",
                []
            )
        )


        recovery_history = RecoveryHistory(
            data.get(
                "recovery_history",
                []
            )
        )


        performance_history = PerformanceHistory(
            data.get(
                "performance_history",
                []
            )
        )



        return {


            "training_history":
                training_history,


            "recovery_history":
                recovery_history,


            "performance_history":
                performance_history,


        }