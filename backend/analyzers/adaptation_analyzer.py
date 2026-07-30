"""
IronCoach Adaptation Analyzer v0.1

Valuta la capacità dell'atleta di adattarsi
al carico allenante.

Non decide il piano.

Fornisce informazioni utili al sistema decisionale.

Input:

{
    "athlete_profile": {},
    "load_analysis": {}
}

Output:

{
    "adaptation_level": "",
    "risk_factors": [],
    "positive_factors": [],
    "reasons": []
}
"""


class AdaptationAnalyzer:


    LEVEL_UNKNOWN = "UNKNOWN"
    LEVEL_GOOD = "GOOD"
    LEVEL_MODERATE = "MODERATE"
    LEVEL_LIMITED = "LIMITED"



    def analyze(
        self,
        context,
    ):

        context = context or {}


        profile = context.get(
            "athlete_profile",
            {}
        ) or {}


        load = context.get(
            "load_analysis",
            {}
        ) or {}



        limitations = profile.get(
            "limitations",
            []
        )


        total_load = load.get(
            "total_load",
            0
        )


        reasons = []

        risk_factors = []

        positive_factors = []



        if profile:

            positive_factors.append(
                "Profilo atleta disponibile"
            )


        if total_load >= 2000:

            reasons.append(
                "Carico storico elevato"
            )


        elif total_load > 0:

            reasons.append(
                "Carico storico presente"
            )


        else:

            reasons.append(
                "Dati carico insufficienti"
            )



        if limitations:

            risk_factors.extend(
                limitations
            )

            reasons.append(
                "Presenti limitazioni fisiche note"
            )



        if (
            total_load >= 2000
            and limitations
        ):

            level = self.LEVEL_LIMITED


        elif total_load >= 1000:

            level = self.LEVEL_MODERATE


        elif total_load > 0:

            level = self.LEVEL_GOOD


        else:

            level = self.LEVEL_UNKNOWN



        return {

            "adaptation_level": level,

            "risk_factors": risk_factors,

            "positive_factors": positive_factors,

            "reasons": reasons,

        }
    