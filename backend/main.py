"""
IronCoach

Programma principale.
"""

from backend.airtable_client import AirtableClient
from backend.context_builder import ContextBuilder
from backend.coach_engine import CoachEngine
from backend.workout_adapter import WorkoutAdapter
from backend.decision_writer import DecisionWriter
from backend.report_builder import ReportBuilder


def main():

    print("\n")
    print("=" * 60)
    print("IRONCOACH BETA 0.2")
    print("=" * 60)

    # 1. Connessione ad Airtable
    client = AirtableClient()

    # 2. Costruzione del contesto
    builder = ContextBuilder(client)
    context = builder.build()

    # 3. Valutazione Coach Engine
    coach = CoachEngine()
    decision = coach.evaluate(context)

    # 4. Generazione dell'allenamento modificato
    adapter = WorkoutAdapter()

    decision["modified_workout"] = adapter.adapt(
        context=context,
        decision=decision,
    )

    # 5. Salvataggio Decisione
    writer = DecisionWriter(client)
    writer.save(decision)

    # 6. Costruzione Report
    report = ReportBuilder().build(
        context,
        decision,
    )

    print("\n")
    print(report)


if __name__ == "__main__":
    main()