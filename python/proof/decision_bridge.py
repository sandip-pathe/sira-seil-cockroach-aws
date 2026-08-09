"""Map verified K1 trial aggregates into the existing Decision Graph."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from decision_engine.bounds import ExactRatio
from decision_engine.graph_v1 import evaluate_decision_graph_once
from decision_engine.graph_v1_models import (
    DecisionGraphInput,
    EvidencePolicy,
    EvidenceRecord,
    FrozenFact,
    FrozenVersions,
    GateMode,
    GateRule,
    IdentityNormalization,
    NormalizationKind,
    OfferCost,
    Predicate,
    PreferenceCriterion,
    ProductFact,
    RawCandidateRecord,
    RiskRule,
)
from domain.enums import CandidateStatus, PackAuthority, SolutionAction, StackRisk
from domain.money import Money

from .models import CandidateVerdict, EvaluationManifest, ProofContractError

EVALUATED_AT = datetime(2030, 1, 1, tzinfo=UTC)


def evaluate_with_decision_graph(
    manifest: EvaluationManifest, verdicts: tuple[CandidateVerdict, ...]
) -> tuple[str, str, str]:
    gate_fields = {
        "FUNCTIONAL_CANARY_PASSED": "proof.functional_canary_passed",
        "EXECUTION_REGION_ALLOWED": "proof.execution_region_allowed",
        "REQUIRED_SCHEMA_SUPPORTED": "proof.required_schema_supported",
        "RAW_PII_EGRESS_FORBIDDEN": "proof.raw_pii_egress_forbidden",
    }
    manifest_gate_ids = {gate.gate_id for gate in manifest.gates}
    active_gate_ids = ("FUNCTIONAL_CANARY_PASSED", *sorted(manifest_gate_ids))
    buyer_facts = (
        *(
            FrozenFact(
                fact_id=f"manifest_{gate_id.lower()}",
                field=gate_fields[gate_id],
                value=True,
                private=True,
                version=manifest.manifest_hash,
                asserted_by_role="datahub_manifest_compiler",
                authority_level="GOVERNED_CONTEXT",
                authority_rank=100,
            )
            for gate_id in active_gate_ids
        ),
        FrozenFact(
            fact_id="proof_fixed_price_policy",
            field="proof.price_policy",
            value="LOWER_IS_BETTER",
            private=False,
            version=manifest.policy_version,
            asserted_by_role="proof_campaign",
            authority_level="FROZEN_POLICY",
            authority_rank=100,
        ),
    )
    candidates: list[RawCandidateRecord] = []
    offers: list[OfferCost] = []
    evidence: list[EvidenceRecord] = []
    policies: list[EvidencePolicy] = []
    policy_fields = set(gate_fields[gate_id] for gate_id in active_gate_ids)
    policy_fields.add("proof.declared_price_cents")
    for field in sorted(policy_fields):
        policies.append(
            EvidencePolicy(
                field=field,
                allowed_source_classes=("CURATED_ADAPTER_RUNTIME",),
                allowed_verification_methods=("DETERMINISTIC_REPLAY",),
                required_scope="proof-campaign-v1",
                freshness_sla_seconds=3600,
            )
        )
    for verdict in verdicts:
        suffix = verdict.adapter_id.replace("-", "_")
        record_id = f"proof_record_{suffix}"
        evidence_id = f"proof_evidence_{suffix}"
        failed = set(verdict.failed_gate_ids)
        facts = tuple(
            [
                ProductFact(
                    field=gate_fields[gate_id],
                    value=gate_id not in failed,
                    evidence_ids=(evidence_id,),
                )
                for gate_id in active_gate_ids
            ]
            + [
                ProductFact(
                    field="proof.declared_price_cents",
                    value=int(Decimal(verdict.declared_price) * 100),
                    evidence_ids=(evidence_id,),
                )
            ]
        )
        offer_id = f"proof_offer_{suffix}"
        candidates.append(
            RawCandidateRecord(
                record_id=record_id,
                pack_id=f"proof_pack_{suffix}",
                pack_version=1,
                seller_id=f"proof_seller_{suffix}",
                product_id=verdict.adapter_id,
                edition="curated-v1",
                region="EU",
                offer_id=offer_id,
                # K1's two digest-pinned curated fixtures are authoritative inputs.
                # K2 replaces this fixture seam with persisted seller publication.
                authority=PackAuthority.SELLER_SEALED,
                available=True,
                facts=facts,
            )
        )
        offers.append(
            OfferCost(
                offer_id=offer_id,
                low=Money(verdict.declared_price, "USD"),
                base=Money(verdict.declared_price, "USD"),
                high=Money(verdict.declared_price, "USD"),
                horizon_days=1,
            )
        )
        evidence.append(
            EvidenceRecord(
                evidence_id=evidence_id,
                record_id=record_id,
                source_class="CURATED_ADAPTER_RUNTIME",
                verification_method="DETERMINISTIC_REPLAY",
                verification_scope="proof-campaign-v1",
                reconstructable=True,
                observed_at_lower=EVALUATED_AT,
                observed_at_upper=EVALUATED_AT,
            )
        )
    gates = tuple(
        GateRule(
            gate_id=f"proof_gate_{gate_id.lower()}",
            predicates=(Predicate(gate_fields[gate_id], "eq", True),),
            mode=GateMode.REQUIRE_MATCH,
            blocked_status=CandidateStatus.SIRA_INELIGIBLE,
            reason_code=gate_id,
            source_fact_ids=(f"manifest_{gate_id.lower()}",),
            applies_to_actions=(SolutionAction.REPLACE,),
        )
        for gate_id in active_gate_ids
    )
    graph_input = DecisionGraphInput(
        versions=FrozenVersions(
            request_version="proof-request/v1",
            company_profile_version=manifest.environment_fingerprint,
            stackfile_version="not-applicable",
            registry_version="k1-curated-adapters",
            pack_set_version="k1-direct-runtime",
            offer_set_version="k1-fixed-prices",
            taxonomy_version="support-agent/v1",
            normalization_version="proof-normalization/v1",
            policy_version=manifest.policy_version,
            fx_version="usd-fixed/v1",
            pipeline_version="proof-k1/v1",
            engine_version="decision-graph-v1",
        ),
        evaluated_at=EVALUATED_AT,
        buyer_facts=buyer_facts,
        candidates=tuple(candidates),
        offers=tuple(offers),
        evidence=tuple(evidence),
        evidence_policies=tuple(policies),
        gates=gates,
        preferences=(
            PreferenceCriterion(
                criterion_id="proof_declared_price",
                field="proof.declared_price_cents",
                weight=5,
                coverage_weight=5,
                normalization=NormalizationKind.LOWER_IS_BETTER,
                expected=0,
                source_fact_ids=("proof_fixed_price_policy",),
                applies_to_actions=(SolutionAction.REPLACE,),
                allowed_satisfactions=(ExactRatio(0), ExactRatio(1)),
                lower_is_better_points=((2, ExactRatio(1)), (5, ExactRatio(0))),
            ),
        ),
        risk_rules=(
            RiskRule(
                rule_id="proof_curated_adapter_risk",
                actions=(SolutionAction.REPLACE,),
                predicate=None,
                lower=StackRisk.LOW,
                base=StackRisk.LOW,
                upper=StackRisk.LOW,
            ),
        ),
        risk_rule_set_complete=True,
        current_actions=(),
        identity_normalization=IdentityNormalization(version="proof-identity/v1", aliases=()),
    )
    evaluation = evaluate_decision_graph_once(
        graph_input,
        evaluation_id=f"proof_eval_{manifest.manifest_hash[-16:]}",
        generated_at=EVALUATED_AT,
    )
    if evaluation.selected_plan_id is None:
        diagnostics = tuple(
            (
                plan.components[0].component_id if plan.components else "unknown",
                plan.status.value,
                plan.dimensions.bound_unavailable_reasons,
            )
            for plan in evaluation.plans
        )
        raise ProofContractError(
            f"existing Decision Graph could not select a stable proof winner: {diagnostics}"
        )
    selected = next(
        plan for plan in evaluation.plans if plan.plan_id == evaluation.selected_plan_id
    )
    if len(selected.components) != 1:
        raise ProofContractError("proof winner must contain exactly one adapter")
    return (
        selected.components[0].component_id,
        evaluation.selected_plan_id,
        evaluation.evaluation_payload_hash,
    )
