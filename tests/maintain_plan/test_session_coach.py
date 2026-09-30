from dataclasses import replace
from datetime import timedelta
import http.client
from http.server import ThreadingHTTPServer
from threading import Thread

from backend.maintain_plan.coach_web import make_handler
from backend.maintain_plan.repository import MaintainPlanRepository
from backend.maintain_plan.session_coach import ai_comment, save_relation
from tests.maintain_plan.fixtures import NOW, RUN_PRESCRIPTION, RUN_SESSION


def test_ai_comment_uses_session_and_pertinent_history_without_a_plan(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "synthetic.db")
    previous = replace(RUN_SESSION, session_id="previous", start=NOW - timedelta(days=2))
    repository.create_actual_session(previous)
    repository.create_actual_session(RUN_SESSION)
    captured = {}

    def generator(payload):
        captured.update(payload)
        return {"observed": "Corsa di 60 minuti.",
                "interpretation": "Seduta aerobica regolare.",
                "uncertainties": "RPE non disponibile."}

    comment = ai_comment(repository, "athlete-1", "session-1", generator=generator)

    assert comment.available
    assert captured["session"]["duration_minutes"] == 60
    assert captured["pertinent_history"][0]["session_id"] == "previous"
    assert captured["plan_comparison"] is None


def test_ai_comment_is_explicitly_unavailable_without_configuration(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    repository = MaintainPlanRepository(tmp_path / "synthetic.db")
    repository.create_actual_session(RUN_SESSION)

    comment = ai_comment(repository, "athlete-1", "session-1")

    assert not comment.available
    assert "OPENAI_API_KEY non configurata" in comment.unavailable_reason
    assert comment.interpretation == ""


def test_ambiguous_relation_is_persisted_without_creating_a_mapping(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "synthetic.db")
    repository.create_prescription_snapshot(RUN_PRESCRIPTION)
    repository.create_actual_session(RUN_SESSION)

    save_relation(repository, "athlete-1", "session-1", "AUTONOMOUS", now=NOW)

    assert repository.get_session_relation("session-1") == ("AUTONOMOUS", None)
    assert repository.list_prescription_mappings() == ()


def test_browser_can_open_a_session_when_no_prescription_exists(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    repository = MaintainPlanRepository(tmp_path / "synthetic.db")
    repository.create_actual_session(RUN_SESSION)
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), make_handler(str(repository.database_path)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        connection = http.client.HTTPConnection(host, port)
        connection.request("GET", "/?subject=athlete-1&session=session-1")
        response = connection.getresponse()
        page = response.read().decode()
        assert response.status == 200
        assert "Sessione autonoma" in page
        assert "Parere IA non disponibile" in page
        assert "OPENAI_API_KEY non configurata" in page
        assert "RPE facoltativo" in page
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
