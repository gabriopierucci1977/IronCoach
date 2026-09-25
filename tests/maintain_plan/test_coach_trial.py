from dataclasses import replace
from hashlib import sha256
import http.client
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlencode
from pathlib import Path

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
    repository.create_actual_session(replace(
        RUN_SESSION, session_id="bike-1",
        components=(replace(RUN_SESSION.components[0], discipline=Discipline.BIKE),)))
    return path


def test_trial_copies_only_selected_real_activity_and_never_changes_archive(tmp_path):
    archive = _archive(tmp_path)
    before = sha256(archive.read_bytes()).digest()
    activities = available_activities(archive, "athlete-1")

    trial = create_trial(archive, tmp_path / "trial.db", "athlete-1", ({
        "session_id": "session-1", "sport": "RUN",
        "duration_minutes": 42, "rpe": 6,
    },), now=NOW)

    assert {sport for item in activities for sport in item.sports} == {"RUN", "SWIM", "BIKE"}
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


def _codespaces_server(tmp_path):
    archive = _archive(tmp_path)
    trial = tmp_path / "trial.db"
    environment = {
        "CODESPACE_NAME": "ironcoach-space",
        "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN": "app.github.dev",
    }
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_trial_handler(
        str(archive), str(trial), action_token="codespace-secret",
        environment=environment))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return archive, trial, server, thread


def test_private_codespaces_get_fill_post_creates_and_shows_scenario(tmp_path):
    archive, trial, server, thread = _codespaces_server(tmp_path)
    _host, port = server.server_address
    loopback_host = f"localhost:{port}"
    public_origin = f"https://ironcoach-space-{port}.app.github.dev"
    before = sha256(archive.read_bytes()).digest()
    try:
        connection = http.client.HTTPConnection("127.0.0.1", port)
        connection.request("GET", "/?subject=athlete-1", headers={"Host": loopback_host})
        initial = connection.getresponse()
        page = initial.read().decode()
        cookie = initial.getheader("Set-Cookie").split(";", 1)[0]
        assert initial.status == 200
        assert page.count("Usa questa attività") == 3
        assert "Secure" in initial.getheader("Set-Cookie")

        payload = urlencode([
            ("operation", "create"), ("action_token", "codespace-secret"),
            ("subject", "athlete-1"),
            ("selected", "0"), ("session_0", "swim-1"),
            ("sport_0", "SWIM"), ("duration_0", "45"), ("rpe_0", "6"),
            ("selected", "1"), ("session_1", "session-1"),
            ("sport_1", "RUN"), ("duration_1", "50"), ("rpe_1", "8"),
            ("selected", "2"), ("session_2", "bike-1"),
            ("sport_2", "BIKE"), ("duration_2", "90"), ("rpe_2", "7"),
        ])
        connection.request("POST", "/", payload, {
            "Host": loopback_host, "Origin": public_origin, "Cookie": cookie,
            "Content-Type": "application/x-www-form-urlencoded",
        })
        posted = connection.getresponse()
        result = posted.read().decode()
        assert posted.status == 200
        assert "Scenario ipotetico creato" in result
        assert "Azione respinta" not in result
        assert "Nessuna attività Garmin" not in result
        repository = MaintainPlanRepository(trial)
        assert len(repository.list_actual_sessions("athlete-1")) == 3
        assert len(repository.list_prescription_snapshots("athlete-1")) == 3
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert sha256(archive.read_bytes()).digest() == before


def test_rejected_codespaces_post_explains_reason_and_keeps_activities(tmp_path):
    _archive_path, trial, server, thread = _codespaces_server(tmp_path)
    _host, port = server.server_address
    try:
        connection = http.client.HTTPConnection("127.0.0.1", port)
        payload = urlencode({"operation": "create", "action_token": "codespace-secret",
                             "subject": "athlete-1"})
        connection.request("POST", "/", payload, {
            "Host": f"localhost:{port}",
            "Origin": f"https://ironcoach-space-{port}.app.github.dev",
            "Content-Type": "application/x-www-form-urlencoded",
        })
        rejected = connection.getresponse()
        page = rejected.read().decode()
        cookie = rejected.getheader("Set-Cookie").split(";", 1)[0]
        assert rejected.status == 403
        assert "cookie di autorizzazione mancante" in page
        assert page.count("Usa questa attività") == 3
        assert "Nessuna attività Garmin" not in page

        connection.request("POST", "/", payload, {
            "Host": f"localhost:{port}", "Origin": "https://attacker.example",
            "Cookie": cookie, "Content-Type": "application/x-www-form-urlencoded",
        })
        wrong_origin = connection.getresponse()
        wrong_origin_page = wrong_origin.read().decode()
        assert wrong_origin.status == 403
        assert "origine HTTPS inattesa" in wrong_origin_page
        assert wrong_origin_page.count("Usa questa attività") == 3
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert not trial.exists()


def test_failed_trial_is_atomic_and_retry_replaces_without_duplicates(tmp_path):
    archive = _archive(tmp_path)
    trial_path = tmp_path / "trial.db"
    good = ({"session_id": "session-1", "sport": "RUN",
             "duration_minutes": 50, "rpe": 8},)
    create_trial(archive, trial_path, "athlete-1", good, now=NOW)
    original = trial_path.read_bytes()

    bad = good + ({"session_id": "missing", "sport": "BIKE",
                   "duration_minutes": 90, "rpe": 7},)
    try:
        create_trial(archive, trial_path, "athlete-1", bad, now=NOW)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid trial should fail")
    assert trial_path.read_bytes() == original
    assert not tuple(Path(tmp_path).glob(".trial.db.*.tmp*"))

    retried = create_trial(archive, trial_path, "athlete-1", good, now=NOW)
    assert len(retried.list_actual_sessions("athlete-1")) == 1
    assert len(retried.list_prescription_snapshots("athlete-1")) == 1
