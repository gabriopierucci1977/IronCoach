"""
IronCoach Performance History v0.1

Modello dello storico performance.

In futuro potrà contenere:

- FTP
- CSS
- VO2max
- tempi gara
- record personali
- trend prestativi
"""


class PerformanceHistory:


    def __init__(
        self,
        metrics=None,
    ):

        self.metrics = metrics or []



    def add_metric(
        self,
        metric,
    ):

        self.metrics.append(
            metric
        )



    def get_metrics(self):

        return self.metrics



    def count(self):

        return len(
            self.metrics
        )