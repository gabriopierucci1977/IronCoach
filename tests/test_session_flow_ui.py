from datetime import datetime, timezone
from types import SimpleNamespace

from backend.maintain_plan.coach_web import render_page
from backend.maintain_plan.session_flow import (list_sessions, validate_imported_plan,
    persist_imported_plan, load_imported_plan, build_export_prompt)
from backend.maintain_plan.models import Discipline


def _session(i, sport="RUN"):
    component = SimpleNamespace(discipline=Discipline.RUN if sport == "RUN" else Discipline.BIKE, quantity_primary_metric="distance",
                               missing_fields=(), secondary_metrics=(), blocks=(), quantity_observation=None,
                               start=None, end=None)
    return SimpleNamespace(session_id=str(i), subject_ref="a", start=datetime(2025, 1, 1, tzinfo=timezone.utc),
                           end=None, components=(component,), source_activities=(), missing_fields=(), athlete_feedback=None)


def test_pagination_and_filtering():
    class Repo:
        def list_actual_sessions(self, subject): return tuple(_session(i, "BIKE" if i == 1 else "RUN") for i in range(51))
    page = list_sessions(Repo(), "a", page=1, sport="RUN")
    assert page.pages == 1 and len(page.items) == 50


def test_render_contains_navigation_export_and_import_preview():
    html = render_page("a", sessions=(_session(1),), selected_session=_session(1), page=1, pages=2)
    assert "Esamina" in html and "Esporta dati verso ChatGPT" in html
    assert "chatgpt.com/?q=" in html and "Importa piano JSON" in html


def test_plan_json_validation():
    assert validate_imported_plan('{"sessions":[{"date":"2025-01-01T10:00:00Z","sport":"RUN"}]}')

def test_import_persists_and_reloads_after_restart(tmp_path):
    value = {"sessions": [{"date": "2025-01-01T10:00:00Z", "sport": "RUN"}]}
    persist_imported_plan(value, tmp_path / "plan.json")
    assert load_imported_plan(tmp_path / "plan.json") == value

def test_export_prompt_contains_session_history_prescription_and_feedback():
    session = _session(1); session.athlete_feedback = {"rpe": 8, "comment": "duro"}
    prompt = build_export_prompt(session, [session], {"id": "p1"})
    assert '"session_id": "1"' in prompt and "storico_recente" in prompt
    assert '"id": "p1"' in prompt and "duro" in prompt and "8" in prompt

from backend.maintain_plan.session_flow import preview_text_plan, text_to_plan


def test_text_plan_is_converted_to_internal_sessions():
    plan = text_to_plan(
        "06/10/2026 - corsa facile per 45 minuti\n"
        "2026-10-08 - bici con 6 ripetute"
    )
    assert [item["sport"] for item in plan["sessions"]] == ["RUN", "BIKE"]
    assert preview_text_plan("2026-10-06 - nuoto tecnico")[0]["sport"] == "SWIM"


def test_text_plan_reports_missing_date():
    try:
        text_to_plan("corsa facile senza data")
    except ValueError as error:
        assert "data" in str(error)
    else:
        raise AssertionError(
            "La descrizione senza data deve chiedere un chiarimento"
        )
