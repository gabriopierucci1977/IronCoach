"""
IronCoach Decision Memory Injury Outcome Evaluator.

Valuta la risposta fisica successiva a una decisione
con primary_intent PROTECT_INJURY.

Usa esclusivamente segnali temporali correnti presenti
nello storico training Airtable:

- pain_score;
- current_problem.

Non usa injury history o limitazioni statiche del profilo atleta.

Finestre:
- 24h: giorno +1;
- 72h: giorni +2 / +3;
- 7d: giorni +4 ... +7.

Dati mancanti non vengono interpretati come miglioramento
o peggioramento.
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.analyzers.injury_analyzer import (
    InjuryAnalyzer,
)


class DecisionMemoryInjuryOutcomeEvaluator:
    """
    Valuta l'evoluzione dei segnali fisici correnti
    rispetto alla baseline pre-decisione.
    """

    PRIMARY_INTENT = "PROTECT_INJURY"

    LEVEL_UNKNOWN = "UNKNOWN"

    LEVEL_RANK = {
        "LOW": 0,
        "MODERATE": 1,
        "HIGH": 2,
        "CRITICAL": 3,
    }

    BASELINE_EVALUABLE_LEVELS = {
        "MODERATE",
        "HIGH",
        "CRITICAL",
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
            else InjuryAnalyzer()
        )

    def evaluate(
        self,
        episode,
        training_history,
        as_of=None,
    ):
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

        pre_decision_state = (
            episode.pre_decision_state
            if isinstance(
                episode.pre_decision_state,
                dict,
            )
            else {}
        )

        baseline_training = (
            pre_decision_state.get(
                "training",
                {},
            )
            or {}
        )

        # Importante: non viene passato athlete_profile.
        # In questo modo history e limitazioni statiche
        # non contaminano l'outcome temporale.
        baseline_assessment = (
            self.analyzer.analyze(
                baseline_training
            )
        )

        baseline_level = (
            baseline_assessment.get(
                "level",
                self.LEVEL_UNKNOWN,
            )
        )

        observations = (
            self._prepare_observations(
                training_history
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
            != self.PRIMARY_INTENT
        ):
            evidence["reason"] = (
                "injury_signal_not_valid_for_primary_intent"
            )

            return {
                "status": "INSUFFICIENT_DATA",
                "evidence": evidence,
            }

        if (
            baseline_level
            not in self.BASELINE_EVALUABLE_LEVELS
        ):
            evidence["reason"] = (
                "baseline_current_injury_not_evaluable"
            )

            return {
                "status": "INSUFFICIENT_DATA",
                "evidence": evidence,
            }

        candidates = [
            item
            for item in observations
            if (
                start_day
                <= (
                    item["date"]
                    - decision_date
                ).days
                <= end_day
                and self._has_explicit_injury_observation(
                    item["record"]
                )
            )
        ]

        if not candidates:
            evidence["reason"] = (
                "no_explicit_injury_observation_in_window"
            )

            return {
                "status": "INSUFFICIENT_DATA",
                "evidence": evidence,
            }

        valid = []

        for item in candidates:
            assessment = (
                self.analyzer.analyze(
                    item["record"]
                )
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
                "injury_observations_not_evaluable"
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

    def _prepare_observations(
        self,
        training_history,
    ):
        observations = []

        for record in (
            training_history
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

    @staticmethod
    def _has_explicit_injury_observation(
        record,
    ):
        if not isinstance(
            record,
            dict,
        ):
            return False

        keys = (
            "pain_score",
            "Pain Score",
            "Dolore",
            "current_problem",
            "pain_notes",
            "injury_notes",
            "Dolori/problematiche",
            "dolori_problematiche",
            "Dolori",
        )

        raw = record.get(
            "raw",
            {},
        )

        for data in (
            record,
            raw,
        ):
            if not isinstance(
                data,
                dict,
            ):
                continue

            for key in keys:
                if key not in data:
                    continue

                value = data.get(
                    key
                )

                if value not in (
                    None,
                    "",
                ):
                    return True

        return False

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
