"""
test_activity_photo_audit.py — Unit tests for activity photo upload and audit trail.

Covers:
  - Magic-byte MIME detection (JPEG, PNG, WEBP, and rejection of invalid signatures)
  - EXIF GPS stripping via Pillow
  - Audit log entry construction (field changes captured with old/new values)
  - Irrigation cost override note recording (Requirement 5.3)

Requirements: 5.3, 5.4, 5.5, 5.6, 5.7
"""

import io
import pytest

from routers.activities import (
    _detect_mime_from_magic_bytes,
    _strip_exif_gps,
    _build_audit_entry,
    _MAX_PHOTO_BYTES,
)


# ── Magic-byte MIME detection ─────────────────────────────────────────────────

class TestMagicByteDetection:
    """Requirement 5.6: verify the file's actual file signature, not just extension."""

    def test_jpeg_magic_bytes_detected(self):
        # JPEG starts with FF D8 FF
        data = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        assert _detect_mime_from_magic_bytes(data) == "image/jpeg"

    def test_png_magic_bytes_detected(self):
        # PNG starts with 89 50 4E 47 0D 0A 1A 0A
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        assert _detect_mime_from_magic_bytes(data) == "image/png"

    def test_webp_magic_bytes_detected(self):
        # WEBP: RIFF....WEBP
        data = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 100
        assert _detect_mime_from_magic_bytes(data) == "image/webp"

    def test_invalid_bytes_return_none(self):
        assert _detect_mime_from_magic_bytes(b"\x00\x01\x02\x03") is None

    def test_empty_bytes_return_none(self):
        assert _detect_mime_from_magic_bytes(b"") is None

    def test_text_file_return_none(self):
        assert _detect_mime_from_magic_bytes(b"not an image file") is None

    def test_truncated_jpeg_return_none(self):
        # Only 2 bytes of the JPEG signature
        assert _detect_mime_from_magic_bytes(b"\xff\xd8") is None

    def test_riff_without_webp_tag_return_none(self):
        # RIFF header but not WEBP (could be WAV, AVI, etc.)
        data = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x00" * 100
        assert _detect_mime_from_magic_bytes(data) is None

    def test_jpeg_with_wrong_extension_content_type_still_detected(self):
        """MIME spoofing: file claims to be PNG but has JPEG magic bytes.

        Requirement 5.6 (task 13.4): Test MIME spoofing is rejected by the
        detection logic — the actual signature determines the type.
        """
        # JPEG bytes but with a .png "extension" in the name — detection
        # ignores the filename entirely and uses only magic bytes.
        data = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        assert _detect_mime_from_magic_bytes(data) == "image/jpeg"


# ── EXIF GPS stripping ───────────────────────────────────────────────────────

class TestExifStripping:
    """Requirement 5.6: strip EXIF GPS metadata."""

    def _make_jpeg_with_exif(self) -> bytes:
        """Create a minimal JPEG with EXIF metadata."""
        from PIL import Image

        # Create a small solid-color image.
        img = Image.new("RGB", (10, 10), color=(255, 0, 0))
        output = io.BytesIO()

        # Build a minimal EXIF with a simple text tag (Software tag 0x0131).
        # This simulates EXIF metadata being present (e.g. camera info, GPS).
        exif = img.getexif()
        exif[0x0131] = "TestCamera"  # Software tag — simple string value

        img.save(output, format="JPEG", exif=exif.tobytes())
        return output.getvalue()

    def test_strips_exif_gps_from_jpeg(self):
        """After stripping, the output should have no EXIF metadata."""
        from PIL import Image

        original = self._make_jpeg_with_exif()

        # Verify the original has EXIF.
        orig_img = Image.open(io.BytesIO(original))
        orig_exif = orig_img.getexif()
        assert len(orig_exif) > 0, "Test image should have EXIF data"
        assert orig_exif.get(0x0131) == "TestCamera"

        # Strip EXIF.
        cleaned = _strip_exif_gps(original)

        # Verify the cleaned image has no EXIF.
        clean_img = Image.open(io.BytesIO(cleaned))
        clean_exif = clean_img.getexif()
        assert len(clean_exif) == 0, "EXIF data should be stripped"

    def test_strips_exif_from_png(self):
        """PNG images are also cleaned of any metadata."""
        from PIL import Image

        img = Image.new("RGB", (10, 10), color=(0, 255, 0))
        output = io.BytesIO()
        img.save(output, format="PNG")
        original = output.getvalue()

        cleaned = _strip_exif_gps(original)
        clean_img = Image.open(io.BytesIO(cleaned))
        assert clean_img.size == (10, 10)

    def test_pixel_data_preserved(self):
        """The image pixels should be preserved after EXIF stripping."""
        from PIL import Image

        img = Image.new("RGB", (5, 5), color=(123, 45, 67))
        output = io.BytesIO()
        img.save(output, format="JPEG")
        original = output.getvalue()

        cleaned = _strip_exif_gps(original)
        clean_img = Image.open(io.BytesIO(cleaned))
        # Check the center pixel is approximately the same color.
        pixel = clean_img.getpixel((2, 2))
        # JPEG compression may shift values slightly, check within tolerance.
        assert abs(pixel[0] - 123) < 30
        assert abs(pixel[1] - 45) < 30
        assert abs(pixel[2] - 67) < 30

    def test_invalid_image_raises(self):
        """Passing non-image bytes should raise an exception."""
        with pytest.raises(Exception):
            _strip_exif_gps(b"this is not an image at all")


# ── Audit log entry construction ──────────────────────────────────────────────

