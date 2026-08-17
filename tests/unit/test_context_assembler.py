from __future__ import annotations

import pytest
from sira_agents.context_assembler import (
    ContextAssembler,
    PolicyCatalog,
    PrincipalPolicy,
    context_cache_key,
)
from sira_agents.guardrails import AgentBoundaryViolation
from sira_agents.kernel_models import ContextReference, Party, Principal, TurnBudget


def _assembler() -> ContextAssembler:
    return ContextAssembler(
        PolicyCatalog(
            (
                PrincipalPolicy(
                    principal="SIRA",
                    party="BUYER",
                    purpose="software_selection",
                    allowed_tools=frozenset({"read_buyer_context", "read_released_evidence"}),
                    budget=TurnBudget(max_cost_usd=0.20),
                ),
                PrincipalPolicy(
                    principal="SEIL",
                    party="SELLER",
                    purpose="seller_evidence",
                    allowed_tools=frozenset({"read_seller_product", "publish_evidence"}),
                    budget=TurnBudget(max_cost_usd=0.15),
                ),
            )
        )
    )


def test_context_assembler_filters_tools_and_separates_cache_keys() -> None:
    assembler = _assembler()
    sira = assembler.assemble(
        principal=Principal.SIRA,
        party=Party.BUYER,
        organization_id="org-buyer",
        actor_id="buyer-1",
        purpose="software_selection",
        conversation_id="conversation-1",
        turn_id="turn-1",
        current_message="Compare the released evidence.",
        private_context={"buyer_private_preferences": {"region": "EU"}},
        exchange_projection={"evidence_pack_id": "pack-1"},
        requested_tools=("read_buyer_context", "publish_evidence"),
    )
    seil = assembler.assemble(
        principal=Principal.SEIL,
        party=Party.SELLER,
        organization_id="org-seller",
        actor_id="seller-1",
        purpose="seller_evidence",
        conversation_id="conversation-1",
        turn_id="turn-1",
        current_message="Prepare evidence.",
        private_context={"seller_private_capacity": {"seats": 100}},
        requested_tools=("read_buyer_context", "read_seller_product"),
    )
    assert sira.available_tools == ("read_buyer_context",)
    assert seil.available_tools == ("read_seller_product",)
    assert context_cache_key(sira) != context_cache_key(seil)


@pytest.mark.parametrize(
    ("principal", "party", "purpose", "private_context"),
    [
        (Principal.SIRA, Party.BUYER, "software_selection", {"seller_floor": 10}),
        (Principal.SEIL, Party.SELLER, "seller_evidence", {"buyer_private_budget": 100}),
    ],
)
def test_context_assembler_rejects_opposing_private_plane(
    principal: Principal, party: Party, purpose: str, private_context: dict[str, object]
) -> None:
    with pytest.raises(AgentBoundaryViolation):
        _assembler().assemble(
            principal=principal,
            party=party,
            organization_id="org-1",
            actor_id="actor-1",
            purpose=purpose,
            conversation_id="conversation-1",
            turn_id="turn-1",
            current_message="Continue.",
            private_context=private_context,
        )


def test_context_manifest_rejects_opposing_private_reference() -> None:
    reference = ContextReference(
        kind="memory",
        data_class="seller_private",
        object_id="seller-memory-1",
        version=1,
        content_hash="sha256:" + "a" * 64,
    )
    with pytest.raises(ValueError, match="opposing private plane"):
        _assembler().assemble(
            principal=Principal.SIRA,
            party=Party.BUYER,
            organization_id="org-buyer",
            actor_id="buyer-1",
            purpose="software_selection",
            conversation_id="conversation-1",
            turn_id="turn-1",
            current_message="Continue.",
            references=(reference,),
        )
