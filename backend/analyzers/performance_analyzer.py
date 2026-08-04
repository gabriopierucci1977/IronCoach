"""
IronCoach Performance Analyzer v0.3

Analizza l'evoluzione prestativa dell'atleta.

Supporta:

- formato verticale di PerformanceHistory:
  {
      "date": "...",
      "metric": "ftp",
      "value": 280
  }

- formato largo storico:
  {
      "date": "...",
      "ftp": 280,
      "vo2max_run": 52
  }

Output:

- trend generale;
- variazione percentuale per metrica;
- dettagli storici prima/ultima misura.

Non decide.
Non modifica allenamenti.
"""


from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple



class PerformanceAnalyzer:


    TREND_IMPROVING = "IMPROVING"

    TREND_STABLE = "STABLE"

    TREND_DECLINING = "DECLINING"

    TREND_UNKNOWN = "UNKNOWN"



    SUPPORTED_METRICS = (

        "vo2max_run",

        "vo2max_bike",

        "ftp",

        "css",

    )



    CHANGE_THRESHOLD_PERCENT = 2.0



    def analyze(
        self,
        history,
    ):


        history = history or {}



        records = history.get(
            "performance_history",
            [],
        ) or []



        grouped = self._group_records(
            records
        )



        metrics = {}

        details = {}

        improvements = 0

        declines = 0



        for metric_name in sorted(
            grouped
        ):


            values = sorted(
                grouped[metric_name],
                key=lambda item: item[0],
            )



            if len(values) < 2:

                continue



            old = values[0][1]

            new = values[-1][1]



            if old == 0:

                continue



            change = (

                (new - old)

                /

                old

                *

                100.0

            )



            rounded_change = round(
                change,
                1,
            )



            metrics[metric_name] = rounded_change



            details[metric_name] = {

                "start": old,

                "end": new,

                "change_percent": rounded_change,

            }



            if change > self.CHANGE_THRESHOLD_PERCENT:

                improvements += 1


            elif change < -self.CHANGE_THRESHOLD_PERCENT:

                declines += 1
        if not metrics:

            return {
                "trend": self.TREND_UNKNOWN,
                "metrics": {},
                "details": {},
                "strengths": [],
                "concerns": [],
                "reasons": [
                    "Storico performance confrontabile insufficiente"
                ],
            }



        if improvements > declines:

            trend = self.TREND_IMPROVING


        elif declines > improvements:

            trend = self.TREND_DECLINING


        else:

            trend = self.TREND_STABLE



        strengths = []

        concerns = []



        if trend == self.TREND_IMPROVING:

            strengths.append(
                "Performance in crescita"
            )


        elif trend == self.TREND_DECLINING:

            concerns.append(
                "Performance in calo"
            )



        return {

            "trend": trend,

            "metrics": metrics,

            "details": details,

            "strengths": strengths,

            "concerns": concerns,

            "reasons": [

                f"Trend performance: {trend}"

            ],

        }




    def _group_records(
        self,
        records,
    ) -> Dict[str, List[Tuple[datetime, float]]]:



        grouped = defaultdict(
            list
        )



        for record in records:



            if not isinstance(
                record,
                dict,
            ):

                continue



            record_date = self._parse_datetime(

                self._first_value(

                    record,

                    [

                        "date",

                        "Date",

                        "Data",

                        "timestamp",

                    ],

                )

            )



            if record_date is None:

                continue



            metric_name = self._normalized_metric_name(

                record.get(
                    "metric"
                )

            )



            if metric_name:



                value = self._number(

                    record.get(
                        "value"
                    )

                )



                if value is not None:

                    grouped[metric_name].append(

                        (

                            record_date,

                            value,

                        )

                    )



                continue



            for supported_metric in self.SUPPORTED_METRICS:



                value = self._number(

                    record.get(
                        supported_metric
                    )

                )



                if value is None:

                    continue



                grouped[supported_metric].append(

                    (

                        record_date,

                        value,

                    )

                )



        return dict(
            grouped
        )




    def _normalized_metric_name(
        self,
        value,
    ):

        text = str(
            value or ""
        ).strip().lower()



        aliases = {

            "vo2max": "vo2max_run",

            "vo2_max": "vo2max_run",

            "vo2maxrun": "vo2max_run",

            "vo2maxbike": "vo2max_bike",

            "functional_threshold_power": "ftp",

            "critical_swim_speed": "css",

        }



        text = aliases.get(
            text,
            text,
        )



        if text not in self.SUPPORTED_METRICS:

            return ""



        return text




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

                +

                "+00:00"

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



        if number != number:

            return None



        if number in {

            float("inf"),

            float("-inf"),

        }:

            return None



        return number
