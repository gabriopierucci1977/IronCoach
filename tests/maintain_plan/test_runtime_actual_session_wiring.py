from pathlib import Path


def test_wiring_precedes_decision_memory_and_uses_only_garmin_history():
    source = (Path(__file__).parents[2] / "backend" / "main.py").read_text()
    capture = source.index('"cattura attività MAINTAIN_PLAN"')
    memory = source.index('"caricamento evidenza Decision Memory"')
    assert capture < memory
    block = source[capture:memory]
    assert 'context.get("garmin_training_history")' in block
    assert 'context.get("training")' not in block
    assert "if not dry_run:" in source[source.rfind("if not dry_run:", 0, capture):capture]
