from backend.airtable_client import AirtableClient


class FakeTable:
    def __init__(self, records):
        self._records = records

    def all(self):
        return list(self._records)


class FakeBase:
    def __init__(self, tables):
        self._tables = tables

    def table(self, name):
        return FakeTable(
            self._tables.get(
                name,
                [],
            )
        )


def _client_with_athlete(athlete):
    client = AirtableClient.__new__(AirtableClient)
    client.base = FakeBase(
        {
            "Performance Log": [],
        }
    )
    client.get_athlete_profile = lambda: athlete
    return client


def _client_with_tables(tables, athlete=None):
    client = AirtableClient.__new__(AirtableClient)
    client.base = FakeBase(tables)
    client.get_athlete_profile = lambda: athlete or {}
    return client


def test_performance_history_reads_real_airtable_field_names() -> None:
    client = _client_with_athlete(
        {
            "FTP": 265,
            "CSS": 107,
            "VO₂max corsa": 57,
            "VO₂max bici": 55,
        }
    )

    history = client.get_performance_history()

    assert history == [
        {
            "ftp": 265,
            "vo2max_run": 57,
            "vo2max_bike": 55,
            "css": 107,
        }
    ]


def test_performance_history_is_empty_without_athlete() -> None:
    client = _client_with_athlete({})

    assert client.get_performance_history() == []


def test_performance_history_reads_vertical_performance_log() -> None:
    client = _client_with_tables(
        {
            "Performance Log": [
                {
                    "fields": {
                        "Data": "2026-01-15",
                        "Metrica": "ftp",
                        "Valore": 255,
                        "Note": "Test indoor",
                    }
                },
                {
                    "fields": {
                        "Data": "2026-07-30",
                        "Metrica": "ftp",
                        "Valore": 265,
                    }
                },
                {
                    "fields": {
                        "Data": "2026-07-30",
                        "Metrica": "vo2max_run",
                        "Valore": 57,
                    }
                },
            ]
        }
    )

    history = client.get_performance_history()

    assert history == [
        {
            "date": "2026-01-15",
            "metric": "ftp",
            "value": 255,
            "note": "Test indoor",
        },
        {
            "date": "2026-07-30",
            "metric": "ftp",
            "value": 265,
        },
        {
            "date": "2026-07-30",
            "metric": "vo2max_run",
            "value": 57,
        },
    ]


def test_performance_log_records_are_sorted_by_date() -> None:
    client = _client_with_tables(
        {
            "Performance Log": [
                {
                    "fields": {
                        "Data": "2026-07-30",
                        "Metrica": "ftp",
                        "Valore": 265,
                    }
                },
                {
                    "fields": {
                        "Data": "2026-01-15",
                        "Metrica": "ftp",
                        "Valore": 255,
                    }
                },
            ]
        }
    )

    history = client.get_performance_history()

    assert [
        record["date"]
        for record in history
    ] == [
        "2026-01-15",
        "2026-07-30",
    ]


def test_performance_history_falls_back_to_profile_when_log_is_empty() -> None:
    client = _client_with_tables(
        {
            "Performance Log": [],
        },
        athlete={
            "FTP": 265,
            "CSS": 107,
            "VO₂max corsa": 57,
            "VO₂max bici": 55,
        },
    )

    assert client.get_performance_history() == [
        {
            "ftp": 265,
            "vo2max_run": 57,
            "vo2max_bike": 55,
            "css": 107,
        }
    ]


def test_empty_performance_records_are_ignored() -> None:
    client = _client_with_tables(
        {
            "Performance Log": [
                {
                    "fields": {},
                },
                {
                    "fields": {
                        "Data": "2026-01-15",
                        "Metrica": "ftp",
                        "Valore": 255,
                    }
                },
            ]
        }
    )

    history = client.get_performance_history()

    assert history == [
        {
            "date": "2026-01-15",
            "metric": "ftp",
            "value": 255,
        }
    ]