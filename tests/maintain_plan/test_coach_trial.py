from dataclasses import replace
from hashlib import sha256
import http.client
import re
import sqlite3
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlencode
from pathlib import Path

from backend.maintain_plan.coach_review import resolve_coach_choice, review_subject
import backend.maintain_plan.coach_review as coach_review_module
from backend.maintain_plan.coach_trial import available_activities, create_trial
from backend.maintain_plan.coach_trial_web import make_trial_handler, render_trial_page
from backend.maintain_plan.models import Discipline
from backend.maintain_plan.repository import MaintainPlanRepository
from tests.maintain_plan.fixtures import NOW, RUN_PRESCRIPTION, RUN_SESSION


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
        cookie = created.getheader("Set-Cookie").split(";", 1)[0]
        assert created.status == 200
        assert "Scenario ipotetico creato" in body
        assert "Conferma abbinamento nello scenario di prova" in body
        prescription = re.search(r'name="prescription" value="([^"]+)"', body).group(1)
        session = re.search(r'name="session" value="([^"]+)"', body).group(1)
        confirmation = urlencode({
            "operation": "confirm", "action_token": "secret", "subject": "athlete-1",
            "prescription": prescription, "session": session,
        })
        connection.request("POST", "/", confirmation, {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": f"http://{host}:{port}", "Cookie": cookie,
        })
        evaluated = connection.getresponse()
        evaluated_page = evaluated.read().decode()
        assert evaluated.status == 200
        assert "Valutazione salvata" in evaluated_page
        assert "Conferma abbinamento nello scenario di prova" not in evaluated_page
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

        current_page = result
        used_tokens = set()
        for completed in range(1, 4):
            form = re.search(r'<form method="post" class="candidate">(.*?)</form>',
                             current_page)
            assert form is not None
            prescription = re.search(
                r'name="prescription" value="([^"]+)"', form.group(1)).group(1)
            session = re.search(r'name="session" value="([^"]+)"',
                                form.group(1)).group(1)
            current_token = re.search(
                r'name="action_token" value="([^"]+)"', form.group(1)).group(1)
            assert current_token not in used_tokens
            used_tokens.add(current_token)
            confirmation = urlencode({
                "operation": "confirm", "action_token": current_token,
                "subject": "athlete-1", "prescription": prescription,
                "session": session,
            })
            connection.request("POST", "/", confirmation, {
                "Host": loopback_host, "Origin": public_origin, "Cookie": cookie,
                "Content-Type": "application/x-www-form-urlencoded",
            })
            response = connection.getresponse()
            current_page = response.read().decode()
            cookie = response.getheader("Set-Cookie").split(";", 1)[0]
            assert response.status == 200
            assert current_page.count("Valutazione salvata:") == completed
            assert current_page.count(
                "Conferma abbinamento nello scenario di prova") == 3 - completed
        with sqlite3.connect(trial) as connection_db:
            assert connection_db.execute(
                "SELECT count(*) FROM maintain_plan_prescription_mappings").fetchone()[0] == 3
            assert connection_db.execute(
                "SELECT count(*) FROM maintain_plan_execution_evaluations").fetchone()[0] == 3
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


def test_confirmed_post_shows_saved_evaluation_not_expired_confirmation(tmp_path):
    archive = _archive(tmp_path)
    trial = create_trial(archive, tmp_path / "trial.db", "athlete-1", ({
        "session_id": "session-1", "sport": "RUN",
        "duration_minutes": 50, "rpe": 8,
    },), now=NOW)
    initial = review_subject(trial, "athlete-1", now=NOW)
    candidate = initial.decision.candidates[0]

    confirmed = resolve_coach_choice(
        trial, "athlete-1", candidate.prescription_snapshot_id,
        candidate.session_id, now=NOW)
    page = render_trial_page("athlete-1", review=confirmed,
                             action_token="no-longer-actionable")

    assert "Valutazione appena salvata" in page
    assert "Conferma abbinamento nello scenario di prova" not in page
    assert trial.get_execution_evaluation(confirmed.evaluation.evaluation_id) == confirmed.evaluation


def test_secondary_garmin_duration_and_missing_rpe_remain_insufficient(tmp_path):
    archive = tmp_path / "real-maintain-plan.db"
    repository = MaintainPlanRepository(archive)
    component = replace(
        RUN_SESSION.components[0], quantity_observation=None,
        quantity_primary_metric=None, quantity_unit=None,
        secondary_metrics=({"metric": "duration", "value": 50, "unit": "min"},),
        intensity_methods=(), intensity_observations=None,
        missing_fields=("quantity_primary_metric", "intensity_methods"),
    )
    repository.create_actual_session(replace(RUN_SESSION, components=(component,)))
    before = sha256(archive.read_bytes()).digest()
    trial = create_trial(archive, tmp_path / "trial.db", "athlete-1", ({
        "session_id": "session-1", "sport": "RUN",
        "duration_minutes": 50, "rpe": 8,
    },), now=NOW)
    candidate = review_subject(trial, "athlete-1", now=NOW).decision.candidates[0]

    confirmed = resolve_coach_choice(
        trial, "athlete-1", candidate.prescription_snapshot_id,
        candidate.session_id, now=NOW)
    result = confirmed.evaluation.component_results[0]
    page = render_trial_page("athlete-1", review=confirmed)

    assert result.quantity.status.value == "INSUFFICIENT_DATA"
    assert result.intensity.status.value == "INSUFFICIENT_DATA"
    assert confirmed.evaluation.overall.value == "INSUFFICIENT_DATA"
    assert "Dati insufficienti" in page
    assert "metriche secondarie non è trattata come equivalente" in page
    assert "RPE osservato assente" in page
    assert sha256(archive.read_bytes()).digest() == before


