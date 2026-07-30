# backend/analyzers/nutrition_analyzer.py

"""
IronCoach Nutrition Analyzer

Valuta il recupero nutrizionale dell'atleta considerando:

- recupero nutrizionale
- idratazione
- disponibilità di carboidrati

L'output è volutamente identico a quello restituito in precedenza
da CoachEngine._assess_nutrition(), così da evitare regressioni.
"""

from __future__ import annotations

from typing import Any


class NutritionAnalyzer:
    """Analizza lo stato nutrizionale dell'atleta."""

    LEVEL_LOW = "LOW"
    LEVEL_MODERATE = "MODERATE"
    LEVEL_HIGH = "HIGH"
    LEVEL_UNKNOWN = "UNKNOWN"

    def analyze(self, nutrition: dict[str, Any] | None) -> dict[str, Any]:
        """
        Valuta il recupero nutrizionale.

        Args:
            nutrition: dizionario contenente i dati nutrizionali.

        Returns:
            Dizionario compatibile con il CoachEngine attuale.
        """

        nutrition = nutrition or {}

        recovery_status = self._normalized_text(
            nutrition.get("Stato recupero nutrizionale")
            or nutrition.get("stato_recupero_nutrizionale")
        ).lower()

        hydration_status = self._normalized_text(
            nutrition.get("Stato idratazione")
            or nutrition.get("stato_idratazione")
        ).lower()

        carbohydrate_status = self._normalized_text(
            nutrition.get("Stato carboidrati")
            or nutrition.get("stato_carboidrati")
        ).lower()

        reasons: list[str] = []

        statuses = [
            recovery_status,
            hydration_status,
            carbohydrate_status,
        ]

        insufficient_count = 0
        critical_count = 0

        for status in statuses:
            if not status:
                continue

            if self._contains_any(
                status,
                (
                    "insufficiente",
                    "critico",
                    "scarso",
                    "inadeguato",
                ),
            ):
                critical_count += 1
                insufficient_count += 1

            elif self._contains_any(
                status,
                (
                    "da migliorare",
                    "migliorare",
                    "parziale",
                    "basso",
                ),
            ):
                insufficient_count += 1

        if recovery_status:
            reasons.append(
                f"Recupero nutrizionale: {recovery_status.upper()}"
            )

        if hydration_status:
            reasons.append(
                f"Idratazione: {hydration_status.upper()}"
            )

        if carbohydrate_status:
            reasons.append(
                f"Disponibilità carboidrati: "
                f"{carbohydrate_status.upper()}"
            )

        if critical_count >= 1 or insufficient_count >= 2:
            level = self.LEVEL_HIGH

        elif insufficient_count == 1:
            level = self.LEVEL_MODERATE

        elif any(statuses):
            level = self.LEVEL_LOW

        else:
            level = self.LEVEL_UNKNOWN
            reasons.append("Dati nutrizionali insufficienti")

        return {
            "level": level,
            "recovery_status": recovery_status,
            "hydration_status": hydration_status,
            "carbohydrate_status": carbohydrate_status,
            "reasons": reasons,
        }

    @staticmethod
    def _normalized_text(value: Any) -> str:
        """Normalizza un valore testuale proveniente da Airtable."""

        if value is None:
            return ""

        if isinstance(value, dict):
            generated_value = value.get("value")

            if generated_value is not None:
                return str(generated_value).strip()

        if isinstance(value, (list, tuple, set)):
            return " ".join(
                str(item).strip()
                for item in value
                if item is not None
            ).strip()

        return str(value).strip()

    @staticmethod
    def _contains_any(
        text: str,
        expressions: tuple[str, ...],
    ) -> bool:
        """Verifica se il testo contiene almeno una delle espressioni indicate."""

        if not text:
            return False

        return any(expression in text for expression in expressions)