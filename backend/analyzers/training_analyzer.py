"""
IronCoach Training Analyzer v0.3.0

Analizzatore dedicato alla valutazione dello stress prodotto dall'ultima
seduta di allenamento.

Questa versione estrae fedelmente la logica precedentemente contenuta nel
CoachEngine v3, senza modificare soglie, livelli o comportamento.

Interfaccia pubblica:

    TrainingAnalyzer().analyze(training)

Il metodo restituisce un dizionario compatibile con il formato utilizzato
dal CoachEngine.
"""


class TrainingAnalyzer:
    """
    Valuta lo stress generato dall'ultima seduta.

    L'analizzatore non conosce Airtable e riceve esclusivamente un
    dizionario contenente i dati della seduta.
    """

    LEVEL_LOW = "LOW"
    LEVEL_MODERATE = "MODERATE"
    LEVEL_HIGH = "HIGH"
    LEVEL_CRITICAL = "CRITICAL"
    LEVEL_UNKNOWN = "UNKNOWN"

    def analyze(self, training):
        """
        Valuta lo stress prodotto dall'ultima seduta.

        Vengono considerati:

        - RPE;
        - tipo di seduta;
        - zona prevista;
        - durata;
        - carico interno.

        Args:
            training: dizionario contenente i dati della seduta.

        Returns:
            dict: assessment strutturato compatibile con CoachEngine.
        """

        training = training or {}

        # Prefer the canonical ActivityNormalizer contract.  ``raw`` is only
        # a backwards-compatible fallback for contexts created before the
        # canonical coaching fields were promoted by the normalizer.
        rpe = self._number(
            self._value_with_raw_fallback(
                training,
                (
                    "rpe",
                    "RPE percepito",
                    "RPE",
                    "perceived_exertion",
                ),
            )
        )

        session_type = self._normalized_text(
            self._value_with_raw_fallback(
                training,
                (
                    "session_type",
                    "Tipo seduta",
                    "tipo_seduta",
                    "workout_type",
                ),
            )
        ).lower()

        planned_zone = self._normalized_text(
            self._value_with_raw_fallback(
                training,
                (
                    "intensity",
                    "planned_zone",
                    "Zona prevista",
                    "zona_prevista",
                    "zone",
                ),
            )
        ).lower()

        duration_minutes = self._number(
            self._value_with_raw_fallback(
                training,
                (
                    "duration_minutes",
                    "Durata minuti",
                    "durata_minuti",
                    "duration",
                ),
            )
        )

        internal_load = self._number(
            self._value_with_raw_fallback(
                training,
                (
                    "training_load",
                    "Carico interno",
                    "carico_interno",
                    "load",
                    "tss",
                    "icu_training_load",
                ),
            )
        )

        reasons = []

        high_intensity_session = self._contains_any(
            session_type,
            (
                "qualità",
                "vo2",
                "vo₂",
                "ripetute",
                "intervalli",
                "soglia",
                "gara",
                "test",
            ),
        )

        high_intensity_zone = self._contains_any(
            planned_zone,
            (
                "z4",
                "z5",
                "soglia",
                "vo2",
                "vo₂",
                "anaerob",
            ),
        )

        if rpe is not None:
            reasons.append(
                f"RPE ultima seduta: {self._format_number(rpe)}"
            )

        if high_intensity_session:
            reasons.append(
                "Ultima seduta classificata ad alta intensità"
            )

        if high_intensity_zone:
            reasons.append("Zona prevista ad alta intensità")

        if duration_minutes is not None and duration_minutes >= 150:
            reasons.append(
                f"Durata elevata: "
                f"{self._format_number(duration_minutes)} minuti"
            )

        if internal_load is not None and internal_load >= 900:
            reasons.append(
                f"Carico interno elevato: "
                f"{self._format_number(internal_load)}"
            )

        if rpe is not None and rpe >= 9:
            return self._result(
                level=self.LEVEL_HIGH,
                rpe=rpe,
                session_type=session_type,
                planned_zone=planned_zone,
                duration_minutes=duration_minutes,
                internal_load=internal_load,
                reasons=reasons,
            )

        if (
            rpe is not None
            and rpe >= 8
            and (high_intensity_session or high_intensity_zone)
        ):
            return self._result(
                level=self.LEVEL_HIGH,
                rpe=rpe,
                session_type=session_type,
                planned_zone=planned_zone,
                duration_minutes=duration_minutes,
                internal_load=internal_load,
                reasons=reasons,
            )

        moderate_factors = 0

        if rpe is not None and rpe >= 7:
            moderate_factors += 1

        if high_intensity_session:
            moderate_factors += 1

        if high_intensity_zone:
            moderate_factors += 1

        if duration_minutes is not None and duration_minutes >= 120:
            moderate_factors += 1

        if internal_load is not None and internal_load >= 700:
            moderate_factors += 1

        if moderate_factors >= 2:
            level = self.LEVEL_MODERATE

        elif moderate_factors == 1:
            level = self.LEVEL_MODERATE

        elif (
            rpe is None
            and not session_type
            and not planned_zone
            and duration_minutes is None
            and internal_load is None
        ):
            level = self.LEVEL_UNKNOWN
            reasons.append("Dati sul carico allenante insufficienti")

        else:
            level = self.LEVEL_LOW

        return self._result(
            level=level,
            rpe=rpe,
            session_type=session_type,
            planned_zone=planned_zone,
            duration_minutes=duration_minutes,
            internal_load=internal_load,
            reasons=reasons,
        )

    def _result(
        self,
        level,
        rpe,
        session_type,
        planned_zone,
        duration_minutes,
        internal_load,
        reasons,
    ):
        """
        Costruisce il risultato dell'analisi in formato uniforme.
        """

        return {
            "level": level,
            "rpe": rpe,
            "session_type": session_type,
            "planned_zone": planned_zone,
            "duration_minutes": duration_minutes,
            "internal_load": internal_load,
            "reasons": reasons,
        }

    def _value_with_raw_fallback(
        self,
        training,
        keys,
    ):
        """Return the first present value, preferring canonical fields."""

        for data in (
            training,
            training.get("raw", {})
            if isinstance(training, dict)
            else {},
        ):
            if not isinstance(data, dict):
                continue

            for key in keys:
                if key not in data:
                    continue

                value = data.get(key)

                if value not in (
                    None,
                    "",
                ):
                    return value

        return None

    def _number(self, value):
        """
        Converte un valore numerico in float.

        Restituisce None quando il valore non è presente oppure non può
        essere convertito.
        """

        if value is None:
            return None

        if isinstance(value, str):
            cleaned_value = value.strip().replace(",", ".")

            if not cleaned_value:
                return None

            value = cleaned_value

        try:
            return float(value)

        except (TypeError, ValueError):
            return None

    def _normalized_text(self, value):
        """
        Normalizza un valore testuale proveniente dal contesto.

        Supporta stringhe, dizionari con chiave ``value``, sequenze e
        altri valori convertibili in stringa.
        """

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

    def _contains_any(self, text, expressions):
        """
        Verifica se il testo contiene almeno una delle espressioni.
        """

        if not text:
            return False

        return any(expression in text for expression in expressions)

    def _format_number(self, value):
        """
        Formatta i numeri senza decimali inutili.
        """

        if value is None:
            return "N/D"

        if float(value).is_integer():
            return str(int(value))

        return f"{value:.1f}"