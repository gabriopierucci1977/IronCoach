"""
IronCoach Decision Model

Rappresenta la decisione ufficiale
prodotta dal Coach Engine.
"""


class Decision:

    def __init__(
        self,
        decision,
        reason,
        priority,
        confidence,
        strategy,
        recommended_action,
        modified_workout=None,
        reasoning=None,
        risk_level=None,
        intelligence=None,
        decision_id=None,
        rule_id=None,
        primary_intent=None,
        supporting_intents=None,
    ):

        self.decision = decision
        self.reason = reason
        self.priority = priority
        self.confidence = confidence
        self.strategy = strategy
        self.recommended_action = recommended_action
        self.modified_workout = modified_workout
        self.reasoning = reasoning or []
        self.risk_level = risk_level or "NORMAL"
        self.intelligence = intelligence or {}

        # Beta 0.4 decision metadata.
        #
        # Optional for backward compatibility.
        self.decision_id = decision_id
        self.rule_id = rule_id
        self.primary_intent = primary_intent
        self.supporting_intents = list(
            supporting_intents or []
        )

    def to_dict(self):

        return {
            "decision": self.decision,
            "reason": self.reason,
            "priority": self.priority,
            "confidence": self.confidence,
            "strategy": self.strategy,
            "recommended_action": self.recommended_action,
            "modified_workout": self.modified_workout,
            "reasoning": self.reasoning,
            "risk_level": self.risk_level,
            "intelligence": self.intelligence,
            "decision_id": self.decision_id,
            "rule_id": self.rule_id,
            "primary_intent": self.primary_intent,
            "supporting_intents": self.supporting_intents,
        }