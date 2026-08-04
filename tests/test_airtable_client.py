from backend.airtable_client import AirtableClient


def _client_with_athlete(athlete):
    client = AirtableClient.__new__(AirtableClient)
    client.get_athlete_profile = lambda: athlete
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