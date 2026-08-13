"""Labelled live-model evaluation for the Bedrock qualification boundary."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sira_agents.bedrock_runtime import (
    BedrockClient,
    BedrockConverseRuntime,
    BedrockGuardrail,
    BedrockTool,
)
from sira_agents.runtime import AgentRole, AgentRunContext, AgentRunRequest, AuthorityMode

from persistence.repositories import PersistenceConflict

from .qualification import QualificationAgentDecision, _validate_grounded_decision


class EvaluationEvidence(BaseModel):
    """Synthetic buyer-safe evidence returned through the production-style tool seam."""

    model_config = ConfigDict(extra="forbid")

    dependency_id: str = Field(min_length=1, max_length=80)
    claim: str = Field(min_length=1, max_length=500)


class BedrockQualificationEvalCase(BaseModel):
    """A labelled qualification case containing no customer or credential data."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    requirement: str = Field(min_length=1, max_length=1000)
    policy: str = Field(min_length=1, max_length=1000)
    expected_product_id: str = Field(min_length=1, max_length=64)
    evidence_by_product: dict[str, list[EvaluationEvidence]] = Field(min_length=2)


@dataclass(frozen=True, slots=True)
class BedrockQualificationCaseResult:
    case_id: str
    expected_product_id: str
    actual_product_id: str | None
    structured_output_valid: bool
    inspected_every_candidate: bool
    grounded: bool
    expected_product_match: bool
    output_sha256: str | None
    input_sha256: str
    failure_category: str | None
    input_tokens: int
    output_tokens: int


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + sha256(encoded.encode("utf-8")).hexdigest()


def _failure_category(error: Exception) -> str:
    if isinstance(error, PersistenceConflict):
        return "GROUNDING_REJECTED"
    name = type(error).__name__
    if name == "ValidationError":
        return "STRUCTURED_OUTPUT_INVALID"
    if name in {"BedrockRuntimeError", "BedrockGuardrailBlocked"}:
        return "BEDROCK_CONTRACT_REJECTED"
    return "PROVIDER_ERROR"


