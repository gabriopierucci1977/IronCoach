"""
IronCoach - Workout Adapter

Trasforma la decisione del Coach Engine in una proposta
concreta di allenamento modificato.

Il modulo non decide se confermare, adattare, ridurre
o recuperare: applica operativamente la strategia già
stabilita dal Coach Engine.

Le proposte vengono generate in modo specifico per:

- corsa;
- ciclismo;
- nuoto;
- attività generica.
"""

import unicodedata


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

        strategy = self._normalize_text(
            decision.get("strategy", "")
        ).upper()

        if strategy == "KEEP_PLAN":
            return None

        sport = self._get_text(
            training,
            "Sport",
            "sport",
        ) or "Attività aerobica"

        sport_category = self._classify_sport(sport)

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

        workout_data = {
            "sport": sport,
            "sport_category": sport_category,
            "workout_name": workout_name,
            "session_type": session_type,
            "planned_zone": planned_zone,
            "original_duration": original_duration,
        }

        if strategy == "ADAPT":
            return self._build_adapted_workout(
                **workout_data
            )

        if strategy == "REDUCE_LOAD":
            return self._build_reduced_workout(
                **workout_data
            )

        if strategy == "RECOVERY":
            return self._build_recovery_workout(
                **workout_data
            )

        return None

    # -------------------------------------------------
    # DISTRIBUZIONE DELLE STRATEGIE
    # -------------------------------------------------

    def _build_adapted_workout(
        self,
        sport,
        sport_category,
        workout_name,
        session_type,
        planned_zone,
        original_duration,
    ):
        """
        Mantiene parte dello stimolo allenante riducendo
        intensità, volume o complessità della seduta.
        """

        duration = self._calculate_duration(
            original_duration=original_duration,
            percentage=0.80,
            default_duration=45,
            minimum_duration=30,
        )

        common_data = self._build_common_data(
            strategy="ADAPT",
            sport=sport,
            sport_category=sport_category,
            workout_name=workout_name,
            session_type=session_type,
            planned_zone=planned_zone,
            original_duration=original_duration,
            duration=duration,
        )

        if sport_category == "RUN":
            workout = self._build_run_adapted(duration)

        elif sport_category == "BIKE":
            workout = self._build_bike_adapted(duration)

        elif sport_category == "SWIM":
            workout = self._build_swim_adapted(duration)

        else:
            workout = self._build_generic_adapted(duration)

        return {
            **common_data,
            **workout,
        }

    def _build_reduced_workout(
        self,
        sport,
        sport_category,
        workout_name,
        session_type,
        planned_zone,
        original_duration,
    ):
        """
        Riduce in modo significativo il carico previsto,
        mantenendo soltanto lavoro facile e controllato.
        """

        duration = self._calculate_duration(
            original_duration=original_duration,
            percentage=0.65,
            default_duration=40,
            minimum_duration=25,
        )

        common_data = self._build_common_data(
            strategy="REDUCE_LOAD",
            sport=sport,
            sport_category=sport_category,
            workout_name=workout_name,
            session_type=session_type,
            planned_zone=planned_zone,
            original_duration=original_duration,
            duration=duration,
        )

        if sport_category == "RUN":
            workout = self._build_run_reduced(duration)

        elif sport_category == "BIKE":
            workout = self._build_bike_reduced(duration)

        elif sport_category == "SWIM":
            workout = self._build_swim_reduced(duration)

        else:
            workout = self._build_generic_reduced(duration)

        return {
            **common_data,
            **workout,
        }

    def _build_recovery_workout(
        self,
        sport,
        sport_category,
        workout_name,
        session_type,
        planned_zone,
        original_duration,
    ):
        """
        Genera una proposta esclusivamente rigenerante,
        specifica per lo sport rilevato.
        """

        duration = self._calculate_recovery_duration(
            original_duration
        )

        common_data = self._build_common_data(
            strategy="RECOVERY",
            sport=sport,
            sport_category=sport_category,
            workout_name=workout_name,
            session_type=session_type,
            planned_zone=planned_zone,
            original_duration=original_duration,
            duration=duration,
        )

        if sport_category == "RUN":
            workout = self._build_run_recovery(duration)

        elif sport_category == "BIKE":
            workout = self._build_bike_recovery(duration)

        elif sport_category == "SWIM":
            workout = self._build_swim_recovery(duration)

        else:
            workout = self._build_generic_recovery(duration)

        return {
            **common_data,
            **workout,
        }

    # -------------------------------------------------
    # CORSA
    # -------------------------------------------------

    def _build_run_adapted(self, duration):
        """
        Seduta di corsa adattata.

        Rimuove il lavoro ad alta intensità e mantiene
        una corsa aerobica controllata.
        """

        warmup_duration, main_duration, cooldown_duration = (
            self._split_duration(
                duration=duration,
                warmup_target=10,
                cooldown_target=8,
                minimum_main=12,
            )
        )

        return {
            "intensity": "Z1-Z2",
            "warmup": (
                f"{warmup_duration}' di corsa facile "
                "con progressione graduale da Z1 a Z2"
            ),
            "main_set": (
                f"{main_duration}' di corsa aerobica continua "
                "in Z2 controllata"
            ),
            "cooldown": (
                f"{cooldown_duration}' di corsa molto facile "
                "in Z1"
            ),
            "technical_focus": (
                "Passo regolare, appoggio rilassato e cadenza naturale"
            ),
            "removed_elements": (
                "Ripetute intense, sprint, salite impegnative "
                "e lavoro in Z4-Z5"
            ),
            "notes": (
                "Seduta di corsa adattata: volume ridotto del 20% "
                "circa e intensità limitata al lavoro aerobico. "
                "Non forzare il ritmo in presenza di rigidità o dolore."
            ),
        }

    def _build_run_reduced(self, duration):
        """
        Seduta di corsa con carico fortemente ridotto.
        """

        warmup_duration, main_duration, cooldown_duration = (
            self._split_duration(
                duration=duration,
                warmup_target=8,
                cooldown_target=7,
                minimum_main=10,
            )
        )

        return {
            "intensity": "Z1-Z2 facile",
            "warmup": (
                f"{warmup_duration}' alternando camminata attiva "
                "e corsa molto facile"
            ),
            "main_set": (
                f"{main_duration}' di corsa facile in Z1-Z2, "
                "senza variazioni di ritmo"
            ),
            "cooldown": (
                f"{cooldown_duration}' di corsa molto facile "
                "o camminata"
            ),
            "technical_focus": (
                "Movimento fluido, rilassato e senza ricerca della velocità"
            ),
            "removed_elements": (
                "Qualsiasi lavoro di soglia, VO2max, sprint, "
                "progressivo o salita intensa"
            ),
            "notes": (
                "Carico di corsa ridotto del 35% circa. "
                "La seduta deve rimanere completamente controllata. "
                "Interrompere in caso di aumento del dolore."
            ),
        }

    def _build_run_recovery(self, duration):
        """
        Proposta rigenerante per la corsa.
        """

        warmup_duration, main_duration, cooldown_duration = (
            self._split_duration(
                duration=duration,
                warmup_target=5,
                cooldown_target=5,
                minimum_main=10,
            )
        )

        return {
            "intensity": "Z1 molto facile",
            "warmup": (
                f"{warmup_duration}' di camminata attiva "
                "o corsa molto lenta"
            ),
            "main_set": (
                f"{main_duration}' di corsa rigenerante in Z1, "
                "eventualmente alternata a camminata"
            ),
            "cooldown": (
                f"{cooldown_duration}' di camminata rilassata"
            ),
            "technical_focus": (
                "Rilassamento muscolare e assenza di tensioni"
            ),
            "alternative": (
                "Riposo completo oppure camminata facile"
            ),
            "notes": (
                "Nessun lavoro di qualità. La corsa è facoltativa "
                "e deve essere sostituita dal riposo completo in presenza "
                "di dolore, zoppia o peggioramento delle sensazioni."
            ),
        }

    # -------------------------------------------------
    # CICLISMO
    # -------------------------------------------------

    def _build_bike_adapted(self, duration):
        """
        Seduta di ciclismo adattata.

        Mantiene lavoro aerobico con cadenza fluida,
        eliminando intervalli intensi.
        """

        warmup_duration, main_duration, cooldown_duration = (
            self._split_duration(
                duration=duration,
                warmup_target=12,
                cooldown_target=8,
                minimum_main=15,
            )
        )

        return {
            "intensity": "Z1-Z2",
            "warmup": (
                f"{warmup_duration}' di pedalata progressiva "
                "da Z1 a Z2"
            ),
            "main_set": (
                f"{main_duration}' continui in Z2 bassa, "
                "con cadenza agile e pressione costante sui pedali"
            ),
            "cooldown": (
                f"{cooldown_duration}' di pedalata facile in Z1"
            ),
            "technical_focus": (
                "Cadenza fluida indicativamente tra 85 e 95 rpm"
            ),
            "removed_elements": (
                "Intervalli VO2max, soglia, sprint, forza a bassa cadenza "
                "e salite impegnative"
            ),
            "notes": (
                "Seduta ciclistica adattata: volume ridotto del 20% "
                "circa e intensità limitata al lavoro aerobico controllato."
            ),
        }

    def _build_bike_reduced(self, duration):
        """
        Seduta ciclistica con carico fortemente ridotto.
        """

        warmup_duration, main_duration, cooldown_duration = (
            self._split_duration(
                duration=duration,
                warmup_target=10,
                cooldown_target=8,
                minimum_main=10,
            )
        )

        return {
            "intensity": "Z1-Z2 facile",
            "warmup": (
                f"{warmup_duration}' di pedalata molto facile in Z1"
            ),
            "main_set": (
                f"{main_duration}' in Z1-Z2 bassa, "
                "preferibilmente su percorso pianeggiante o rulli"
            ),
            "cooldown": (
                f"{cooldown_duration}' molto facili con cadenza libera"
            ),
            "technical_focus": (
                "Pedalata rotonda, rapporto agile e bassa tensione muscolare"
            ),
            "removed_elements": (
                "Soglia, VO2max, sprint, lavori di forza, "
                "salite e cambi di ritmo"
            ),
            "notes": (
                "Carico ciclistico ridotto del 35% circa. "
                "Mantenere una percezione dello sforzo molto bassa "
                "e non inseguire potenza o velocità."
            ),
        }

    def _build_bike_recovery(self, duration):
        """
        Proposta rigenerante per il ciclismo.
        """

        warmup_duration, main_duration, cooldown_duration = (
            self._split_duration(
                duration=duration,
                warmup_target=5,
                cooldown_target=5,
                minimum_main=10,
            )
        )

        return {
            "intensity": "Z1 molto facile",
            "warmup": (
                f"{warmup_duration}' di pedalata estremamente facile"
            ),
            "main_set": (
                f"{main_duration}' rigeneranti in Z1, "
                "con rapporto agile e senza pressione sui pedali"
            ),
            "cooldown": (
                f"{cooldown_duration}' molto facili"
            ),
            "technical_focus": (
                "Cadenza confortevole e completa assenza di affaticamento"
            ),
            "alternative": (
                "Riposo completo oppure mobilità leggera"
            ),
            "notes": (
                "Nessun lavoro di qualità o forza. "
                "La seduta deve favorire il recupero e non produrre "
                "ulteriore fatica."
            ),
        }

    # -------------------------------------------------
    # NUOTO
    # -------------------------------------------------

    def _build_swim_adapted(self, duration):
        """
        Seduta di nuoto adattata.

        Mantiene tecnica e continuità aerobica eliminando
        lavori intensi e partenze massimali.
        """

        warmup_duration, main_duration, cooldown_duration = (
            self._split_duration(
                duration=duration,
                warmup_target=10,
                cooldown_target=8,
                minimum_main=12,
            )
        )

        return {
            "intensity": "Facile-aerobica",
            "warmup": (
                f"{warmup_duration}' di nuoto facile alternando "
                "stile libero e dorso"
            ),
            "main_set": (
                f"{main_duration}' di lavoro aerobico regolare, "
                "con pause brevi e ritmo sempre controllato"
            ),
            "cooldown": (
                f"{cooldown_duration}' di nuoto molto facile"
            ),
            "technical_focus": (
                "Assetto, presa sull'acqua, respirazione regolare "
                "e qualità della bracciata"
            ),
            "removed_elements": (
                "Serie massimali, sprint, partenze forti, "
                "palette impegnative e lavoro anaerobico"
            ),
            "notes": (
                "Seduta di nuoto adattata: volume ridotto del 20% circa. "
                "Privilegiare tecnica ed economia del gesto senza cercare "
                "ritmi elevati."
            ),
        }

    def _build_swim_reduced(self, duration):
        """
        Seduta di nuoto con carico fortemente ridotto.
        """

        warmup_duration, main_duration, cooldown_duration = (
            self._split_duration(
                duration=duration,
                warmup_target=8,
                cooldown_target=7,
                minimum_main=10,
            )
        )

        return {
            "intensity": "Molto facile",
            "warmup": (
                f"{warmup_duration}' di nuoto sciolto "
                "con ampio recupero"
            ),
            "main_set": (
                f"{main_duration}' di tecnica e nuoto aerobico facile, "
                "interrompendo le ripetizioni prima della fatica"
            ),
            "cooldown": (
                f"{cooldown_duration}' di nuoto rilassato"
            ),
            "technical_focus": (
                "Scivolamento, rilassamento e controllo respiratorio"
            ),
            "removed_elements": (
                "Soglia, CSS intenso, sprint, palette pesanti "
                "e serie con recupero ridotto"
            ),
            "notes": (
                "Carico di nuoto ridotto del 35% circa. "
                "Le pause possono essere aumentate per mantenere "
                "la tecnica sempre pulita."
            ),
        }

    def _build_swim_recovery(self, duration):
        """
        Proposta rigenerante per il nuoto.
        """

        warmup_duration, main_duration, cooldown_duration = (
            self._split_duration(
                duration=duration,
                warmup_target=5,
                cooldown_target=5,
                minimum_main=10,
            )
        )

        return {
            "intensity": "Rigenerante",
            "warmup": (
                f"{warmup_duration}' di nuoto libero molto facile"
            ),
            "main_set": (
                f"{main_duration}' di nuoto sciolto e tecnica leggera, "
                "con recuperi completi"
            ),
            "cooldown": (
                f"{cooldown_duration}' rilassati a scelta"
            ),
            "technical_focus": (
                "Respirazione, mobilità e sensazioni positive in acqua"
            ),
            "alternative": (
                "Riposo completo oppure mobilità fuori dall'acqua"
            ),
            "notes": (
                "Nessun lavoro cronometrato o ad alta intensità. "
                "Evitare palette e strumenti che aumentano il carico "
                "muscolare."
            ),
        }

    # -------------------------------------------------
    # ATTIVITÀ GENERICA
    # -------------------------------------------------

    def _build_generic_adapted(self, duration):
        """
        Adattamento utilizzato quando lo sport non viene
        riconosciuto.
        """

        warmup_duration, main_duration, cooldown_duration = (
            self._split_duration(
                duration=duration,
                warmup_target=10,
                cooldown_target=10,
                minimum_main=10,
            )
        )

        return {
            "intensity": "Z1-Z2",
            "warmup": (
                f"{warmup_duration}' progressivi in Z1"
            ),
            "main_set": (
                f"{main_duration}' di lavoro aerobico controllato "
                "in Z2"
            ),
            "cooldown": (
                f"{cooldown_duration}' facili in Z1"
            ),
            "technical_focus": (
                "Movimento fluido e intensità costante"
            ),
            "removed_elements": (
                "Intervalli ad alta intensità e lavoro massimale"
            ),
            "notes": (
                "Seduta adattata: volume ridotto del 20% circa "
                "e intensità limitata al lavoro aerobico controllato."
            ),
        }

    def _build_generic_reduced(self, duration):
        """
        Riduzione generica del carico.
        """

        warmup_duration, main_duration, cooldown_duration = (
            self._split_duration(
                duration=duration,
                warmup_target=8,
                cooldown_target=8,
                minimum_main=9,
            )
        )

        return {
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
            "technical_focus": (
                "Controllo del gesto e bassa percezione dello sforzo"
            ),
            "removed_elements": (
                "Soglia, VO2max, sprint e progressioni intense"
            ),
            "notes": (
                "Carico ridotto del 35% circa. "
                "Mantenere tutta la seduta a intensità facile."
            ),
        }

    def _build_generic_recovery(self, duration):
        """
        Recupero generico.
        """

        warmup_duration, main_duration, cooldown_duration = (
            self._split_duration(
                duration=duration,
                warmup_target=5,
                cooldown_target=5,
                minimum_main=10,
            )
        )

        return {
            "intensity": "Z1 molto facile",
            "warmup": (
                f"{warmup_duration}' molto facili"
            ),
            "main_set": (
                f"{main_duration}' rigeneranti in Z1"
            ),
            "cooldown": (
                f"{cooldown_duration}' molto facili"
            ),
            "technical_focus": (
                "Rilassamento e recupero attivo"
            ),
            "alternative": (
                "Riposo completo"
            ),
            "notes": (
                "Nessun lavoro di qualità. Interrompere la seduta "
                "in presenza di dolore o peggioramento delle sensazioni."
            ),
        }

    # -------------------------------------------------
    # DATI COMUNI
    # -------------------------------------------------

    def _build_common_data(
        self,
        strategy,
        sport,
        sport_category,
        workout_name,
        session_type,
        planned_zone,
        original_duration,
        duration,
    ):
        """
        Costruisce i dati comuni a tutte le proposte.
        """

        original_duration_value = None

        if original_duration is not None:
            original_duration_value = round(
                original_duration,
                1,
            )

        return {
            "strategy": strategy,
            "original_workout": workout_name,
            "sport": sport,
            "sport_category": sport_category,
            "original_type": session_type,
            "original_zone": planned_zone,
            "original_duration_minutes": original_duration_value,
            "duration_minutes": duration,
        }

    # -------------------------------------------------
    # CLASSIFICAZIONE SPORT
    # -------------------------------------------------

    def _classify_sport(self, sport):
        """
        Classifica il valore dello sport in una categoria
        interna stabile.

        Returns:
            str: RUN, BIKE, SWIM oppure GENERIC.
        """

        normalized_sport = self._normalize_text(
            sport
        ).lower()

        run_keywords = (
            "corsa",
            "run",
            "running",
            "trail",
            "jogging",
        )

        bike_keywords = (
            "bici",
            "bike",
            "cycling",
            "ciclismo",
            "ciclist",
            "mtb",
            "mountain bike",
            "rulli",
            "indoor cycling",
        )

        swim_keywords = (
            "nuoto",
            "swim",
            "swimming",
            "piscina",
            "acque libere",
            "open water",
        )

        if any(
            keyword in normalized_sport
            for keyword in run_keywords
        ):
            return "RUN"

        if any(
            keyword in normalized_sport
            for keyword in bike_keywords
        ):
            return "BIKE"

        if any(
            keyword in normalized_sport
            for keyword in swim_keywords
        ):
            return "SWIM"

        return "GENERIC"

    # -------------------------------------------------
    # DURATE
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

        if (
            original_duration is None
            or original_duration <= 0
        ):
            return int(default_duration)

        calculated_duration = round(
            original_duration * percentage
        )

        return int(
            max(
                minimum_duration,
                calculated_duration,
            )
        )

    def _calculate_recovery_duration(
        self,
        original_duration,
    ):
        """
        Calcola la durata di una seduta rigenerante.

        La durata viene limitata per evitare che una seduta
        di recupero diventi troppo lunga.
        """

        if (
            original_duration is None
            or original_duration <= 0
        ):
            return 30

        calculated_duration = round(
            original_duration * 0.50
        )

        return int(
            min(
                40,
                max(
                    20,
                    calculated_duration,
                ),
            )
        )

    def _split_duration(
        self,
        duration,
        warmup_target,
        cooldown_target,
        minimum_main,
    ):
        """
        Divide la durata totale tra riscaldamento,
        parte centrale e defaticamento.

        Garantisce che la somma delle tre parti sia
        uguale alla durata totale.
        """

        duration = int(
            max(
                1,
                duration,
            )
        )

        warmup_duration = min(
            int(warmup_target),
            max(
                3,
                duration // 4,
            ),
        )

        cooldown_duration = min(
            int(cooldown_target),
            max(
                3,
                duration // 5,
            ),
        )

        main_duration = (
            duration
            - warmup_duration
            - cooldown_duration
        )

        if main_duration < minimum_main:
            missing_minutes = (
                minimum_main
                - main_duration
            )

            reducible_warmup = max(
                0,
                warmup_duration - 3,
            )

            reduction = min(
                missing_minutes,
                reducible_warmup,
            )

            warmup_duration -= reduction
            main_duration += reduction
            missing_minutes -= reduction

            reducible_cooldown = max(
                0,
                cooldown_duration - 3,
            )

            reduction = min(
                missing_minutes,
                reducible_cooldown,
            )

            cooldown_duration -= reduction
            main_duration += reduction

        main_duration = max(
            1,
            duration
            - warmup_duration
            - cooldown_duration,
        )

        return (
            warmup_duration,
            main_duration,
            cooldown_duration,
        )

    # -------------------------------------------------
    # ESTRAZIONE E NORMALIZZAZIONE
    # -------------------------------------------------

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

        value = self._get_value(
            data,
            *field_names,
        )

        if value is None:
            return ""

        if isinstance(value, dict):
            value = value.get(
                "value",
                "",
            )

        return str(value).strip()

    def _get_number(self, data, *field_names):
        """
        Estrae e converte un valore numerico.

        Returns:
            float | None: Valore convertito oppure None.
        """

        value = self._get_value(
            data,
            *field_names,
        )

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

    def _normalize_text(self, value):
        """
        Normalizza il testo rimuovendo spazi superflui
        e segni diacritici.

        Esempio:
            "Ciclismo" -> "Ciclismo"
            "attività" -> "attivita"
        """

        if value is None:
            return ""

        if isinstance(value, dict):
            value = value.get(
                "value",
                "",
            )

        text = str(value).strip()

        normalized_text = unicodedata.normalize(
            "NFKD",
            text,
        )

        normalized_text = "".join(
            character
            for character in normalized_text
            if not unicodedata.combining(character)
        )

        return " ".join(
            normalized_text.split()
        )