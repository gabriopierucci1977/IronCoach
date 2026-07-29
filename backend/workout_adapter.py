"""
IronCoach - Workout Adapter

Trasforma la decisione del Coach Engine in una proposta
concreta di allenamento modificato.

Il modulo non decide se confermare, adattare, ridurre
o recuperare: applica operativamente la strategia già
stabilita dal Coach Engine.
"""


class WorkoutAdapter:
    """
    Genera un allenamento modificato sulla base della
    strategia prodotta dal Coach Engine.
    """

    def adapt(self, context, decision):
        """
        Costruisce l'eventuale allenamento modificato.

        Args:
            context (dict): Contesto complessivo dell'atleta.
            decision (dict): Decisione prodotta dal Coach Engine.

        Returns:
            dict | None: Allenamento modificato oppure None
                quando il piano viene confermato.
        """

        context = context or {}
        decision = decision or {}

        training = context.get("training", {}) or {}

        strategy = str(
            decision.get("strategy", "")
        ).strip().upper()

        if strategy == "KEEP_PLAN":
            return None

        sport = self._get_text(
            training,
            "Sport",
            "sport",
        ) or "Attività aerobica"

        workout_name = self._get_text(
            training,
            "Nome seduta",
            "nome_seduta",
        ) or "Allenamento programmato"

        session_type = self._get_text(
            training,
            "Tipo seduta",
            "tipo_seduta",
        ) or "Allenamento"

        planned_zone = self._get_text(
            training,
            "Zona prevista",
            "zona_prevista",
        ) or "N/D"

        original_duration = self._get_number(
            training,
            "Durata minuti",
            "durata_minuti",
            "duration",
        )

        if strategy == "ADAPT":
            return self._build_adapted_workout(
                sport=sport,
                workout_name=workout_name,
                session_type=session_type,
                planned_zone=planned_zone,
                original_duration=original_duration,
            )

        if strategy == "REDUCE_LOAD":
            return self._build_reduced_workout(
                sport=sport,
                workout_name=workout_name,
                session_type=session_type,
                planned_zone=planned_zone,
                original_duration=original_duration,
            )

        if strategy == "RECOVERY":
            return self._build_recovery_workout(
                sport=sport,
                workout_name=workout_name,
            )

        return None

    # -------------------------------------------------
    # STRATEGIE
    # -------------------------------------------------

    def _build_adapted_workout(
        self,
        sport,
        workout_name,
        session_type,
        planned_zone,
        original_duration,
    ):
        """
        Mantiene lo stimolo allenante riducendo intensità
        e durata.
        """

        duration = self._calculate_duration(
            original_duration=original_duration,
            percentage=0.80,
            default_duration=45,
            minimum_duration=30,
        )

        warmup_duration = min(10, max(5, duration // 4))
        cooldown_duration = min(10, max(5, duration // 4))

        main_duration = max(
            10,
            duration - warmup_duration - cooldown_duration,
        )

        return {
            "strategy": "ADAPT",
            "original_workout": workout_name,
            "sport": sport,
            "original_type": session_type,
            "original_zone": planned_zone,
            "duration_minutes": duration,
            "intensity": "Z1-Z2",
            "warmup": (
                f"{warmup_duration}' progressivi in Z1"
            ),
            "main_set": (
                f"{main_duration}' in Z2 controllata, "
                "senza intervalli ad alta intensità"
            ),
            "cooldown": (
                f"{cooldown_duration}' facili in Z1"
            ),
            "notes": (
                "Seduta adattata: volume ridotto del 20% circa "
                "e intensità limitata al lavoro aerobico controllato."
            ),
        }

    def _build_reduced_workout(
        self,
        sport,
        workout_name,
        session_type,
        planned_zone,
        original_duration,
    ):
        """
        Riduce in modo significativo il carico previsto.
        """

        duration = self._calculate_duration(
            original_duration=original_duration,
            percentage=0.65,
            default_duration=40,
            minimum_duration=25,
        )

        warmup_duration = min(10, max(5, duration // 4))
        cooldown_duration = min(10, max(5, duration // 4))

        main_duration = max(
            10,
            duration - warmup_duration - cooldown_duration,
        )

        return {
            "strategy": "REDUCE_LOAD",
            "original_workout": workout_name,
            "sport": sport,
            "original_type": session_type,
            "original_zone": planned_zone,
            "duration_minutes": duration,
            "intensity": "Z1-Z2 facile",
            "warmup": (
                f"{warmup_duration}' molto facili in Z1"
            ),
            "main_set": (
                f"{main_duration}' aerobici facili tra Z1 e Z2"
            ),
            "cooldown": (
                f"{cooldown_duration}' di defaticamento in Z1"
            ),
            "notes": (
                "Carico ridotto del 35% circa. Eliminati lavori "
                "di soglia, VO2max, sprint e progressioni intense."
            ),
        }

    def _build_recovery_workout(
        self,
        sport,
        workout_name,
    ):
        """
        Genera una proposta esclusivamente rigenerante.
        """

        return {
            "strategy": "RECOVERY",
            "original_workout": workout_name,
            "sport": sport,
            "duration_minutes": 30,
            "intensity": "Z1 molto facile",
            "warmup": "5' molto facili",
            "main_set": "20' rigeneranti in Z1",
            "cooldown": "5' molto facili",
            "alternative": "Riposo completo",
            "notes": (
                "Nessun lavoro di qualità. Interrompere la seduta "
                "in presenza di dolore, peggioramento delle sensazioni "
                "o affaticamento anomalo."
            ),
        }

    # -------------------------------------------------
    # UTILITÀ
    # -------------------------------------------------

    def _calculate_duration(
        self,
        original_duration,
        percentage,
        default_duration,
        minimum_duration,
    ):
        """
        Calcola la nuova durata della seduta.
        """

        if original_duration is None or original_duration <= 0:
            return default_duration

        calculated_duration = round(
            original_duration * percentage
        )

        return max(minimum_duration, calculated_duration)

    def _get_value(self, data, *field_names):
        """
        Restituisce il primo valore disponibile.
        """

        if not isinstance(data, dict):
            return None

        for field_name in field_names:
            value = data.get(field_name)

            if value is not None and value != "":
                return value

        return None

    def _get_text(self, data, *field_names):
        """
        Estrae e normalizza un valore testuale.
        """

        value = self._get_value(data, *field_names)

        if value is None:
            return ""

        if isinstance(value, dict):
            value = value.get("value", "")

        return str(value).strip()

    def _get_number(self, data, *field_names):
        """
        Estrae e converte un valore numerico.

        Returns:
            float | None: Valore convertito oppure None.
        """

        value = self._get_value(data, *field_names)

        if value is None or isinstance(value, bool):
            return None

        if isinstance(value, dict):
            value = value.get("value")

        if isinstance(value, (int, float)):
            return float(value)

        try:
            normalized_value = (
                str(value)
                .strip()
                .replace(",", ".")
            )

            return float(normalized_value)

        except (TypeError, ValueError):
            return None