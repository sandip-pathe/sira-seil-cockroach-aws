"""Provider-neutral contracts for the bounded SIRA/SEIL cognitive kernel."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Annotated, Any, Literal

import rfc8785
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Principal(StrEnum):
    SIRA = "SIRA"
    SEIL = "SEIL"


class Party(StrEnum):
    BUYER = "BUYER"
    SELLER = "SELLER"


class ToolRisk(StrEnum):
    READ = "read"
    MUTATION = "mutation"
    PROTECTED_EFFECT = "protected_effect"


class FailureCode(StrEnum):
    INVALID_DECISION = "INVALID_DECISION"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    TOOL_DENIED = "TOOL_DENIED"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    CANCELLED = "CANCELLED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    STALE_CONTEXT = "STALE_CONTEXT"


class KernelModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TurnBudget(KernelModel):
    max_model_calls: int = Field(default=3, ge=1, le=3)
    max_parallel_reads: int = Field(default=4, ge=1, le=4)
    max_mutations: int = Field(default=1, ge=0, le=1)
    max_input_tokens: int = Field(default=12_000, ge=1, le=100_000)
    max_output_tokens: int = Field(default=2_048, ge=1, le=8_192)
    timeout_seconds: float = Field(default=90, gt=0, le=300)
    max_cost_usd: float = Field(default=0.25, ge=0, le=10)


class ContextReference(KernelModel):
    kind: str = Field(min_length=1, max_length=64)
    data_class: Literal["buyer_private", "seller_private", "exchange", "public"]
    object_id: str = Field(min_length=1, max_length=128)
    version: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ContextManifest(KernelModel):
    principal: Principal
    party: Party
    organization_id: str = Field(min_length=1, max_length=100)
    actor_id: str = Field(min_length=1, max_length=100)
    actor_roles: tuple[str, ...] = Field(default=(), max_length=32)
    permissions: tuple[str, ...] = Field(default=(), max_length=64)
    purpose: str = Field(min_length=1, max_length=100)
    conversation_id: str = Field(min_length=1, max_length=128)
    turn_id: str = Field(min_length=1, max_length=128)
    current_message: str = Field(min_length=1, max_length=16_000)
    recent_messages: tuple[dict[str, Any], ...] = Field(default=(), max_length=20)
    summary: str | None = Field(default=None, max_length=8_000)
    unresolved_questions: tuple[str, ...] = Field(default=(), max_length=8)
    references: tuple[ContextReference, ...] = Field(default=(), max_length=40)
    exchange_projection: dict[str, Any] = Field(default_factory=dict)
    available_tools: tuple[str, ...] = Field(default=(), max_length=32)
    budget: TurnBudget = Field(default_factory=TurnBudget)
    manifest_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_hash(self) -> ContextManifest:
        expected_party = Party.BUYER if self.principal is Principal.SIRA else Party.SELLER
        if self.party is not expected_party:
            raise ValueError("context principal and party do not match")
        forbidden = "seller_private" if self.principal is Principal.SIRA else "buyer_private"
        if any(reference.data_class == forbidden for reference in self.references):
            raise ValueError("context contains a reference from the opposing private plane")
        calculated = self.calculate_hash()
        if self.manifest_hash is not None and self.manifest_hash != calculated:
            raise ValueError("context manifest hash does not match its contents")
        return self

    def calculate_hash(self) -> str:
        payload = self.model_dump(mode="json", exclude={"manifest_hash"})
        return f"sha256:{sha256(rfc8785.dumps(payload)).hexdigest()}"

    def sealed(self) -> ContextManifest:
        return self.model_copy(update={"manifest_hash": self.calculate_hash()})


class Respond(KernelModel):
    kind: Literal["respond"]
    message: str = Field(min_length=1, max_length=8_000)


class Clarify(KernelModel):
    kind: Literal["clarify"]
    question: str = Field(min_length=1, max_length=800)
    reason: str = Field(min_length=1, max_length=500)


class ProposedToolCall(KernelModel):
    call_id: str = Field(min_length=1, max_length=100)
    tool_name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    contract_version: str = Field(pattern=r"^v[1-9][0-9]*$")
    arguments: dict[str, Any]


class ProposeTools(KernelModel):
    kind: Literal["propose_tools"]
    calls: tuple[ProposedToolCall, ...] = Field(min_length=1, max_length=4)


class RequestApproval(KernelModel):
    kind: Literal["request_approval"]
    action: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=800)
    payload_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class WaitForExternal(KernelModel):
    kind: Literal["wait_for_external"]
    reason: str = Field(min_length=1, max_length=500)


class Complete(KernelModel):
    kind: Literal["complete"]
    message: str = Field(min_length=1, max_length=8_000)


class FailSafely(KernelModel):
    kind: Literal["fail_safely"]
    code: FailureCode
    message: str = Field(min_length=1, max_length=800)
    retryable: bool = False


TurnDecision = Annotated[
    Respond | Clarify | ProposeTools | RequestApproval | WaitForExternal | Complete | FailSafely,
    Field(discriminator="kind"),
]


class TurnDecisionEnvelope(KernelModel):
    decision: TurnDecision


class ToolManifest(KernelModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    contract_version: str = Field(pattern=r"^v[1-9][0-9]*$")
    description: str = Field(min_length=1, max_length=500)
    allowed_principals: frozenset[Principal]
    allowed_parties: frozenset[Party]
    purposes: frozenset[str]
    allowed_stages: frozenset[str]
    risk: ToolRisk
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    timeout_seconds: float = Field(default=20, gt=0, le=120)

    @model_validator(mode="after")
    def validate_schemas(self) -> ToolManifest:
        if self.input_schema.get("type") != "object":
            raise ValueError("tool input schema must describe an object")
        if self.input_schema.get("additionalProperties") is not False:
            raise ValueError("tool input schema must reject additional properties")
        if self.output_schema.get("type") != "object":
            raise ValueError("tool output schema must describe an object")
        return self


class CapabilityGrant(KernelModel):
    id: str = Field(min_length=1, max_length=64)
    capability: str = Field(min_length=1, max_length=100)
    principal: Principal
    party: Party
    actor_id: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=1, max_length=100)
    tool_name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    contract_version: str = Field(pattern=r"^v[1-9][0-9]*$")
    scope: dict[str, Any]
    payload_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    object_versions: dict[str, int] = Field(default_factory=dict)
    status: Literal["ACTIVE", "REVOKED", "EXPIRED", "CONSUMED"]
    expires_at: datetime
    max_uses: int = Field(default=1, ge=1, le=10)
    uses: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_authority(self) -> CapabilityGrant:
        if self.uses > self.max_uses:
            raise ValueError("capability uses exceed its maximum")
        expected_party = Party.BUYER if self.principal is Principal.SIRA else Party.SELLER
        if self.party is not expected_party:
            raise ValueError("capability principal and party do not match")
        if self.expires_at.tzinfo is None:
            raise ValueError("capability expiry must be timezone-aware")
        return self

    def active(self, *, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        return self.status == "ACTIVE" and self.uses < self.max_uses and self.expires_at > current


class ToolResult(KernelModel):
    call_id: str
    tool_name: str
    contract_version: str
    output: dict[str, Any]
    output_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class UserEvent(KernelModel):
    kind: Literal[
        "message_received",
        "work_started",
        "clarification_needed",
        "approval_needed",
        "work_completed",
        "waiting",
        "could_not_complete",
    ]
    message: str = Field(min_length=1, max_length=800)
    retryable: bool = False
