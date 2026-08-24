from backend.decision import Decision


def test_decision_remains_backward_compatible():
    decision = Decision(
        decision="CONFERMA",
        reason="Condizioni favorevoli.",
        priority="Performance",
        confidence=95,
        strategy="KEEP_PLAN",
        recommended_action="Allenamento confermato.",
    )

    result = decision.to_dict()

    assert result["decision"] == "CONFERMA"
    assert result["strategy"] == "KEEP_PLAN"

    assert result["decision_id"] is None
    assert result["rule_id"] is None
    assert result["primary_intent"] is None
    assert result["supporting_intents"] == []


def test_decision_serializes_beta_04_metadata():
    decision = Decision(
        decision="RECUPERA",
        reason="Problematica fisica critica.",
        priority="Recovery",
        confidence=99,
        strategy="RECOVERY",
        recommended_action="Sospendi il carico.",
        decision_id="decision-123",
        rule_id="INJURY_CRITICAL",
        primary_intent="PROTECT_INJURY",
        supporting_intents=[
            "RESTORE_RECOVERY",
            "REDUCE_LOAD",
        ],
    )

    result = decision.to_dict()

    assert result["decision_id"] == "decision-123"
    assert result["rule_id"] == "INJURY_CRITICAL"
    assert result["primary_intent"] == "PROTECT_INJURY"
    assert result["supporting_intents"] == [
        "RESTORE_RECOVERY",
        "REDUCE_LOAD",
    ]


def test_supporting_intents_default_is_not_shared_between_instances():
    first = Decision(
        decision="CONFERMA",
        reason="OK",
        priority="Performance",
        confidence=95,
        strategy="KEEP_PLAN",
        recommended_action="Conferma.",
    )

    second = Decision(
        decision="CONFERMA",
        reason="OK",
        priority="Performance",
        confidence=95,
        strategy="KEEP_PLAN",
        recommended_action="Conferma.",
    )

    first.supporting_intents.append("REDUCE_LOAD")

    assert second.supporting_intents == []
