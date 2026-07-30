"""
IronCoach Athlete Profile Engine v0.2

Costruisce il profilo intelligente dell'atleta
utilizzando i dati anagrafici, sportivi e storici
già disponibili nel contesto.

Non prende decisioni allenanti.
"""


class AthleteProfileEngine:

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
            "load_tolerance": self._load_tolerance(),
            "injury_patterns": self._injury_patterns(
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

    def _load_tolerance(self):

        return {
            "status": "DA STIMARE",
            "source": (
                "Storico Garmin/Strava "
                "non ancora disponibile"
            ),
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