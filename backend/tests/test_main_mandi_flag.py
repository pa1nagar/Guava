"""test_main_mandi_flag.py - MANDI_INGEST_ON_RENDER gate (helper only; no scheduler)."""
import os

import pytest

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-key")
os.environ.setdefault("GEMINI_API_KEY", "test-key")

import main  # noqa: E402


def test_default_is_off(monkeypatch):
    monkeypatch.delenv("MANDI_INGEST_ON_RENDER", raising=False)
    assert main._mandi_ingest_on_render_enabled() is False


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "maybe"])
def test_falsy_values(monkeypatch, value):
    monkeypatch.setenv("MANDI_INGEST_ON_RENDER", value)
    assert main._mandi_ingest_on_render_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " On "])
def test_truthy_values(monkeypatch, value):
    monkeypatch.setenv("MANDI_INGEST_ON_RENDER", value)
    assert main._mandi_ingest_on_render_enabled() is True
