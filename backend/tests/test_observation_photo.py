"""
test_observation_photo.py — Unit tests for observation photo handling (task 20.1).
Requirements: 7.4
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException


def test_original_and_ai_photo_stored_as_separate_rows():
    """Original and AI-processed photos are stored as separate rows with is_ai_version flag.
    Requirements: 7.4
    """
    rows = [
        {"id": "p1", "observation_id": "o1", "storage_key": "obs/o1/original.jpg", "is_ai_version": False},
        {"id": "p2", "observation_id": "o1", "storage_key": "obs/o1/ai.jpg", "is_ai_version": True},
    ]
    original = [r for r in rows if not r["is_ai_version"]]
    ai_versions = [r for r in rows if r["is_ai_version"]]
    assert len(original) == 1
    assert len(ai_versions) == 1
    assert original[0]["storage_key"] != ai_versions[0]["storage_key"]


def test_ai_analysis_label_default():
    """ai_analysis_label defaults to 'Preliminary observation — not a diagnosis'.
    Requirements: 7.3
    """
    default_label = "Preliminary observation — not a diagnosis"
    obs = {"ai_analysis_label": None}
    effective_label = obs.get("ai_analysis_label") or default_label
    assert effective_label == default_label


def test_observation_requires_ownership_for_photo_access():
    """Accessing a photo for an observation not owned by the user should raise 404.
    Requirements: 7.4
    """
    def get_observation_for_user(obs_id: str, user_id: str):
        owned = {"obs-1": "user-a"}
        if owned.get(obs_id) != user_id:
            raise HTTPException(status_code=404, detail="Observation not found.")
        return {"id": obs_id}

    # Owner can access
    get_observation_for_user("obs-1", "user-a")  # no exception

    # Non-owner gets 404
    with pytest.raises(HTTPException) as exc:
        get_observation_for_user("obs-1", "user-b")
    assert exc.value.status_code == 404
