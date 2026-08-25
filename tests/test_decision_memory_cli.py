"""
Test Decision Memory CLI.
"""

import backend.main as main_module


def test_main_accepts_decision_memory_flag():

    parser = main_module._build_argument_parser()

    args = parser.parse_args(
        [
            "--decision-memory",
        ]
    )

    assert args.decision_memory is True