"""Bedrock Automated Reasoning as a bounded explanatory review.

The result is deliberately incapable of authorizing a commercial effect.  CockroachDB
constraints, application policy and explicit human actions remain authoritative.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field

_FINDING_TYPES = (
    "valid",
    "invalid",
    "satisfiable",
    "impossible",
    "translationAmbiguous",
    "tooComplex",
    "noTranslations",
)
_OUTCOME_PRIORITY = {
    "ERROR": 7,
    "TOO_COMPLEX": 6,
    "AMBIGUOUS": 5,
    "IMPOSSIBLE": 4,
    "CONTRADICTED": 3,
    "NEEDS_CONTEXT": 2,
    "CONSISTENT": 1,
    "NOT_EVALUATED": 0,
}
_MAX_TEXT = 12_000


class ApplyGuardrailClient(Protocol):
    def apply_guardrail(self, **kwargs: Any) -> Mapping[str, Any]: ...


class AutomatedReasoningFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal[
        "valid",
        "invalid",
        "satisfiable",
        "impossible",
        "translationAmbiguous",
        "tooComplex",
        "noTranslations",
    ]
    rule_ids: tuple[str, ...] = ()
    translation_confidence: float | None = Field(default=None, ge=0, le=1)
    untranslated_premises: int = Field(default=0, ge=0)
    untranslated_claims: int = Field(default=0, ge=0)


class AutomatedReasoningReview(BaseModel):
    """Sanitized advisory artifact safe to persist beside a model decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: Literal[
        "CONSISTENT",
        "CONTRADICTED",
        "NEEDS_CONTEXT",
        "IMPOSSIBLE",
        "AMBIGUOUS",
        "TOO_COMPLEX",
        "NOT_EVALUATED",
        "ERROR",
    ]
    findings: tuple[AutomatedReasoningFinding, ...]
    evaluated_units: int = Field(ge=0)
    input_hash: str
    authority: Literal["EXPLANATORY_ONLY"] = "EXPLANATORY_ONLY"
    authoritative: Literal[False] = False
    may_authorize: Literal[False] = False


@dataclass(slots=True)
class BedrockAutomatedReasoningReviewer:
    client: ApplyGuardrailClient = field(repr=False)
    guardrail_identifier: str
    guardrail_version: str
    timeout_seconds: float = 45

    def __post_init__(self) -> None:
        if not self.guardrail_identifier.strip() or not self.guardrail_version.strip():
            raise ValueError("Automated Reasoning requires a versioned Guardrail")
        if self.guardrail_version == "DRAFT":
            raise ValueError("Automated Reasoning production review cannot use DRAFT")

    async def review(self, *, query: str, claim: str) -> AutomatedReasoningReview:
        normalized_query = _bounded(query, "query")
        normalized_claim = _bounded(claim, "claim")
        digest = "sha256:" + sha256(
            (normalized_query + "\x00" + normalized_claim).encode("utf-8")
        ).hexdigest()
        async with asyncio.timeout(self.timeout_seconds):
            response = await asyncio.to_thread(
                self.client.apply_guardrail,
                guardrailIdentifier=self.guardrail_identifier,
                guardrailVersion=self.guardrail_version,
                source="OUTPUT",
                outputScope="FULL",
                content=[
                    {
                        "text": {
                            "text": normalized_query,
                            "qualifiers": ["query"],
                        }
                    },
                    {
                        "text": {
                            "text": normalized_claim,
                            "qualifiers": ["guard_content"],
                        }
                    },
                ],
            )
        return _parse_review(response, digest)


def _parse_review(response: Mapping[str, Any], input_hash: str) -> AutomatedReasoningReview:
    usage = response.get("usage", {})
    units = int(usage.get("automatedReasoningPolicyUnits", 0)) if isinstance(usage, Mapping) else 0
    parsed: list[AutomatedReasoningFinding] = []
    assessments = response.get("assessments", [])
    if isinstance(assessments, list):
        for assessment in assessments:
            if not isinstance(assessment, Mapping):
                continue
            policy = assessment.get("automatedReasoningPolicy", {})
            if not isinstance(policy, Mapping):
                continue
            findings = policy.get("findings", [])
            if not isinstance(findings, list):
                continue
            for finding in findings:
                parsed_finding = _parse_finding(finding)
                if parsed_finding is not None:
                    parsed.append(parsed_finding)
    if units <= 0:
        return AutomatedReasoningReview(
            outcome="NOT_EVALUATED",
            findings=tuple(parsed),
            evaluated_units=0,
            input_hash=input_hash,
        )
    outcomes = [_outcome(item.kind) for item in parsed]
    outcome = max(outcomes, key=_OUTCOME_PRIORITY.__getitem__) if outcomes else "ERROR"
    return AutomatedReasoningReview(
        outcome=outcome,
        findings=tuple(parsed),
        evaluated_units=units,
        input_hash=input_hash,
    )


def _parse_finding(value: object) -> AutomatedReasoningFinding | None:
    if not isinstance(value, Mapping):
        return None
    present = [name for name in _FINDING_TYPES if name in value]
    if len(present) != 1:
        return None
    kind = present[0]
    detail = value.get(kind)
    detail = detail if isinstance(detail, Mapping) else {}
    rules: list[str] = []
    for key in ("supportingRules", "contradictingRules"):
        candidates = detail.get(key, [])
        if isinstance(candidates, list):
            for candidate in candidates:
                if isinstance(candidate, Mapping):
                    identifier = candidate.get("identifier")
                    if isinstance(identifier, str) and identifier:
                        rules.append(identifier)
    translation = detail.get("translation", {})
    translation = translation if isinstance(translation, Mapping) else {}
    confidence = translation.get("confidence")
    finding_kind = cast(
        Literal[
            "valid",
            "invalid",
            "satisfiable",
            "impossible",
            "translationAmbiguous",
            "tooComplex",
            "noTranslations",
        ],
        kind,
    )
    return AutomatedReasoningFinding(
        kind=finding_kind,
        rule_ids=tuple(dict.fromkeys(rules)),
        translation_confidence=(
            float(confidence) if isinstance(confidence, (int, float)) else None
        ),
        untranslated_premises=_list_length(translation.get("untranslatedPremises")),
        untranslated_claims=_list_length(translation.get("untranslatedClaims")),
    )


def _outcome(kind: str) -> str:
    return {
        "valid": "CONSISTENT",
        "invalid": "CONTRADICTED",
        "satisfiable": "NEEDS_CONTEXT",
        "impossible": "IMPOSSIBLE",
        "translationAmbiguous": "AMBIGUOUS",
        "tooComplex": "TOO_COMPLEX",
        "noTranslations": "NOT_EVALUATED",
    }[kind]


def _bounded(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"Automated Reasoning {field_name} is required")
    if len(normalized) > _MAX_TEXT:
        raise ValueError(f"Automated Reasoning {field_name} exceeds {_MAX_TEXT} characters")
    return normalized


def _list_length(value: object) -> int:
    return len(value) if isinstance(value, list) else 0
