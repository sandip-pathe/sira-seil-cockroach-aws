"""Principal-specific context selection before retrieval or model invocation."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

import rfc8785

from sira_agents.guardrails import validate_principal_payload
from sira_agents.kernel_models import (
    ContextManifest,
    ContextReference,
    KernelModel,
    Party,
    Principal,
    TurnBudget,
)


class PrincipalPolicy(KernelModel):
    principal: Principal
    party: Party
    purpose: str
    allowed_tools: frozenset[str]
    budget: TurnBudget


@dataclass(frozen=True, slots=True)
class PolicyCatalog:
    policies: tuple[PrincipalPolicy, ...]

    def resolve(self, principal: Principal, party: Party, purpose: str) -> PrincipalPolicy:
        matches = [
            policy
            for policy in self.policies
            if policy.principal is principal and policy.party is party and policy.purpose == purpose
        ]
        if len(matches) != 1:
            raise PermissionError("PRINCIPAL_POLICY_NOT_FOUND")
        return matches[0]


@dataclass(frozen=True, slots=True)
class ContextAssembler:
    policies: PolicyCatalog

    def assemble(
        self,
        *,
        principal: Principal,
        party: Party,
        organization_id: str,
        actor_id: str,
        purpose: str,
        conversation_id: str,
        turn_id: str,
        current_message: str,
        recent_messages: tuple[dict[str, Any], ...] = (),
        summary: str | None = None,
        unresolved_questions: tuple[str, ...] = (),
        references: tuple[ContextReference, ...] = (),
        private_context: dict[str, Any] | None = None,
        exchange_projection: dict[str, Any] | None = None,
        requested_tools: tuple[str, ...] = (),
    ) -> ContextManifest:
        policy = self.policies.resolve(principal, party, purpose)
        selected_tools = tuple(sorted(set(requested_tools).intersection(policy.allowed_tools)))
        private = private_context or {}
        exchange = exchange_projection or {}
        validate_principal_payload(
            {
                "current_message": current_message,
                "recent_messages": recent_messages,
                "summary": summary,
                "principal_context": private,
                "exchange_projection": exchange,
            },
            principal=principal.value,
        )
        return ContextManifest(
            principal=principal,
            party=party,
            organization_id=organization_id,
            actor_id=actor_id,
            purpose=purpose,
            conversation_id=conversation_id,
            turn_id=turn_id,
            current_message=current_message,
            recent_messages=recent_messages,
            summary=summary,
            unresolved_questions=unresolved_questions,
            references=references,
            exchange_projection={"private": private, "released": exchange},
            available_tools=selected_tools,
            budget=policy.budget,
        ).sealed()


def context_cache_key(manifest: ContextManifest) -> str:
    identity = {
        "organization_id": manifest.organization_id,
        "principal": manifest.principal.value,
        "party": manifest.party.value,
        "purpose": manifest.purpose,
        "conversation_id": manifest.conversation_id,
        "manifest_hash": manifest.manifest_hash,
    }
    return f"ctx:{sha256(rfc8785.dumps(identity)).hexdigest()}"


def default_context_assembler(
    *, sira_tools: frozenset[str], seil_tools: frozenset[str]
) -> ContextAssembler:
    return ContextAssembler(
        PolicyCatalog(
            (
                PrincipalPolicy(
                    principal=Principal.SIRA,
                    party=Party.BUYER,
                    purpose="software_selection",
                    allowed_tools=sira_tools,
                    budget=TurnBudget(max_cost_usd=0.25),
                ),
                PrincipalPolicy(
                    principal=Principal.SEIL,
                    party=Party.SELLER,
                    purpose="seller_evidence",
                    allowed_tools=seil_tools,
                    budget=TurnBudget(max_cost_usd=0.20),
                ),
            )
        )
    )
