"""
IronCoach Athlete Profile Engine v0.1

Costruisce una prima rappresentazione intelligente
dell'atleta.

Non prende decisioni allenanti.

Il suo compito è sintetizzare:
- caratteristiche atleta;
- punti di forza;
- limitazioni;
- preferenze;
- pattern conosciuti.

In futuro utilizzerà:
- storico Garmin;
- storico Strava;
- storico decisioni;
- dati fisiologici.
"""


class AthleteProfileEngine:


    def analyze(self, context):

        context = context or {}


        athlete = context.get(
            "athlete",
            {},
        ) or {}


        profile = {

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

            "load_tolerance": {},

            "injury_patterns": [],

        }


        return profile



    def _athlete_type(
        self,
        athlete,
    ):

        level = str(
            athlete.get(
                "Livello atleta",
                ""
            )
        ).lower()


        sport = str(
            athlete.get(
                "Sport principale",
                ""
            )
        ).lower()


        if (
            "age group" in level
            or "triathlon" in sport
        ):

            return (
                "Age Group endurance athlete"
            )


        return "Endurance athlete"



    def _strengths(
        self,
        athlete,
    ):

        strengths = []


        years = athlete.get(
            "Anni di attività sportiva"
        )


        if years:

            strengths.append(
                "Elevata esperienza sportiva"
            )


        notes = str(
            athlete.get(
                "Note coach",
                ""
            )
        ).lower()


        if "dati" in notes:

            strengths.append(
                "Approccio orientato ai dati"
            )


        return strengths



    def _limitations(
        self,
        athlete,
    ):

        limitations = []


        physical = str(
            athlete.get(
                "Limitazioni fisiche",
                ""
            )
        ).lower()


        injuries = str(
            athlete.get(
                "Storico infortuni",
                ""
            )
        ).lower()


        combined = (
            physical
            + " "
            + injuries
        )


        if "tendine" in combined:

            limitations.append(
                "Storico problematiche tendinee"
            )


        return limitations



    def _preferences(
        self,
        athlete,
    ):

        preferences = []


        availability = str(
            athlete.get(
                "Disponibilità allenamento",
                ""
            )
        )


        if availability:

            preferences.append(
                availability
            )


        return preferences