from pathlib import Path

from backend.config import DEFAULT_MAINTAIN_PLAN_SHADOW_ENABLED


PROTECTED_RUNTIME_MODULES = (
    "runtime_shadow_chain",
    "runtime_shadow_consistency",
    "runtime_outcome_shadow",
    "runtime_shadow_orchestration",
)


def test_new_shadow_chain_modules_are_not_imported_by_legacy_runtime():
    backend_root = Path(__file__).resolve().parents[2] / "backend"
    offenders = []
    for source in backend_root.rglob("*.py"):
        if "maintain_plan" in source.parts:
            continue
        text = source.read_text(encoding="utf-8")
        for module in PROTECTED_RUNTIME_MODULES:
            if f"backend.maintain_plan.{module}" in text:
                offenders.append(f"{source}:{module}")
    assert offenders == []


def test_maintain_plan_shadow_remains_default_off():
    assert DEFAULT_MAINTAIN_PLAN_SHADOW_ENABLED is False
