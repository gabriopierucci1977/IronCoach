"""
IronCoach Report Builder

Costruisce un report leggibile a partire
dal Context Builder e dal Coach Engine.
"""


class ReportBuilder:

    def build(self, context, decision):

        atleta = context.get("athlete", {})
        recovery = context.get("recovery", {})
        training = context.get("training", {})
        nutrition = context.get("nutrition", {})
        last_decision = context.get("decision", {})

        report = []

        report.append("=" * 60)
        report.append("IRONCOACH REPORT")
        report.append("=" * 60)

        report.append("")
        report.append("ATLETA")
        report.append("-" * 60)

        for k, v in atleta.items():
            report.append(f"{k}: {v}")

        report.append("")
        report.append("RECOVERY")
        report.append("-" * 60)

        for k, v in recovery.items():
            report.append(f"{k}: {v}")

        report.append("")
        report.append("TRAINING")
        report.append("-" * 60)

        for k, v in training.items():
            report.append(f"{k}: {v}")

        report.append("")
        report.append("NUTRITION")
        report.append("-" * 60)

        for k, v in nutrition.items():
            report.append(f"{k}: {v}")

        report.append("")
        report.append("ULTIMA DECISIONE")
        report.append("-" * 60)

        if last_decision:

            for k, v in last_decision.items():
                report.append(f"{k}: {v}")

        else:

            report.append("Nessuna decisione precedente.")

        report.append("")
        report.append("=" * 60)
        report.append("DECISIONE DEL COACH")
        report.append("=" * 60)

        for k, v in decision.items():
            report.append(f"{k}: {v}")

        report.append("")
        report.append("=" * 60)

        return "\n".join(report)