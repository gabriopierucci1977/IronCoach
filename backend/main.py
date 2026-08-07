"""
IronCoach

Programma principale.
"""

from backend.airtable_client import AirtableClient
from backend.coach_engine import CoachEngine
from backend.config import get_runtime_config
from backend.context_builder import ContextBuilder
from backend.decision_writer import DecisionWriter
from backend.report_builder import ReportBuilder
from backend.workout_adapter import WorkoutAdapter


def main():
    print("\n")
    print("=" * 60)
    print("IRONCOACH BETA 0.2")
    print("=" * 60)

    # 1. Configurazione runtime
    runtime_config = get_runtime_config()

    # 2. Connessione ad Airtable
    client = AirtableClient()

    # 3. Costruzione del contesto
    #
    # Il contesto contiene anche l'ultima decisione
    # già presente in Airtable prima della nuova valutazione.
    builder = ContextBuilder(
        client,
        runtime_config=runtime_config,
    )
    context = builder.build()

    # 4. Valutazione Coach Engine
    coach = CoachEngine()
    decision = coach.evaluate(context)

    # 5. Generazione dell'allenamento modificato
    adapter = WorkoutAdapter()

    decision["modified_workout"] = adapter.adapt(
        context=context,
        decision=decision,
    )

    # 6. Costruzione del report
    #
    # Il report viene creato prima del salvataggio della nuova
    # decisione. In questo modo:
    #
    # - ULTIMA DECISIONE mostra la decisione precedente;
    # - DECISIONE DEL COACH mostra la nuova decisione.
    report = ReportBuilder().build(
        context,
        decision,
    )

    # 7. Salvataggio della nuova decisione
    writer = DecisionWriter(client)
    writer.save(decision)

    # 8. Visualizzazione del report
    print("\n")
    print(report)


if __name__ == "__main__":
    main()