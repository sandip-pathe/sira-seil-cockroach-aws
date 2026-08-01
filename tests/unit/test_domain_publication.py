import json
from pathlib import Path

import pytest

from domain.errors import DomainValidationError
from domain.publication import (
    assert_public_payload,
    publish_seil_pack,
    sanitize_requirement_brief,
)

FIXTURES = Path(__file__).parents[2] / "fixtures" / "demo"


def test_checked_in_requirement_brief_has_no_denied_buyer_fields() -> None:
    requirement = json.loads((FIXTURES / "requirement_brief.json").read_text(encoding="utf-8"))
    assert_public_payload(requirement)
    serialized = json.dumps(requirement).lower()
    for forbidden in (
        "org_consultco",
        "hidden_budget",
        "budget_envelope",
        "contact_details",
        "private_failures",
        "competing_offers",
    ):
        assert forbidden not in serialized


def test_requirement_sanitizer_is_deny_by_default() -> None:
    source = {
        "category_id": "meeting_intelligence_client_services_v1",
        "seat_count": 10,
        "organization_id": "org_private",
        "hidden_budget": "1000",
        "unexpected": "drop me",
    }
    result = sanitize_requirement_brief(
        source,
        allowlist={"category_id", "seat_count"},
    )
    assert result == {
        "category_id": "meeting_intelligence_client_services_v1",
        "seat_count": 10,
    }


def test_product_passport_publication_uses_explicit_fixture_allowlist() -> None:
    passport = json.loads(
        (FIXTURES / "product_passports" / "fixture_selected_fit.json").read_text(encoding="utf-8")
    )
    published = publish_seil_pack(passport, allowlist=passport["publication_allowlist"])
    assert set(published) == {
        "approved_positioning_library",
        "pack_source",
        "public_identity",
    }
    serialized = json.dumps(published).lower()
    for forbidden in (
        "source_material",
        "roadmap_notes",
        "negotiation_bounds",
        "service_account_ref",
        "compilation_history",
    ):
        assert forbidden not in serialized


def test_nested_secret_in_an_allowed_section_fails_closed() -> None:
    with pytest.raises(DomainValidationError, match="denied fields"):
        publish_seil_pack(
            {"identity": {"name": "safe", "provider_credentials": "never"}},
            allowlist={"identity"},
        )
    with pytest.raises(DomainValidationError, match="prohibited field"):
        publish_seil_pack(
            {"private_negotiation_bounds": {"floor": "1.00"}},
            allowlist={"private_negotiation_bounds"},
        )
