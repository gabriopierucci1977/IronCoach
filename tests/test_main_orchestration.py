"""
Test orchestrazione applicazione principale.

Verifica che il flusso principale:
- costruisca il contesto;
- valuti la decisione;
- applichi l'adattamento workout;
- generi il report;
- salvi la decisione finale.

Non usa servizi esterni.
"""

import backend.main as main_module



class FakeClient:
    pass



class FakeContextBuilder:

    def __init__(
        self,
        client,
    ):
        self.client = client

    def build(
        self,
    ):
        return {
            "athlete_profile": {},
            "training": {},
            "recovery": {},
            "nutrition": {},
            "decision": {},
        }



class FakeCoachEngine:

    def evaluate(
        self,
        context,
    ):
        return {
            "decision": "ADATTA",
            "reason": "Test",
            "confidence": 90,
            "strategy": "ADAPT",
        }



class FakeWorkoutAdapter:

    def adapt(
        self,
        context,
        decision,
    ):
        return {
            "strategy": "ADAPT",
            "duration_minutes": 40,
        }



class FakeReportBuilder:

    def build(
        self,
        context,
        decision,
    ):
        assert decision[
            "modified_workout"
        ][
            "duration_minutes"
        ] == 40

        return "REPORT TEST"



class FakeDecisionWriter:

    saved = None

    def __init__(
        self,
        client,
    ):
        self.client = client

    def save(
        self,
        decision,
    ):
        FakeDecisionWriter.saved = decision



def test_main_orchestration_keeps_full_flow(
    monkeypatch,
    capsys,
):

    monkeypatch.setattr(
        main_module,
        "AirtableClient",
        FakeClient,
    )

    monkeypatch.setattr(
        main_module,
        "ContextBuilder",
        FakeContextBuilder,
    )

    monkeypatch.setattr(
        main_module,
        "CoachEngine",
        FakeCoachEngine,
    )

    monkeypatch.setattr(
        main_module,
        "WorkoutAdapter",
        FakeWorkoutAdapter,
    )

    monkeypatch.setattr(
        main_module,
        "ReportBuilder",
        FakeReportBuilder,
    )

    monkeypatch.setattr(
        main_module,
        "DecisionWriter",
        FakeDecisionWriter,
    )


    main_module.main()


    assert FakeDecisionWriter.saved is not None


    assert (
        FakeDecisionWriter.saved[
            "decision"
        ]
        == "ADATTA"
    )


    assert (
        FakeDecisionWriter.saved[
            "modified_workout"
        ][
            "duration_minutes"
        ]
        == 40
    )


    output = capsys.readouterr().out


    assert "REPORT TEST" in output