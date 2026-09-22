"""Focused tests for the pure runtime-matching input boundary."""

from dataclasses import FrozenInstanceError, replace

import pytest

from backend.maintain_plan.models import DirectIdEvidence, SourceActivity
from backend.maintain_plan.runtime_matching_scope import (
    DirectIdEvidenceIssue, RuntimeMatchingScopeError, validate_runtime_matching_scope,
)
from tests.maintain_plan.fixtures import NOW, RUN_PRESCRIPTION, RUN_SESSION


def _snapshot(identifier: str, subject: str = "athlete-1"):
    return replace(RUN_PRESCRIPTION, prescription_snapshot_id=identifier, subject_ref=subject)


def _session(identifier: str, subject: str = "athlete-1", **changes):
    return replace(RUN_SESSION, session_id=identifier, subject_ref=subject, **changes)


def _evidence(identifier: str, session: str, target="snapshot-1"):
    return DirectIdEvidence(identifier, session, target, "explicit-return", {})


def test_valid_complete_scope_and_empty_collections_have_no_outcome():
    scope = validate_runtime_matching_scope(
        "athlete-1", (_snapshot("p"),), (_session("s"),), (_evidence("e", "s"),))
    assert (scope.subject_ref, len(scope.snapshots), len(scope.sessions)) == ("athlete-1", 1, 1)
    empty = validate_runtime_matching_scope("athlete-1", (), (), ())
    assert empty.snapshots == empty.sessions == empty.direct_id_evidence == ()
    assert not hasattr(empty, "status") and not hasattr(empty, "candidate_set")


def test_input_permutation_and_unsigned_utf8_order_are_canonical():
    # UTF-8: ASCII 'z' precedes U+0080 (c2 80), which precedes U+00E9 (c3 a9).
    snapshot_ids = ("é", "z", "\u0080")
    session_ids = ("sé", "sz", "s\u0080")
    evidence_ids = ("é", "z", "\u0080")
    first = validate_runtime_matching_scope(
        "athlete-1", map(_snapshot, snapshot_ids), map(_session, session_ids),
        (_evidence(evidence_ids[i], session_ids[i]) for i in range(3)))
    second = validate_runtime_matching_scope(
        "athlete-1", map(_snapshot, reversed(snapshot_ids)), map(_session, reversed(session_ids)),
        (_evidence(evidence_ids[i], session_ids[i]) for i in reversed(range(3))))
    assert first == second
    assert tuple(x.prescription_snapshot_id for x in first.snapshots) == ("z", "\u0080", "é")
    assert tuple(x.session_id for x in first.sessions) == ("sz", "s\u0080", "sé")
    assert tuple(x.evidence_id for x in first.direct_id_evidence) == ("z", "\u0080", "é")


@pytest.mark.parametrize("owned", ["ATHLETE-1", "é", "e\u0301", " athlete-1 "])
def test_ownership_has_no_case_folding_normalization_or_trimming(owned):
    with pytest.raises(RuntimeMatchingScopeError, match="byte-exactly"):
        validate_runtime_matching_scope("athlete-1", (_snapshot("p", owned),), (), ())


@pytest.mark.parametrize("kind", ["snapshot", "session"])
def test_duplicate_authoritative_ids_reject_the_whole_scope(kind):
    snapshots = (_snapshot("same"), _snapshot("same")) if kind == "snapshot" else ()
    sessions = (_session("same"), _session("same")) if kind == "session" else ()
    with pytest.raises(RuntimeMatchingScopeError, match="must be unique"):
        validate_runtime_matching_scope("athlete-1", snapshots, sessions)


@pytest.mark.parametrize("subject", [None, "", "   ", "bad\ud800"])
def test_missing_blank_invalid_authoritative_ownership_rejects_scope(subject):
    with pytest.raises(RuntimeMatchingScopeError):
        validate_runtime_matching_scope("athlete-1", (_snapshot("p", subject),), (), ())