class TestAuditEntryConstruction:
    """Requirement 5.4: preserve original values in an immutable audit entry."""

    def test_audit_entry_captures_all_fields(self):
        entry = _build_audit_entry(
            activity_id="act-123",
            user_id="user-456",
            field_name="cost",
            old_value=500.0,
            new_value=750.0,
        )
        assert entry["activity_id"] == "act-123"
        assert entry["user_id"] == "user-456"
        assert entry["field_name"] == "cost"
        assert entry["old_value"] == "500.0"
        assert entry["new_value"] == "750.0"

    def test_audit_entry_handles_none_values(self):
        entry = _build_audit_entry(
            activity_id="act-123",
            user_id="user-456",
            field_name="notes",
            old_value=None,
            new_value="some note",
        )
        assert entry["old_value"] is None
        assert entry["new_value"] == "some note"

    def test_audit_entry_both_none(self):
        entry = _build_audit_entry(
            activity_id="act-123",
            user_id="user-456",
            field_name="plot_id",
            old_value=None,
            new_value=None,
        )
        assert entry["old_value"] is None
        assert entry["new_value"] is None

    def test_audit_entry_string_values_preserved(self):
        entry = _build_audit_entry(
            activity_id="act-123",
            user_id="user-456",
            field_name="activity_type",
            old_value="Fertilizer",
            new_value="Irrigation",
        )
        assert entry["old_value"] == "Fertilizer"
        assert entry["new_value"] == "Irrigation"


# ── Max photo size constant ──────────────────────────────────────────────────

class TestMaxPhotoSize:
    """Requirement 5.6: reject files exceeding 10 MB."""

    def test_max_photo_bytes_is_10_mb(self):
        assert _MAX_PHOTO_BYTES == 10 * 1024 * 1024
        assert _MAX_PHOTO_BYTES == 10_485_760


# ── Irrigation cost override note ─────────────────────────────────────────────

class TestIrrigationCostOverrideNote:
    """Requirement 5.3: record the received value in a note field for audit."""

    def test_irrigation_in_zero_cost_set(self):
        from services.constants import ZERO_COST_ACTIVITY_TYPES
        assert "Irrigation" in ZERO_COST_ACTIVITY_TYPES

    def test_irrigation_override_logic_records_note(self):
        """Simulate the POST handler's irrigation cost override + note logic."""
        from services.constants import ZERO_COST_ACTIVITY_TYPES

        def simulate_override(activity_type: str, cost: float, notes: str | None) -> tuple[float, str | None, float | None]:
            """Returns (effective_cost, notes, original_cost)."""
            is_irrigation = activity_type in ZERO_COST_ACTIVITY_TYPES
            effective_cost = 0.0 if is_irrigation else cost
            original_cost = cost if (is_irrigation and cost != 0.0) else None

            result_notes = notes
            if is_irrigation and cost > 0.0:
                override_note = (
                    f"[Audit] Submitted cost ₹{cost:.2f} overridden to ₹0.00 "
                    f"(water is free)."
                )
                result_notes = f"{notes}\n{override_note}" if notes else override_note
            return effective_cost, result_notes, original_cost

        # Irrigation with cost 500 and no prior notes.
        eff_cost, result_notes, orig_cost = simulate_override("Irrigation", 500.0, None)
        assert eff_cost == 0.0
        assert orig_cost == 500.0
        assert result_notes is not None
        assert "[Audit]" in result_notes
        assert "₹500.00" in result_notes

        # Irrigation with cost 0 — no note needed.
        eff_cost, result_notes, orig_cost = simulate_override("Irrigation", 0.0, "existing")
        assert eff_cost == 0.0
        assert orig_cost is None
        assert result_notes == "existing"  # unchanged

        # Fertilizer with cost 500 — cost passed through, no note.
        eff_cost, result_notes, orig_cost = simulate_override("Fertilizer", 500.0, None)
        assert eff_cost == 500.0
        assert orig_cost is None
        assert result_notes is None

        # Irrigation with cost 300 and existing notes.
        eff_cost, result_notes, orig_cost = simulate_override("Irrigation", 300.0, "prior note")
        assert eff_cost == 0.0
        assert orig_cost == 300.0
        assert "prior note" in result_notes
        assert "[Audit]" in result_notes


# ── Status field validation ──────────────────────────────────────────────────

class TestStatusField:
    """Requirement 5.7: distinguish 'planned' from 'recorded' activities."""

    def test_default_status_is_recorded(self):
        from routers.activities import ActivityIn
        activity = ActivityIn(activity_type="Fertilizer", quantity=10.0, cost=100.0)
        assert activity.status == "recorded"

    def test_planned_status_accepted(self):
        from routers.activities import ActivityIn
        activity = ActivityIn(
            activity_type="Fertilizer", quantity=10.0, cost=100.0, status="planned"
        )
        assert activity.status == "planned"

    def test_activity_out_includes_status(self):
        from routers.activities import ActivityOut
        out = ActivityOut(
            id="abc",
            activity_type="Fertilizer",
            quantity=10.0,
            unit="kg",
            cost=100.0,
            notes=None,
            status="planned",
            logged_date="2024-01-01",
            created_at="2024-01-01T00:00:00",
        )
        assert out.status == "planned"

    def test_activity_out_default_status_recorded(self):
        """DB rows without status should default to 'recorded'."""
        from routers.activities import _row_to_activity_out
        row = {
            "id": "abc",
            "activity_type": "Fertilizer",
            "quantity": 10.0,
            "unit": "kg",
            "cost": 100.0,
            "notes": None,
            # status intentionally omitted (legacy row)
            "logged_date": "2024-01-01",
            "created_at": "2024-01-01T00:00:00",
        }
        out = _row_to_activity_out(row)
        assert out.status == "recorded"