def test_get_reads_previous_schema_without_migrating_real_archive(tmp_path):
    archive = _archive(tmp_path)
    with sqlite3.connect(archive) as connection:
        connection.execute("DROP INDEX idx_mp_mappings_snapshot_unique")
        connection.execute("DROP INDEX idx_mp_mappings_session_unique")
        connection.execute("DELETE FROM maintain_plan_schema_migrations WHERE version = 8")
    before = sha256(archive.read_bytes()).digest()
    trial = tmp_path / "trial.db"
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_trial_handler(
        str(archive), str(trial), action_token="secret"))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        connection = http.client.HTTPConnection(host, port)
        connection.request("GET", "/?subject=athlete-1")
        response = connection.getresponse()
        page = response.read().decode()
        assert response.status == 200
        assert page.count("Usa questa attività") == 3
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

    assert sha256(archive.read_bytes()).digest() == before
    with sqlite3.connect(f"file:{archive}?mode=ro", uri=True) as connection:
        assert connection.execute(
            "SELECT max(version) FROM maintain_plan_schema_migrations").fetchone()[0] == 7
        indexes = {row[1] for row in connection.execute(
            "PRAGMA index_list(maintain_plan_prescription_mappings)")}
    assert "idx_mp_mappings_snapshot_unique" not in indexes
    assert "idx_mp_mappings_session_unique" not in indexes
    assert not trial.exists()


def test_subject_query_ignores_corrupt_payload_owned_by_another_athlete(tmp_path):
    archive = tmp_path / "real-maintain-plan.db"
    repository = MaintainPlanRepository(archive)
    repository.create_actual_session(RUN_SESSION)
    repository.create_actual_session(replace(
        RUN_SESSION, session_id="foreign-session", subject_ref="athlete-2"))
    with sqlite3.connect(archive) as connection:
        connection.execute(
            "UPDATE maintain_plan_actual_sessions SET payload_json = ? "
            "WHERE session_id = ?", ("{corrupt", "foreign-session"))
    before = sha256(archive.read_bytes()).digest()

    activities = available_activities(archive, "athlete-1")

    assert [item.session_id for item in activities] == ["session-1"]
    assert sha256(archive.read_bytes()).digest() == before


def test_suspended_candidate_shows_reason_without_confirmation_form(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "trial.db")
    conflict = {
        "conflict_id": "conflict-1",
        "schema_version": "maintain-plan-source-conflict/1.0.0-draft",
        "field_path": "components.run.quantity_observation",
        "values": ({"value": 59, "source": "Garmin"},
                   {"value": 60, "source": "other"}),
        "provenance": {}, "captured_at": NOW,
        "missing_fields": (), "warnings": (),
    }
    repository.create_prescription_snapshot(RUN_PRESCRIPTION)
    repository.create_actual_session(replace(RUN_SESSION, source_conflicts=(conflict,)))

    review = review_subject(repository, "athlete-1", now=NOW)
    page = render_trial_page("athlete-1", review=review, action_token="token")

    assert "Valutazione sospesa" in page
    assert "dati in conflitto" in page
    assert "Conferma abbinamento nello scenario di prova" not in page
    assert repository.list_prescription_mappings() == ()


def test_mapping_saved_evaluation_failure_is_rendered_after_database_reread(
        tmp_path, monkeypatch):
    archive = _archive(tmp_path)
    before = sha256(archive.read_bytes()).digest()
    trial = tmp_path / "trial.db"
    original_evaluate = coach_review_module.evaluate

    def fail_evaluation(*_args, **_kwargs):
        raise RuntimeError("interruzione simulata")

    monkeypatch.setattr(coach_review_module, "evaluate", fail_evaluation)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_trial_handler(
        str(archive), str(trial), action_token="secret"))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        connection = http.client.HTTPConnection(host, port)
        create = urlencode({
            "operation": "create", "action_token": "secret", "subject": "athlete-1",
            "selected": "0", "session_0": "swim-1", "sport_0": "SWIM",
            "duration_0": "45", "rpe_0": "6",
        })
        connection.request("POST", "/", create, {
            "Origin": f"http://{host}:{port}", "Cookie": "ironcoach_action=secret",
            "Content-Type": "application/x-www-form-urlencoded",
        })
        created = connection.getresponse()
        page = created.read().decode()
        cookie = created.getheader("Set-Cookie").split(";", 1)[0]
        prescription = re.search(r'name="prescription" value="([^"]+)"', page).group(1)
        session = re.search(r'name="session" value="([^"]+)"', page).group(1)
        confirm = urlencode({
            "operation": "confirm", "action_token": "secret", "subject": "athlete-1",
            "prescription": prescription, "session": session,
        })
        connection.request("POST", "/", confirm, {
            "Origin": f"http://{host}:{port}", "Cookie": cookie,
            "Content-Type": "application/x-www-form-urlencoded",
        })
        response = connection.getresponse()
        result = response.read().decode()
        assert response.status == 200
        assert "Abbinamento salvato nello scenario di prova" in result
        assert "Valutazione sospesa" in result
        assert "Valutazione non completata" in result
        assert "Scenario non salvato" not in result
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        monkeypatch.setattr(coach_review_module, "evaluate", original_evaluate)

    trial_repository = MaintainPlanRepository(trial)
    assert len(trial_repository.list_prescription_mappings()) == 1
    with sqlite3.connect(trial) as connection:
        assert connection.execute(
            "SELECT count(*) FROM maintain_plan_execution_evaluations").fetchone()[0] == 0
    assert sha256(archive.read_bytes()).digest() == before
