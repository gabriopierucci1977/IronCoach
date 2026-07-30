"""
IronCoach Injury Analyzer v0.3.1

Analizzatore dedicato alla valutazione del rischio fisico associato
a dolori, fastidi, affaticamento o problematiche segnalate dall'atleta.

Il modello combina:

- descrizione del sintomo;
- tipologia del sintomo;
- Pain Score espresso su scala 0-10;
- presenza di segnali clinici di allarme.

Il metodo pubblico è:

    InjuryAnalyzer().analyze(training)

Il risultato rimane compatibile con il CoachEngine e include anche
informazioni aggiuntive utili per reasoning, test e sviluppi futuri.
"""

import re


class InjuryAnalyzer:
    """
    Valuta il rischio fisico partendo dai dati dell'ultima seduta.

    L'analizzatore non conosce Airtable e riceve esclusivamente
    un dizionario contenente i dati dell'allenamento.
    """

    LEVEL_LOW = "LOW"
    LEVEL_MODERATE = "MODERATE"
    LEVEL_HIGH = "HIGH"
    LEVEL_CRITICAL = "CRITICAL"
    LEVEL_UNKNOWN = "UNKNOWN"

    TYPE_NONE = "NONE"
    TYPE_FATIGUE = "FATIGUE"
    TYPE_MUSCLE = "MUSCLE"
    TYPE_TENDON = "TENDON"
    TYPE_JOINT = "JOINT"
    TYPE_PAIN = "PAIN"
    TYPE_CLINICAL = "CLINICAL"
    TYPE_UNKNOWN = "UNKNOWN"

    INTENSITY_NONE = "NONE"
    INTENSITY_VERY_LOW = "VERY_LOW"
    INTENSITY_LOW = "LOW"
    INTENSITY_MODERATE = "MODERATE"
    INTENSITY_HIGH = "HIGH"
    INTENSITY_CRITICAL = "CRITICAL"
    INTENSITY_UNKNOWN = "UNKNOWN"

    def analyze(self, training):
        """
        Analizza dolori e problematiche riportati dall'atleta.

        Args:
            training: dizionario contenente i dati dell'ultima seduta.

        Returns:
            dict: valutazione strutturata del rischio fisico.
        """

        training = training or {}

        problem = self._normalized_text(
            training.get("Dolori/problematiche")
            or training.get("dolori_problematiche")
            or training.get("Dolori")
            or training.get("dolori")
        ).lower()

        if not problem:
            return self._result(
                level=self.LEVEL_UNKNOWN,
                problem="",
                symptom_type=self.TYPE_UNKNOWN,
                pain_score=None,
                intensity=self.INTENSITY_UNKNOWN,
                safety_override=False,
                reasons=[
                    "Nessuna informazione disponibile su dolori o problemi"
                ],
            )

        if self._is_no_problem(problem):
            return self._result(
                level=self.LEVEL_LOW,
                problem=problem,
                symptom_type=self.TYPE_NONE,
                pain_score=0.0,
                intensity=self.INTENSITY_NONE,
                safety_override=False,
                reasons=[
                    "Nessun dolore o problema fisico segnalato"
                ],
            )

        pain_score = self._extract_pain_score(problem)
        symptom_type = self._classify_symptom(problem)
        intensity = self._classify_intensity(pain_score)

        if symptom_type == self.TYPE_CLINICAL:
            return self._result(
                level=self.LEVEL_CRITICAL,
                problem=problem,
                symptom_type=symptom_type,
                pain_score=pain_score,
                intensity=(
                    intensity
                    if pain_score is not None
                    else self.INTENSITY_CRITICAL
                ),
                safety_override=True,
                reasons=self._build_reasons(
                    problem=problem,
                    symptom_type=symptom_type,
                    pain_score=pain_score,
                    level=self.LEVEL_CRITICAL,
                    clinical_override=True,
                ),
            )

        level = self._calculate_risk_level(
            symptom_type=symptom_type,
            pain_score=pain_score,
            problem=problem,
        )

        return self._result(
            level=level,
            problem=problem,
            symptom_type=symptom_type,
            pain_score=pain_score,
            intensity=intensity,
            safety_override=False,
            reasons=self._build_reasons(
                problem=problem,
                symptom_type=symptom_type,
                pain_score=pain_score,
                level=level,
                clinical_override=False,
            ),
        )

    def _is_no_problem(self, problem):
        """
        Riconosce le espressioni che indicano assenza di problemi.
        """

        no_problem_expressions = (
            "nessun dolore",
            "nessun problema",
            "nessuna problematica",
            "nessun fastidio",
            "nessun disturbo",
            "nessun sintomo",
            "no dolore",
            "no problemi",
            "dolore assente",
            "problema assente",
            "nessuno",
            "assente",
        )

        return self._contains_any(problem, no_problem_expressions)

    def _extract_pain_score(self, text):
        """
        Estrae un Pain Score espresso su scala 0-10.

        Formati supportati:

        - 1/10
        - 1.5/10
        - 1,5/10
        - 3 su 10
        - dolore 4
        - fastidio 2
        """

        if not text:
            return None

        normalized = text.replace(",", ".")

        explicit_patterns = (
            r"\b(\d+(?:\.\d+)?)\s*/\s*10\b",
            r"\b(\d+(?:\.\d+)?)\s+su\s+10\b",
        )

        for pattern in explicit_patterns:
            match = re.search(pattern, normalized)

            if match:
                return self._validated_pain_score(match.group(1))

        contextual_pattern = (
            r"\b(?:dolore|fastidio|affaticamento|rigidità|"
            r"indolenzimento|problema)\s*[:\-]?\s*"
            r"(\d+(?:\.\d+)?)\b"
        )

        match = re.search(contextual_pattern, normalized)

        if match:
            return self._validated_pain_score(match.group(1))

        return None

    def _validated_pain_score(self, value):
        """
        Converte e valida un Pain Score sulla scala 0-10.
        """

        try:
            score = float(value)
        except (TypeError, ValueError):
            return None

        if 0 <= score <= 10:
            return score

        return None

    def _classify_symptom(self, problem):
        """
        Classifica la natura prevalente del sintomo.

        L'ordine è importante: un'espressione come
        'affaticamento muscolare 1/10' deve essere classificata
        come FATIGUE, non come MUSCLE.
        """

        clinical_expressions = (
            "zoppia",
            "zoppicare",
            "gonfiore",
            "blocco articolare",
            "articolazione bloccata",
            "instabilità",
            "cedimento",
            "perdita di forza",
            "perdita di sensibilità",
            "formicolio persistente",
            "lesione",
            "strappo",
            "rottura",
            "impossibile correre",
            "impossibile camminare",
            "impossibile pedalare",
            "impossibile nuotare",
            "non riesco a caricare",
            "non riesco ad appoggiare",
        )

        fatigue_expressions = (
            "affaticamento",
            "gambe stanche",
            "gamba stanca",
            "gambe pesanti",
            "gamba pesante",
            "stanchezza muscolare",
            "fatica muscolare",
            "doms",
            "indolenzimento",
            "indolenzito",
            "indolenzita",
            "rigidità lieve",
            "rigidita lieve",
        )

        tendon_expressions = (
            "tendine",
            "tendineo",
            "tendinea",
            "tendinopatia",
            "tendinite",
            "achille",
            "rotuleo",
            "fascia plantare",
            "plantare",
        )

        joint_expressions = (
            "articolare",
            "articolazione",
            "ginocchio",
            "caviglia",
            "anca",
            "spalla",
            "gomito",
            "polso",
            "schiena",
            "lombare",
            "cervicale",
        )

        muscle_expressions = (
            "contrattura",
            "stiramento",
            "crampo",
            "muscolare",
            "muscolo",
            "quadricipite",
            "polpaccio",
            "bicipite femorale",
            "ischiocrurale",
            "adduttore",
            "gluteo",
        )

        pain_expressions = (
            "dolore",
            "fastidio",
            "bruciore",
            "fitta",
            "tensione",
            "infiammazione",
            "problema",
        )

        if self._contains_any(problem, clinical_expressions):
            return self.TYPE_CLINICAL

        if self._contains_any(problem, fatigue_expressions):
            return self.TYPE_FATIGUE

        if self._contains_any(problem, tendon_expressions):
            return self.TYPE_TENDON

        if self._contains_any(problem, joint_expressions):
            return self.TYPE_JOINT

        if self._contains_any(problem, muscle_expressions):
            return self.TYPE_MUSCLE

        if self._contains_any(problem, pain_expressions):
            return self.TYPE_PAIN

        return self.TYPE_UNKNOWN

    def _classify_intensity(self, pain_score):
        """
        Converte il Pain Score in una fascia descrittiva.
        """

        if pain_score is None:
            return self.INTENSITY_UNKNOWN

        if pain_score == 0:
            return self.INTENSITY_NONE

        if pain_score <= 2:
            return self.INTENSITY_VERY_LOW

        if pain_score <= 4:
            return self.INTENSITY_LOW

        if pain_score <= 6:
            return self.INTENSITY_MODERATE

        if pain_score <= 8:
            return self.INTENSITY_HIGH

        return self.INTENSITY_CRITICAL

    def _calculate_risk_level(
        self,
        symptom_type,
        pain_score,
        problem,
    ):
        """
        Combina natura e intensità del sintomo.

        La tipologia del problema modifica il significato del Pain Score:
        un sintomo tendineo o articolare viene trattato con maggiore
        prudenza rispetto al semplice affaticamento fisiologico.
        """

        if self._contains_any(
            problem,
            (
                "peggiora",
                "peggioramento",
                "in aumento",
                "aumentato",
                "più forte",
                "persistente",
            ),
        ):
            progression_factor = True
        else:
            progression_factor = False

        if pain_score is None:
            level = self._risk_without_pain_score(symptom_type, problem)
        else:
            level = self._risk_with_pain_score(
                symptom_type=symptom_type,
                pain_score=pain_score,
            )

        if progression_factor:
            level = self._increase_level(level)

        return level

    def _risk_without_pain_score(self, symptom_type, problem):
        """
        Valuta il rischio quando non è disponibile un Pain Score.
        """

        if symptom_type == self.TYPE_FATIGUE:
            return self.LEVEL_LOW

        if symptom_type in (
            self.TYPE_MUSCLE,
            self.TYPE_TENDON,
            self.TYPE_JOINT,
            self.TYPE_PAIN,
        ):
            if self._contains_any(
                problem,
                (
                    "forte",
                    "intenso",
                    "acuto",
                    "importante",
                ),
            ):
                return self.LEVEL_HIGH

            return self.LEVEL_MODERATE

        if symptom_type == self.TYPE_UNKNOWN:
            return self.LEVEL_MODERATE

        return self.LEVEL_UNKNOWN

    def _risk_with_pain_score(self, symptom_type, pain_score):
        """
        Applica la matrice tipo di sintomo × Pain Score.
        """

        if pain_score == 0:
            return self.LEVEL_LOW

        if symptom_type == self.TYPE_FATIGUE:
            if pain_score <= 2:
                return self.LEVEL_LOW

            if pain_score <= 5:
                return self.LEVEL_MODERATE

            return self.LEVEL_HIGH

        if symptom_type == self.TYPE_MUSCLE:
            if pain_score <= 2:
                return self.LEVEL_MODERATE

            if pain_score <= 5:
                return self.LEVEL_HIGH

            return self.LEVEL_CRITICAL

        if symptom_type in (
            self.TYPE_TENDON,
            self.TYPE_JOINT,
        ):
            if pain_score <= 2:
                return self.LEVEL_MODERATE

            if pain_score <= 5:
                return self.LEVEL_HIGH

            return self.LEVEL_CRITICAL

        if symptom_type == self.TYPE_PAIN:
            if pain_score <= 2:
                return self.LEVEL_MODERATE

            if pain_score <= 5:
                return self.LEVEL_HIGH

            return self.LEVEL_CRITICAL

        if symptom_type == self.TYPE_UNKNOWN:
            if pain_score <= 2:
                return self.LEVEL_LOW

            if pain_score <= 5:
                return self.LEVEL_MODERATE

            return self.LEVEL_HIGH

        return self.LEVEL_UNKNOWN

    def _increase_level(self, level):
        """
        Aumenta di un livello il rischio in caso di peggioramento.
        """

        progression = {
            self.LEVEL_LOW: self.LEVEL_MODERATE,
            self.LEVEL_MODERATE: self.LEVEL_HIGH,
            self.LEVEL_HIGH: self.LEVEL_CRITICAL,
            self.LEVEL_CRITICAL: self.LEVEL_CRITICAL,
            self.LEVEL_UNKNOWN: self.LEVEL_MODERATE,
        }

        return progression.get(level, self.LEVEL_UNKNOWN)

    def _build_reasons(
        self,
        problem,
        symptom_type,
        pain_score,
        level,
        clinical_override,
    ):
        """
        Costruisce una spiegazione leggibile dell'analisi.
        """

        reasons = [
            f"Tipo di sintomo: {self._symptom_label(symptom_type)}"
        ]

        if pain_score is not None:
            reasons.append(
                f"Pain Score: {self._format_number(pain_score)}/10"
            )
        else:
            reasons.append("Pain Score non disponibile")

        if clinical_override:
            reasons.append(
                "Presente un segnale clinico di allarme: "
                "applicato blocco di sicurezza"
            )
            reasons.append(
                f"Problematica critica segnalata: {problem}"
            )

            return reasons

        if (
            symptom_type == self.TYPE_FATIGUE
            and level == self.LEVEL_LOW
        ):
            reasons.append(
                "Affaticamento lieve compatibile con il carico svolto, "
                "senza segnali specifici di infortunio"
            )

        elif (
            symptom_type == self.TYPE_FATIGUE
            and level == self.LEVEL_MODERATE
        ):
            reasons.append(
                "Affaticamento da monitorare prima di introdurre "
                "un nuovo stimolo intenso"
            )

        elif symptom_type == self.TYPE_TENDON:
            reasons.append(
                "Sintomo tendineo valutato con maggiore prudenza"
            )

        elif symptom_type == self.TYPE_JOINT:
            reasons.append(
                "Sintomo articolare valutato con maggiore prudenza"
            )

        elif symptom_type == self.TYPE_MUSCLE:
            reasons.append(
                "Sintomo muscolare distinto dalla semplice fatica fisiologica"
            )

        elif symptom_type == self.TYPE_PAIN:
            reasons.append(
                "Dolore o fastidio generico da monitorare"
            )

        else:
            reasons.append(
                "Segnalazione fisica non classificabile con precisione"
            )

        reasons.append(
            f"Rischio fisico risultante: {self._level_label(level)}"
        )

        return reasons

    def _result(
        self,
        level,
        problem,
        symptom_type,
        pain_score,
        intensity,
        safety_override,
        reasons,
    ):
        """
        Costruisce il risultato dell'analisi in formato uniforme.
        """

        return {
            "level": level,
            "problem": problem,
            "symptom_type": symptom_type,
            "pain_score": pain_score,
            "intensity": intensity,
            "safety_override": safety_override,
            "reasons": reasons,
        }

    def _symptom_label(self, symptom_type):
        """
        Restituisce un'etichetta italiana per il tipo di sintomo.
        """

        labels = {
            self.TYPE_NONE: "nessun sintomo",
            self.TYPE_FATIGUE: "affaticamento fisiologico",
            self.TYPE_MUSCLE: "problematica muscolare",
            self.TYPE_TENDON: "problematica tendinea",
            self.TYPE_JOINT: "problematica articolare",
            self.TYPE_PAIN: "dolore o fastidio generico",
            self.TYPE_CLINICAL: "segnale clinico",
            self.TYPE_UNKNOWN: "non determinato",
        }

        return labels.get(symptom_type, "non determinato")

    def _level_label(self, level):
        """
        Restituisce un'etichetta italiana per il livello di rischio.
        """

        labels = {
            self.LEVEL_LOW: "basso",
            self.LEVEL_MODERATE: "moderato",
            self.LEVEL_HIGH: "alto",
            self.LEVEL_CRITICAL: "critico",
            self.LEVEL_UNKNOWN: "non determinato",
        }

        return labels.get(level, "non determinato")

    def _normalized_text(self, value):
        """
        Normalizza un valore testuale proveniente dal contesto.
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
        Verifica se il testo contiene almeno una delle espressioni indicate.
        """

        if not text:
            return False

        return any(
            expression in text
            for expression in expressions
        )

    def _format_number(self, value):
        """
        Formatta un numero senza decimali inutili.
        """

        if value is None:
            return "N/D"

        if float(value).is_integer():
            return str(int(value))

        return f"{value:.1f}"