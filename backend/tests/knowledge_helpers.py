"""Shared builders for the knowledge admin tests."""
from datetime import datetime, timezone

from services.knowledge.access import Principal
from services.knowledge.models import ItemIn
from tests.fake_knowledge_repo import FakeKnowledgeRepo

ADMIN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ADMIN2_ID = "a2a2a2a2-a2a2-4a2a-8a2a-a2a2a2a2a2a2"
REVIEWER_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
REVIEWER2_ID = "b2b2b2b2-b2b2-4b2b-8b2b-b2b2b2b2b2b2"
NOCRED_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
FARMER_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
T0 = datetime(2026, 12, 1, 9, 0, tzinfo=timezone.utc)


def item_dict(item_id="GUA-VAR-0001", **over) -> dict:
    base = {
        "id": item_id,
        "topic": "varieties",
        "subtopic": "regional_varieties",
        "region": "MP",
        "applicability": {"varieties": ["L-49"]},
        "statement_en": "Guava varieties grown in Madhya Pradesh include L-49 and Allahabad Safeda.",
        "statement_hi": "मध्य प्रदेश में एल-49 और इलाहाबाद सफेदा उगाई जाती हैं।",
        "hi_machine_translated": True,
        "hi_reviewed": False,
        "values": [],
        "risk_level": "LOW",
        "involves_chemical": False,
        "cibrc_check_required": False,
        "sources": [{
            "title": "Guava model project report", "publisher": "National Horticulture Board", "year": 2004,
            "url": "https://nhb.gov.in/report_files/guava/GUAVA.htm", "page": None,
            "section_or_table": "5.3 Varieties", "quote": "L-49, Allahabad safeda, Gwalior-27",
            "access": "opened_read",
        }],
        "source_confidence": "official_guideline",
        "conflicts": [],
        "retrieved_on": "2026-11-20",
    }
    base.update(over)
    return base


def make_item(item_id="GUA-VAR-0001", **over) -> ItemIn:
    return ItemIn.model_validate(item_dict(item_id, **over))


def high_item(item_id="GUA-PEST-0001", **over) -> ItemIn:
    return make_item(item_id, topic="pests", risk_level="HIGH", involves_chemical=True,
                     cibrc_check_required=True, **over)


def principal(role="admin", user_id=ADMIN_ID, name="Asha Admin", credential=None) -> Principal:
    return Principal(user_id=user_id, role=role, email=f"{role}@example.test",
                     display_name=name, credential=credential)


ADMIN = principal("admin", ADMIN_ID, "Asha Admin")
REVIEWER = principal("reviewer", REVIEWER_ID, "Dr Ravi Rao", "PhD Horticulture, ICAR-CISH")
REVIEWER2 = principal("reviewer", REVIEWER2_ID, "Dr Meera Joshi", "Scientist, MPKV Rahuri")
NOCRED = principal("reviewer", NOCRED_ID, "Sam Student", None)


def members_repo() -> FakeKnowledgeRepo:
    repo = FakeKnowledgeRepo()
    repo.add_admin(ADMIN_ID, "admin", "admin@example.test", "Asha Admin")
    repo.add_admin(REVIEWER_ID, "reviewer", "r1@example.test", "Dr Ravi Rao", "PhD Horticulture, ICAR-CISH")
    repo.add_admin(REVIEWER2_ID, "reviewer", "r2@example.test", "Dr Meera Joshi", "Scientist, MPKV Rahuri")
    repo.add_admin(NOCRED_ID, "reviewer", "r3@example.test", "Sam Student", None)
    return repo
