"""
IronCoach Recovery Trend Analyzer v0.1

Analizza l'evoluzione temporale del recupero dell'atleta.

Non conosce:
- Garmin Connect
- Strava
- Airtable

Riceve esclusivamente uno storico recovery già normalizzato
o parzialmente normalizzato.
"""

from datetime import datetime


class RecoveryTrendAnalyzer:

    TREND_IMPROVING = "IMPROVING"
    TREND_STABLE = "STABLE"
    TREND_DECLINING = "DECLINING"
    TREND_UNKNOWN = "UNKNOWN"

    DATA_NONE = "NONE"
    DATA_LIMITED = "LIMITED"
    DATA_GOOD = "GOOD"

    CHANGE_THRESHOLD = 3.0
    DEFAULT_WINDOW_SIZE = 7

    def analyze(
        self,
        history,
    ):

        history = history or {}

        records = history.get(
            "recovery_history",
            [],
        ) or []

        ordered_records = self._sort_records(
            records
        )

        recovery_scores = self._extract_values(
            ordered_records,
            (
                "recovery_score",
                "Recovery Score",
                "readiness_score",
                "Readiness Score",
                "score",
            ),
        )

        sleep_scores = self._extract_values(
            ordered_records,
            (
                "sleep_score",
                "Sleep Score",
                "sleep",
            ),
        )

        data_quality = self._data_quality(
            recovery_scores
        )

        if len(recovery_scores) < 2:

            return {
                "trend": self.TREND_UNKNOWN,
                "data_quality": data_quality,
                "records": len(records),
                "valid_records": len(recovery_scores),
                "previous_average": None,
                "recent_average": None,
                "change": None,
                "sleep_trend": self.TREND_UNKNOWN,
                "sleep_change": None,
                "reasons": self._insufficient_reasons(
                    records=records,
                    recovery_scores=recovery_scores,
                ),
            }

        recovery_comparison = self._compare_windows(
            recovery_scores
        )

        sleep_comparison = self._compare_windows(
            sleep_scores
        )

        trend = self._classify_change(
            recovery_comparison.get(
                "change"
            )
        )

        sleep_trend = self._classify_change(
            sleep_comparison.get(
                "change"
            )
        )

        reasons = self._build_reasons(
            trend=trend,
            recovery_comparison=recovery_comparison,
            sleep_trend=sleep_trend,
            sleep_comparison=sleep_comparison,
        )

        return {
            "trend": trend,
            "data_quality": data_quality,
            "records": len(records),
            "valid_records": len(recovery_scores),
            "previous_average": recovery_comparison.get(
                "previous_average"
            ),
            "recent_average": recovery_comparison.get(
                "recent_average"
            ),
            "change": recovery_comparison.get(
                "change"
            ),
            "sleep_trend": sleep_trend,
            "sleep_change": sleep_comparison.get(
                "change"
            ),
            "reasons": reasons,
        }

    def _compare_windows(
        self,
        values,
    ):

        if len(values) < 2:

            return {
                "previous_average": None,
                "recent_average": None,
                "change": None,
            }

        recent_size = min(
            self.DEFAULT_WINDOW_SIZE,
            max(
                1,
                len(values) // 2,
            ),
        )

        previous_size = min(
            recent_size,
            len(values) - recent_size,
        )

        recent_values = values[
            -recent_size:
        ]

        previous_values = values[
            -(
                recent_size
                + previous_size
            ):
            -recent_size
        ]

        if not previous_values or not recent_values:

            return {
                "previous_average": None,
                "recent_average": None,
                "change": None,
            }

        previous_average = (
            sum(previous_values)
            / len(previous_values)
        )

        recent_average = (
            sum(recent_values)
            / len(recent_values)
        )

        change = (
            recent_average
            - previous_average
        )

        return {
            "previous_average": round(
                previous_average,
                1,
            ),
            "recent_average": round(
                recent_average,
                1,
            ),
            "change": round(
                change,
                1,
            ),
        }

    def _classify_change(
        self,
        change,
    ):

        if change is None:

            return self.TREND_UNKNOWN

        if change >= self.CHANGE_THRESHOLD:

            return self.TREND_IMPROVING

        if change <= -self.CHANGE_THRESHOLD:

            return self.TREND_DECLINING

        return self.TREND_STABLE

    def _build_reasons(
        self,
        trend,
        recovery_comparison,
        sleep_trend,
        sleep_comparison,
    ):

        reasons = []

        previous_average = recovery_comparison.get(
            "previous_average"
        )

        recent_average = recovery_comparison.get(
            "recent_average"
        )

        change = recovery_comparison.get(
            "change"
        )

        if trend == self.TREND_IMPROVING:

            reasons.append(
                "Trend recovery in miglioramento"
            )

        elif trend == self.TREND_DECLINING:

            reasons.append(
                "Trend recovery in peggioramento"
            )

        elif trend == self.TREND_STABLE:

            reasons.append(
                "Trend recovery stabile"
            )

        else:

            reasons.append(
                "Trend recovery non determinabile"
            )

        if (
            previous_average is not None
            and recent_average is not None
            and change is not None
        ):

            reasons.append(
                "Recovery medio passato: "
                f"{self._format_number(previous_average)}; "
                "recovery medio recente: "
                f"{self._format_number(recent_average)}; "
                "variazione: "
                f"{self._format_signed_number(change)}"
            )

        sleep_change = sleep_comparison.get(
            "change"
        )

        if sleep_trend == self.TREND_IMPROVING:

            reasons.append(
                "Sleep Score in miglioramento"
            )

        elif sleep_trend == self.TREND_DECLINING:

            reasons.append(
                "Sleep Score in peggioramento"
            )

        elif (
            sleep_trend == self.TREND_STABLE
            and sleep_change is not None
        ):

            reasons.append(
                "Sleep Score stabile"
            )

        return reasons

    def _insufficient_reasons(
        self,
        records,
        recovery_scores,
    ):

        if not records:

            return [
                "Storico recovery non disponibile"
            ]

        if not recovery_scores:

            return [
                "Storico recovery privo di valori validi"
            ]

        return [
            "Storico recovery insufficiente per stimare il trend"
        ]

    def _data_quality(
        self,
        recovery_scores,
    ):

        valid_count = len(
            recovery_scores
        )

        if valid_count == 0:

            return self.DATA_NONE

        if valid_count < 4:

            return self.DATA_LIMITED

        return self.DATA_GOOD

    def _extract_values(
        self,
        records,
        field_names,
    ):

        values = []

        for record in records:

            if not isinstance(
                record,
                dict,
            ):
                continue

            value = self._find_value(
                record,
                field_names,
            )

            number = self._number(
                value
            )

            if number is not None:

                values.append(
                    number
                )

        return values

    def _find_value(
        self,
        record,
        field_names,
    ):

        expected_keys = {
            self._normalize_key(
                field_name
            )
            for field_name in field_names
        }

        for key, value in record.items():

            if self._normalize_key(
                key
            ) in expected_keys:

                return value

        return None

    def _sort_records(
        self,
        records,
    ):

        valid_records = [
            record
            for record in records
            if isinstance(
                record,
                dict,
            )
        ]

        dated_records = []

        for index, record in enumerate(
            valid_records
        ):

            date_value = self._find_value(
                record,
                (
                    "date",
                    "data",
                    "recorded_at",
                    "timestamp",
                ),
            )

            parsed_date = self._parse_date(
                date_value
            )

            dated_records.append(
                (
                    parsed_date,
                    index,
                    record,
                )
            )

        if not any(
            item[0] is not None
            for item in dated_records
        ):

            return valid_records

        dated_records.sort(
            key=lambda item: (
                item[0] is None,
                item[0] or datetime.max,
                item[1],
            )
        )

        return [
            item[2]
            for item in dated_records
        ]

    def _parse_date(
        self,
        value,
    ):

        if value is None:

            return None

        text = str(
            value
        ).strip()

        if not text:

            return None

        try:

            return datetime.fromisoformat(
                text.replace(
                    "Z",
                    "+00:00",
                )
            )

        except ValueError:

            return None

    def _normalize_key(
        self,
        value,
    ):

        return (
            str(value)
            .strip()
            .lower()
            .replace("_", " ")
        )

    def _number(
        self,
        value,
    ):

        if value is None:

            return None

        if isinstance(
            value,
            dict,
        ):

            value = value.get(
                "value"
            )

        if isinstance(
            value,
            str,
        ):

            value = (
                value
                .strip()
                .replace(",", ".")
            )

            if not value:

                return None

        try:

            return float(value)

        except (
            TypeError,
            ValueError,
        ):

            return None

    def _format_number(
        self,
        value,
    ):

        if value is None:

            return "N/D"

        if float(value).is_integer():

            return str(
                int(value)
            )

        return f"{value:.1f}"

    def _format_signed_number(
        self,
        value,
    ):

        if value is None:

            return "N/D"

        formatted = self._format_number(
            abs(value)
        )

        if value > 0:

            return f"+{formatted}"

        if value < 0:

            return f"-{formatted}"

        return "0"