from backend.config import RuntimeConfig


def test_decision_memory_database_path_has_project_default():
    config = RuntimeConfig()

    assert (
        config.decision_memory_database_path
        == "data/ironcoach_memory.db"
    )


def test_decision_memory_database_path_can_be_overridden_from_env(
    monkeypatch,
):
    monkeypatch.setenv(
        "IRONCOACH_DECISION_MEMORY_DATABASE_PATH",
        "/tmp/ironcoach-test-memory.db",
    )

    config = RuntimeConfig.from_env()

    assert (
        config.decision_memory_database_path
        == "/tmp/ironcoach-test-memory.db"
    )