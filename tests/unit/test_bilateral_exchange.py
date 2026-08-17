from __future__ import annotations

import pytest

from domain.bilateral_exchange import (
    CoordinatorState,
    ExchangeConflict,
    PartyCommand,
    compile_party_command,
)


def _command(
    command_type: str,
    party: str,
    version: int,
    payload: dict[str, object],
) -> PartyCommand:
    return PartyCommand.model_validate(
        {
            "id": f"command-{version}",
            "case_id": "case-1",
            "party": party,
            "actor_id": f"actor-{party.casefold()}",
            "command_type": command_type,
            "expected_version": version,
            "idempotency_key": f"idem-{version}",
            "payload": payload,
        }
    )


def test_bilateral_protocol_advances_only_through_party_owned_commands() -> None:
    state = CoordinatorState(case_id="case-1")
    for command in (
        _command("RELEASE_REQUIREMENT", "BUYER", 1, {"goal": "Meeting intelligence"}),
        _command("PUBLISH_EVIDENCE", "SELLER", 2, {"pack_id": "pack-1", "version": 2}),
        _command("PROPOSE_OFFER", "BUYER", 3, {"amount": "1200.00", "currency": "USD"}),
        _command("COUNTER_OFFER", "SELLER", 4, {"amount": "1350.00", "currency": "USD"}),
        _command("ACCEPT_COUNTER", "BUYER", 5, {"offer_hash": "sha256:" + "a" * 64}),
        _command("APPROVE_HANDOFF", "SYSTEM", 6, {"approval_id": "approval-1"}),
    ):
        transition = compile_party_command(state, command)
        assert transition.buyer_projection.projection_hash.startswith("sha256:")
        assert transition.seller_projection.released == transition.buyer_projection.released
        state = transition.next_state
    assert state.state == "APPROVED_FOR_HANDOFF"
    assert state.version == 7


def test_bilateral_protocol_rejects_stale_wrong_party_and_private_canaries() -> None:
    state = CoordinatorState(case_id="case-1")
    with pytest.raises(ExchangeConflict, match="stale"):
        compile_party_command(
            state,
            _command("RELEASE_REQUIREMENT", "BUYER", 2, {"goal": "Meetings"}),
        )
    with pytest.raises(ValueError, match="does not own"):
        _command("RELEASE_REQUIREMENT", "SELLER", 1, {"goal": "Meetings"})
    with pytest.raises(ValueError, match="private-plane"):
        _command(
            "RELEASE_REQUIREMENT",
            "BUYER",
            1,
            {"goal": "Meetings", "hidden_budget": 1000},
        )
