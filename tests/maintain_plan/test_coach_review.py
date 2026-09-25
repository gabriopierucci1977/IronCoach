from dataclasses import replace
from datetime import timedelta
import http.client
from http.server import ThreadingHTTPServer
from pathlib import Path
import re
import sqlite3
import subprocess
from threading import Thread
from urllib.parse import urlencode

import pytest

import backend.maintain_plan.coach_review as coach_review_module
from backend import main as main_module

from backend.maintain_plan.coach_review import (
    database_review_readiness, format_coach_review, resolve_coach_choice,
    retry_saved_evaluation, review_database, review_subject,
)
from backend.maintain_plan.coach_web import (
    _trusted_origins, configured_database_path, make_handler, render_page,
)
from backend.maintain_plan.matching_service import build_mapping
from backend.maintain_plan.models import (
    PolicyRef, Requiredness, ResolutionMethod, SupportStatus,
)
from backend.maintain_plan.repository import MaintainPlanRepository
from backend.maintain_plan.runtime_matching_decision import DecisionStatus
from tests.maintain_plan.fixtures import NOW, RUN_PRESCRIPTION, RUN_SESSION


def _repository(tmp_path, sessions=(RUN_SESSION,)):
    repository = MaintainPlanRepository(tmp_path / "coach-review.db")
    repository.create_prescription_snapshot(RUN_PRESCRIPTION)
    for session in sessions:
        repository.create_actual_session(session)
    return repository


def test_unique_match_is_saved_and_its_plan_consequence_is_visible(tmp_path):
    repository = _repository(tmp_path)

    review = review_subject(repository, "athlete-1", now=NOW)

    assert review.decision.status is DecisionStatus.MATCHED
    assert repository.list_prescription_mappings() == ()
    review = resolve_coach_choice(repository, "athlete-1", "snapshot-1",
                                  "session-1", now=NOW)
    assert review.evaluation is not None
    assert repository.get_prescription_mapping(
        review.evaluation.prescription_mapping_ref) is not None
    rendered = format_coach_review(review)
    assert "Corrispondenza affidabile salvata" in rendered
    assert f"Conseguenza sul piano: {review.evaluation.overall.value}" in rendered


def test_ambiguity_shows_data_and_asks_coach_without_saving(tmp_path):
    sessions = (RUN_SESSION, replace(RUN_SESSION, session_id="session-2"))
    repository = _repository(tmp_path, sessions)

    review = review_subject(repository, "athlete-1", now=NOW)

    assert review.decision.status is DecisionStatus.CONFIRMATION_REQUIRED
    assert repository.list_prescription_mappings() == ()
    rendered = format_coach_review(review)
    assert "snapshot-1 ← session-1" in rendered
    assert "snapshot-1 ← session-2" in rendered
    assert "quale attività corrisponde" in rendered


def test_no_activity_is_not_interpreted_as_skipped(tmp_path):
    repository = _repository(tmp_path, ())

    rendered = format_coach_review(review_subject(repository, "athlete-1", now=NOW))

    assert "nessun allenamento è considerato saltato" in rendered
    assert repository.list_prescription_mappings() == ()


