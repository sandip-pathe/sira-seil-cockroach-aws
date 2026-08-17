from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sira_agents.kernel_models import Party, Principal
from sira_agents.runtime_ticket import (
    InMemoryReplayGuard,
    RuntimeTicketCodec,
    RuntimeTicketError,
)


def _clock() -> datetime:
    return datetime(2026, 8, 18, 12, tzinfo=UTC)


def _ticket(codec: RuntimeTicketCodec) -> str:
    return codec.issue(
        principal=Principal.SIRA,
        party=Party.BUYER,
        organization_id="org-buyer",
        actor_id="buyer-1",
        purpose="software_selection",
        audience="sira-runtime",
        allowed_tools=("read_evidence",),
    )


async def test_runtime_ticket_is_exact_short_lived_and_replay_protected() -> None:
    codec = RuntimeTicketCodec(b"x" * 32, clock=_clock)
    guard = InMemoryReplayGuard()
    token = _ticket(codec)

    claims = await codec.verify(
        token,
        expected_principal=Principal.SIRA,
        expected_party=Party.BUYER,
        expected_organization_id="org-buyer",
        expected_purpose="software_selection",
        expected_audience="sira-runtime",
        replay_guard=guard,
    )
    assert claims.organization_id == "org-buyer"
    assert claims.allowed_tools == ("read_evidence",)
    assert "database" not in claims.model_dump_json().casefold()
    assert "credential" not in claims.model_dump_json().casefold()

    with pytest.raises(RuntimeTicketError, match="REPLAYED"):
        await codec.verify(
            token,
            expected_principal=Principal.SIRA,
            expected_party=Party.BUYER,
            expected_organization_id="org-buyer",
            expected_purpose="software_selection",
            expected_audience="sira-runtime",
            replay_guard=guard,
        )


@pytest.mark.parametrize(
    ("principal", "party", "purpose", "audience"),
    [
        (Principal.SEIL, Party.SELLER, "software_selection", "sira-runtime"),
        (Principal.SIRA, Party.BUYER, "seller_evidence", "sira-runtime"),
        (Principal.SIRA, Party.BUYER, "software_selection", "seil-runtime"),
    ],
)
async def test_runtime_ticket_rejects_wrong_identity_scope(
    principal: Principal, party: Party, purpose: str, audience: str
) -> None:
    codec = RuntimeTicketCodec(b"x" * 32, clock=_clock)
    with pytest.raises(RuntimeTicketError, match="SCOPE_MISMATCH"):
        await codec.verify(
            _ticket(codec),
            expected_principal=principal,
            expected_party=party,
            expected_organization_id="org-buyer",
            expected_purpose=purpose,
            expected_audience=audience,
            replay_guard=InMemoryReplayGuard(),
        )


async def test_runtime_ticket_rejects_tampering_and_expiry() -> None:
    codec = RuntimeTicketCodec(b"x" * 32, clock=_clock)
    token = _ticket(codec)
    with pytest.raises(RuntimeTicketError, match="SIGNATURE_INVALID"):
        await codec.verify(
            token[:-2] + "aa",
            expected_principal=Principal.SIRA,
            expected_party=Party.BUYER,
            expected_organization_id="org-buyer",
            expected_purpose="software_selection",
            expected_audience="sira-runtime",
            replay_guard=InMemoryReplayGuard(),
        )

    expired_codec = RuntimeTicketCodec(
        b"x" * 32,
        clock=lambda: _clock() + timedelta(minutes=3),
    )
    with pytest.raises(RuntimeTicketError, match="EXPIRED"):
        await expired_codec.verify(
            token,
            expected_principal=Principal.SIRA,
            expected_party=Party.BUYER,
            expected_organization_id="org-buyer",
            expected_purpose="software_selection",
            expected_audience="sira-runtime",
            replay_guard=InMemoryReplayGuard(),
        )
