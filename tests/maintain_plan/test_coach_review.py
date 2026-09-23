from dataclasses import replace

from backend.maintain_plan.coach_review import (
    format_coach_review, resolve_coach_choice, review_subject,
)
from backend.maintain_plan.coach_web import render_page
from backend.maintain_plan.models import ResolutionMethod
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


def test_browser_page_offers_every_candidate_and_a_no_write_exit(tmp_path):
    sessions = (RUN_SESSION, replace(RUN_SESSION, session_id="session-2"))
    repository = _repository(tmp_path, sessions)
    review = review_subject(repository, "athlete-1", now=NOW)

    page = render_page("athlete-1", review=review)

    assert page.count("Conferma questa corrispondenza") == 2
    assert "Non lo so: non salvare nulla" in page
    assert repository.list_prescription_mappings() == ()
