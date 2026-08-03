"""
IronCoach Report Preview

Esegue la pipeline di valutazione e costruisce il report
senza salvare la nuova decisione.

Questo modulo:
- può creare un AirtableClient oppure riceverne uno esistente;
- costruisce il contesto;
- esegue CoachEngine;
- applica WorkoutAdapter;
- costruisce il report;
- non importa componenti di persistenza;
- non esegue scritture.
"""

from backend.airtable_client import AirtableClient
from backend.context_builder import ContextBuilder
from backend.coach_engine import CoachEngine
from backend.workout_adapter import WorkoutAdapter
from backend.report_builder import ReportBuilder


def generate_report_preview(
    client=None,
):
    """
    Costruisce e restituisce il report senza persistere la decisione.

    Args:
        client:
            Client Airtable opzionale. Quando assente viene creato
            un AirtableClient standard.

    Returns:
        str: report completo prodotto da ReportBuilder.
    """

    active_client = (
        client
        if client is not None
        else AirtableClient()
    )

    context = ContextBuilder(
        active_client
    ).build()

    decision = CoachEngine().evaluate(
        context
    )

    decision[
        "modified_workout"
    ] = WorkoutAdapter().adapt(
        context=context,
        decision=decision,
    )

    return ReportBuilder().build(
        context,
        decision,
    )


def main():
    print(
        generate_report_preview()
    )


if __name__ == "__main__":
    main()