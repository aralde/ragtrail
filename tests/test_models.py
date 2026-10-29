from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from ragtrail.keys import band_key, band_key_in_scope, trajectory_key
from ragtrail.models import NodeRef, RecallResult, Step, Trajectory

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make(**overrides: object) -> Trajectory:
    fields: dict[str, object] = {
        "scope": "acme",
        "query": "How do I refresh a token?",
        "query_norm": "refresh token",
        "signature": [1, 2, 3],
        "steps": [Step(tool="search", args={"q": "refresh"}, returned=["n33", "n35"])],
        "useful": [NodeRef(node_id="n33", content_hash="h33")],
        "outcome": "verified",
        "created_at": NOW,
        "expires_at": NOW + timedelta(days=30),
    }
    fields.update(overrides)
    return Trajectory.model_validate(fields)


def test_json_round_trip() -> None:
    t = make()
    assert Trajectory.model_validate_json(t.model_dump_json()) == t


def test_ids_are_unique_by_default() -> None:
    assert make().id != make().id


@pytest.mark.parametrize("scope", ["", "a#b"])
def test_scope_must_be_key_safe(scope: str) -> None:
    with pytest.raises(ValidationError):
        make(scope=scope)


def test_id_must_be_key_safe() -> None:
    with pytest.raises(ValidationError):
        make(id="x#y")


def test_naive_datetimes_rejected() -> None:
    with pytest.raises(ValidationError):
        make(created_at=datetime(2026, 1, 1), expires_at=datetime(2026, 2, 1))


def test_expiry_must_follow_creation() -> None:
    with pytest.raises(ValidationError):
        make(expires_at=NOW)


def test_outcome_is_restricted() -> None:
    with pytest.raises(ValidationError):
        make(outcome="none")


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        make(answer="the answer is 42")


def test_models_are_frozen() -> None:
    with pytest.raises(ValidationError):
        make().hits = 3  # type: ignore[misc]


def test_recall_similarity_bounds() -> None:
    with pytest.raises(ValidationError):
        RecallResult(mode="hint", trajectory_id="x", similarity=1.5, rendered="")


def test_key_layout() -> None:
    assert trajectory_key("acme", "t1") == "t#acme#t1"
    assert band_key("acme", 0, "ff") == "b#acme#0#ff"
    assert band_key_in_scope("b#acme#0#ff", "acme")
    assert not band_key_in_scope("t#acme#t1", "acme")
    assert not band_key_in_scope("b#acme#x#ff", "acme")
    with pytest.raises(ValueError):
        trajectory_key("a#b", "t1")
    with pytest.raises(ValueError):
        band_key("acme", -1, "ff")
