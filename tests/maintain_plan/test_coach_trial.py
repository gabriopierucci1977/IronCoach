from dataclasses import replace
from hashlib import sha256
import http.client
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlencode

from backend.maintain_plan.coach_review import review_subject
from backend.maintain_plan.coach_trial import available_activities, create_trial
from backend.maintain_plan.coach_trial_web import make_trial_handler, render_trial_page
from backend.maintain_plan.models import Discipline
from backend.maintain_plan.repository import MaintainPlanRepository
from tests.maintain_plan.fixtures import NOW, RUN_SESSION


def _archive(tmp_path):
    path = tmp_path / "real-maintain-plan.db"
    repository = MaintainPlanRepository(path)
    repository.create_actual_session(RUN_SESSION)
    repository.create_actual_session(replace(
        RUN_SESSION, session_id="swim-1",
        components=(replace(RUN_SESSION.components[0], discipline=Discipline.SWIM),)))
    return path


def test_trial_copies_only_selected_real_activity_and_never_changes_archive(tmp_path):
    archive = _archive(tmp_path)
    before = sha256(archive.read_bytes()).digest()
    activities = available_activities(archive, "athlete-1")

    trial = create_trial(archive, tmp_path / "trial.db", "athlete-1", ({
        "session_id": "session-1", "sport": "RUN",
        "duration_minutes": 42, "rpe": 6,
    },), now=NOW)

    assert {sport for item in activities for sport in item.sports} == {"RUN", "SWIM"}
    assert sha256(archive.read_bytes()).digest() == before
    assert [item.session_id for item in trial.list_actual_sessions("athlete-1")] == ["session-1"]
    snapshot = trial.list_prescription_snapshots("athlete-1")[0]
    assert snapshot.components[0].quantity.target.value == 42
    assert snapshot.components[0].intensity.target.value == 6
    assert snapshot.provenance.source == "coach-hypothetical-trial"
    assert review_subject(trial, "athlete-1").decision.candidates


def test_page_always_labels_hypothesis_and_does_not_prepopulate_targets(tmp_path):
    archive = _archive(tmp_path)
    page = render_trial_page("athlete-1", activities=available_activities(
        archive, "athlete-1"), action_token="token")

    assert "PIANO IPOTETICO" in page
    assert "solo in questo scenario" in page
    assert "Airtable" in page
    assert 'name="duration_0" min="1" step="1"' in page
    assert 'name="duration_0" value=' not in page
    assert "Non vengono inventate attività mancanti" in render_trial_page(
        "athlete-1", activities=())


def test_browser_flow_writes_only_trial_database(tmp_path):
    archive = _archive(tmp_path)
    trial = tmp_path / "trial.db"
    before = sha256(archive.read_bytes()).digest()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_trial_handler(
        str(archive), str(trial), action_token="secret"))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        connection = http.client.HTTPConnection(host, port)
        connection.request("GET", "/?subject=athlete-1")
        response = connection.getresponse()
        assert response.status == 200
        assert "PIANO IPOTETICO" in response.read().decode()
        payload = urlencode({
            "operation": "create", "action_token": "secret", "subject": "athlete-1",
            "selected": "0", "session_0": "swim-1", "sport_0": "SWIM",
            "duration_0": "35", "rpe_0": "5",
        })
        connection.request("POST", "/", payload, {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": f"http://{host}:{port}", "Cookie": "ironcoach_action=secret",
        })
        created = connection.getresponse()
        body = created.read().decode()
        assert created.status == 200
        assert "Scenario ipotetico creato" in body
        assert "Conferma abbinamento nello scenario di prova" in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert trial.is_file()
    assert sha256(archive.read_bytes()).digest() == before
