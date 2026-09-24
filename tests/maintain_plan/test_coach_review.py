from dataclasses import replace
from datetime import timedelta
import sqlite3

import backend.maintain_plan.coach_review as coach_review_module

from backend.maintain_plan.coach_review import (
    format_coach_review, resolve_coach_choice, review_subject,
)
from backend.maintain_plan.coach_web import render_page
from backend.maintain_plan.matching_service import build_mapping
from backend.maintain_plan.models import Requiredness, ResolutionMethod
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


def test_browser_page_offers_every_candidate_and_a_no_write_exit(tmp_path):
    sessions = (RUN_SESSION, replace(RUN_SESSION, session_id="session-2"))
    repository = _repository(tmp_path, sessions)
    review = review_subject(repository, "athlete-1", now=NOW)

    page = render_page("athlete-1", review=review)

    assert page.count("Conferma questa corrispondenza") == 2
    assert "Non lo so: non salvare nulla" in page
    assert repository.list_prescription_mappings() == ()


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

    first = review_subject(repository, "athlete-1", now=NOW)
    assert first.evaluation is None
    assert "Collegamento salvato; valutazione non completata" in first.evaluation_message
    assert len(repository.list_prescription_mappings()) == 1

    retry = review_subject(repository, "athlete-1", now=NOW)
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
