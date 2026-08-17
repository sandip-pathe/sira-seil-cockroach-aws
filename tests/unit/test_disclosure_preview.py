from __future__ import annotations

from sira_api.decision_room_projection import _disclosure_preview
from sira_api.fixtures import DemoFixtureBundle


def test_disclosure_preview_names_exact_fields_and_omits_private_context() -> None:
    preview = _disclosure_preview(DemoFixtureBundle.load())

    assert preview["recipient"] == "SELLER"
    assert preview["source_hash"].startswith("sha256:")
    assert "team.seat_count" in preview["exact_fields"]
    assert "hidden_budget" in preview["omitted_categories"]
    assert "organization_identity" in preview["omitted_categories"]

    serialized = repr(preview).lower()
    assert "consultco" not in serialized
    assert "1200.00" not in serialized
    assert "employee" not in " ".join(preview["exact_fields"])


def test_expired_requirement_brief_is_not_presented_as_active() -> None:
    preview = _disclosure_preview(DemoFixtureBundle.load())

    assert preview["status"] == "EXPIRED"
