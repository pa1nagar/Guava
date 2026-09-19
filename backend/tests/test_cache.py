"""
test_cache.py — Tests for services/cache.py

Covers:
  - Same inputs always produce same hash (determinism)
  - Different inputs produce different hashes
  - date and ISO string inputs produce same hash
  - Hash is a valid 64-char hex string
"""

import pytest
from datetime import date
from services.cache import compute_profile_hash


class TestComputeProfileHash:

    def test_deterministic(self):
        h1 = compute_profile_hash("guava", 2100, "Madhya Pradesh", "Dhar", date(2024, 6, 1))
        h2 = compute_profile_hash("guava", 2100, "Madhya Pradesh", "Dhar", date(2024, 6, 1))
        assert h1 == h2

    def test_different_crop_different_hash(self):
        h1 = compute_profile_hash("guava", 2100, "MP", "Dhar", date(2024, 6, 1))
        h2 = compute_profile_hash("mango", 2100, "MP", "Dhar", date(2024, 6, 1))
        assert h1 != h2

    def test_different_plant_count_different_hash(self):
        h1 = compute_profile_hash("guava", 2100, "MP", "Dhar", date(2024, 6, 1))
        h2 = compute_profile_hash("guava", 500,  "MP", "Dhar", date(2024, 6, 1))
        assert h1 != h2

    def test_different_date_different_hash(self):
        h1 = compute_profile_hash("guava", 2100, "MP", "Dhar", date(2024, 6, 1))
        h2 = compute_profile_hash("guava", 2100, "MP", "Dhar", date(2024, 7, 1))
        assert h1 != h2

    def test_date_object_and_iso_string_same_hash(self):
        h1 = compute_profile_hash("guava", 2100, "MP", "Dhar", date(2024, 6, 1))
        h2 = compute_profile_hash("guava", 2100, "MP", "Dhar", "2024-06-01")
        assert h1 == h2

    def test_hash_is_64_char_hex(self):
        h = compute_profile_hash("guava", 2100, "MP", "Dhar", date(2024, 6, 1))
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)
