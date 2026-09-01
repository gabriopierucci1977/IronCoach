"""
IronCoach Decision Memory Recovery Outcome Evaluator.

Valuta la risposta recovery successiva a una decisione
usando le stesse categorie del RecoveryAnalyzer.

Non valuta:
- aderenza;
- performance;
- nutrizione;
- injury outcome.

Le finestre usano granularità giornaliera:
- 24h: giorno +1;
- 72h: giorni +2 / +3;
- 7d: giorni +4 ... +7.

Una finestra non ancora maturata resta senza status.
Una finestra maturata senza dati validi produce
INSUFFICIENT_DATA.
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.analyzers.recovery_analyzer import (
    RecoveryAnalyzer,
)


class DecisionMemoryRecoveryOutcomeEvaluator:
    """
    Valuta l'evoluzione del recovery rispetto
    alla baseline pre-decisione.
    """

    SUPPORTED_PRIMARY_INTENTS = {
        "RESTORE_RECOVERY",
        "REDUCE_LOAD",
    }

    UNCERTAINTY_PRIMARY_INTENT = (
        "MANAGE_UNCERTAINTY"
    )

    LEVEL_UNKNOWN = "UNKNOWN"

    LEVEL_RANK = {
        "LOW": 0,
        "MODERATE": 1,
        "HIGH": 2,
        "CRITICAL": 3,
    }

    WINDOWS = {
        "24h": (1, 1),
        "72h": (2, 3),
        "7d": (4, 7),
    }

    def __init__(
        self,
        analyzer=None,
    ):
        self.analyzer = (
            analyzer
            if analyzer is not None
            else RecoveryAnalyzer()
        )

    def evaluate(
        self,
        episode,
        recovery_history,
        as_of=None,
    ):
        """
        Restituisce la valutazione delle tre finestre.

        Non modifica il DecisionEpisode.
        """
        decision_time = self._parse_datetime(
            episode.decision_timestamp
        )

        as_of_time = (
            self._parse_datetime(
                as_of
            )
            if as_of is not None
            else datetime.now(
                timezone.utc
            )
        )

        if (
            decision_time is None
            or as_of_time is None
        ):
            return self._all_insufficient(
                reason="invalid_timestamp"
            )

        baseline_recovery = (
            episode.pre_decision_state.get(
                "recovery",
                {},
            )
            if isinstance(
                episode.pre_decision_state,
                dict,
            )
            else {}
        )

        baseline_assessment = (
            self.analyzer.analyze(
                baseline_recovery
            )
        )

        baseline_level = (
            baseline_assessment.get(
                "level",
                "UNKNOWN",
            )
        )

        observations = (
            self._prepare_observations(
                recovery_history
            )
        )

        result = {}

        for (
            window_name,
            (
                start_day,
                end_day,
            ),
        ) in self.WINDOWS.items():
            result[
                window_name
            ] = self._evaluate_window(
                episode=episode,
                decision_time=decision_time,
                as_of_time=as_of_time,
                baseline_level=baseline_level,
                observations=observations,
                window_name=window_name,
                start_day=start_day,
                end_day=end_day,
            )

        if (
            episode.primary_intent
            == self.UNCERTAINTY_PRIMARY_INTENT
        ):
            result["overall"] = (
                self._evaluate_uncertainty_overall(
                    result
                )
            )

        return result

    def _evaluate_window(
        self,
        episode,
        decision_time,
        as_of_time,
        baseline_level,
        observations,
        window_name,
        start_day,
        end_day,
    ):
        decision_date = (
            decision_time.date()
        )

        as_of_date = (
            as_of_time.date()
        )

        age_days = (
            as_of_date
            - decision_date
        ).days

        evidence = {
            "window": window_name,
            "start_day": start_day,
            "end_day": end_day,
            "baseline_level": baseline_level,
            "primary_intent": (
                episode.primary_intent
            ),
        }

        if age_days < end_day:
            evidence["mature"] = False

            return {
                "status": None,
                "evidence": evidence,
            }

        evidence["mature"] = True

        if (
            episode.primary_intent
            == self.UNCERTAINTY_PRIMARY_INTENT
        ):
            return self._evaluate_uncertainty_window(
                baseline_level=baseline_level,
                observations=observations,
                decision_date=decision_date,
                start_day=start_day,
                end_day=end_day,
                evidence=evidence,
            )

        if (
            episode.primary_intent
            not in self.SUPPORTED_PRIMARY_INTENTS
        ):
            evidence["reason"] = (
                "recovery_signal_not_valid_for_primary_intent"
            )

            return {
                "status": "INSUFFICIENT_DATA",
                "evidence": evidence,
            }

        if (
            baseline_level
            not in self.LEVEL_RANK
        ):
            evidence["reason"] = (
                "baseline_recovery_unknown"
            )

            return {
                "status": "INSUFFICIENT_DATA",
                "evidence": evidence,
            }

        candidates = [
            item
            for item in observations
            if start_day
            <= (
                item["date"]
                - decision_date
            ).days
            <= end_day
        ]

        if not candidates:
            evidence["reason"] = (
                "no_recovery_observation_in_window"
            )

            return {
                "status": "INSUFFICIENT_DATA",
                "evidence": evidence,
            }

        observation = max(
            candidates,
            key=lambda item: item[
                "date"
            ],
        )

        post_assessment = (
            self.analyzer.analyze(
                observation["record"]
            )
        )

        post_level = (
            post_assessment.get(
                "level",
                "UNKNOWN",
            )
        )

        evidence[
            "observation_date"
        ] = observation[
            "date"
        ].isoformat()

        evidence[
            "post_level"
        ] = post_level

        if post_level not in self.LEVEL_RANK:
            evidence["reason"] = (
                "post_recovery_unknown"
            )

            return {
                "status": "INSUFFICIENT_DATA",
                "evidence": evidence,
            }

        baseline_rank = (
            self.LEVEL_RANK[
                baseline_level
            ]
        )

        post_rank = (
            self.LEVEL_RANK[
                post_level
            ]
        )

        if post_rank < baseline_rank:
            status = "POSITIVE"

        elif post_rank > baseline_rank:
            status = "NEGATIVE"

        else:
            status = "NEUTRAL"

        return {
            "status": status,
            "evidence": evidence,
        }

    def _evaluate_uncertainty_window(
        self,
        baseline_level,
        observations,
        decision_date,
        start_day,
        end_day,
        evidence,
    ):
        if baseline_level != self.LEVEL_UNKNOWN:
            evidence["reason"] = (
                "baseline_recovery_not_uncertain"
            )

            return {
                "status": "INSUFFICIENT_DATA",
                "evidence": evidence,
            }

        candidates = [
            item
            for item in observations
            if start_day
            <= (
                item["date"]
                - decision_date
            ).days
            <= end_day
        ]

        if not candidates:
            evidence["reason"] = (
                "no_recovery_observation_in_window"
            )

            return {
                "status": "INSUFFICIENT_DATA",
                "evidence": evidence,
            }

        valid = []

        for item in candidates:
            assessment = self.analyzer.analyze(
                item["record"]
            )

            level = assessment.get(
                "level",
                self.LEVEL_UNKNOWN,
            )

            if level in self.LEVEL_RANK:
                valid.append(
                    (
                        item,
                        level,
                    )
                )

        if not valid:
            evidence["reason"] = (
                "recovery_observations_remain_unknown"
            )

            return {
                "status": "INSUFFICIENT_DATA",
                "evidence": evidence,
            }

        observation, post_level = max(
            valid,
            key=lambda item: item[0][
                "date"
            ],
        )

        evidence[
            "observation_date"
        ] = observation[
            "date"
        ].isoformat()

        evidence[
            "post_level"
        ] = post_level

        evidence["reason"] = (
            "recovery_data_became_evaluable"
        )

        return {
            "status": "POSITIVE",
            "evidence": evidence,
        }

    @staticmethod
    def _evaluate_uncertainty_overall(
        result,
    ):
        window_statuses = {
            window_name: (
                result.get(
                    window_name,
                    {},
                ).get(
                    "status"
                )
            )
            for window_name in (
                "24h",
                "72h",
                "7d",
            )
        }

        if window_statuses.get(
            "7d"
        ) is None:
            return {
                "status": None,
                "evidence": {
                    "mature": False,
                    "window_statuses": (
                        window_statuses
                    ),
                },
            }

        if "POSITIVE" in window_statuses.values():
            status = "POSITIVE"
            reason = (
                "uncertainty_reduced_in_at_least_one_window"
            )

        else:
            status = "INSUFFICIENT_DATA"
            reason = (
                "no_evaluable_recovery_data_in_outcome_windows"
            )

        return {
            "status": status,
            "evidence": {
                "mature": True,
                "reason": reason,
                "window_statuses": (
                    window_statuses
                ),
            },
        }

    def _prepare_observations(
        self,
        recovery_history,
    ):
        observations = []

        for record in (
            recovery_history
            or []
        ):
            if not isinstance(
                record,
                dict,
            ):
                continue

            parsed = self._parse_datetime(
                record.get(
                    "date"
                )
            )

            if parsed is None:
                continue

            observations.append(
                {
                    "date": parsed.date(),
                    "record": record,
                }
            )

        return observations

    def _all_insufficient(
        self,
        reason,
    ):
        return {
            window_name: {
                "status": "INSUFFICIENT_DATA",
                "evidence": {
                    "window": window_name,
                    "reason": reason,
                    "mature": True,
                },
            }
            for window_name
            in self.WINDOWS
        }

    @staticmethod
    def _parse_datetime(
        value,
    ):
        if isinstance(
            value,
            datetime,
        ):
            parsed = value

        elif value:
            try:
                parsed = datetime.fromisoformat(
                    str(value).replace(
                        "Z",
                        "+00:00",
                    )
                )
            except ValueError:
                return None

        else:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed
