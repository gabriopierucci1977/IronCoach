"""
IronCoach Adaptation Analyzer v0.2

Valuta la capacità dell'atleta di adattarsi al carico allenante.

Combina:
- profilo atleta e limitazioni note;
- analisi del carico recente;
- rapporto acuto/cronico;
- trend prestativo;
- recupero, quando disponibile.

Non decide il piano.
Fornisce informazioni utili al sistema decisionale.
"""

from __future__ import annotations

from typing import Any, List, Optional


class AdaptationAnalyzer:

    LEVEL_UNKNOWN = "UNKNOWN"
    LEVEL_GOOD = "GOOD"
    LEVEL_MODERATE = "MODERATE"
    LEVEL_LIMITED = "LIMITED"

    HIGH_ACUTE_CHRONIC_RATIO = 1.5

    def analyze(
        self,
        context,
    ):
        context = context or {}

        profile = context.get(
            "athlete_profile",
            {},
        ) or {}

        load = context.get(
            "load_analysis",
            {},
        ) or {}

        performance = context.get(
            "performance_analysis",
            {},
        ) or {}

        recovery = context.get(
            "recovery_analysis",
            {},
        ) or {}

        limitations = self._profile_limitations(
            profile
        )

        load_level = self._normalized_text(
            load.get(
                "level",
                "",
            )
        ).upper()

        total_load = self._number(
            load.get(
                "total_load"
            )
        )

        acute_chronic_ratio = self._number(
            load.get(
                "acute_chronic_ratio"
            )
        )

        sessions_with_load = self._number(
            load.get(
                "sessions_with_load"
            )
        )

        performance_trend = self._normalized_text(
            performance.get(
                "trend",
                "",
            )
        ).upper()

        recovery_state = self._normalized_text(
            self._first_value(
                recovery,
                [
                    "state",
                    "recovery_state",
                    "status",
                ],
                "",
            )
        ).upper()

        recovery_level = self._normalized_text(
            self._first_value(
                recovery,
                [
                    "level",
                    "recovery_level",
                ],
                "",
            )
        ).upper()

        risk_factors: List[str] = []
        positive_factors: List[str] = []
        reasons: List[str] = []

        has_load_data = (
            load_level not in {
                "",
                "UNKNOWN",
            }
            and (
                sessions_with_load is None
                or sessions_with_load > 0
            )
        )

        has_performance_data = performance_trend not in {
            "",
            "UNKNOWN",
        }

        has_recovery_data = (
            recovery_state not in {
                "",
                "UNKNOWN",
            }
            or recovery_level not in {
                "",
                "UNKNOWN",
            }
        )

        has_meaningful_data = (
            has_load_data
            or has_performance_data
            or has_recovery_data
            or bool(limitations)
        )

        if not has_meaningful_data:
            return {
                "adaptation_level": self.LEVEL_UNKNOWN,
                "risk_factors": [],
                "positive_factors": [],
                "reasons": [
                    "Dati insufficienti per valutare l'adattamento"
                ],
            }

        if profile:
            positive_factors.append(
                "Profilo atleta disponibile"
            )

        for limitation in limitations:
            self._append_unique(
                risk_factors,
                limitation,
            )

        if limitations:
            reasons.append(
                "Presenti limitazioni fisiche note"
            )

        if load_level == "HIGH":
            self._append_unique(
                risk_factors,
                "Carico recente elevato",
            )
            reasons.append(
                "Carico recente elevato"
            )
        elif load_level in {
            "LOW",
            "NORMAL",
        }:
            reasons.append(
                "Carico recente disponibile"
            )

        high_ratio = (
            acute_chronic_ratio is not None
            and acute_chronic_ratio
            > self.HIGH_ACUTE_CHRONIC_RATIO
        )

        if high_ratio:
            self._append_unique(
                risk_factors,
                "Rapporto acuto/cronico elevato",
            )
            reasons.append(
                "Incremento rapido del carico recente"
            )

        if performance_trend == "IMPROVING":
            self._append_unique(
                positive_factors,
                "Performance in crescita",
            )
            reasons.append(
                "Trend prestativo favorevole"
            )
        elif performance_trend == "DECLINING":
            self._append_unique(
                risk_factors,
                "Performance in calo",
            )
            reasons.append(
                "Trend prestativo sfavorevole"
            )
        elif performance_trend == "STABLE":
            self._append_unique(
                positive_factors,
                "Performance stabile",
            )

        poor_recovery = (
            recovery_state in {
                "ROSSO",
                "RED",
            }
            or recovery_level in {
                "POOR",
                "LIMITED",
                "BAD",
                "CRITICAL",
            }
        )

        moderate_recovery = (
            recovery_state in {
                "GIALLO",
                "YELLOW",
            }
            or recovery_level == "MODERATE"
        )

        good_recovery = (
            recovery_state in {
                "VERDE",
                "GREEN",
            }
            or recovery_level in {
                "GOOD",
                "HIGH",
                "NORMAL",
                "OPTIMAL",
            }
            or (
                recovery_level == "LOW"
                and recovery_state not in {
                    "ROSSO",
                    "RED",
                }
            )
        )

        if poor_recovery:
            self._append_unique(
                risk_factors,
                "Recupero insufficiente",
            )
            reasons.append(
                "Recupero recente insufficiente"
            )
        elif moderate_recovery:
            self._append_unique(
                risk_factors,
                "Recupero da monitorare",
            )
            reasons.append(
                "Recupero recente moderato"
            )
        elif good_recovery:
            self._append_unique(
                positive_factors,
                "Recupero adeguato",
            )
            reasons.append(
                "Recupero recente adeguato"
            )

        severe_risk = (
            (
                load_level == "HIGH"
                and bool(limitations)
            )
            or (
                load_level == "HIGH"
                and poor_recovery
            )
            or (
                poor_recovery
                and high_ratio
            )
        )

        moderate_risk = (
            load_level == "HIGH"
            or high_ratio
            or performance_trend == "DECLINING"
            or poor_recovery
            or moderate_recovery
            or bool(limitations)
        )

        if severe_risk:
            level = self.LEVEL_LIMITED
        elif moderate_risk:
            level = self.LEVEL_MODERATE
        elif has_load_data:
            level = self.LEVEL_GOOD
        elif (
            has_performance_data
            or has_recovery_data
        ):
            level = self.LEVEL_GOOD
        else:
            level = self.LEVEL_UNKNOWN

        if level == self.LEVEL_GOOD:
            reasons.append(
                "Adattamento al carico favorevole"
            )
        elif level == self.LEVEL_MODERATE:
            reasons.append(
                "Adattamento da monitorare"
            )
        elif level == self.LEVEL_LIMITED:
            reasons.append(
                "Capacità di adattamento limitata"
            )

        return {
            "adaptation_level": level,
            "risk_factors": risk_factors,
            "positive_factors": positive_factors,
            "reasons": reasons,
        }

    def _profile_limitations(
        self,
        profile,
    ) -> List[str]:
        """Collect limitations from canonical and legacy profile shapes."""

        constraints = profile.get(
            "constraints",
            {},
        ) or {}

        candidates = (
            profile.get(
                "limitations"
            ),
            profile.get(
                "physical_limitations"
            ),
            constraints.get(
                "physical_limitations"
            )
            if isinstance(
                constraints,
                dict,
            )
            else None,
            constraints.get(
                "limitations"
            )
            if isinstance(
                constraints,
                dict,
            )
            else None,
        )

        limitations: List[str] = []

        for candidate in candidates:
            for limitation in self._normalize_list(
                candidate
            ):
                self._append_unique(
                    limitations,
                    limitation,
                )

        return limitations

    def _normalize_list(
        self,
        value,
    ) -> List[str]:
        if value is None:
            return []

        if isinstance(
            value,
            str,
        ):
            text = value.strip()
            return [
                text
            ] if text else []

        if isinstance(
            value,
            dict,
        ):
            text = self._normalized_text(
                value
            )
            return [
                text
            ] if text else []

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):
            result = []

            for item in value:
                text = self._normalized_text(
                    item
                )

                if text:
                    self._append_unique(
                        result,
                        text,
                    )

            return result

        text = self._normalized_text(
            value
        )

        return [
            text
        ] if text else []

    def _first_value(
        self,
        data,
        keys,
        default=None,
    ):
        data = data or {}

        for key in keys:
            value = data.get(
                key
            )

            if value not in (
                None,
                "",
            ):
                return value

        return default

    def _number(
        self,
        value,
    ) -> Optional[float]:
        if value is None:
            return None

        if isinstance(
            value,
            str,
        ):
            value = (
                value
                .strip()
                .replace(
                    ",",
                    ".",
                )
            )

            if not value:
                return None

        try:
            number = float(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return None

        if number != number or number in {
            float("inf"),
            float("-inf"),
        }:
            return None

        return number

    def _normalized_text(
        self,
        value,
    ) -> str:
        if value is None:
            return ""

        if isinstance(
            value,
            dict,
        ):
            value = value.get(
                "value",
                "",
            )

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):
            return " ".join(
                str(item).strip()
                for item in value
                if item is not None
            ).strip()

        return str(
            value
        ).strip()

    def _append_unique(
        self,
        target,
        value,
    ) -> None:
        if value and value not in target:
            target.append(
                value
            )