def test_coach_can_answer_ambiguity_and_get_the_evaluation(tmp_path):
    sessions = (RUN_SESSION, replace(RUN_SESSION, session_id="session-2"))
    repository = _repository(tmp_path, sessions)

    review = resolve_coach_choice(repository, "athlete-1", "snapshot-1",
                                  "session-2", now=NOW)

    mapping = repository.list_prescription_mappings()[0]
    assert mapping.actual_session_ref == "session-2"
    assert mapping.resolution_method is ResolutionMethod.ATHLETE_CONFIRMATION
    assert mapping.actor == "coach"
    assert review.evaluation is not None
    page = render_page("athlete-1", review=review,
                       message="Scelta del coach salvata e piano valutato.")
    assert "Scelta del coach salvata" in page
    assert f"Conseguenza sul piano: {review.evaluation.overall.value}" in page
    assert "Corrispondenza salvata:</strong> snapshot-1 ← session-2" in page
    assert "Conferma questa corrispondenza" not in page

    with sqlite3.connect(repository.database_path) as connection:
        confirmation_ids = [row[0] for row in connection.execute(
            "SELECT confirmation_id FROM maintain_plan_confirmations "
            "ORDER BY confirmation_id").fetchall()]
        assert connection.execute(
            "SELECT count(*) FROM maintain_plan_matching_results"
        ).fetchone()[0] == 2
    assert len(confirmation_ids) == 2
    confirmations = [repository.get_confirmation(item) for item in confirmation_ids]
    answered = next(item for item in confirmations if item.selected_session_ref)
    request = next(item for item in confirmations if not item.selected_session_ref)
    assert request.candidate_session_refs == ("session-1", "session-2")
    assert answered.candidate_session_refs == request.candidate_session_refs
    assert answered.selected_session_ref == "session-2"
    assert answered.actor == "coach"
    assert answered.answered_at == NOW
    assert mapping.confirmation_ref == answered.confirmation_id

    reopened = MaintainPlanRepository(repository.database_path)
    assert reopened.get_confirmation(answered.confirmation_id) == answered
    assert reopened.get_prescription_mapping(mapping.mapping_id) == mapping
    assert len(reopened.list_prescription_mappings()) == 1


def test_browser_page_offers_every_candidate_and_a_no_write_exit(tmp_path):
    sessions = (RUN_SESSION, replace(RUN_SESSION, session_id="session-2"))
    repository = _repository(tmp_path, sessions)
    review = review_subject(repository, "athlete-1", now=NOW)

    page = render_page("athlete-1", review=review)

    assert page.count("Conferma questa corrispondenza") == 2
    assert "Non lo so: non salvare nulla" in page
    assert repository.list_prescription_mappings() == ()


