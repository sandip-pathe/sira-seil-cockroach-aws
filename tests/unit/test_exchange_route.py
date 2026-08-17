from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from domain.exchange_route import ExchangeRoute, ExchangeRouteCodec, ExchangeRouteError


def test_route_is_opaque_and_scoped_to_both_participants() -> None:
    now = datetime(2026, 8, 18, tzinfo=UTC)
    codec = ExchangeRouteCodec("x" * 32)
    token = codec.encode(
        ExchangeRoute(
            case_id="case-1",
            candidate_id="candidate-1",
            product_id="product-1",
            merchant_name="Seller",
            merchant_url="https://seller.example.test/pay",
            buyer_organization_id="org-buyer",
            seller_organization_id="org-seller",
            expires_at=now + timedelta(hours=1),
        )
    )

    assert "org-buyer" not in token
    assert codec.decode(token, organization_id="org-buyer", now=now).case_id == "case-1"
    assert codec.decode(token, organization_id="org-seller", now=now).case_id == "case-1"
    with pytest.raises(ExchangeRouteError, match="another organization"):
        codec.decode(token, organization_id="org-attacker", now=now)


def test_route_rejects_expiry_and_tampering() -> None:
    now = datetime(2026, 8, 18, tzinfo=UTC)
    codec = ExchangeRouteCodec("x" * 32)
    token = codec.encode(
        ExchangeRoute(
            case_id="case-1",
            candidate_id="candidate-1",
            product_id="product-1",
            merchant_name="Seller",
            merchant_url="https://seller.example.test/pay",
            buyer_organization_id="org-buyer",
            seller_organization_id="org-seller",
            expires_at=now,
        )
    )

    with pytest.raises(ExchangeRouteError, match="expired"):
        codec.decode(token, organization_id="org-buyer", now=now)
    with pytest.raises(ExchangeRouteError, match="invalid"):
        codec.decode(f"{token[:-1]}x", organization_id="org-buyer", now=now)
