"""
IronCoach Coach Engine v6.9.5

Motore centrale di orchestrazione.

Responsabilità:

- ricevere il contesto atleta;
- eseguire gli analyzer dello stato attuale;
- analizzare carico, adattamento e performance;
- analizzare il trend storico del recupero;
- passare gli assessment al DecisionEngine;
- allegare l'intelligence alla decisione finale.

La logica decisionale rimane nel DecisionEngine.
"""


from backend.config import get_runtime_config
from backend.engines.decision_engine import DecisionEngine

from backend.analyzers.recovery_analyzer import RecoveryAnalyzer
from backend.analyzers.recovery_trend_analyzer import RecoveryTrendAnalyzer
from backend.analyzers.training_analyzer import TrainingAnalyzer
from backend.analyzers.injury_analyzer import InjuryAnalyzer
from backend.analyzers.nutrition_analyzer import NutritionAnalyzer
from backend.analyzers.load_analyzer import LoadAnalyzer
from backend.analyzers.adaptation_analyzer import AdaptationAnalyzer
from backend.analyzers.performance_analyzer import PerformanceAnalyzer



class CoachEngine:
    """
    Orchestratore principale IronCoach.
    """



    def __init__(
        self,
        runtime_config=None,
    ):

        self.runtime_config = (
            runtime_config
            or get_runtime_config()
        )

        self.recovery_analyzer = RecoveryAnalyzer()

        self.recovery_trend_analyzer = (
            RecoveryTrendAnalyzer()
        )

        self.training_analyzer = TrainingAnalyzer()

        self.injury_analyzer = InjuryAnalyzer()

        self.nutrition_analyzer = NutritionAnalyzer()

        self.load_analyzer = LoadAnalyzer()

        self.adaptation_analyzer = AdaptationAnalyzer()

        self.performance_analyzer = PerformanceAnalyzer()

        self.decision_engine = DecisionEngine(
            runtime_config=self.runtime_config,
        )



    # ==================================================
    # HELPERS
    # ==================================================


    def _first_value(
        self,
        data,
        keys,
        default="N/D",
    ):

        data = data or {}


        for key in keys:

            value = data.get(key)


            if value not in (
                None,
                "",
                [],
            ):

                return value


        return default
    def _raw_value(
        self,
        data,
        keys,
        default="N/D",
    ):

        data = data or {}


        raw = data.get(
            "raw",
            {},
        ) or {}


        return self._first_value(
            raw,
            keys,
            default,
        )




    def _nested_value(
        self,
        data,
        section,
        keys,
        default="N/D",
    ):

        data = data or {}


        section_data = data.get(
            section,
            {},
        ) or {}


        return self._first_value(
            section_data,
            keys,
            default,
        )




    def _extract_training_distribution(
        self,
        raw,
    ):

        """
        Estrae la distribuzione allenamento
        dal testo raw Airtable.

        Estrazione delimitata:
        prende solo il contenuto dopo
        "Allenamento distribuito tra:"
        evitando campi successivi.
        """

        raw = raw or {}

        marker = "Allenamento distribuito tra:"

        text_sources = []

        for value in raw.values():

            if isinstance(value, str):

                text_sources.append(value)


        full_text = "\n".join(
            text_sources
        )


        if marker not in full_text:

            return "N/D"


        extracted = (
            full_text
            .split(
                marker,
                1,
            )[1]
            .strip()
        )


        # elimina campi successivi Airtable
        stop_markers = [
            "; Storico problema",
            "; VO₂max",
            "; VO2max",
            "\nStorico problema",
            "\nVO₂max",
            "\nVO2max",
        ]


        for stop in stop_markers:

            if stop in extracted:

                extracted = extracted.split(
                    stop,
                    1,
                )[0].strip()


        # elimina eventuali separatori
        # rimasti da campi Airtable concatenati

        extracted = (
            extracted
            .replace(
                "\\n",
                " "
            )
            .strip()
        )


        return extracted



    # ==================================================
    # ATHLETE INTELLIGENCE
    # ==================================================


    def _build_athlete_intelligence(
        self,
        athlete_profile,
    ):

        """
        Costruisce il profilo intelligence atleta.

        Compatibile con:

        - AthleteNormalizer;
        - Airtable originale;
        - raw Airtable.
        """


        athlete_profile = athlete_profile or {}



        identity = athlete_profile.get(
            "identity",
            {},
        ) or {}



        goals = athlete_profile.get(
            "goals",
            {},
        ) or {}



        physiology = athlete_profile.get(
            "physiology",
            {},
        ) or {}



        constraints = athlete_profile.get(
            "constraints",
            {},
        ) or {}



        preferences = athlete_profile.get(
            "preferences",
            {},
        ) or {}



        raw = athlete_profile.get(
            "raw",
            {},
        ) or {}





        # ==================================================
        # GOALS FALLBACK
        # ==================================================


        primary_goal = self._first_value(
            goals,
            [
                "primary",
                "primary_goal",
                "goal",
            ],
            "",
        )



        if not primary_goal:

            primary_goal = self._first_value(
                raw,
                [
                    "Obiettivo principale",
                    "Obiettivo Principale",
                    "Obiettivi principali",
                    "Obiettivi Principali",
                    "primary_goal",
                    "goal",
                ],
            )



        race_targets = self._first_value(
            goals,
            [
                "race_targets",
                "target_races",
            ],
            "",
        )



        if not race_targets:

            race_targets = self._first_value(
                raw,
                [
                    "Gare obiettivo",
                    "Gare Obiettivo",
                    "race_targets",
                    "target_races",
                ],
            )
        goal_profile = athlete_profile.get(
            "goal_profile",
            {},
        ) or {}

        if not goal_profile:
            goal_type = self._first_value(
                goals,
                [
                    "goal_type",
                    "type",
                ],
                "",
            )

            goal_profile = {
                "goal_type": goal_type,
                "primary_goal": primary_goal,
                "race_target": race_targets,
            }

        return {


            "athlete_name":

                self._first_value(
                    identity,
                    [
                        "name",
                        "Nome atleta",
                    ],
                    self._first_value(
                        raw,
                        [
                            "Nome atleta",
                            "Nome Atleta",
                        ],
                    ),
                ),




            "athlete_type":

                self._first_value(
                    identity,
                    [
                        "level",
                        "Livello atleta",
                        "athlete_level",
                    ],
                    self._first_value(
                        raw,
                        [
                            "Livello atleta",
                            "Livello Atleta",
                            "Tipo atleta",
                        ],
                    ),
                ),




            "goals":

                primary_goal,


            "goal_profile":

                goal_profile,




            "race_targets":

                race_targets,




            "strengths":

                self._first_value(
                    athlete_profile,
                    [
                        "strengths",
                        "Punti di forza",
                        "Note coach",
                        "Note Coach",
                        "note_coach",
                    ],
                    self._first_value(
                        raw,
                        [
                            "Punti di forza",
                            "Note coach",
                            "Note Coach",
                        ],
                    ),
                ),




            "limitations":

                self._first_value(
                    constraints,
                    [
                        "physical_limitations",
                        "Limitazioni fisiche",
                        "limitations",
                    ],
                    self._first_value(
                        raw,
                        [
                            "Limitazioni fisiche",
                            "Limitazioni Fisiche",
                            "Limitazioni note",
                        ],
                    ),
                ),




            "injury_history":

                self._first_value(
                    constraints,
                    [
                        "injury_history",
                        "Storico infortuni",
                    ],
                    self._first_value(
                        raw,
                        [
                            "Storico infortuni",
                            "Storico Infortuni",
                        ],
                    ),
                ),




            "training_preferences":

                self._first_value(
                    preferences,
                    [
                        "session_preferences",
                        "training_preferences",
                    ],
                    self._first_value(
                        raw,
                        [
                            "Preferenza",
                            "Preferenze allenamento",
                            "Disponibilità allenamento",
                        ],
                    ),
                ),
            "sport_profile":

                self._first_value(
                    athlete_profile,
                    [
                        "sport_profile",
                        "Sport principale",
                        "Sport Principale",
                    ],
                    self._first_value(
                        raw,
                        [
                            "Sport principale",
                            "Sport Principale",
                        ],
                    ),
                ),




            "training_distribution":

                self._extract_training_distribution(
                    raw
                ),




            "availability":

                self._first_value(
                    preferences,
                    [
                        "availability",
                        "Disponibilità allenamento",
                    ],
                    self._first_value(
                        raw,
                        [
                            "Disponibilità allenamento",
                            "Disponibilita allenamento",
                        ],
                    ),
                ),




            "load_tolerance":

                self._first_value(
                    preferences,
                    [
                        "load_tolerance",
                        "availability",
                    ],
                    self._first_value(
                        raw,
                        [
                            "Tolleranza al carico",
                            "Disponibilità allenamento",
                        ],
                    ),
                ),




            "ftp":

                self._first_value(
                    physiology,
                    [
                        "ftp",
                        "FTP",
                        "Ftp",
                    ],
                    self._first_value(
                        raw,
                        [
                            "FTP",
                            "Ftp",
                        ],
                    ),
                ),




            "css":

                self._first_value(
                    physiology,
                    [
                        "css",
                        "CSS",
                        "Css",
                    ],
                    self._first_value(
                        raw,
                        [
                            "CSS",
                            "Css",
                        ],
                    ),
                ),
            "vo2max_run":

                self._first_value(
                    physiology,
                    [
                        "vo2max_run",
                        "Vo₂max corsa",
                        "VO₂max corsa",
                        "VO2max corsa",
                    ],
                    self._first_value(
                        raw,
                        [
                            "Vo₂max corsa",
                            "VO₂max corsa",
                            "VO2max corsa",
                        ],
                    ),
                ),




            "vo2max_bike":

                self._first_value(
                    physiology,
                    [
                        "vo2max_bike",
                        "Vo₂max bici",
                        "VO₂max bici",
                        "VO2max bici",
                    ],
                    self._first_value(
                        raw,
                        [
                            "Vo₂max bici",
                            "VO₂max bici",
                            "VO2max bici",
                        ],
                    ),
                ),




            "weight":

                self._first_value(
                    physiology,
                    [
                        "weight",
                        "Peso attuale kg",
                    ],
                    self._first_value(
                        raw,
                        [
                            "Peso attuale kg",
                            "Peso Attuale kg",
                        ],
                    ),
                ),




            "height":

                self._first_value(
                    physiology,
                    [
                        "height",
                        "Altezza cm",
                    ],
                    self._first_value(
                        raw,
                        [
                            "Altezza cm",
                            "Altezza Cm",
                        ],
                    ),
                ),




            "equipment":

                self._first_value(
                    athlete_profile,
                    [
                        "equipment",
                        "Attrezzatura disponibile",
                    ],
                    self._first_value(
                        raw,
                        [
                            "Attrezzatura disponibile",
                            "Attrezzatura Disponibile",
                        ],
                    ),
                ),

        }




    def _build_data_freshness_assessment(
        self,
        warnings,
    ):
        """
        Trasforma i warning di freschezza del ContextBuilder
        in un assessment strutturato per il DecisionEngine.
        """

        relevant = [
            str(item).strip()
            for item in (warnings or [])
            if str(item).strip()
            and (
                "dato obsoleto" in str(item).lower()
                or "data futura" in str(item).lower()
            )
        ]

        if not relevant:
            return {
                "level": "LOW",
                "reasons": [],
            }

        recovery_issue = any(
            str(item).lower().startswith("recovery:")
            for item in relevant
        )

        level = (
            "HIGH"
            if recovery_issue
            else "MODERATE"
        )

        return {
            "level": level,
            "reasons": relevant,
        }


    # ==================================================
    # MAIN EVALUATION
    # ==================================================


    def evaluate(
        self,
        context,
    ):


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



        athlete_profile = (

            context.get(
                "athlete_profile"
            )

            or context.get(
                "athlete"
            )

            or context.get(
                "athlete_profile_data"
            )

            or {}

        )



        generated_athlete_intelligence = (
            self._build_athlete_intelligence(
                athlete_profile
            )
        )



        context_athlete_intelligence = (

            context.get(
                "athlete_profile_intelligence"
            )

            or {}

        )



        athlete_profile_intelligence = {

            **generated_athlete_intelligence,

            **context_athlete_intelligence,

        }



        training_history = context.get(
            "training_history",
            [],
        ) or []



        recovery_history = context.get(
            "recovery_history",
            [],
        ) or []



        performance_history = context.get(
            "performance_history",
            [],
        ) or []

        data_freshness_assessment = (
            context.get(
                "data_freshness",
                {},
            )
            or self._build_data_freshness_assessment(
                context.get(
                    "context_warnings",
                    [],
                )
            )
        )



        recovery_assessment = (

            self.recovery_analyzer.analyze(
                recovery
            )

        )

        explicit_recovery_level = recovery.get(
            "level"
        )

        if explicit_recovery_level:
            recovery_assessment = {
                **recovery_assessment,
                "level": explicit_recovery_level,
            }




        recovery_trend_analysis = (

            self.recovery_trend_analyzer.analyze(

                {
                    "recovery_history":

                        recovery_history,

                }

            )

        )




        training_assessment = (

            self.training_analyzer.analyze(
                training
            )

        )




        injury_assessment = (

            self.injury_analyzer.analyze(

                {
                    "training":

                        training,


                    "athlete_profile":

                        athlete_profile,

                }

            )

        )




        nutrition_assessment = (

            self.nutrition_analyzer.analyze(
                nutrition
            )

        )




        load_context = {
            "training_history": training_history,
        }

        load_tolerance = (
            athlete_profile_intelligence.get(
                "load_tolerance",
                {},
            )
            if isinstance(
                athlete_profile_intelligence,
                dict,
            )
            else {}
        )

        if load_tolerance:
            load_context[
                "load_tolerance"
            ] = load_tolerance

        source_training_freshness = {}

        if isinstance(
            data_freshness_assessment,
            dict,
        ):
            candidate = (
                data_freshness_assessment.get(
                    "training",
                    {},
                )
                or {}
            )

            if isinstance(
                candidate,
                dict,
            ):
                source_training_freshness = (
                    candidate
                )

        source_status = str(
            source_training_freshness.get(
                "status",
                "",
            )
            or ""
        ).strip().upper()

        source_basis = str(
            source_training_freshness.get(
                "basis",
                "",
            )
            or ""
        ).strip().lower()

        source_checked_at = (
            source_training_freshness.get(
                "source_checked_at"
            )
        )

        if (
            source_basis
            == "source_checked_at"
            and source_status
            == "CURRENT"
            and source_checked_at
        ):
            load_context[
                "analysis_date"
            ] = source_checked_at
            load_context[
                "training_window_complete"
            ] = True

        load_analysis = (
            self.load_analyzer.analyze(
                load_context
            )
        )

        training_freshness = {}

        if isinstance(
            data_freshness_assessment,
            dict,
        ):
            candidate_training_freshness = (
                data_freshness_assessment.get(
                    "training",
                    {},
                )
                or {}
            )

            if isinstance(
                candidate_training_freshness,
                dict,
            ):
                training_freshness = (
                    candidate_training_freshness
                )

        training_freshness_status = str(
            training_freshness.get(
                "status",
                "",
            )
            or ""
        ).strip().upper()

        unreliable_training_history = (
            training_freshness_status
            in {
                "STALE",
                "FUTURE",
            }
        )

        if (
            not unreliable_training_history
            and isinstance(
                data_freshness_assessment,
                dict,
            )
        ):
            freshness_reasons = (
                data_freshness_assessment.get(
                    "reasons",
                    [],
                )
                or []
            )

            unreliable_training_history = any(
                str(reason).strip().lower().startswith(
                    "allenamento:"
                )
                and (
                    "dato obsoleto"
                    in str(reason).lower()
                    or "data futura"
                    in str(reason).lower()
                )
                for reason in freshness_reasons
            )

        if unreliable_training_history:
            freshness_reason = (
                "Carico corrente non valutabile: "
                "freschezza allenamenti insufficiente"
            )

            load_analysis = {
                **load_analysis,
                "level": "UNKNOWN",
                "reasons": [
                    freshness_reason
                ],
            }


        performance_analysis = (

            self.performance_analyzer.analyze(

                {
                    "performance_history":

                        performance_history,

                }

            )

        )




        adaptation_analysis = (

            self.adaptation_analyzer.analyze(

                {
                    "athlete_profile":

                        athlete_profile,


                    "load_analysis":

                        load_analysis,


                    "performance_analysis":

                        performance_analysis,


                    "recovery_analysis":

                        recovery_assessment,

                }

            )

        )




        assessments = {



            "recovery":

                recovery_assessment,



            "recovery_trend":

                recovery_trend_analysis,



            "training":

                training_assessment,



            "injury":

                injury_assessment,



            "nutrition":

                nutrition_assessment,



            "load":

                load_analysis,



            "adaptation":

                adaptation_analysis,



            "performance":

                performance_analysis,



            "athlete_profile":

                athlete_profile_intelligence,



            "goal_profile":

                athlete_profile_intelligence.get(
                    "goal_profile",
                    {},
                ),


            "data_freshness":

                data_freshness_assessment,


            "decision_memory":

                context.get(
                    "decision_memory",
                    {},
                ) or {},

        }




        decision = (

            self.decision_engine.decide(
                assessments
            )

        )




        decision_intelligence = dict(
            decision.get(
                "intelligence",
                {},
            )
            or {}
        )

        decision_intelligence.update(
            {
                "athlete_profile":
                    athlete_profile_intelligence,

                "goal_profile":
                    athlete_profile_intelligence.get(
                        "goal_profile",
                        {},
                    ),

                "load":
                    load_analysis,

                "adaptation":
                    adaptation_analysis,

                "recovery_trend":
                    recovery_trend_analysis,

                "performance":
                    performance_analysis,

                "data_freshness":
                    data_freshness_assessment,
            }
        )

        decision["intelligence"] = (
            decision_intelligence
        )




        return decision