"""
IronCoach Recovery Analyzer v0.3.0

Analizzatore dedicato alla valutazione della disponibilità fisiologica
dell'atleta.

Questa prima versione è un'estrazione fedele della logica precedentemente
contenuta nel CoachEngine v3.

Obiettivi:

- separare la valutazione recovery dall'orchestrazione;
- mantenere invariato il comportamento decisionale;
- non introdurre nuove soglie o nuove interpretazioni;
- preparare il modulo per evoluzioni future.

Interfaccia pubblica:

    RecoveryAnalyzer().analyze(recovery)

Il metodo restituisce un dizionario compatibile con il formato attualmente
utilizzato dal CoachEngine.
"""


class RecoveryAnalyzer:
    """
    Valuta la disponibilità fisiologica dell'atleta.

    L'analizzatore non conosce Airtable e riceve esclusivamente un
    dizionario contenente dati recovery già raccolti e normalizzati,
    oppure parzialmente normalizzati.
    """

    RECOVERY_GREEN = "VERDE"
    RECOVERY_YELLOW = "GIALLO"
    RECOVERY_RED = "ROSSO"

    LEVEL_LOW = "LOW"
    LEVEL_MODERATE = "MODERATE"
    LEVEL_HIGH = "HIGH"
    LEVEL_CRITICAL = "CRITICAL"
    LEVEL_UNKNOWN = "UNKNOWN"

    def analyze(self, recovery):
        """
        Valuta la disponibilità fisiologica dell'atleta.

        La valutazione usa prioritariamente lo stato recovery già
        calcolato.

        Il Recovery Score e lo Sleep Score vengono utilizzati come
        informazioni di supporto.

        Args:
            recovery: dizionario contenente i dati recovery.

        Returns:
            dict: assessment strutturato e compatibile con CoachEngine.
        """

        recovery = recovery or {}

        recovery_state = self._normalized_text(
            recovery.get("Stato Recovery")
            or recovery.get("stato_recovery")
        ).upper()

        recovery_score = self._number(
            recovery.get("Recovery Score")
            or recovery.get("recovery_score")
        )

        sleep_score = self._number(
            recovery.get("Sleep Score")
            or recovery.get("sleep_score")
        )

        reasons = []

        if recovery_state == self.RECOVERY_RED:
            reasons.append("Recovery in stato ROSSO")

            if recovery_score is not None:
                reasons.append(
                    f"Recovery Score pari a "
                    f"{self._format_number(recovery_score)}"
                )

            if sleep_score is not None and sleep_score < 60:
                reasons.append(
                    f"Sleep Score basso: "
                    f"{self._format_number(sleep_score)}"
                )

            return self._result(
                state=recovery_state,
                level=self.LEVEL_CRITICAL,
                recovery_score=recovery_score,
                sleep_score=sleep_score,
                reasons=reasons,
            )

        if recovery_state == self.RECOVERY_YELLOW:
            reasons.append("Recovery in stato GIALLO")

            if recovery_score is not None:
                reasons.append(
                    f"Recovery Score pari a "
                    f"{self._format_number(recovery_score)}"
                )

            if sleep_score is not None and sleep_score < 65:
                reasons.append(
                    f"Sleep Score ridotto: "
                    f"{self._format_number(sleep_score)}"
                )

            return self._result(
                state=recovery_state,
                level=self.LEVEL_MODERATE,
                recovery_score=recovery_score,
                sleep_score=sleep_score,
                reasons=reasons,
            )

        if recovery_state == self.RECOVERY_GREEN:
            reasons.append("Recovery in stato VERDE")

            if recovery_score is not None:
                reasons.append(
                    f"Recovery Score pari a "
                    f"{self._format_number(recovery_score)}"
                )

            if sleep_score is not None and sleep_score < 60:
                reasons.append(
                    "Sleep Score basso nonostante recovery VERDE: "
                    f"{self._format_number(sleep_score)}"
                )

                return self._result(
                    state=recovery_state,
                    level=self.LEVEL_MODERATE,
                    recovery_score=recovery_score,
                    sleep_score=sleep_score,
                    reasons=reasons,
                )

            return self._result(
                state=recovery_state,
                level=self.LEVEL_LOW,
                recovery_score=recovery_score,
                sleep_score=sleep_score,
                reasons=reasons,
            )

        if recovery_score is not None:
            if recovery_score < 50:
                reasons.append(
                    "Stato recovery non disponibile, "
                    "ma Recovery Score critico"
                )

                return self._result(
                    state=recovery_state,
                    level=self.LEVEL_CRITICAL,
                    recovery_score=recovery_score,
                    sleep_score=sleep_score,
                    reasons=reasons,
                )

            if recovery_score < 70:
                reasons.append(
                    "Stato recovery non disponibile, "
                    "ma Recovery Score moderato"
                )

                return self._result(
                    state=recovery_state,
                    level=self.LEVEL_MODERATE,
                    recovery_score=recovery_score,
                    sleep_score=sleep_score,
                    reasons=reasons,
                )

            reasons.append(
                "Stato recovery non disponibile, "
                "ma Recovery Score favorevole"
            )

            return self._result(
                state=recovery_state,
                level=self.LEVEL_LOW,
                recovery_score=recovery_score,
                sleep_score=sleep_score,
                reasons=reasons,
            )

        reasons.append("Dati recovery insufficienti")

        return self._result(
            state=recovery_state,
            level=self.LEVEL_UNKNOWN,
            recovery_score=recovery_score,
            sleep_score=sleep_score,
            reasons=reasons,
        )

    def _result(
        self,
        state,
        level,
        recovery_score,
        sleep_score,
        reasons,
    ):
        """
        Costruisce il risultato dell'analisi in formato uniforme.
        """

        return {
            "state": state,
            "level": level,
            "score": recovery_score,
            "sleep_score": sleep_score,
            "reasons": reasons,
        }

    def _number(self, value):
        """
        Converte un valore numerico in float.

        Restituisce None quando il valore non è presente oppure
        non può essere convertito.
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

        Supporta:

        - stringhe;
        - dizionari contenenti una chiave ``value``;
        - liste, tuple e set;
        - valori numerici o altri oggetti convertibili in stringa.
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

    def _format_number(self, value):
        """
        Formatta i numeri senza decimali inutili.
        """

        if value is None:
            return "N/D"

        if float(value).is_integer():
            return str(int(value))

        return f"{value:.1f}"