def test_browser_checks_readiness_after_subject_is_entered(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "plan-only.db")
    repository.create_prescription_snapshot(RUN_PRESCRIPTION)
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), make_handler(str(repository.database_path)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        connection = http.client.HTTPConnection(host, port)
        connection.request("GET", "/")
        initial = connection.getresponse()
        initial_page = initial.read().decode()
        assert initial.status == 200
        assert "ID atleta" in initial_page
        assert "Revisione pronta" not in initial_page

        connection.request("GET", "/?subject=athlete-1")
        checked = connection.getresponse()
        checked_page = checked.read().decode()
        assert checked.status == 200
        assert "Revisione non pronta per athlete-1" in checked_page
        assert "un’attività Garmin acquisita" in checked_page
        assert "Esito:" not in checked_page
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_shell_launcher_supports_no_argument_and_athlete_mode(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls = tmp_path / "calls"
    python = fake_bin / "python"
    python.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$#:$*\" >> \"$CALLS\"\n",
        encoding="utf-8",
    )
    python.chmod(0o755)
    environment = {
        "PATH": f"{fake_bin}:/usr/bin:/bin",
        "CALLS": str(calls),
    }
    launcher = str(Path(__file__).parents[2] / "Avvia revisione coach.sh")

    subprocess.run([launcher], env=environment, check=True)
    subprocess.run([launcher, "athlete-1"], env=environment, check=True)

    no_argument, with_athlete = calls.read_text(encoding="utf-8").splitlines()
    assert no_argument.startswith("2:-c ")
    assert no_argument.endswith("run()")
    assert with_athlete.startswith("3:-c ")
    assert with_athlete.endswith(" athlete-1")


def test_saved_match_with_conflicting_data_is_explicitly_not_evaluated(tmp_path):
    conflict = {
        "conflict_id": "conflict-1",
        "schema_version": "maintain-plan-source-conflict/1.0.0-draft",
        "field_path": "components.run.quantity_observation",
        "values": ({"value": 59, "source": "Garmin"},
                   {"value": 60, "source": "Strava"}),
        "provenance": {}, "captured_at": NOW,
        "missing_fields": (), "warnings": (),
    }
    session = replace(RUN_SESSION, source_conflicts=(conflict,))
    repository = _repository(tmp_path, (session,))

    review = review_subject(repository, "athlete-1", now=NOW)
    page = render_page("athlete-1", review=review)

    assert repository.list_prescription_mappings() == ()
    assert review.evaluation is None
    assert "Abbinamento automatico sospeso" in page
    assert "Conferma questa corrispondenza" not in page
    assert "piano valutato" not in page


def test_evaluation_failure_is_retried_without_duplicate_mapping(
        tmp_path, monkeypatch):
    repository = _repository(tmp_path)
    original_evaluate = coach_review_module.evaluate
    attempts = 0

    def interrupted(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("interruzione simulata")
        return original_evaluate(*args, **kwargs)

    monkeypatch.setattr(coach_review_module, "evaluate", interrupted)

    first = resolve_coach_choice(repository, "athlete-1", "snapshot-1",
                                 "session-1", now=NOW)
    assert first.evaluation is None
    assert "Collegamento salvato; valutazione non completata" in first.evaluation_message
    assert len(repository.list_prescription_mappings()) == 1

    retry = retry_saved_evaluation(repository, "athlete-1", "snapshot-1",
                                   "session-1", now=NOW)
    assert retry.evaluation is not None
    assert retry.saved_pair.session_id == "session-1"
    assert len(repository.list_prescription_mappings()) == 1
    assert repository.get_execution_evaluation(retry.evaluation.evaluation_id) == retry.evaluation
    assert attempts == 2


def test_suspended_conflict_does_not_block_a_new_independent_review(tmp_path):
    conflict = {
        "conflict_id": "conflict-1",
        "schema_version": "maintain-plan-source-conflict/1.0.0-draft",
        "field_path": "components.run.quantity_observation",
        "values": ({"value": 59, "source": "Garmin"},
                   {"value": 60, "source": "Strava"}),
        "provenance": {}, "captured_at": NOW,
        "missing_fields": (), "warnings": (),
    }
    conflicted = replace(RUN_SESSION, source_conflicts=(conflict,))
    repository = _repository(tmp_path, (conflicted,))
    first_mapping = build_mapping(
        RUN_PRESCRIPTION, conflicted, mapping_id="confirmed-conflict",
        created_at=NOW, resolution_method=ResolutionMethod.ATHLETE_CONFIRMATION,
        actor="coach",
    )
    repository.create_prescription_mapping(first_mapping)

    later = NOW + timedelta(days=1)
    second_snapshot = replace(
        RUN_PRESCRIPTION, prescription_snapshot_id="snapshot-2",
        workout_id="workout-2", decision_id="decision-2",
        scheduled_window=replace(RUN_PRESCRIPTION.scheduled_window,
                                 start=later, end=later),
    )
    second_session = replace(RUN_SESSION, session_id="session-2", start=later)
    repository.create_prescription_snapshot(second_snapshot)
    repository.create_actual_session(second_session)

    review = review_subject(repository, "athlete-1", now=later)
    assert review.saved_pair is None
    review = resolve_coach_choice(repository, "athlete-1", "snapshot-2",
                                  "session-2", now=later)
    page = render_page("athlete-1", review=review)

    assert review.saved_pair.session_id == "session-2"
    assert review.evaluation is not None
    assert len(repository.list_prescription_mappings()) == 2


    with sqlite3.connect(repository.database_path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM maintain_plan_execution_evaluations "
            "WHERE actual_session_ref = 'session-1'"
        ).fetchone()[0] == 0
    assert any(pair.session_id == "session-1"
               for pair, _ in review.suspended_evaluations)
    assert "Attività sospesa:</strong> snapshot-1 ← session-1" in page
    assert "Valutazione ancora da chiarire" in page
    assert "Corrispondenza salvata:</strong> snapshot-2 ← session-2" in page

    # Reopening the same archive must keep skipping the deliberately suspended
    # evaluation instead of returning early or re-evaluating either mapping.
    for _ in range(2):
        repeated = review_subject(repository, "athlete-1", now=later)
        repeated_page = render_page("athlete-1", review=repeated)
        assert repeated.evaluation is None
        assert any(pair.session_id == "session-1"
                   for pair, _ in repeated.suspended_evaluations)
        assert "Attività sospesa:</strong> snapshot-1 ← session-1" in repeated_page

    with sqlite3.connect(repository.database_path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM maintain_plan_execution_evaluations "
            "WHERE actual_session_ref = 'session-1'"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT count(*) FROM maintain_plan_execution_evaluations "
            "WHERE actual_session_ref = 'session-2'"
        ).fetchone()[0] == 1
    assert len(repository.list_prescription_mappings()) == 2

def test_evaluation_without_overall_is_saved_and_rendered_without_inventing_outcome(
        tmp_path):
    optional_component = replace(
        RUN_PRESCRIPTION.components[0], requiredness=Requiredness.OPTIONAL)
    optional_snapshot = replace(RUN_PRESCRIPTION, components=(optional_component,))
    repository = MaintainPlanRepository(tmp_path / "optional-review.db")
    repository.create_prescription_snapshot(optional_snapshot)
    repository.create_actual_session(RUN_SESSION)

    review = review_subject(repository, "athlete-1", now=NOW)
    assert review.evaluation is None
    review = resolve_coach_choice(repository, "athlete-1", "snapshot-1",
                                  "session-1", now=NOW)

    assert review.evaluation is not None
    assert review.evaluation.overall is None
    assert repository.get_execution_evaluation(
        review.evaluation.evaluation_id) == review.evaluation

    page = render_page("athlete-1", review=review)
    text_summary = format_coach_review(review)
    expected = "giudizio complessivo non disponibile per questa prescrizione"
    assert expected in page
    assert expected in text_summary
    assert "Conseguenza sul piano: None" not in page
    assert "Conseguenza sul piano: None" not in text_summary

    # A later read leaves both persisted records intact and does not duplicate
    # the evaluation even though it has no overall status.
    repeated = review_subject(repository, "athlete-1", now=NOW)
    assert repeated.evaluation is None
    with sqlite3.connect(repository.database_path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM maintain_plan_prescription_mappings"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT count(*) FROM maintain_plan_execution_evaluations"
        ).fetchone()[0] == 1
    assert repository.get_execution_evaluation(
        review.evaluation.evaluation_id) == review.evaluation


def test_new_activity_before_atomic_save_prevents_automatic_choice(
        tmp_path, monkeypatch):
    repository = _repository(tmp_path)
    proposed = review_subject(repository, "athlete-1", now=NOW)
    assert proposed.decision.status is DecisionStatus.MATCHED
    original = repository.persist_prescription_mapping
    inserted = False

    def insert_concurrent_activity(*args, **kwargs):
        nonlocal inserted
        if not inserted:
            inserted = True
            repository.create_actual_session(
                replace(RUN_SESSION, session_id="late-session"))
        return original(*args, **kwargs)

    monkeypatch.setattr(repository, "persist_prescription_mapping",
                        insert_concurrent_activity)

    with pytest.raises(ValueError, match="actual-session scope changed"):
        resolve_coach_choice(repository, "athlete-1", "snapshot-1",
                             "session-1", now=NOW)

    assert repository.list_prescription_mappings() == ()
    refreshed = review_subject(repository, "athlete-1", now=NOW)
    assert refreshed.decision.status is DecisionStatus.CONFIRMATION_REQUIRED
    assert {item.session_id for item in refreshed.decision.candidates} == {
        "session-1", "late-session"}


def test_browser_get_is_read_only_and_cross_origin_post_is_rejected(tmp_path):
    repository = _repository(tmp_path)
    token = "test-action-token"
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), make_handler(str(repository.database_path),
                                       action_token=token))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        connection = http.client.HTTPConnection(host, port)
        connection.request("GET", "/?subject=athlete-1",
                           headers={"Host": "evil.example"})
        foreign_get = connection.getresponse()
        foreign_page = foreign_get.read().decode()
        assert foreign_get.status == 400
        assert token not in foreign_page
        assert foreign_get.getheader("Set-Cookie") is None
        assert repository.list_prescription_mappings() == ()

        foreign_payload = urlencode({"subject": "athlete-1",
                                     "prescription": "snapshot-1",
                                     "session": "session-1",
                                     "action_token": token})
        connection.request("POST", "/", foreign_payload, {
            "Host": "evil.example",
            "Origin": "http://evil.example",
            "Cookie": f"ironcoach_action={token}",
            "Content-Type": "application/x-www-form-urlencoded",
        })
        foreign_post = connection.getresponse()
        foreign_post.read()
        assert foreign_post.status == 400
        assert repository.list_prescription_mappings() == ()

        connection.request("GET", "/?subject=athlete-1")
        response = connection.getresponse()
        page = response.read().decode()
        assert response.status == 200
        assert "Corrispondenza univoca proposta" in page
        assert repository.list_prescription_mappings() == ()

        payload = urlencode({"subject": "athlete-1",
                             "prescription": "snapshot-1",
                             "session": "session-1",
                             "action_token": token})
        headers = {"Content-Type": "application/x-www-form-urlencoded",
                   "Cookie": f"ironcoach_action={token}",
                   "Origin": "https://pagina-estranea.example"}
        connection.request("POST", "/", payload, headers)
        rejected = connection.getresponse()
        rejected.read()
        assert rejected.status == 403
        assert repository.list_prescription_mappings() == ()

        headers["Origin"] = f"http://{host}:{port}"
        connection.request("POST", "/", payload, headers)
        accepted = connection.getresponse()
        accepted_page = accepted.read().decode()
        assert accepted.status == 200
        assert "Corrispondenza salvata" in accepted_page
        assert len(repository.list_prescription_mappings()) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize("origin_has_default_port", [False, True])
