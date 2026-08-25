"""
Test Decision Memory CLI output.
"""

import backend.main as main_module


def test_main_decision_memory_prints_viewer_output(
    monkeypatch,
    capsys,
):

    class FakeViewer:

        def latest(
            self,
            limit=10,
        ):
            return [
                {
                    "decision_action": "ADATTA",
                    "strategy": "ADAPT",
                }
            ]

    monkeypatch.setattr(
        main_module,
        "DecisionMemoryViewer",
        lambda repository: FakeViewer(),
    )

    monkeypatch.setattr(
        main_module,
        "DecisionMemoryRepository",
        lambda path: object(),
    )

    monkeypatch.setattr(
        main_module,
        "get_runtime_config",
        lambda: type(
            "Config",
            (),
            {
                "decision_memory_database_path": (
                    "memory.db"
                )
            },
        )(),
    )

    exit_code = main_module.main(
        [
            "--decision-memory",
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "ADATTA" in output
    assert "ADAPT" in output