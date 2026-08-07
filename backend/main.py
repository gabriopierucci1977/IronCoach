"""
IronCoach

Programma principale.
"""

from __future__ import annotations

from typing import Callable, TypeVar

from backend.airtable_client import AirtableClient
from backend.coach_engine import CoachEngine
from backend.config import get_runtime_config
from backend.context_builder import ContextBuilder
from backend.decision_writer import DecisionWriter
from backend.report_builder import ReportBuilder
from backend.workout_adapter import WorkoutAdapter


APP_NAME = "IRONCOACH"
APP_VERSION = "BETA 0.3"

T = TypeVar("T")


class IronCoachExecutionError(RuntimeError):
    """
    Errore controllato di esecuzione della pipeline.
    """

    def __init__(
        self,
        phase: str,
        original_error: Exception,
    ) -> None:
        self.phase = phase
        self.original_error = original_error

        super().__init__(
            f"{phase}: "
            f"{type(original_error).__name__}: "
            f"{original_error}"
        )


def _execute_phase(
    phase: str,
    operation: Callable[[], T],
) -> T:
    try:
        return operation()
    except Exception as exc:
        raise IronCoachExecutionError(
            phase=phase,
            original_error=exc,
        ) from exc


def _print_banner() -> None:
    print("\n")
    print("=" * 60)
    print(f"{APP_NAME} {APP_VERSION}")
    print("=" * 60)


def _print_error(
    error: IronCoachExecutionError,
) -> None:
    print("\n")
    print("=" * 60)
    print("❌ IRONCOACH NON COMPLETATO")
    print("=" * 60)
    print(f"Fase: {error.phase}")
    print(
        "Errore: "
        f"{type(error.original_error).__name__}: "
        f"{error.original_error}"
    )
    print(
        "La decisione non è stata completata. "
        "Correggere il problema e ripetere l'esecuzione."
    )
    print("=" * 60)


def run_pipeline() -> str:
    runtime_config = _execute_phase(
        "caricamento configurazione runtime",
        get_runtime_config,
    )

    client = _execute_phase(
        "connessione ad Airtable",
        AirtableClient,
    )

    builder = _execute_phase(
        "inizializzazione Context Builder",
        lambda: ContextBuilder(
            client,
            runtime_config=runtime_config,
        ),
    )

    context = _execute_phase(
        "costruzione contesto atleta",
        builder.build,
    )

    coach = _execute_phase(
        "inizializzazione Coach Engine",
        CoachEngine,
    )

    decision = _execute_phase(
        "valutazione Coach Engine",
        lambda: coach.evaluate(context),
    )

    adapter = _execute_phase(
        "inizializzazione Workout Adapter",
        WorkoutAdapter,
    )

    decision["modified_workout"] = _execute_phase(
        "adattamento allenamento",
        lambda: adapter.adapt(
            context=context,
            decision=decision,
        ),
    )

    report_builder = _execute_phase(
        "inizializzazione Report Builder",
        ReportBuilder,
    )

    report = _execute_phase(
        "costruzione report",
        lambda: report_builder.build(
            context,
            decision,
        ),
    )

    writer = _execute_phase(
        "inizializzazione Decision Writer",
        lambda: DecisionWriter(client),
    )

    _execute_phase(
        "salvataggio decisione",
        lambda: writer.save(decision),
    )

    return report


def main() -> int:
    _print_banner()

    try:
        report = run_pipeline()
    except IronCoachExecutionError as exc:
        _print_error(exc)
        return 1

    print("\n")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())