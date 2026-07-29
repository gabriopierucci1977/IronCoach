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
        }