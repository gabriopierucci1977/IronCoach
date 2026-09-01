"""
IronCoach Decision Memory Outcome Runtime.

Coordina le fasi successive al collegamento dell'attività reale:

1. valutazione aderenza;
2. valutazione outcome intent-specific;
3. chiusura COMPLETE / INCOMPLETE.

Aderenza e outcome restano concetti separati.
"""

from __future__ import annotations

from backend.decision_memory.injury_outcome_processor import (
    DecisionMemoryInjuryOutcomeProcessor,
)
from backend.decision_memory.outcome_processor import (
    DecisionMemoryOutcomeProcessor,
)
from backend.decision_memory.recovery_outcome_processor import (
    DecisionMemoryRecoveryOutcomeProcessor,
)


class DecisionMemoryOutcomeRuntime:
    """
    Runtime per processare episodi WAITING_FOR_OUTCOME.
    """

    def __init__(
        self,
        repository,
        processor=None,
        processor_class=DecisionMemoryOutcomeProcessor,
        recovery_processor=None,
        recovery_processor_class=(
            DecisionMemoryRecoveryOutcomeProcessor
        ),
        injury_processor=None,
        injury_processor_class=(
            DecisionMemoryInjuryOutcomeProcessor
        ),
    ):
        self.repository = repository

        self.processor = (
            processor
            if processor is not None
            else processor_class(
                repository
            )
        )

        self.recovery_processor = (
            recovery_processor
            if recovery_processor is not None
            else recovery_processor_class(
                repository
            )
        )

        self.injury_processor = (
            injury_processor
            if injury_processor is not None
            else injury_processor_class(
                repository
            )
        )

    def evaluate_outcome(
        self,
        episode_id,
    ):
        """
        Valuta l'aderenza di un singolo episodio.

        Usato dal percorso CLI/manuale.
        Non inventa episodi se l'ID non esiste.
        """
        episode = (
            self.repository
            .get_by_episode_id(
                episode_id
            )
        )

        if episode is None:
            return None

        return self.processor.process(
            episode
        )

    def process_outcomes(
        self,
        athlete_id,
        recovery_history=None,
        airtable_training_history=None,
        as_of=None,
    ):
        """
        Processa il ciclo outcome di un atleta.

        Prima completa l'aderenza ancora pendente.

        Poi instrada ogni episodio verso il segnale
        valido per il suo primary_intent:

        - PROTECT_INJURY -> training history Airtable;
        - altri intenti attualmente supportati ->
          recovery history.

        Una sorgente None indica indisponibilità tecnica
        e non viene interpretata come assenza di segnale.
        """
        processed = {}

        adherence_episodes = (
            self.repository
            .list_pending_outcomes(
                athlete_id
            )
        )

        for episode in adherence_episodes:
            result = self.processor.process(
                episode
            )

            self._remember_result(
                processed,
                result,
            )

        if (
            recovery_history is None
            and airtable_training_history is None
        ):
            return list(
                processed.values()
            )

        outcome_episodes = (
            self.repository
            .list_waiting_for_outcome_by_athlete(
                athlete_id
            )
        )

        for episode in outcome_episodes:
            if (
                episode.primary_intent
                == "PROTECT_INJURY"
            ):
                if airtable_training_history is None:
                    continue

                result = (
                    self.injury_processor
                    .process(
                        episode=episode,
                        training_history=(
                            airtable_training_history
                        ),
                        as_of=as_of,
                    )
                )

            else:
                if recovery_history is None:
                    continue

                result = (
                    self.recovery_processor
                    .process(
                        episode=episode,
                        recovery_history=(
                            recovery_history
                        ),
                        as_of=as_of,
                    )
                )

            self._remember_result(
                processed,
                result,
            )

        return list(
            processed.values()
        )

    @staticmethod
    def _remember_result(
        processed,
        result,
    ):
        if result is None:
            return

        episode_id = getattr(
            result,
            "episode_id",
            None,
        )

        key = (
            episode_id
            if episode_id is not None
            else str(result)
        )

        processed[key] = result
