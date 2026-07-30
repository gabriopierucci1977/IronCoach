"""
IronCoach Coach Engine v4

Motore di orchestrazione.

Responsabilità:
- raccogliere le valutazioni dai diversi analyzer;
- inviare gli assessment al DecisionEngine;
- mantenere invariata l'interfaccia pubblica:

    CoachEngine().evaluate(context)

Il metodo restituisce sempre un dizionario generato da Decision.
"""

from backend.engines.decision_engine import DecisionEngine


class CoachEngine:
    """
    Motore centrale di IronCoach.

    Gli analyzer producono valutazioni separate:

    - recovery readiness
    - training stress
    - injury risk
    - nutrition status

    Il DecisionEngine combina successivamente
    gli assessment e genera la decisione finale.
    """


    RECOVERY_GREEN = "VERDE"
    RECOVERY_YELLOW = "GIALLO"
    RECOVERY_RED = "ROSSO"


    LEVEL_LOW = "LOW"
    LEVEL_MODERATE = "MODERATE"
    LEVEL_HIGH = "HIGH"
    LEVEL_CRITICAL = "CRITICAL"
    LEVEL_UNKNOWN = "UNKNOWN"


    def __init__(self):

        self.decision_engine = DecisionEngine()


    def evaluate(self, context):

        """
        Valuta il contesto completo dell'atleta.

        Args:
            context:
                dizionario contenente:
                - recovery
                - training
                - nutrition

        Returns:
            dict:
                rappresentazione serializzata di Decision.
        """

        context = context or {}


        recovery = context.get(
            "recovery",
            {},
        ) or {}


        training = context.get(
            "training",
            {},
        ) or {}


        nutrition = context.get(
            "nutrition",
            {},
        ) or {}


        recovery_assessment = self._assess_recovery(
            recovery
        )


        training_assessment = self._assess_training(
            training
        )


        injury_assessment = self._assess_injury(
            training
        )


        nutrition_assessment = self._assess_nutrition(
            nutrition
        )


        assessments = {
            "recovery": recovery_assessment,
            "training": training_assessment,
            "injury": injury_assessment,
            "nutrition": nutrition_assessment,
        }


        return self.decision_engine.decide(
            assessments
        )

    def _assess_recovery(self, recovery):

        """
        Valuta la disponibilità fisiologica dell'atleta.

        Usa:
        - Stato Recovery
        - Recovery Score
        - Sleep Score
        """

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

            reasons.append(
                "Recovery in stato ROSSO"
            )


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


            return {
                "state": recovery_state,
                "level": self.LEVEL_CRITICAL,
                "score": recovery_score,
                "sleep_score": sleep_score,
                "reasons": reasons,
            }



        if recovery_state == self.RECOVERY_YELLOW:

            reasons.append(
                "Recovery in stato GIALLO"
            )


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


            return {
                "state": recovery_state,
                "level": self.LEVEL_MODERATE,
                "score": recovery_score,
                "sleep_score": sleep_score,
                "reasons": reasons,
            }



        if recovery_state == self.RECOVERY_GREEN:

            reasons.append(
                "Recovery in stato VERDE"
            )


            if recovery_score is not None:

                reasons.append(
                    f"Recovery Score pari a "
                    f"{self._format_number(recovery_score)}"
                )


            if sleep_score is not None and sleep_score < 60:

                reasons.append(
                    "Sleep Score basso nonostante "
                    "recovery VERDE: "
                    f"{self._format_number(sleep_score)}"
                )


                return {
                    "state": recovery_state,
                    "level": self.LEVEL_MODERATE,
                    "score": recovery_score,
                    "sleep_score": sleep_score,
                    "reasons": reasons,
                }


            return {
                "state": recovery_state,
                "level": self.LEVEL_LOW,
                "score": recovery_score,
                "sleep_score": sleep_score,
                "reasons": reasons,
            }



        if recovery_score is not None:

            if recovery_score < 50:

                reasons.append(
                    "Stato recovery non disponibile, "
                    "ma Recovery Score critico"
                )


                return {
                    "state": recovery_state,
                    "level": self.LEVEL_CRITICAL,
                    "score": recovery_score,
                    "sleep_score": sleep_score,
                    "reasons": reasons,
                }



            if recovery_score < 70:

                reasons.append(
                    "Stato recovery non disponibile, "
                    "ma Recovery Score moderato"
                )


                return {
                    "state": recovery_state,
                    "level": self.LEVEL_MODERATE,
                    "score": recovery_score,
                    "sleep_score": sleep_score,
                    "reasons": reasons,
                }


            reasons.append(
                "Stato recovery non disponibile, "
                "ma Recovery Score favorevole"
            )


            return {
                "state": recovery_state,
                "level": self.LEVEL_LOW,
                "score": recovery_score,
                "sleep_score": sleep_score,
                "reasons": reasons,
            }

    def _assess_training(self, training):

        """
        Valuta lo stress prodotto dall'ultima seduta.

        Considera:

        - RPE
        - tipo seduta
        - zona prevista
        - durata
        - carico interno
        """

        rpe = self._number(
            training.get("RPE percepito")
            or training.get("RPE")
            or training.get("rpe")
        )


        session_type = self._normalized_text(
            training.get("Tipo seduta")
            or training.get("tipo_seduta")
        ).lower()


        planned_zone = self._normalized_text(
            training.get("Zona prevista")
            or training.get("zona_prevista")
        ).lower()


        duration_minutes = self._number(
            training.get("Durata minuti")
            or training.get("durata_minuti")
        )


        internal_load = self._number(
            training.get("Carico interno")
            or training.get("carico_interno")
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
                f"RPE ultima seduta: "
                f"{self._format_number(rpe)}"
            )


        if high_intensity_session:

            reasons.append(
                "Ultima seduta classificata ad alta intensità"
            )


        if high_intensity_zone:

            reasons.append(
                "Zona prevista ad alta intensità"
            )


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

            return {
                "level": self.LEVEL_HIGH,
                "rpe": rpe,
                "session_type": session_type,
                "planned_zone": planned_zone,
                "duration_minutes": duration_minutes,
                "internal_load": internal_load,
                "reasons": reasons,
            }


        if (
            rpe is not None
            and rpe >= 8
            and (
                high_intensity_session
                or high_intensity_zone
            )
        ):

            return {
                "level": self.LEVEL_HIGH,
                "rpe": rpe,
                "session_type": session_type,
                "planned_zone": planned_zone,
                "duration_minutes": duration_minutes,
                "internal_load": internal_load,
                "reasons": reasons,
            }


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


        if moderate_factors >= 1:

            level = self.LEVEL_MODERATE


        elif (
            rpe is None
            and not session_type
            and not planned_zone
            and duration_minutes is None
            and internal_load is None
        ):

            level = self.LEVEL_UNKNOWN

            reasons.append(
                "Dati sul carico allenante insufficienti"
            )


        else:

            level = self.LEVEL_LOW


        return {
            "level": level,
            "rpe": rpe,
            "session_type": session_type,
            "planned_zone": planned_zone,
            "duration_minutes": duration_minutes,
            "internal_load": internal_load,
            "reasons": reasons,
        }

    def _assess_injury(self, training):

        """
        Valuta il rischio legato a dolori o problematiche segnalate.
        """

        problem = self._normalized_text(
            training.get("Dolori/problematiche")
            or training.get("dolori_problematiche")
            or training.get("Dolori")
        ).lower()


        reasons = []


        if not problem:

            reasons.append(
                "Nessuna informazione disponibile "
                "su dolori o problemi"
            )


            return {
                "level": self.LEVEL_UNKNOWN,
                "problem": problem,
                "reasons": reasons,
            }


        no_problem_expressions = (
            "nessun dolore",
            "nessun problema",
            "nessuna problematica",
            "nessun fastidio",
            "nessuno",
            "no dolore",
            "no problemi",
            "assente",
        )


        if self._contains_any(
            problem,
            no_problem_expressions,
        ):

            reasons.append(
                "Nessun dolore o problema segnalato"
            )


            return {
                "level": self.LEVEL_LOW,
                "problem": problem,
                "reasons": reasons,
            }


        critical_expressions = (
            "forte",
            "acuto",
            "zoppia",
            "gonfiore",
            "impossibile",
            "blocco",
            "peggioramento",
            "lesione",
        )


        moderate_expressions = (
            "dolore",
            "fastidio",
            "tendine",
            "tendineo",
            "muscolare",
            "contrattura",
            "rigidità",
            "infiammazione",
            "problema",
        )


        if self._contains_any(
            problem,
            critical_expressions,
        ):

            reasons.append(
                f"Problematica critica segnalata: {problem}"
            )


            return {
                "level": self.LEVEL_CRITICAL,
                "problem": problem,
                "reasons": reasons,
            }


        if self._contains_any(
            problem,
            moderate_expressions,
        ):

            reasons.append(
                f"Problematica fisica segnalata: {problem}"
            )


            return {
                "level": self.LEVEL_HIGH,
                "problem": problem,
                "reasons": reasons,
            }


        reasons.append(
            f"Segnalazione fisica da monitorare: {problem}"
        )


        return {
            "level": self.LEVEL_MODERATE,
            "problem": problem,
            "reasons": reasons,
        }



    def _assess_nutrition(self, nutrition):

        """
        Valuta il recupero nutrizionale e l'idratazione.
        """

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


        reasons = []


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
                f"Recupero nutrizionale: "
                f"{recovery_status.upper()}"
            )


        if hydration_status:

            reasons.append(
                f"Idratazione: "
                f"{hydration_status.upper()}"
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

            reasons.append(
                "Dati nutrizionali insufficienti"
            )


        return {
            "level": level,
            "recovery_status": recovery_status,
            "hydration_status": hydration_status,
            "carbohydrate_status": carbohydrate_status,
            "reasons": reasons,
        }

    def _number(self, value):

        """
        Converte un valore numerico in float.

        Restituisce None quando il valore
        non è presente o non è valido.
        """

        if value is None:

            return None


        if isinstance(value, str):

            cleaned_value = (
                value
                .strip()
                .replace(",", ".")
            )


            if not cleaned_value:

                return None


            value = cleaned_value


        try:

            return float(value)


        except (
            TypeError,
            ValueError,
        ):

            return None



    def _normalized_text(self, value):

        """
        Normalizza un valore testuale proveniente da Airtable.
        """

        if value is None:

            return ""


        if isinstance(value, dict):

            generated_value = value.get(
                "value"
            )


            if generated_value is not None:

                return str(
                    generated_value
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
                str(item).strip()
                for item in value
                if item is not None
            ).strip()


        return str(value).strip()



    def _contains_any(
        self,
        text,
        expressions,
    ):

        """
        Verifica se il testo contiene
        almeno una delle espressioni indicate.
        """

        if not text:

            return False


        return any(
            expression in text
            for expression in expressions
        )



    def _format_number(self, value):

        """
        Formatta i numeri senza decimali inutili.
        """

        if value is None:

            return "N/D"


        if float(value).is_integer():

            return str(
                int(value)
            )


        return f"{value:.1f}"
