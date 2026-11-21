"""
config.py - limits, enums and the error type for the knowledge admin module.
"""
from __future__ import annotations

STATUSES = ("DRAFT", "IN_REVIEW", "CHANGES_REQUESTED", "APPROVED", "REJECTED", "RETIRED")
ROLES = ("admin", "reviewer")
RISK_LEVELS = ("LOW", "MEDIUM", "HIGH")
REGIONS = ("MP", "MH", "ALL")
TOPICS = (
    "varieties", "climate_soil", "planting_system", "propagation",
    "bahar_crop_regulation", "canopy_pruning", "nutrient_management", "irrigation",
    "flowering_fruit_set", "pests", "diseases", "harvest_maturity",
    "post_harvest", "yield", "economics",
)
SOURCE_CONFIDENCE = ("official_guideline", "peer_reviewed", "secondary")
ACCESS_VALUES = ("opened_read", "opened_partial", "found_not_opened", "pdf_unreadable")
BAHAR_VALUES = ("ambe", "mrig", "hasta", "any")

APPROVAL_VALIDITY_DAYS = 365
INVITE_VALIDITY_DAYS = 14
EXPIRING_SOON_DAYS = 30

ID_PATTERN = r"^GUA-[A-Z]{3,6}-\d{4}$"
UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
MAX_QUERY_LEN = 100

# Quotes must stay short (fair use, and a quote is evidence, not a copy).
MAX_QUOTE_WORDS = 29
MAX_QUOTE_CHARS = 200

MAX_REASON_CHARS = 1000
MIN_REASON_CHARS = 3
MAX_COMMENT_CHARS = 4000

SEED_ACTOR = "seed-import"

# Item ids that must never be published (same list the farmer-facing governance uses).
from services.content_governance import PERMANENTLY_BLOCKED_CONTENT_IDENTIFIERS  # noqa: E402,F401


class KnowledgeError(Exception):
    """An expected, client-visible failure. ``detail`` is safe to return as is."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
