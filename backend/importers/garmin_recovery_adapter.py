"""
Garmin Recovery Adapter

Converte i payload giornalieri Garmin Connect in una
osservazione fisiologica IronCoach descrittiva.

Principi:
- non calcola un Recovery Score;
- Body Battery non viene chiamata readiness;
- valori Garmin mancanti restano None;
- sleepTimeSeconds nullo/zero non diventa "0 ore di sonno";
- i payload sorgente restano disponibili in raw.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class GarminRecoveryAdapter:
    """Adapter conservativo per dati recovery Garmin."""

    @classmethod
    def convert(
        cls,
        *,
        date: str,
        sleep: Optional[Dict[str, Any]] = None,
        hrv: Optional[Dict[str, Any]] = None,
        training_readiness: Any = None,
        stress: Optional[Dict[str, Any]] = None,
        body_battery: Any = None,
        stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        sleep = sleep or {}
        hrv = hrv or {}
        stress = stress or {}
        stats = stats or {}

        sleep_dto = (
            sleep.get("dailySleepDTO", {})
            if isinstance(sleep, dict)
            else {}
        ) or {}

        sleep_seconds = cls._positive_number(
            sleep_dto.get("sleepTimeSeconds")
        )

        sleep_hours = (
            round(
                sleep_seconds / 3600.0,
                2,
            )
            if sleep_seconds is not None
            else None
        )

        resting_hr = cls._number(
            stats.get("restingHeartRate")
        )

        average_stress = cls._number(
            stress.get("avgStressLevel")
        )

        if average_stress is None:
            average_stress = cls._number(
                stats.get("averageStressLevel")
            )

        body_battery_value = cls._number(
            stats.get(
                "bodyBatteryMostRecentValue"
            )
        )

        charged = cls._number(
            stats.get(
                "bodyBatteryChargedValue"
            )
        )

        drained = cls._number(
            stats.get(
                "bodyBatteryDrainedValue"
            )
        )

        first_battery_record = (
            body_battery[0]
            if (
                isinstance(
                    body_battery,
                    list,
                )
                and body_battery
                and isinstance(
                    body_battery[0],
                    dict,
                )
            )
            else {}
        )

        if charged is None:
            charged = cls._number(
                first_battery_record.get(
                    "charged"
                )
            )

        if drained is None:
            drained = cls._number(
                first_battery_record.get(
                    "drained"
                )
            )

        return {
            "source": "garmin",
            "source_id": (
                f"garmin-recovery:{date}"
            ),
            "date": date,
            "sleep": {
                "score": None,
                "hours": sleep_hours,
                "quality": None,
            },
            # Rimane distinto dal campo IronCoach
            # "readiness", che oggi significa
            # Recovery Score valutabile.
            "training_readiness": (
                cls._training_readiness_score(
                    training_readiness
                )
            ),
            # Non estraiamo HRV finché non abbiamo
            # osservato il formato reale restituito
            # dall'account/dispositivo.
            "hrv": None,
            "resting_hr": resting_hr,
            "stress": average_stress,
            "body_battery": (
                body_battery_value
            ),
            "body_battery_charged": charged,
            "body_battery_drained": drained,
            "raw": {
                "sleep": sleep,
                "hrv": hrv,
                "training_readiness": (
                    training_readiness
                ),
                "stress": stress,
                "body_battery": body_battery,
                "stats": stats,
            },
        }

    @classmethod
    def _training_readiness_score(
        cls,
        value: Any,
    ) -> Optional[float]:
        record = None

        if isinstance(value, dict):
            record = value
        elif (
            isinstance(value, list)
            and value
            and isinstance(
                value[0],
                dict,
            )
        ):
            record = value[0]

        if not record:
            return None

        for key in (
            "score",
            "trainingReadinessScore",
            "readinessScore",
        ):
            number = cls._number(
                record.get(key)
            )

            if number is not None:
                return number

        return None

    @staticmethod
    def _number(
        value: Any,
    ) -> Optional[float]:
        if isinstance(
            value,
            bool,
        ):
            return None

        if isinstance(
            value,
            (int, float),
        ):
            return float(value)

        if isinstance(value, str):
            text = (
                value.strip()
                .replace(",", ".")
            )

            if not text:
                return None

            try:
                return float(text)
            except ValueError:
                return None

        return None

    @classmethod
    def _positive_number(
        cls,
        value: Any,
    ) -> Optional[float]:
        number = cls._number(value)

        if (
            number is None
            or number <= 0
        ):
            return None

        return number
