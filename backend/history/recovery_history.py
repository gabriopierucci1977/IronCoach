"""
IronCoach Recovery History v0.1

Modello dello storico recupero atleta.
"""


class RecoveryHistory:


    def __init__(
        self,
        records=None,
    ):

        self.records = records or []



    def add_record(
        self,
        record,
    ):

        self.records.append(
            record
        )



    def get_records(self):

        return self.records



    def count(self):

        return len(
            self.records
        )