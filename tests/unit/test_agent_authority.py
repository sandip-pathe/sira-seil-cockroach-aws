from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sira_agents.authority import AuthorityDenied, Capability, authorize_effect


def _grant(**overrides: object) -> Capability:
    values: dict[str, object] = {
        "id": "grant_1",
        "capability": "payment.authorize",
        "scope": {"merchant_id": "merchant_1", "amount_minor": 99000},
        "status": "ACTIVE",
        "expires_at": datetime.now(UTC) + timedelta(minutes=5),
        "max_uses": 1,
        "uses": 0,
    }
    values.update(overrides)
    return Capability(**values)  # type: ignore[arg-type]


def test_exact_capability_allows_protected_effect() -> None:
    authorize_effect(
        effect_type="payment.authorize",
        request_payload={"merchant_id": "merchant_1", "amount_minor": 99000},
        grant=_grant(),
    )


@pytest.mark.parametrize(
    "grant,payload",
    [
        (None, {"merchant_id": "merchant_1", "amount_minor": 99000}),
        (_grant(uses=1), {"merchant_id": "merchant_1", "amount_minor": 99000}),
        (_grant(), {"merchant_id": "merchant_1", "amount_minor": 100}),
    ],
)
def test_capability_boundary_fails_closed(
    grant: Capability | None, payload: dict[str, object]
) -> None:
    with pytest.raises(AuthorityDenied):
        authorize_effect(
            effect_type="payment.authorize",
            request_payload=payload,
            grant=grant,
        )
