"""
IronCoach Recovery Analyzer v0.4

Analizzatore dedicato alla valutazione della disponibilità fisiologica
dell'atleta.

Supporta:

- formato Airtable storico;
- formato normalizzato IronCoach;
- dati Garmin / Whoop / Oura normalizzati.

Responsabilità:

- interpretare il livello recovery;
- classificare lo stato fisiologico;
- fornire assessment al CoachEngine.

Non contiene logica decisionale.
"""



class RecoveryAnalyzer:


    RECOVERY_GREEN = "VERDE"

    RECOVERY_YELLOW = "GIALLO"

    RECOVERY_RED = "ROSSO"



    LEVEL_LOW = "LOW"

    LEVEL_MODERATE = "MODERATE"

    LEVEL_HIGH = "HIGH"

    LEVEL_CRITICAL = "CRITICAL"

    LEVEL_UNKNOWN = "UNKNOWN"




    def analyze(
        self,
        recovery,
    ):


        recovery = recovery or {}



        # ==================================================
        # SUPPORTO NUOVO FORMATO NORMALIZZATO
        # ==================================================


        sleep = recovery.get(
            "sleep",
            {},
        ) or {}



        recovery_state = self._normalized_text(

            recovery.get(
                "Stato Recovery"
            )

            or recovery.get(
                "stato_recovery"
            )

        ).upper()




        recovery_score = self._number(

            recovery.get(
                "Recovery Score"
            )

            or recovery.get(
                "recovery_score"
            )

            or recovery.get(
                "readiness"
            )

        )




        sleep_score = self._number(

            recovery.get(
                "Sleep Score"
            )

            or recovery.get(
                "sleep_score"
            )

            or sleep.get(
                "score"
            )

        )




        # se lo stato non arriva dalla sorgente,
        # viene calcolato dal readiness


        if not recovery_state:


            recovery_state = self._calculate_state(
                recovery_score
            )




        reasons = []



        # ==================================================
        # ROSSO
        # ==================================================


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


            return self._result(

                state=recovery_state,

                level=self.LEVEL_CRITICAL,

                recovery_score=recovery_score,

                sleep_score=sleep_score,

                reasons=reasons,

            )




        # ==================================================
        # GIALLO
        # ==================================================


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


            return self._result(

                state=recovery_state,

                level=self.LEVEL_MODERATE,

                recovery_score=recovery_score,

                sleep_score=sleep_score,

                reasons=reasons,

            )

        # ==================================================
        # VERDE
        # ==================================================


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




        # ==================================================
        # FALLBACK SCORE
        # ==================================================


        if recovery_score is not None:


            if recovery_score < 50:


                reasons.append(

                    "Recovery Score critico"

                )


                return self._result(

                    state=self.RECOVERY_RED,

                    level=self.LEVEL_CRITICAL,

                    recovery_score=recovery_score,

                    sleep_score=sleep_score,

                    reasons=reasons,

                )



            if recovery_score < 70:


                reasons.append(

                    "Recovery Score moderato"

                )


                return self._result(

                    state=self.RECOVERY_YELLOW,

                    level=self.LEVEL_MODERATE,

                    recovery_score=recovery_score,

                    sleep_score=sleep_score,

                    reasons=reasons,

                )



            reasons.append(

                "Recovery Score favorevole"

            )


            return self._result(

                state=self.RECOVERY_GREEN,

                level=self.LEVEL_LOW,

                recovery_score=recovery_score,

                sleep_score=sleep_score,

                reasons=reasons,

            )




        # ==================================================
        # DATI INSUFFICIENTI
        # ==================================================


        reasons.append(
            "Dati recovery insufficienti"
        )


        return self._result(

            state="",

            level=self.LEVEL_UNKNOWN,

            recovery_score=recovery_score,

            sleep_score=sleep_score,

            reasons=reasons,

        )




    # ==================================================
    # RESULT
    # ==================================================


    def _result(
        self,
        state,
        level,
        recovery_score,
        sleep_score,
        reasons,
    ):


        return {


            "state":

                state,



            "level":

                level,



            "score":

                recovery_score,



            "sleep_score":

                sleep_score,



            "reasons":

                reasons,

        }




    # ==================================================
    # STATE CALCULATION
    # ==================================================


    def _calculate_state(
        self,
        score,
    ):


        if score is None:

            return ""



        if score < 50:

            return self.RECOVERY_RED



        if score < 70:

            return self.RECOVERY_YELLOW



        return self.RECOVERY_GREEN




    # ==================================================
    # HELPERS
    # ==================================================


    def _number(
        self,
        value,
    ):


        if value is None:

            return None



        if isinstance(
            value,
            str,
        ):


            value = (

                value
                .strip()
                .replace(
                    ",",
                    ".",
                )

            )


            if not value:

                return None



        try:

            return float(
                value
            )


        except (
            TypeError,
            ValueError,
        ):

            return None




    def _normalized_text(
        self,
        value,
    ):


        if value is None:

            return ""



        if isinstance(
            value,
            dict,
        ):


            value = value.get(
                "value",
                "",
            )



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



        return str(
            value
        ).strip()




    def _format_number(
        self,
        value,
    ):


        if value is None:

            return "N/D"



        if float(value).is_integer():

            return str(
                int(value)
            )



        return f"{value:.1f}"
