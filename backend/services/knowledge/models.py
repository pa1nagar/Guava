"""
models.py - request models (Pydantic v2). Every model forbids unknown fields.
"""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from services.knowledge import config as cfg


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _check_url(v: str) -> str:
    parsed = urlparse(v)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or any(c.isspace() for c in v):
        raise ValueError("url must be an http or https address")
    return v


class Applicability(_Strict):
    tree_age_months_min: Optional[int] = Field(default=None, ge=0, le=1200)
    tree_age_months_max: Optional[int] = Field(default=None, ge=0, le=1200)
    months: Optional[list[int]] = Field(default=None, max_length=12)
    bahar: Optional[Literal["ambe", "mrig", "hasta", "any"]] = None
    irrigation_type: Optional[str] = Field(default=None, max_length=60)
    planting_system: Optional[str] = Field(default=None, max_length=60)
    varieties: Optional[list[str]] = Field(default=None, max_length=30)

    @field_validator("months")
    @classmethod
    def _months(cls, v):
        if v is not None and (len(set(v)) != len(v) or any(m < 1 or m > 12 for m in v)):
            raise ValueError("months must be unique numbers 1-12")
        return v

    @field_validator("varieties")
    @classmethod
    def _varieties(cls, v):
        if v is not None and any(len(x) > 60 for x in v):
            raise ValueError("variety name too long")
        return v


class Value(_Strict):
    name: str = Field(min_length=1, max_length=80)
    value: Optional[float | str] = None
    min: Optional[float] = None
    max: Optional[float] = None
    unit: Optional[str] = Field(default=None, max_length=40)
    per: Optional[str] = Field(default=None, max_length=80)

    @field_validator("value")
    @classmethod
    def _value_len(cls, v):
        if isinstance(v, str) and len(v) > 80:
            raise ValueError("value too long")
        return v

    @model_validator(mode="after")
    def _one_of(self):
        if self.value is None and self.min is None and self.max is None:
            raise ValueError("a value needs value, min or max")
        return self


class Source(_Strict):
    title: str = Field(min_length=1, max_length=300)
    publisher: str = Field(min_length=1, max_length=200)
    year: Optional[int] = Field(default=None, ge=1800, le=2200)
    url: str = Field(min_length=8, max_length=600)
    page: Optional[str] = Field(default=None, max_length=40)
    section_or_table: str = Field(min_length=1, max_length=200)
    quote: str = Field(min_length=1, max_length=cfg.MAX_QUOTE_CHARS)
    access: Literal["opened_read", "opened_partial", "found_not_opened", "pdf_unreadable"] = "opened_read"

    @field_validator("url")
    @classmethod
    def _url(cls, v):
        return _check_url(v)

    @field_validator("quote")
    @classmethod
    def _quote(cls, v):
        if len(v.split()) > cfg.MAX_QUOTE_WORDS:
            raise ValueError("quote must be under 30 words")
        return v


class Conflict(_Strict):
    source_title: str = Field(min_length=1, max_length=300)
    url: str = Field(min_length=8, max_length=600)
    quote: str = Field(min_length=1, max_length=cfg.MAX_QUOTE_CHARS)
    note: str = Field(min_length=1, max_length=400)

    @field_validator("url")
    @classmethod
    def _url(cls, v):
        return _check_url(v)

    @field_validator("quote")
    @classmethod
    def _quote(cls, v):
        if len(v.split()) > cfg.MAX_QUOTE_WORDS:
            raise ValueError("quote must be under 30 words")
        return v


class ItemIn(_Strict):
    """Content of a knowledge item. Status, version and approval are server-owned."""

    id: str = Field(pattern=cfg.ID_PATTERN)
    topic: Literal[*cfg.TOPICS]  # type: ignore[valid-type]
    subtopic: str = Field(min_length=1, max_length=80)
    region: Literal["MP", "MH", "ALL"]
    applicability: Applicability = Field(default_factory=Applicability)
    statement_en: str = Field(min_length=10, max_length=600)
    statement_hi: str = Field(min_length=5, max_length=900)
    hi_machine_translated: bool = True
    hi_reviewed: bool = False
    values: list[Value] = Field(default_factory=list, max_length=30)
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    involves_chemical: bool = False
    cibrc_check_required: bool = False
    sources: list[Source] = Field(min_length=1, max_length=20)
    source_confidence: Literal["official_guideline", "peer_reviewed", "secondary"]
    conflicts: list[Conflict] = Field(default_factory=list, max_length=20)
    retrieved_on: Optional[date] = None

    @model_validator(mode="after")
    def _chemical_is_high(self):
        if self.involves_chemical and self.risk_level != "HIGH":
            raise ValueError("an item that involves a chemical must be HIGH risk")
        return self

    def to_payload(self) -> dict:
        return self.model_dump(mode="json")


class ItemCreateIn(_Strict):
    item: ItemIn


class ItemEditIn(_Strict):
    item: ItemIn
    expected_row_version: int = Field(ge=1)
    reason: Optional[str] = Field(default=None, max_length=cfg.MAX_REASON_CHARS)


class ProposalIn(_Strict):
    item: ItemIn
    reason: Optional[str] = Field(default=None, max_length=cfg.MAX_REASON_CHARS)


class ActionIn(_Strict):
    expected_row_version: int = Field(ge=1)
    reason: Optional[str] = Field(default=None, max_length=cfg.MAX_REASON_CHARS)


class CommentIn(_Strict):
    body: str = Field(min_length=1, max_length=cfg.MAX_COMMENT_CHARS)
    version: Optional[int] = Field(default=None, ge=1)


class ReviewerIn(_Strict):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    display_name: str = Field(min_length=1, max_length=120)
    credential: Optional[str] = Field(default=None, max_length=300)


class ImportIn(_Strict):
    dry_run: bool = False