@pytest.mark.parametrize("subject", [None, "", "   ", "bad\ud800"])
def test_missing_blank_or_invalid_declared_subject_rejects_scope(subject):
    with pytest.raises(RuntimeMatchingScopeError):
        validate_runtime_matching_scope(subject, (), (), ())


@pytest.mark.parametrize("identifier", [None, "", "   ", "bad\ud800"])
def test_missing_blank_or_invalid_authoritative_identifiers_reject_scope(identifier):
    with pytest.raises(RuntimeMatchingScopeError):
        validate_runtime_matching_scope(
            "athlete-1", (replace(RUN_PRESCRIPTION, prescription_snapshot_id=identifier),), ())
    with pytest.raises(RuntimeMatchingScopeError):
        validate_runtime_matching_scope(
            "athlete-1", (), (replace(RUN_SESSION, session_id=identifier),))


def test_one_corrupt_artifact_does_not_filter_to_a_good_subset():
    with pytest.raises(RuntimeMatchingScopeError):
        validate_runtime_matching_scope(
            "athlete-1", (_snapshot("good"), _snapshot("bad", "someone-else")),
            (_session("good"),))


def test_evidence_envelope_membership_and_duplicate_ids_are_structural():
    with pytest.raises(RuntimeMatchingScopeError, match="outside the complete scope"):
        validate_runtime_matching_scope("athlete-1", (), (_session("inside"),),
                                        (_evidence("e", "outside"),))
    with pytest.raises(RuntimeMatchingScopeError, match="evidence_id must be unique"):
        validate_runtime_matching_scope("athlete-1", (), (_session("s"),),
                                        (_evidence("e", "s"), _evidence("e", "s", "other")))


def test_duplicate_contradictory_and_malformed_targets_are_semantic_not_matches():
    scope = validate_runtime_matching_scope(
        "athlete-1", (_snapshot("p"),), (_session("s"),),
        (_evidence("a", "s", "unknown"), _evidence("b", "s", "unknown"),
         _evidence("c", "s", "different"), _evidence("d", "s", " "),
         _evidence("e", "s", None)))
    assert set(scope.direct_id_evidence_issues) == {
        DirectIdEvidenceIssue.DUPLICATE_ASSERTION,
        DirectIdEvidenceIssue.CONTRADICTORY_ASSERTIONS,
        DirectIdEvidenceIssue.MALFORMED_RETURNED_PRESCRIPTION_ID,
        DirectIdEvidenceIssue.MISSING_RETURNED_PRESCRIPTION_ID,
    }
    assert not hasattr(scope, "prescription_mapping")


def test_session_metadata_never_becomes_direct_id_evidence():
    source = SourceActivity("device", "original-p", {"workout": "p"},
                            {"arbitrary_metadata": "p"})
    component = replace(RUN_SESSION.components[0], source_activity_refs=("original-p",))
    session = _session("s", source_activities=(source,), components=(component,),
                       provenance={"normalized_at": NOW}, data_quality={"opaque": "p"})
    scope = validate_runtime_matching_scope("athlete-1", (_snapshot("p"),), (session,))
    assert scope.direct_id_evidence == ()


def test_result_is_immutable_and_does_not_alias_mutable_input_collections():
    snapshots, sessions, evidence = [_snapshot("p")], [_session("s")], [_evidence("e", "s")]
    scope = validate_runtime_matching_scope("athlete-1", snapshots, sessions, evidence)
    snapshots.clear(); sessions.clear(); evidence.clear()
    assert len(scope.snapshots) == len(scope.sessions) == len(scope.direct_id_evidence) == 1
    with pytest.raises(FrozenInstanceError):
        scope.subject_ref = "other"


def test_scope_validation_has_no_database_dependency(monkeypatch):
    import sqlite3
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: pytest.fail("database access"))
    validate_runtime_matching_scope("athlete-1", (_snapshot("p"),), (_session("s"),))
