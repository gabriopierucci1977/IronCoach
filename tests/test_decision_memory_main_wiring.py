"""
Test main Decision Memory wiring.
"""

import backend.main as main_module


def test_main_exposes_decision_memory_factory():
    assert hasattr(
        main_module,
        "create_decision_memory_orchestrator",
    )