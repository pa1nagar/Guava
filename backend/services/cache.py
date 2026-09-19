"""
cache.py — Profile hash computation for plan cache invalidation.

This hash is the sole mechanism for deciding whether to regenerate a plan.
Same inputs must always produce the same hash — do not change the format string
without migrating existing stored hashes.
"""

import hashlib


def compute_profile_hash(
    crop: str,
    plant_count: int,
    state: str,
    district: str,
    sowing_date,  # datetime.date or ISO string — str() normalises both
) -> str:
    """Return a deterministic SHA-256 hex digest of the farmer's profile fields.

    The hash covers exactly the five fields that influence plan content.
    If any field changes, the hash changes and the cached plan is invalidated.
    """
    raw = f"{crop}|{plant_count}|{state}|{district}|{sowing_date}"
    return hashlib.sha256(raw.encode()).hexdigest()
