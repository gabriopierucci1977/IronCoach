"""
IronCoach Load Analyzer v0.4

Analizza il carico allenante recente su finestre temporali mobili.

Principi:
- finestra acuta: ultimi 7 giorni inclusivi;
- finestra cronica: ultimi 28 giorni inclusivi;
- le attività precedenti non influenzano il livello corrente;
- i carichi mancanti vengono ignorati;
- mantiene compatibilità con le chiavi di output storiche.

Non conosce Garmin, Strava o Airtable.
Riceve esclusivamente dati già normalizzati.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple


class LoadAnalyzer:

    LEVEL_UNKNOWN = "UNKNOWN"
    LEVEL_LOW = "LOW"
    LEVEL_NORMAL = "NORMAL"
    LEVEL_HIGH = "HIGH"

    ACUTE_DAYS = 7
    CHRONIC_DAYS = 28

    LOW_THRESHOLD_28D = 500.0
    HIGH_THRESHOLD_28D = 2000.0

    def analyze(
        self,
        history,
    ):
        history = history or {}

        sessions = history.get(
            "training_history",
            [],
        ) or []

        analysis_date = self._resolve_analysis_date(
            history=history,
            sessions=sessions,
        )

        if analysis_date is None:
            return self._empty_result(
                sessions=sessions,
                reason=(
                    "Date dello storico allenamenti insufficienti"
                    if sessions
                    else "Storico allenamenti non disponibile"
                ),
            )

        acute_start = analysis_date - timedelta(
            days=self.ACUTE_DAYS
        )

        chronic_start = analysis_date - timedelta(
            days=self.CHRONIC_DAYS
        )

        acute_load = 0.0
        chronic_load = 0.0

        sessions_7d = 0
        sessions_28d = 0
        sessions_with_load = 0

        sport_distribution: Dict[str, float] = {}

        for session in sessions:
            if not isinstance(
                session,
                dict,
            ):
                continue

            session_date = self._session_date(
                session
            )

            if session_date is None:
                continue

            if (
                session_date < chronic_start
                or session_date > analysis_date
            ):
                continue

            # Conta tutte le sedute valide nella finestra cronica,
            # anche quando il carico è assente o non utilizzabile.
            sessions_28d += 1

            if session_date >= acute_start:
                sessions_7d += 1

            load = self._session_load(
                session
            )

            if load is None:
                continue

            sessions_with_load += 1
            chronic_load += load

            sport = self._session_sport(
                session
            )

            sport_distribution[sport] = (
                sport_distribution.get(
                    sport,
                    0.0,
                )
                + load
            )

            if session_date >= acute_start:
                acute_load += load

        training_window_complete = bool(
            history.get(
                "training_window_complete",
                False,
            )
        )

        absolute_level = self._classify(
            valid_load_sessions=sessions_with_load,
            chronic_load=chronic_load,
            recent_sessions=sessions_28d,
            training_window_complete=training_window_complete,
        )

        (
            level,
            classification_basis,
            personal_baseline_weekly_load,
        ) = self._personalize_level(
            absolute_level=absolute_level,
            acute_load=acute_load,
            load_tolerance=history.get(
                "load_tolerance",
                {},
            ),
        )

        reasons = self._build_reasons(
            level=level,
            valid_load_sessions=sessions_with_load,
            recent_sessions=sessions_28d,
            training_window_complete=training_window_complete,
            classification_basis=classification_basis,
        )

        chronic_weekly_average = (
            chronic_load
            / 4.0
        )

        acute_chronic_ratio = (
            acute_load
            / chronic_weekly_average
            if chronic_weekly_average > 0
            else None
        )

        return {
            "level": level,
            "absolute_level": absolute_level,
            "classification_basis": classification_basis,
            "personal_baseline_weekly_load": (
                round(
                    personal_baseline_weekly_load,
                    2,
                )
                if personal_baseline_weekly_load
                is not None
                else None
            ),

            # Compatibilità storica:
            # total_load ora rappresenta il carico recente a 28 giorni.
            "total_load": round(
                chronic_load,
                2,
            ),
            # Numero di sedute recenti realmente considerate
            # nella finestra cronica di 28 giorni.
            "sessions": sessions_28d,
            "sessions_with_load": sessions_with_load,
            "sport_distribution": {
                sport: round(
                    load,
                    2,
                )
                for sport, load in sorted(
                    sport_distribution.items()
                )
            },
            "reasons": reasons,

            # Metriche temporali esplicite.
            "analysis_date": self._format_datetime(
                analysis_date
            ),
            "acute_load_7d": round(
                acute_load,
                2,
            ),
            "chronic_load_28d": round(
                chronic_load,
                2,
            ),
            "sessions_7d": sessions_7d,
            "sessions_28d": sessions_28d,
            "chronic_weekly_average": round(
                chronic_weekly_average,
                2,
            ),
            "acute_chronic_ratio": (
                round(
                    acute_chronic_ratio,
                    3,
                )
                if acute_chronic_ratio is not None
                else None
            ),
        }

    def _empty_result(
        self,
        sessions,
        reason,
    ):
        return {
            "level": self.LEVEL_UNKNOWN,
            "total_load": 0.0,
            # Nessuna seduta valida è stata inclusa
            # nella finestra temporale analizzata.
            "sessions": 0,
            "sessions_with_load": 0,
            "sport_distribution": {},
            "reasons": [
                reason
            ],
            "analysis_date": None,
            "acute_load_7d": 0.0,
            "chronic_load_28d": 0.0,
            "sessions_7d": 0,
            "sessions_28d": 0,
            "chronic_weekly_average": 0.0,
            "acute_chronic_ratio": None,
        }

    def _resolve_analysis_date(
        self,
        history,
        sessions,
    ) -> Optional[datetime]:
        explicit = self._parse_datetime(
            history.get(
                "analysis_date"
            )
        )

        if explicit is not None:
            return explicit

        valid_dates = [
            session_date
            for session_date in (
                self._session_date(
                    session
                )
                for session in sessions
                if isinstance(
                    session,
                    dict,
                )
            )
            if session_date is not None
        ]

        if not valid_dates:
            return None

        return max(
            valid_dates
        )

    def _session_date(
        self,
        session,
    ) -> Optional[datetime]:
        value = self._first_value(
            session,
            [
                "date",
                "Data allenamento",
                "start_date",
                "start_time",
                "timestamp",
            ],
        )

        if value in (
            None,
            "",
        ):
            raw = session.get(
                "raw"
            )

            if isinstance(
                raw,
                dict,
            ):
                value = self._first_value(
                    raw,
                    [
                        "date",
                        "Data allenamento",
                        "start_date",
                        "start_time",
                        "timestamp",
                    ],
                )

        return self._parse_datetime(
            value
        )

    def _session_load(
        self,
        session,
    ) -> Optional[float]:
        """
        Recupera il carico distinguendo:
        - valore realmente presente, incluso 0;
        - zero sintetico creato da TrainingHistory quando il dato manca.
        """

        raw = session.get(
            "raw"
        )

        if isinstance(
            raw,
            dict,
        ):
            raw_value, raw_present = self._present_value(
                raw,
                [
                    "training_load",
                    "load",
                    "Load",
                    "Carico interno",
                    "Carico",
                    "tss",
                    "icu_training_load",
                ],
            )

            if raw_present:
                return self._number(
                    raw_value
                )

            # TrainingHistory può aver creato training_load=0.0
            # partendo da un dato realmente assente.
            return None

        value, present = self._present_value(
            session,
            [
                "training_load",
                "load",
                "Load",
                "Carico interno",
                "Carico",
                "tss",
                "icu_training_load",
            ],
        )

        if not present:
            return None

        return self._number(
            value
        )

    def _session_sport(
        self,
        session,
    ) -> str:
        sport = self._normalized_text(
            self._first_value(
                session,
                [
                    "sport",
                    "Sport",
                ],
                "unknown",
            )
        ).lower()

        return sport or "unknown"

    def _classify(
        self,
        valid_load_sessions,
        chronic_load,
        recent_sessions,
        training_window_complete,
    ):
        if (
            recent_sessions == 0
            and training_window_complete
        ):
            return self.LEVEL_LOW

        if valid_load_sessions == 0:
            return self.LEVEL_UNKNOWN

        if chronic_load >= self.HIGH_THRESHOLD_28D:
            return self.LEVEL_HIGH

        if chronic_load < self.LOW_THRESHOLD_28D:
            return self.LEVEL_LOW

        return self.LEVEL_NORMAL

    def _personalize_level(
        self,
        *,
        absolute_level,
        acute_load,
        load_tolerance,
    ):
        """
        Evita di interpretare automaticamente un volume
        assoluto elevato come sovraccarico individuale.

        La baseline è utilizzata solo quando:
        - la stima è esplicitamente disponibile;
        - la confidenza è MODERATE o HIGH;
        - la baseline settimanale è positiva;
        - il carico acuto non supera la baseline osservata.

        In tutti gli altri casi resta valida la
        classificazione assoluta storica.
        """

        if absolute_level != self.LEVEL_HIGH:
            return (
                absolute_level,
                "ABSOLUTE_THRESHOLDS",
                None,
            )

        if not isinstance(
            load_tolerance,
            dict,
        ):
            return (
                absolute_level,
                "ABSOLUTE_THRESHOLDS",
                None,
            )

        status = str(
            load_tolerance.get(
                "status",
                "",
            )
            or ""
        ).strip().upper()

        confidence = str(
            load_tolerance.get(
                "confidence",
                "",
            )
            or ""
        ).strip().upper()

        baseline = self._number(
            load_tolerance.get(
                "baseline_weekly_load"
            )
        )

        reliable_baseline = (
            status == "STIMATA"
            and confidence in {
                "MODERATE",
                "HIGH",
            }
            and baseline is not None
            and baseline > 0
        )

        if (
            reliable_baseline
            and acute_load <= baseline
        ):
            return (
                self.LEVEL_NORMAL,
                "PERSONAL_BASELINE",
                baseline,
            )

        return (
            absolute_level,
            "ABSOLUTE_THRESHOLDS",
            baseline
            if reliable_baseline
            else None,
        )

    def _build_reasons(
        self,
        level,
        valid_load_sessions,
        recent_sessions,
        training_window_complete,
        classification_basis,
    ):
        if (
            recent_sessions == 0
            and training_window_complete
        ):
            return [
                "Nessuna attività registrata negli ultimi 28 giorni"
            ]

        if valid_load_sessions == 0:
            return [
                "Dati di carico recente insufficienti"
            ]

        if (
            classification_basis
            == "PERSONAL_BASELINE"
        ):
            return [
                (
                    "Carico assoluto elevato ma coerente "
                    "con la baseline personale"
                )
            ]

        if level == self.LEVEL_HIGH:
            return [
                "Carico recente elevato"
            ]

        if level == self.LEVEL_LOW:
            return [
                "Carico recente contenuto"
            ]

        return [
            "Carico recente nella norma"
        ]

    def _present_value(
        self,
        data,
        keys,
    ) -> Tuple[Any, bool]:
        data = data or {}

        for key in keys:
            if key not in data:
                continue

            value = data.get(
                key
            )

            if value in (
                None,
                "",
            ):
                continue

            return value, True

        return None, False

    def _first_value(
        self,
        data,
        keys,
        default=None,
    ):
        value, present = self._present_value(
            data,
            keys,
        )

        return value if present else default

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

    def _parse_datetime(
        self,
        value,
    ) -> Optional[datetime]:
        text = str(
            value or ""
        ).strip()

        if not text:
            return None

        if text.endswith(
            "Z"
        ):
            text = (
                text[:-1]
                + "+00:00"
            )

        try:
            parsed = datetime.fromisoformat(
                text
            )
        except ValueError:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(
            timezone.utc
        )

    def _format_datetime(
        self,
        value,
    ) -> str:
        return value.isoformat().replace(
            "+00:00",
            "Z",
        )

    def _normalized_text(
        self,
        value,
    ):
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