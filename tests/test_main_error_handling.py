"""
Test della gestione controllata degli errori nel programma principale.
"""

import backend.main as main_module


def test_main_returns_zero_on_success(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        main_module,
        "run_pipeline",
        lambda: "REPORT TEST",
    )

    exit_code = main_module.main()

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "IRONCOACH BETA 0.3" in output
    assert "REPORT TEST" in output
    assert "IRONCOACH NON COMPLETATO" not in output


def test_main_returns_one_and_prints_controlled_error(
    monkeypatch,
    capsys,
) -> None:
    original_error = RuntimeError(
        "Airtable non raggiungibile"
    )

    def fail_pipeline():
        raise main_module.IronCoachExecutionError(
            phase="connessione ad Airtable",
            original_error=original_error,
        )

    monkeypatch.setattr(
        main_module,
        "run_pipeline",
        fail_pipeline,
    )

    exit_code = main_module.main()

    output = capsys.readouterr().out

    assert exit_code == 1
    assert "IRONCOACH NON COMPLETATO" in output
    assert "Fase: connessione ad Airtable" in output
    assert (
        "RuntimeError: Airtable non raggiungibile"
        in output
    )
    assert "Traceback" not in output


def test_execute_phase_preserves_phase_and_original_error() -> None:
    original_error = ValueError(
        "configurazione non valida"
    )

    def fail():
        raise original_error

    try:
        main_module._execute_phase(
            "caricamento configurazione runtime",
            fail,
        )
    except main_module.IronCoachExecutionError as exc:
        assert (
            exc.phase
            == "caricamento configurazione runtime"
        )
        assert exc.original_error is original_error
    else:
        raise AssertionError(
            "IronCoachExecutionError non sollevato"
        )


def test_run_pipeline_reports_context_build_phase(
    monkeypatch,
) -> None:
    class FakeClient:
        pass

    class FakeBuilder:
        def __init__(
            self,
            client,
            runtime_config=None,
            garmin_source_state_path=None,
        ):
            self.client = client
            self.runtime_config = runtime_config
            self.garmin_source_state_path = garmin_source_state_path

        def build(self):
            raise OSError(
                "dati Airtable non disponibili"
            )

    monkeypatch.setattr(
        main_module,
        "get_runtime_config",
        lambda: object(),
    )
    monkeypatch.setattr(
        main_module,
        "AirtableClient",
        FakeClient,
    )
    monkeypatch.setattr(
        main_module,
        "ContextBuilder",
        FakeBuilder,
    )
    monkeypatch.setattr(
        main_module,
        "_sync_garmin_live_best_effort",
        lambda: None,
    )

    try:
        main_module.run_pipeline()
    except main_module.IronCoachExecutionError as exc:
        assert (
            exc.phase
            == "costruzione contesto atleta"
        )
        assert isinstance(
            exc.original_error,
            OSError,
        )
    else:
        raise AssertionError(
            "IronCoachExecutionError non sollevato"
        )