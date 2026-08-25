"""
IronCoach

Programma principale.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from copy import deepcopy
from datetime import datetime, timezone
from typing import Callable, TypeVar

from backend.airtable_client import AirtableClient
from backend.coach_engine import CoachEngine
from backend.config import get_runtime_config
from backend.context_builder import ContextBuilder
from backend.decision_memory.factory import (
    create_decision_memory_orchestrator,
)
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


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.main",
        description=(
            "Esegue la pipeline IronCoach. "
            "La modalità dry-run produce il report "
            "senza salvare la decisione su Airtable "
            "o nella Decision Memory."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Esegue l'intera pipeline senza inizializzare "
            "i componenti di persistenza e senza salvare "
            "la decisione."
        ),
    )

    return parser


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


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat().replace(
        "+00:00",
        "Z",
    )


def _decision_memory_identity(
    context,
    decision,
):
    athlete = (
        context.get(
            "athlete",
            {},
        )
        or context.get(
            "athlete_profile",
            {},
        )
        or {}
    )

    athlete_id = athlete.get(
        "source_id"
    )

    decision_id = decision.get(
        "decision_id"
    )
    rule_id = decision.get(
        "rule_id"
    )
    primary_intent = decision.get(
        "primary_intent"
    )
    decision_action = decision.get(
        "decision"
    )

    if not all(
        (
            athlete_id,
            decision_id,
            rule_id,
            primary_intent,
            decision_action,
        )
    ):
        return None

    return {
        "athlete": athlete,
        "athlete_id": athlete_id,
        "decision_id": decision_id,
        "rule_id": rule_id,
        "primary_intent": primary_intent,
        "decision_action": decision_action,
    }


def _build_pre_decision_state(
    context,
    decision,
):
    return {
        "recovery": deepcopy(
            context.get(
                "recovery",
                {},
            )
            or {}
        ),
        "training": deepcopy(
            context.get(
                "training",
                {},
            )
            or {}
        ),
        "nutrition": deepcopy(
            context.get(
                "nutrition",
                {},
            )
            or {}
        ),
        "data_freshness": deepcopy(
            context.get(
                "data_freshness",
                {},
            )
            or {}
        ),
        "intelligence": deepcopy(
            decision.get(
                "intelligence",
                {},
            )
            or {}
        ),
        "context_warnings": deepcopy(
            context.get(
                "context_warnings",
                [],
            )
            or []
        ),
    }


def _save_decision_memory(
    runtime_config,
    context,
    decision,
    airtable_record,
) -> None:
    orchestrator = (
        create_decision_memory_orchestrator(
            runtime_config,
        )
    )

    orchestrator.save_decision(
        context=context,
        decision=decision,
        airtable_record=airtable_record,
    )


def _print_banner() -> None:
    print("\n")
    print("=" * 60)
    print(f"{APP_NAME} {APP_VERSION}")
    print("=" * 60)


def _print_dry_run_notice() -> None:
    print("\n")
    print("=" * 60)
    print("🧪 DRY RUN — DECISIONE NON SALVATA")
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


def run_pipeline(
    *,
    dry_run: bool = False,
) -> str:
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
        lambda: CoachEngine(
            runtime_config=runtime_config,
        ),
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

    if not dry_run:
        writer = _execute_phase(
            "inizializzazione Decision Writer",
            lambda: DecisionWriter(client),
        )

        airtable_record = _execute_phase(
            "salvataggio decisione",
            lambda: writer.save(decision),
        )

        _execute_phase(
            "salvataggio Decision Memory",
            lambda: _save_decision_memory(
                runtime_config=runtime_config,
                context=context,
                decision=decision,
                airtable_record=airtable_record,
            ),
        )

    return report


def main(
    argv: Sequence[str] | None = None,
) -> int:
    parser = _build_argument_parser()
    args = parser.parse_args(
        list(argv) if argv is not None else []
    )

    _print_banner()

    try:
        if args.dry_run:
            report = run_pipeline(
                dry_run=True,
            )
        else:
            report = run_pipeline()
    except IronCoachExecutionError as exc:
        _print_error(exc)
        return 1

    if args.dry_run:
        _print_dry_run_notice()

    print("\n")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(
        main(sys.argv[1:])
    )