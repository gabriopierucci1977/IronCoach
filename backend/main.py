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
from backend.decision_memory.repository import (
    DecisionMemoryRepository,
)
from backend.decision_memory.viewer import (
    DecisionMemoryViewer,
)
from backend.decision_memory.formatter import (
    DecisionMemoryFormatter,
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

    parser.add_argument(
        "--decision-memory",
        action="store_true",
        help=(
            "Mostra le decisioni recenti della Decision Memory."
        ),
    )

    parser.add_argument(
        "--decision-memory-demo",
        action="store_true",
        help=(
            "Esegue un flusso dimostrativo della Decision Memory."
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


def _run_decision_memory_viewer() -> int:
    runtime_config = _execute_phase(
        "caricamento configurazione Decision Memory",
        get_runtime_config,
    )

    repository = _execute_phase(
        "inizializzazione Decision Memory Repository",
        lambda: DecisionMemoryRepository(
            runtime_config.decision_memory_database_path,
        ),
    )

    viewer = DecisionMemoryViewer(
        repository,
    )

    episodes = viewer.latest()

    formatter = DecisionMemoryFormatter()

    print("\n")

    if not episodes:
        print(
            "=" * 60
        )
        print(
            "IRONCOACH DECISION MEMORY"
        )
        print(
            "=" * 60
        )
        print(
            "Nessuna decisione disponibile."
        )
        print(
            "=" * 60
        )
        return 0

    for episode in episodes:
        print(
            formatter.format(
                episode
            )
        )

    return 0



def _run_decision_memory_demo() -> int:
    runtime_config = _execute_phase(
        "caricamento configurazione Decision Memory",
        get_runtime_config,
    )

    repository = _execute_phase(
        "inizializzazione Decision Memory Repository",
        lambda: DecisionMemoryRepository(
            runtime_config.decision_memory_database_path,
        ),
    )

    from backend.models.decision_episode import (
        DecisionEpisode,
    )

    demo_episode = DecisionEpisode(
        athlete_id="demo-athlete",
        decision_timestamp=_utc_now(),
        decision_action="ADATTA",
        rule_id="DEMO_RULE",
        primary_intent="REDUCE_LOAD",
        pre_decision_state={},
        athlete_state={},
        strategy="ADAPT",
        recommended_workout={
            "sport": "RUN",
            "duration_minutes": 40,
        },
        status="WAITING_FOR_ACTIVITY",
    )

    repository.create(
        demo_episode,
    )

    viewer = DecisionMemoryViewer(
        repository,
    )

    formatter = DecisionMemoryFormatter()

    episodes = viewer.latest()

    print("\n")
    for episode in episodes:
        print(
            formatter.format(
                {
                    "decision_timestamp":
                        episode.get(
                            "decision_timestamp",
                            "",
                        ),
                    "decision_action":
                        episode.get(
                            "decision_action",
                            "",
                        ),
                    "strategy":
                        episode.get(
                            "strategy",
                            "",
                        ),
                    "primary_intent":
                        episode.get(
                            "primary_intent",
                            "",
                        ),
                    "status":
                        episode.get(
                            "status",
                            "",
                        ),
                    "recommended_workout":
                        episode.get(
                            "recommended_workout",
                            {},
                        ),
                }
            )
        )

    return 0


def main(
    argv: Sequence[str] | None = None,
) -> int:
    parser = _build_argument_parser()
    args = parser.parse_args(
        list(argv) if argv is not None else []
    )

    _print_banner()

    if args.decision_memory:
        return _run_decision_memory_viewer()

    if args.decision_memory_demo:
        return _run_decision_memory_demo()

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