"""
Test Performance Analyzer sul formato verticale di PerformanceHistory.

Formato atteso dei record:
{
    "date": "2025-01-01",
    "metric": "vo2max_run",
    "value": 52,
}

Contratto:
- raggruppa i record per metrica;
- ordina ogni metrica per data;
- confronta la prima e l'ultima misurazione valida;
- ignora record non validi;
- non considera STABLE l'assenza di metriche confrontabili;
- gestisce valori iniziali pari a zero senza divisioni per zero;
- mantiene compatibilità con le chiavi di output esistenti.
"""

from backend.analyzers.performance_analyzer import PerformanceAnalyzer


def _record(
    *,
    date: str,
    metric: str,
    value,
):
    return {
        "date": date,
        "metric": metric,
        "value": value,
    }


def test_vertical_records_are_grouped_by_metric() -> None:
    result = PerformanceAnalyzer().analyze(
        {
            "performance_history": [
                _record(
                    date="2025-01-01",
                    metric="vo2max_run",
                    value=50,
                ),
                _record(
                    date="2025-02-01",
                    metric="vo2max_run",
                    value=55,
                ),
            ]
        }
    )

    assert result["trend"] == "IMPROVING"
    assert result["metrics"]["vo2max_run"] == 10.0


def test_records_are_sorted_by_date_before_comparison() -> None:
    result = PerformanceAnalyzer().analyze(
        {
            "performance_history": [
                _record(
                    date="2025-03-01",
                    metric="ftp",
                    value=300,
                ),
                _record(
                    date="2025-01-01",
                    metric="ftp",
                    value=250,
                ),
                _record(
                    date="2025-02-01",
                    metric="ftp",
                    value=275,
                ),
            ]
        }
    )

    assert result["trend"] == "IMPROVING"
    assert result["metrics"]["ftp"] == 20.0


def test_each_metric_uses_its_own_first_and_last_values() -> None:
    result = PerformanceAnalyzer().analyze(
        {
            "performance_history": [
                _record(
                    date="2025-01-01",
                    metric="vo2max_run",
                    value=50,
                ),
                _record(
                    date="2025-01-15",
                    metric="ftp",
                    value=300,
                ),
                _record(
                    date="2025-02-01",
                    metric="vo2max_run",
                    value=55,
                ),
                _record(
                    date="2025-02-15",
                    metric="ftp",
                    value=270,
                ),
            ]
        }
    )

    assert result["metrics"] == {
        "ftp": -10.0,
        "vo2max_run": 10.0,
    }
    assert result["trend"] == "STABLE"


def test_declining_metric_creates_concern() -> None:
    result = PerformanceAnalyzer().analyze(
        {
            "performance_history": [
                _record(
                    date="2025-01-01",
                    metric="css",
                    value=1.5,
                ),
                _record(
                    date="2025-02-01",
                    metric="css",
                    value=1.4,
                ),
            ]
        }
    )

    assert result["trend"] == "DECLINING"
    assert result["concerns"] == [
        "Performance in calo"
    ]
    assert result["strengths"] == []


def test_change_within_two_percent_is_stable() -> None:
    result = PerformanceAnalyzer().analyze(
        {
            "performance_history": [
                _record(
                    date="2025-01-01",
                    metric="vo2max_bike",
                    value=50,
                ),
                _record(
                    date="2025-02-01",
                    metric="vo2max_bike",
                    value=50.5,
                ),
            ]
        }
    )

    assert result["trend"] == "STABLE"
    assert result["metrics"]["vo2max_bike"] == 1.0


def test_unknown_when_no_metric_has_two_valid_values() -> None:
    result = PerformanceAnalyzer().analyze(
        {
            "performance_history": [
                _record(
                    date="2025-01-01",
                    metric="ftp",
                    value=280,
                ),
                _record(
                    date="2025-02-01",
                    metric="css",
                    value=1.4,
                ),
            ]
        }
    )

    assert result["trend"] == "UNKNOWN"
    assert result["metrics"] == {}
    assert result["reasons"] == [
        "Storico performance confrontabile insufficiente"
    ]


def test_invalid_records_are_ignored() -> None:
    result = PerformanceAnalyzer().analyze(
        {
            "performance_history": [
                None,
                {},
                _record(
                    date="invalid-date",
                    metric="ftp",
                    value=250,
                ),
                _record(
                    date="2025-01-01",
                    metric="ftp",
                    value="not-a-number",
                ),
                _record(
                    date="2025-01-01",
                    metric="ftp",
                    value=250,
                ),
                _record(
                    date="2025-02-01",
                    metric="ftp",
                    value=275,
                ),
            ]
        }
    )

    assert result["trend"] == "IMPROVING"
    assert result["metrics"]["ftp"] == 10.0


def test_zero_initial_value_does_not_raise() -> None:
    result = PerformanceAnalyzer().analyze(
        {
            "performance_history": [
                _record(
                    date="2025-01-01",
                    metric="ftp",
                    value=0,
                ),
                _record(
                    date="2025-02-01",
                    metric="ftp",
                    value=100,
                ),
            ]
        }
    )

    assert result["trend"] == "UNKNOWN"
    assert result["metrics"] == {}


def test_legacy_wide_records_are_still_supported() -> None:
    result = PerformanceAnalyzer().analyze(
        {
            "performance_history": [
                {
                    "date": "2025-01-01",
                    "vo2max_run": 50,
                    "ftp": 250,
                },
                {
                    "date": "2025-02-01",
                    "vo2max_run": 55,
                    "ftp": 275,
                },
            ]
        }
    )

    assert result["trend"] == "IMPROVING"
    assert result["metrics"] == {
        "ftp": 10.0,
        "vo2max_run": 10.0,
    }


def test_preserves_legacy_output_keys() -> None:
    result = PerformanceAnalyzer().analyze(
        {
            "performance_history": []
        }
    )

    for key in (
        "trend",
        "metrics",
        "strengths",
        "concerns",
        "reasons",
    ):
        assert key in result