async def evaluate_bedrock_qualification(
    *,
    client: BedrockClient,
    model_id: str,
    cases: Sequence[BedrockQualificationEvalCase],
    guardrail: BedrockGuardrail | None = None,
) -> tuple[BedrockQualificationCaseResult, ...]:
    """Run labelled cases through typed output, tool-use, and grounding gates.

    This evaluates advisory model output only. It never opens a database transaction or
    invokes a commercial side effect.
    """

    results: list[BedrockQualificationCaseResult] = []
    for case in cases:
        allowed_products = frozenset(case.evidence_by_product)
        dependency_products = {
            evidence.dependency_id: product_id
            for product_id, evidence_rows in case.evidence_by_product.items()
            for evidence in evidence_rows
        }
        inspected_products: set[str] = set()
        evidence_by_product = case.evidence_by_product

        async def retrieve(
            tool_input: Mapping[str, Any],
            _context: AgentRunContext | None,
            *,
            scoped_products: frozenset[str] = allowed_products,
            observed_products: set[str] = inspected_products,
            scoped_evidence: Mapping[str, list[EvaluationEvidence]] = evidence_by_product,
        ) -> Mapping[str, Any]:
            product_id = str(tool_input.get("product_id", ""))
            if product_id not in scoped_products:
                raise PersistenceConflict("model requested evidence outside candidate set")
            observed_products.add(product_id)
            return {
                "product_id": product_id,
                "evidence": [
                    evidence.model_dump(mode="json")
                    for evidence in scoped_evidence[product_id]
                ],
            }

        runtime = BedrockConverseRuntime(
            client=client,
            model_id=model_id,
            guardrail=guardrail,
            tools={
                "retrieve_product_evidence": BedrockTool(
                    name="retrieve_product_evidence",
                    description="Retrieve buyer-safe evidence for one candidate in this case.",
                    input_schema={
                        "type": "object",
                        "properties": {"product_id": {"type": "string"}},
                        "required": ["product_id"],
                        "additionalProperties": False,
                    },
                    handler=retrieve,
                )
            },
            max_turns=4,
        )
        structured = False
        grounded = False
        actual_product_id: str | None = None
        output_hash: str | None = None
        failure: str | None = None
        input_tokens = 0
        output_tokens = 0
        try:
            run = await runtime.run(
                AgentRunRequest(
                    role=AgentRole.SIRA,
                    instructions=(
                        "Compare every candidate against the requirement and policy. Call "
                        "retrieve_product_evidence exactly once for every candidate. Recommend "
                        "only a listed candidate and cite only dependency IDs returned by tools. "
                        "For every criterion whose result is not UNKNOWN, provide a non-empty "
                        "rationale and at least one citation; otherwise omit criteria."
                    ),
                    prompt="Produce the best current qualification decision.",
                    model_context={
                        "requirement": case.requirement,
                        "policy": case.policy,
                        "candidate_product_ids": sorted(allowed_products),
                    },
                    run_context=AgentRunContext(
                        organization_id="synthetic-evaluation",
                        actor_id="bedrock-quality-runner",
                        request_id=f"eval-{case.id}",
                    ),
                    allowed_tools=("retrieve_product_evidence",),
                    output_type=QualificationAgentDecision,
                    authority_mode=AuthorityMode.ADVISORY,
                )
            )
            if not isinstance(run.output, QualificationAgentDecision):
                raise TypeError("Bedrock returned an unexpected output type")
            structured = True
            actual_product_id = run.output.recommended_product_id
            output_hash = _digest(run.output.model_dump(mode="json"))
            usage = run.metadata.get("usage", {})
            if isinstance(usage, Mapping):
                input_tokens = int(usage.get("inputTokens", 0))
                output_tokens = int(usage.get("outputTokens", 0))
            if inspected_products != allowed_products:
                raise PersistenceConflict("model did not inspect every candidate")
            _validate_grounded_decision(
                run.output,
                allowed_products=allowed_products,
                dependency_products=dependency_products,
            )
            grounded = True
        except Exception as error:
            failure = _failure_category(error)

        input_hash = _digest(case.model_dump(mode="json"))
        inspected_every = inspected_products == allowed_products
        results.append(
            BedrockQualificationCaseResult(
                case_id=case.id,
                expected_product_id=case.expected_product_id,
                actual_product_id=actual_product_id,
                structured_output_valid=structured,
                inspected_every_candidate=inspected_every,
                grounded=grounded,
                expected_product_match=(
                    grounded and actual_product_id == case.expected_product_id
                ),
                output_sha256=output_hash,
                input_sha256=input_hash,
                failure_category=failure,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        )
    return tuple(results)


def build_bedrock_qualification_report(
    *,
    model_id: str,
    region: str,
    results: Sequence[BedrockQualificationCaseResult],
) -> dict[str, object]:
    """Build a credential-free report without prompts, evidence, or model prose."""

    count = len(results)
    structured = sum(result.structured_output_valid for result in results)
    inspected = sum(result.inspected_every_candidate for result in results)
    grounded = sum(result.grounded for result in results)
    matched = sum(result.expected_product_match for result in results)
    denominator = count or 1
    metrics = {
        "structured_output_rate": structured / denominator,
        "all_candidates_inspected_rate": inspected / denominator,
        "grounded_output_rate": grounded / denominator,
        "expected_product_accuracy": matched / denominator,
    }
    thresholds = {
        "structured_output_rate": 1.0,
        "all_candidates_inspected_rate": 1.0,
        "grounded_output_rate": 1.0,
        "expected_product_accuracy": 0.8,
    }
    passed = count > 0 and all(metrics[name] >= threshold for name, threshold in thresholds.items())
    return {
        "schema_version": 1,
        "evaluation": "bedrock-live-qualification-quality",
        "status": "PASS" if passed else "FAIL",
        "checked_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "provider": "AWS Bedrock Converse",
        "model_id": model_id,
        "region": region,
        "authority_mode": "ADVISORY",
        "case_count": count,
        "metrics": metrics,
        "thresholds": thresholds,
        "usage": {
            "input_tokens": sum(result.input_tokens for result in results),
            "output_tokens": sum(result.output_tokens for result in results),
        },
        "cases": [
            {
                "id": result.case_id,
                "expected_product_id": result.expected_product_id,
                "actual_product_id": result.actual_product_id,
                "structured_output_valid": result.structured_output_valid,
                "inspected_every_candidate": result.inspected_every_candidate,
                "grounded": result.grounded,
                "expected_product_match": result.expected_product_match,
                "input_sha256": result.input_sha256,
                "output_sha256": result.output_sha256,
                "failure_category": result.failure_category,
            }
            for result in results
        ],
        "data_handling": {
            "synthetic_cases_only": True,
            "raw_prompts_persisted": False,
            "raw_evidence_persisted": False,
            "raw_model_output_persisted": False,
            "credentials_persisted": False,
        },
        "limitations": [
            "This small synthetic set is a release gate, not a production accuracy estimate.",
            "Deterministic authorization and grounding checks remain authoritative.",
            "A passing run does not prove deployed Guardrail intervention.",
        ],
    }
