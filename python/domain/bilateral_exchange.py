"""Deterministic two-party exchange compiler with projection-only disclosure."""

from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
from typing import Any, Literal

import rfc8785
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExchangeConflict(ValueError):
    """A party command cannot advance the current coordinator state."""


class ExchangeParty(StrEnum):
    BUYER = "BUYER"
    SELLER = "SELLER"
    SYSTEM = "SYSTEM"


class ExchangeState(StrEnum):
    CREATED = "CREATED"
    REQUIREMENT_RELEASED = "REQUIREMENT_RELEASED"
    EVIDENCE_RELEASED = "EVIDENCE_RELEASED"
    OFFERED = "OFFERED"
    COUNTERED = "COUNTERED"
    AGREED_PENDING_APPROVAL = "AGREED_PENDING_APPROVAL"
    APPROVED_FOR_HANDOFF = "APPROVED_FOR_HANDOFF"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ExchangeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PartyCommand(ExchangeModel):
    id: str = Field(min_length=1, max_length=64)
    case_id: str = Field(min_length=1, max_length=64)
    party: ExchangeParty
    actor_id: str = Field(min_length=1, max_length=100)
    command_type: Literal[
        "RELEASE_REQUIREMENT",
        "PUBLISH_EVIDENCE",
        "PROPOSE_OFFER",
        "COUNTER_OFFER",
        "ACCEPT_OFFER",
        "ACCEPT_COUNTER",
        "APPROVE_HANDOFF",
        "REJECT",
        "EXPIRE",
    ]
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any]

    @model_validator(mode="after")
    def validate_owner(self) -> PartyCommand:
        owner = _COMMAND_OWNERS[self.command_type]
        if self.party is not owner:
            raise ValueError("party does not own this command type")
        _reject_private_fields(self.payload)
        return self


class CoordinatorState(ExchangeModel):
    case_id: str
    state: ExchangeState = ExchangeState.CREATED
    version: int = Field(default=1, ge=1)
    requirement: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None
    current_offer: dict[str, Any] | None = None
    approval: dict[str, Any] | None = None
    last_command_id: str | None = None


class PartyProjection(ExchangeModel):
    case_id: str
    party: Literal["BUYER", "SELLER"]
    state: ExchangeState
    version: int
    released: dict[str, Any]
    source_command_id: str
    projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class CompiledTransition(ExchangeModel):
    previous_state: ExchangeState
    next_state: CoordinatorState
    buyer_projection: PartyProjection
    seller_projection: PartyProjection


_COMMAND_OWNERS: dict[str, ExchangeParty] = {
    "RELEASE_REQUIREMENT": ExchangeParty.BUYER,
    "PUBLISH_EVIDENCE": ExchangeParty.SELLER,
    "PROPOSE_OFFER": ExchangeParty.BUYER,
    "COUNTER_OFFER": ExchangeParty.SELLER,
    "ACCEPT_OFFER": ExchangeParty.SELLER,
    "ACCEPT_COUNTER": ExchangeParty.BUYER,
    "APPROVE_HANDOFF": ExchangeParty.SYSTEM,
    "REJECT": ExchangeParty.SYSTEM,
    "EXPIRE": ExchangeParty.SYSTEM,
}

_TRANSITIONS: dict[tuple[ExchangeState, str], ExchangeState] = {
    (ExchangeState.CREATED, "RELEASE_REQUIREMENT"): ExchangeState.REQUIREMENT_RELEASED,
    (ExchangeState.REQUIREMENT_RELEASED, "PUBLISH_EVIDENCE"): ExchangeState.EVIDENCE_RELEASED,
    (ExchangeState.EVIDENCE_RELEASED, "PROPOSE_OFFER"): ExchangeState.OFFERED,
    (ExchangeState.OFFERED, "COUNTER_OFFER"): ExchangeState.COUNTERED,
    (ExchangeState.OFFERED, "ACCEPT_OFFER"): ExchangeState.AGREED_PENDING_APPROVAL,
    (ExchangeState.COUNTERED, "ACCEPT_COUNTER"): ExchangeState.AGREED_PENDING_APPROVAL,
    (ExchangeState.AGREED_PENDING_APPROVAL, "APPROVE_HANDOFF"): (
        ExchangeState.APPROVED_FOR_HANDOFF
    ),
}

_PRIVATE_PARTS = (
    "buyer_private",
    "seller_private",
    "hidden_budget",
    "reservation_value",
    "seller_floor",
    "private_notes",
    "private_source",
)


def _reject_private_fields(value: object, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).casefold()
            if any(part in normalized for part in _PRIVATE_PARTS):
                raise ValueError("party command contains a private-plane field")
            _reject_private_fields(child, (*path, str(key)))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_private_fields(child, (*path, str(index)))


def _projection(
    state: CoordinatorState, party: Literal["BUYER", "SELLER"], command_id: str
) -> PartyProjection:
    released: dict[str, Any] = {}
    if state.requirement is not None:
        released["requirement"] = state.requirement
    if state.evidence is not None:
        released["evidence"] = state.evidence
    if state.current_offer is not None:
        released["current_offer"] = state.current_offer
    if state.approval is not None:
        released["approval"] = state.approval
    payload = {
        "case_id": state.case_id,
        "party": party,
        "state": state.state.value,
        "version": state.version,
        "released": released,
        "source_command_id": command_id,
    }
    return PartyProjection(
        **payload,
        projection_hash=f"sha256:{sha256(rfc8785.dumps(payload)).hexdigest()}",
    )


def compile_party_command(state: CoordinatorState, command: PartyCommand) -> CompiledTransition:
    if command.case_id != state.case_id:
        raise ExchangeConflict("command targets another exchange case")
    if command.expected_version != state.version:
        raise ExchangeConflict("command expected a stale coordinator version")
    target: ExchangeState | None
    if command.command_type in {"REJECT", "EXPIRE"}:
        target = (
            ExchangeState.REJECTED if command.command_type == "REJECT" else ExchangeState.EXPIRED
        )
    else:
        target = _TRANSITIONS.get((state.state, command.command_type))
        if target is None:
            raise ExchangeConflict("command is invalid for the current exchange state")

    assert target is not None

    changes: dict[str, Any] = {
        "state": target,
        "version": state.version + 1,
        "last_command_id": command.id,
    }
    if command.command_type == "RELEASE_REQUIREMENT":
        changes["requirement"] = command.payload
    elif command.command_type == "PUBLISH_EVIDENCE":
        changes["evidence"] = command.payload
    elif command.command_type in {"PROPOSE_OFFER", "COUNTER_OFFER"}:
        changes["current_offer"] = command.payload
    elif command.command_type == "APPROVE_HANDOFF":
        changes["approval"] = command.payload
    next_state = state.model_copy(update=changes)
    return CompiledTransition(
        previous_state=state.state,
        next_state=next_state,
        buyer_projection=_projection(next_state, "BUYER", command.id),
        seller_projection=_projection(next_state, "SELLER", command.id),
    )