def test_codespaces_confirmation_through_forwarded_https_address(
        tmp_path, origin_has_default_port):
    repository = _repository(tmp_path)
    environment = {
        "CODESPACE_NAME": "sturdy-space-123",
        "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN": "app.github.dev",
    }
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), make_handler(
            str(repository.database_path), environment=environment))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    forwarded_host = f"sturdy-space-123-{port}.app.github.dev"
    try:
        connection = http.client.HTTPConnection(host, port)
        connection.request("GET", "/?subject=athlete-1", headers={
            "Host": f"localhost:{port}",
            "X-Forwarded-Host": "attacker.example",
        })
        accepted = connection.getresponse()
        page = accepted.read().decode()
        assert accepted.status == 200
        assert "Corrispondenza univoca proposta" in page
        assert "Secure" in accepted.getheader("Set-Cookie")
        assert accepted.getheader("X-Frame-Options") == "DENY"
        assert repository.list_prescription_mappings() == ()

        action_token = re.search(
            r'name="action_token" value="([^"]+)"', page).group(1)
        cookie = accepted.getheader("Set-Cookie").split(";", 1)[0]
        payload = urlencode({
            "subject": "athlete-1",
            "prescription": "snapshot-1",
            "session": "session-1",
            "action_token": action_token,
        })
        origin = f"https://{forwarded_host}"
        if origin_has_default_port:
            origin += ":443"
        connection.request("POST", "/", payload, headers={
            "Host": f"localhost:{port}",
            "Origin": origin,
            "Cookie": cookie,
            "Content-Type": "application/x-www-form-urlencoded",
        })
        confirmed = connection.getresponse()
        confirmed_page = confirmed.read().decode()
        assert confirmed.status == 200
        assert "Corrispondenza salvata" in confirmed_page
        assert len(repository.list_prescription_mappings()) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_codespaces_rejects_foreign_host_despite_forwarding_header(tmp_path):
    repository = _repository(tmp_path)
    environment = {
        "CODESPACE_NAME": "sturdy-space-123",
        "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN": "app.github.dev",
    }
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), make_handler(
            str(repository.database_path), environment=environment))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    forwarded_host = f"sturdy-space-123-{port}.app.github.dev"
    try:
        connection = http.client.HTTPConnection(host, port)
        connection.request("GET", "/?subject=athlete-1", headers={
            "Host": f"localhost:{port}",
        })
        accepted = connection.getresponse()
        page = accepted.read().decode()
        action_token = re.search(
            r'name="action_token" value="([^"]+)"', page).group(1)
        cookie = accepted.getheader("Set-Cookie").split(";", 1)[0]
        payload = urlencode({
            "subject": "athlete-1",
            "prescription": "snapshot-1",
            "session": "session-1",
            "action_token": action_token,
        })
        connection.request("POST", "/", payload, headers={
            "Host": f"localhost:{port}",
            "Origin": "https://address-chosen-by-request.example",
            "Cookie": cookie,
            "Content-Type": "application/x-www-form-urlencoded",
        })
        rejected_origin = connection.getresponse()
        rejected_origin.read()
        assert rejected_origin.status == 403
        assert repository.list_prescription_mappings() == ()

        connection.request("GET", "/?subject=athlete-1", headers={
            "Host": "address-chosen-by-request.example",
            "X-Forwarded-Host": forwarded_host,
        })
        rejected = connection.getresponse()
        rejected.read()
        assert rejected.status == 400
        assert rejected.getheader("Set-Cookie") is None
        assert repository.list_prescription_mappings() == ()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_codespaces_origin_is_derived_from_trusted_environment():
    assert _trusted_origins(8765, {
        "CODESPACE_NAME": "sturdy-space-123",
        "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN": "app.github.dev",
    }) == {
        "127.0.0.1:8765":
            "https://sturdy-space-123-8765.app.github.dev",
        "localhost:8765":
            "https://sturdy-space-123-8765.app.github.dev",
        "sturdy-space-123-8765.app.github.dev":
            "https://sturdy-space-123-8765.app.github.dev",
        "sturdy-space-123-8765.app.github.dev:443":
            "https://sturdy-space-123-8765.app.github.dev",
    }


