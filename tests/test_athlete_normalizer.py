from backend.normalization.athlete_normalizer import AthleteNormalizer


normalizer = AthleteNormalizer()


athlete = {

    "id": "athlete_001",

    "Nome atleta": "Gabrio",

    "Livello atleta": "Age Group competitivo",

    "Obiettivo principale":
        "Miglioramento performance medio-lunghe",

    "Gare obiettivo":
        "Triathlon endurance e mezze maratone",

    "Peso attuale kg": 66,

    "Altezza cm": 177,

    "Ftp": 265,

    "Css": 107,

    "Vo₂max corsa": 57,

    "Vo₂max bici": 55,

    "Limitazioni fisiche":
        "Tendenza ad infiammazioni al tendine d'Achille",

    "Storico infortuni":
        "Problema tendine d'Achille",

    "Disponibilità allenamento":
        "Quotidiana",

}


result = normalizer.normalize(
    athlete,
    source="airtable",
)


print(result)
