"""
IronCoach Athlete Profile Engine v0.3

Costruisce il profilo intelligente dell'atleta
utilizzando i dati anagrafici, sportivi e storici
già disponibili nel contesto.

Non prende decisioni allenanti.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median


class AthleteProfileEngine:

    LOAD_TOLERANCE_WINDOW_DAYS = 56
    LOAD_TOLERANCE_MAX_WEEKS = 8

    # Coerenti con le soglie 28d del LoadAnalyzer, espresse come
    # baseline settimanale osservata.
    LOAD_TOLERANCE_LOW_WEEKLY = 125.0
    LOAD_TOLERANCE_HIGH_WEEKLY = 500.0

    def analyze(
        self,
        context,
    ):

        context = context or {}

        athlete = context.get(
            "athlete",
            {},
        ) or {}

        return {
            "athlete_type": self._athlete_type(
                athlete
            ),
            "strengths": self._strengths(
                athlete
            ),
            "limitations": self._limitations(
                athlete
            ),
            "training_preferences": self._preferences(
                athlete
            ),
            "load_tolerance": self._load_tolerance(
                context
            ),
            "injury_patterns": self._injury_patterns(
                athlete
            ),
            "goal_profile": self._goal_profile(
                athlete
            ),
        }

    def _athlete_type(
        self,
        athlete,
    ):

        level = self._field(
            athlete,
            "Livello atleta",
        ).lower()

        sport = self._field(
            athlete,
            "Sport principale",
        ).lower()

        goals = self._field(
            athlete,
            "Obiettivi principali",
        ).lower()

        race_goals = self._field(
            athlete,
            "Gare obiettivo",
        ).lower()

        availability = self._field(
            athlete,
            "Disponibilità allenamento",
        ).lower()

        combined = " ".join(
            (
                sport,
                goals,
                race_goals,
                availability,
            )
        )

        age_group = (
            "age group" in level
        )

        multidisciplinary = (
            "triathlon" in combined
            or (
                self._contains_any(
                    combined,
                    (
                        "nuoto",
                        "swim",
                    ),
                )
                and self._contains_any(
                    combined,
                    (
                        "bici",
                        "bike",
                        "ciclismo",
                    ),
                )
                and self._contains_any(
                    combined,
                    (
                        "corsa",
                        "run",
                    ),
                )
            )
        )

        if age_group and multidisciplinary:

            return (
                "Triatleta Age Group endurance "
                "multidisciplinare"
            )

        if multidisciplinary:

            return (
                "Atleta endurance multidisciplinare"
            )

        if age_group:

            return "Atleta Age Group endurance"

        if sport:

            return (
                f"Atleta endurance - "
                f"{sport.capitalize()}"
            )

        return "Atleta endurance"

    def _strengths(
        self,
        athlete,
    ):

        strengths = []

        years = self._number(
            self._field(
                athlete,
                "Anni di attività sportiva",
            )
        )

        if years is not None and years >= 5:

            strengths.append(
                "Elevata esperienza sportiva"
            )

        notes = self._field(
            athlete,
            "Note coach",
        ).lower()

        goals = self._field(
            athlete,
            "Obiettivi principali",
        ).lower()

        if (
            "dati" in notes
            or "dati" in goals
        ):

            strengths.append(
                "Approccio orientato ai dati"
            )

        availability = self._field(
            athlete,
            "Disponibilità allenamento",
        ).lower()

        if self._contains_any(
            availability,
            (
                "quotidianamente",
                "ogni giorno",
                "tutti i giorni",
            ),
        ):

            strengths.append(
                "Elevata disponibilità allenante"
            )

        if (
            self._contains_any(
                availability,
                (
                    "nuoto",
                    "swim",
                ),
            )
            and self._contains_any(
                availability,
                (
                    "bici",
                    "bike",
                    "ciclismo",
                ),
            )
            and self._contains_any(
                availability,
                (
                    "corsa",
                    "run",
                ),
            )
        ):

            strengths.append(
                "Esperienza multidisciplinare"
            )

        return self._unique(
            strengths
        )

    def _limitations(
        self,
        athlete,
    ):

        limitations = []

        physical = self._field(
            athlete,
            "Limitazioni fisiche",
        ).lower()

        injuries = self._field(
            athlete,
            "Storico infortuni",
        ).lower()

        combined = (
            physical
            + " "
            + injuries
        )

        if self._contains_any(
            combined,
            (
                "tendine",
                "tendineo",
                "achille",
            ),
        ):

            limitations.append(
                "Storico problematiche tendinee"
            )

        if self._contains_any(
            combined,
            (
                "chirurg",
                "intervento",
                "operazione",
            ),
        ):

            limitations.append(
                "Pregressa gestione chirurgica"
            )

        return self._unique(
            limitations
        )

    def _preferences(
        self,
        athlete,
    ):

        preferences = []

        availability = self._field(
            athlete,
            "Disponibilità allenamento",
        ).lower()

        if self._contains_any(
            availability,
            (
                "quotidianamente",
                "ogni giorno",
                "tutti i giorni",
            ),
        ):

            preferences.append(
                "Possibilità di allenamento quotidiano"
            )

        if self._contains_any(
            availability,
            (
                "1,5-2 ore",
                "1.5-2 ore",
                "90-120",
            ),
        ):

            preferences.append(
                "Sessioni preferite da 90-120 minuti"
            )

        if (
            self._contains_any(
                availability,
                (
                    "nuoto",
                    "swim",
                ),
            )
            and self._contains_any(
                availability,
                (
                    "bici",
                    "bike",
                    "ciclismo",
                ),
            )
            and self._contains_any(
                availability,
                (
                    "corsa",
                    "run",
                ),
            )
        ):

            preferences.append(
                "Distribuzione tra nuoto, bici e corsa"
            )

        if self._contains_any(
            availability,
            (
                "forza",
                "pesi",
                "strength",
            ),
        ):

            preferences.append(
                "Disponibilità per allenamento di forza"
            )

        if not preferences and availability:

            preferences.append(
                self._field(
                    athlete,
                    "Disponibilità allenamento",
                )
            )

        return self._unique(
            preferences
        )

    def _load_tolerance(
        self,
        context,
    ):
        """Estimate the athlete's observed training-load baseline.

        This is deliberately descriptive rather than prescriptive: it does
        not declare a physiological safe limit.  It summarizes the load the
        athlete has actually sustained in the available normalized history.

        The estimate uses up to eight rolling seven-day buckets ending on the
        most recent valid activity date.  The median weekly load is used as a
        robust baseline so one peak week does not dominate the estimate.
        """

        sessions = self._training_sessions(
            context
        )

        observations = []
        sources = set()

        for session in sessions:

            if not isinstance(
                session,
                dict,
            ):
                continue

            session_date = self._session_datetime(
                session
            )

            training_load = self._session_training_load(
                session
            )

            if (
                session_date is None
                or training_load is None
                or training_load < 0
            ):
                continue

            observations.append(
                (
                    session_date,
                    training_load,
                )
            )

            source = self._session_source(
                session
            )

            if source:
                sources.add(
                    source
                )

        if not observations:
            return {
                "status": "DA STIMARE",
                "level": "UNKNOWN",
                "confidence": "NONE",
                "source": "Storico training con carico non disponibile",
                "sessions_analyzed": 0,
                "weeks_analyzed": 0,
                "baseline_weekly_load": None,
                "mean_weekly_load": None,
                "peak_weekly_load": None,
                "latest_7d_load": None,
                "data_span_days": 0,
            }

        observations.sort(
            key=lambda item: item[0]
        )

        latest_date = observations[-1][0]
        window_start = latest_date - timedelta(
            days=self.LOAD_TOLERANCE_WINDOW_DAYS - 1
        )

        recent = [
            item
            for item in observations
            if item[0] >= window_start
        ]

        earliest_date = recent[0][0]
        data_span_days = max(
            1,
            (
                latest_date.date()
                - earliest_date.date()
            ).days
            + 1,
        )

        weeks_analyzed = min(
            self.LOAD_TOLERANCE_MAX_WEEKS,
            max(
                1,
                (
                    data_span_days
                    + 6
                )
                // 7,
            ),
        )

        weekly_loads = [
            0.0
            for _ in range(
                weeks_analyzed
            )
        ]

        for session_date, training_load in recent:

            days_ago = (
                latest_date.date()
                - session_date.date()
            ).days

            week_index = (
                days_ago
                // 7
            )

            if week_index >= weeks_analyzed:
                continue

            weekly_loads[
                week_index
            ] += training_load

        baseline_weekly_load = float(
            median(
                weekly_loads
            )
        )

        mean_weekly_load = (
            sum(
                weekly_loads
            )
            / len(
                weekly_loads
            )
        )

        peak_weekly_load = max(
            weekly_loads
        )

        latest_7d_load = weekly_loads[0]

        sufficient_for_estimate = (
            len(recent) >= 4
            and data_span_days >= 7
        )

        if sufficient_for_estimate:
            status = "STIMATA"
            level = self._classify_load_tolerance(
                baseline_weekly_load
            )
        else:
            status = "DATI INSUFFICIENTI"
            level = "UNKNOWN"

        confidence = self._load_tolerance_confidence(
            sessions=len(recent),
            data_span_days=data_span_days,
            sufficient=sufficient_for_estimate,
        )

        return {
            "status": status,
            "level": level,
            "confidence": confidence,
            "source": self._load_tolerance_source(
                sources
            ),
            "sessions_analyzed": len(
                recent
            ),
            "weeks_analyzed": weeks_analyzed,
            "baseline_weekly_load": round(
                baseline_weekly_load,
                2,
            ),
            "mean_weekly_load": round(
                mean_weekly_load,
                2,
            ),
            "peak_weekly_load": round(
                peak_weekly_load,
                2,
            ),
            "latest_7d_load": round(
                latest_7d_load,
                2,
            ),
            "data_span_days": data_span_days,
        }

    def _training_sessions(
        self,
        context,
    ):

        context = context or {}

        sessions = context.get(
            "training_history"
        )

        if isinstance(
            sessions,
            list,
        ):
            return sessions

        history = context.get(
            "history",
            {},
        ) or {}

        training_history = history.get(
            "training"
        )

        if hasattr(
            training_history,
            "sessions",
        ):
            return list(
                training_history.sessions
            )

        return []

    def _session_training_load(
        self,
        session,
    ):

        value = self._find_session_value(
            session,
            (
                "training_load",
                "load",
                "Load",
                "Carico interno",
                "Carico",
                "tss",
                "icu_training_load",
            ),
        )

        number = self._number(
            value
        )

        if number is None:
            return None

        return number

    def _session_datetime(
        self,
        session,
    ):

        value = self._find_session_value(
            session,
            (
                "date",
                "Date",
                "Data allenamento",
                "start_date",
                "start_time",
                "timestamp",
            ),
        )

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

    def _session_source(
        self,
        session,
    ):

        value = self._find_session_value(
            session,
            (
                "source",
            ),
        )

        return str(
            value or ""
        ).strip().lower()

    def _find_session_value(
        self,
        session,
        keys,
        depth=0,
    ):

        if (
            not isinstance(
                session,
                dict,
            )
            or depth > 2
        ):
            return None

        for key in keys:
            if key not in session:
                continue

            value = session.get(
                key
            )

            if value not in (
                None,
                "",
            ):
                return value

        raw = session.get(
            "raw"
        )

        if isinstance(
            raw,
            dict,
        ):
            return self._find_session_value(
                raw,
                keys,
                depth=depth + 1,
            )

        return None

    def _classify_load_tolerance(
        self,
        baseline_weekly_load,
    ):

        if (
            baseline_weekly_load
            < self.LOAD_TOLERANCE_LOW_WEEKLY
        ):
            return "LOW"

        if (
            baseline_weekly_load
            >= self.LOAD_TOLERANCE_HIGH_WEEKLY
        ):
            return "HIGH"

        return "NORMAL"

    def _load_tolerance_confidence(
        self,
        sessions,
        data_span_days,
        sufficient,
    ):

        if not sufficient:
            return "LOW"

        if (
            sessions >= 12
            and data_span_days >= 28
        ):
            return "HIGH"

        if (
            sessions >= 6
            and data_span_days >= 14
        ):
            return "MODERATE"

        return "LOW"

    def _load_tolerance_source(
        self,
        sources,
    ):

        clean_sources = sorted(
            source
            for source in sources
            if source
        )

        if not clean_sources:
            return "Storico training normalizzato"

        return (
            "Storico training normalizzato: "
            + " + ".join(
                clean_sources
            )
        )

    def _goal_profile(
        self,
        athlete,
    ):
        """
        Costruisce una sintesi dell'obiettivo atleta.

        Non modifica la decisione allenante.
        Fornisce solo contesto al coach.
        """

        goals = self._field(
            athlete,
            "Obiettivi principali",
        )

        races = self._field(
            athlete,
            "Gare obiettivo",
        )

        combined = (
            goals
            + " "
            + races
        ).lower()

        if self._contains_any(
            combined,
            (
                "ironman",
                "triathlon",
                "gara",
                "maratona",
                "gran fondo",
            ),
        ):
            goal_type = "EVENTO"

        elif self._contains_any(
            combined,
            (
                "dimagr",
                "salute",
                "benessere",
                "fitness",
            ),
        ):
            goal_type = "BENESSERE"

        elif goals:
            goal_type = "PERFORMANCE"

        else:
            goal_type = "NON DEFINITO"

        return {
            "primary_goal": goals,
            "race_target": races,
            "goal_type": goal_type,
        }


    def _injury_patterns(
        self,
        athlete,
    ):

        patterns = []

        physical = self._field(
            athlete,
            "Limitazioni fisiche",
        ).lower()

        injuries = self._field(
            athlete,
            "Storico infortuni",
        ).lower()

        combined = (
            physical
            + " "
            + injuries
        )

        if self._contains_any(
            combined,
            (
                "tendine",
                "tendineo",
                "achille",
            ),
        ):

            patterns.append(
                "Monitorare la risposta del tendine "
                "d'Achille al carico di corsa"
            )

        return patterns

    def _field(
        self,
        data,
        field_name,
    ):
        """
        Estrae un campo compatibile sia con:

        - formato Airtable flat;
        - formato normalizzato annidato.
        """

        if not isinstance(
            data,
            dict,
        ):

            return ""

        expected = self._normalize_key(
            field_name
        )

        for key, value in data.items():

            if self._normalize_key(
                key
            ) == expected:

                return self._normalized_text(
                    value
                )

            if isinstance(
                value,
                dict,
            ):

                nested_value = self._field(
                    value,
                    field_name,
                )

                if nested_value:

                    return nested_value

        return ""

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

            if "value" in value:

                return self._normalized_text(
                    value.get("value")
                )

            return " ".join(
                self._normalized_text(item)
                for item in value.values()
            ).strip()

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):

            return " ".join(
                self._normalized_text(item)
                for item in value
                if item is not None
            ).strip()

        return str(value).strip()

    def _number(
        self,
        value,
    ):

        if value is None:

            return None

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

    def _contains_any(
        self,
        text,
        expressions,
    ):

        if not text:

            return False

        return any(
            expression in text
            for expression in expressions
        )

    def _unique(
        self,
        values,
    ):

        result = []

        for value in values:

            if value not in result:

                result.append(
                    value
                )

        return result