def test_launcher_loads_project_dotenv_and_requires_configured_archive(
        tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    database = project / "configured" / "coach.db"
    database.parent.mkdir()
    MaintainPlanRepository(database)
    (project / ".env").write_text(
        "IRONCOACH_MAINTAIN_PLAN_DATABASE_PATH=configured/coach.db\n")
    monkeypatch.delenv("IRONCOACH_MAINTAIN_PLAN_DATABASE_PATH", raising=False)

    assert configured_database_path(project) == str(database)

    database.unlink()
    with pytest.raises(FileNotFoundError, match="configurato non trovato"):
        configured_database_path(project)
    assert not database.exists()


@pytest.mark.parametrize(("with_plan", "with_activity", "ready", "missing"), [
    (True, False, False, "un’attività Garmin acquisita"),
    (False, True, False, "una prescrizione MAINTAIN_PLAN"),
    (True, True, True, None),
])
def test_review_readiness_requires_both_artifact_types_for_same_athlete(
        tmp_path, with_plan, with_activity, ready, missing):
    repository = MaintainPlanRepository(tmp_path / "readiness.db")
    if with_plan:
        repository.create_prescription_snapshot(RUN_PRESCRIPTION)
    if with_activity:
        repository.create_actual_session(RUN_SESSION)

    result = database_review_readiness(
        str(repository.database_path), "athlete-1")

    assert result.ready is ready
    assert result.prescription_count == int(with_plan)
    assert result.activity_count == int(with_activity)
    if missing is None:
        assert result.message() == (
            "Revisione pronta per athlete-1: 1 prescrizione/i e "
            "1 attività acquisita/e.")
    else:
        assert missing in result.message()


def test_updated_not_evaluable_result_blocks_candidate_save(tmp_path):
    repository = _repository(tmp_path)
    proposed = review_subject(repository, "athlete-1", now=NOW)
    assert proposed.decision.status is DecisionStatus.MATCHED

    unsupported_component = replace(
        RUN_PRESCRIPTION.components[0], support_status=SupportStatus.UNSUPPORTED)
    unsupported = replace(
        RUN_PRESCRIPTION, prescription_snapshot_id="unsupported-snapshot",
        workout_id="unsupported-workout", decision_id="unsupported-decision",
        components=(unsupported_component,))
    repository.create_prescription_snapshot(unsupported)

    updated = review_subject(repository, "athlete-1", now=NOW)
    assert updated.decision.status is DecisionStatus.NOT_EVALUABLE
    assert any(item.prescription_snapshot_id == "snapshot-1"
               and item.session_id == "session-1"
               for item in updated.decision.candidates)
    with pytest.raises(ValueError, match="non è valutabile.*servono chiarimenti"):
        resolve_coach_choice(repository, "athlete-1", "snapshot-1",
                             "session-1", now=NOW)
    assert repository.list_prescription_mappings() == ()


def test_completed_mapping_and_evaluation_are_visible_after_reopen(tmp_path):
    repository = _repository(tmp_path)
    saved = resolve_coach_choice(repository, "athlete-1", "snapshot-1",
                                 "session-1", now=NOW)
    assert saved.evaluation is not None

    reopened = review_subject(repository, "athlete-1", now=NOW)
    page = render_page("athlete-1", review=reopened)
    summary = format_coach_review(reopened)

    assert len(reopened.completed_evaluations) == 1
    pair, evaluation = reopened.completed_evaluations[0]
    assert pair.prescription_snapshot_id == "snapshot-1"
    assert pair.session_id == "session-1"
    assert evaluation == saved.evaluation
    assert "Abbinamento completato:</strong> snapshot-1 ← session-1" in page
    assert "Abbinamento già completato: snapshot-1 ← session-1" in summary
    assert "Nessuna corrispondenza è stata salvata" not in summary


def test_cli_help_declares_review_read_only_and_points_to_browser():
    help_text = " ".join(main_module._build_argument_parser().format_help().split())

    assert "Consulta senza scrivere" in help_text
    assert "pagina browser coach" in help_text


def test_manual_confirmation_bundle_rolls_back_and_can_be_retried(tmp_path):
    repository = _repository(
        tmp_path, (RUN_SESSION, replace(RUN_SESSION, session_id="session-2")))
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute(
            "CREATE TRIGGER interrupt_confirmation BEFORE INSERT ON "
            "maintain_plan_confirmations WHEN NEW.status = 'ANSWERED' "
            "BEGIN SELECT RAISE(ABORT, 'simulated interruption'); END")

    with pytest.raises(sqlite3.IntegrityError, match="simulated interruption"):
        resolve_coach_choice(repository, "athlete-1", "snapshot-1",
                             "session-2", now=NOW)
    with sqlite3.connect(repository.database_path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM maintain_plan_confirmations").fetchone()[0] == 0
        assert connection.execute(
            "SELECT count(*) FROM maintain_plan_matching_results").fetchone()[0] == 0
        assert connection.execute(
            "SELECT count(*) FROM maintain_plan_prescription_mappings").fetchone()[0] == 0
        connection.execute("DROP TRIGGER interrupt_confirmation")

    resolved = resolve_coach_choice(
        repository, "athlete-1", "snapshot-1", "session-2", now=NOW)
    assert resolved.saved_pair.session_id == "session-2"
    with sqlite3.connect(repository.database_path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM maintain_plan_confirmations").fetchone()[0] == 2
        assert connection.execute(
            "SELECT count(*) FROM maintain_plan_matching_results").fetchone()[0] == 2
        assert connection.execute(
            "SELECT count(*) FROM maintain_plan_prescription_mappings").fetchone()[0] == 1


@pytest.mark.parametrize("chosen_prescription,chosen_session", [
    ("snapshot-1", "session-1"),
    ("snapshot-2", "session-2"),
])
def test_global_candidates_across_prescriptions_can_each_be_confirmed(
        tmp_path, chosen_prescription, chosen_session):
    repository = MaintainPlanRepository(
        tmp_path / f"global-{chosen_prescription}.db")
    later = NOW + timedelta(days=1)
    second_snapshot = replace(
        RUN_PRESCRIPTION, prescription_snapshot_id="snapshot-2",
        workout_id="workout-2", decision_id="decision-2",
        scheduled_window=replace(RUN_PRESCRIPTION.scheduled_window,
                                 start=later, end=later))
    second_session = replace(RUN_SESSION, session_id="session-2", start=later)
    for snapshot in (RUN_PRESCRIPTION, second_snapshot):
        repository.create_prescription_snapshot(snapshot)
    for session in (RUN_SESSION, second_session):
        repository.create_actual_session(session)

    review = review_subject(repository, "athlete-1", now=NOW)
    page = render_page("athlete-1", review=review)
    assert review.decision.status is DecisionStatus.CONFIRMATION_REQUIRED
    assert page.count("Conferma questa corrispondenza") == 2

    saved = resolve_coach_choice(
        repository, "athlete-1", chosen_prescription, chosen_session, now=NOW)
    assert saved.saved_pair.prescription_snapshot_id == chosen_prescription
    assert saved.saved_pair.session_id == chosen_session
    mapping = repository.list_prescription_mappings()[0]
    answered = repository.get_confirmation(mapping.confirmation_ref)
    assert answered.candidate_session_refs == (chosen_session,)
    assert tuple(item.get("session_id") for item in answered.interpretations
                 if item.get("answer_type") == "SELECT_CANDIDATE") == (
                     chosen_session,)
    assert answered.selected_session_ref == chosen_session
    assert answered.prescription_snapshot_ref == chosen_prescription
    assert {(item["prescription_snapshot_id"], item["session_id"])
            for item in answered.ambiguous_data} == {
        ("snapshot-1", "session-1"), ("snapshot-2", "session-2")}
    assert len(repository.list_prescription_mappings()) == 1


def test_read_only_database_open_rejects_missing_path_without_creating_it(tmp_path):
    missing = tmp_path / "missing-parent" / "wrong.db"

    with pytest.raises(FileNotFoundError, match="configurato non trovato"):
        review_database(str(missing), "athlete-1")

    assert not missing.exists()
    assert not missing.parent.exists()


def test_applicable_evaluation_version_is_selected_without_losing_history(tmp_path):
    repository = _repository(tmp_path)
    mapping = build_mapping(
        RUN_PRESCRIPTION, RUN_SESSION, mapping_id="external-mapping",
        created_at=NOW, resolution_method=ResolutionMethod.AUTOMATIC)
    repository.create_prescription_mapping(mapping)
    applicable = coach_review_module.evaluate(
        RUN_PRESCRIPTION, RUN_SESSION, mapping,
        evaluation_id="evaluation-current-policy", evaluated_at=NOW)
    historical = replace(
        applicable, evaluation_id="evaluation-old-policy",
        policy=PolicyRef("maintain-plan-execution-aggregation", "0.9.0-draft"))
    repository.create_execution_evaluation(applicable)
    repository.create_execution_evaluation(historical)

    review = review_subject(repository, "athlete-1", now=NOW)
    page = render_page("athlete-1", review=review)

    assert review.completed_evaluations == ((
        coach_review_module.CandidatePair("snapshot-1", "session-1"), applicable),)
    assert review.suspended_evaluations == ()
    assert "Riprova valutazione" not in page
    retried = retry_saved_evaluation(
        repository, "athlete-1", "snapshot-1", "session-1", now=NOW)
    assert retried.evaluation == applicable
    with sqlite3.connect(repository.database_path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM maintain_plan_execution_evaluations"
        ).fetchone()[0] == 2
    assert repository.get_execution_evaluation(
        "evaluation-current-policy") == applicable
    assert repository.get_execution_evaluation(
        "evaluation-old-policy") == historical
