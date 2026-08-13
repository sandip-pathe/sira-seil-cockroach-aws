from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from integrations.automated_reasoning import BedrockAutomatedReasoningReviewer


@dataclass
class FakeGuardrail:
    response: dict[str, Any]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def apply_guardrail(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.response


async def test_review_is_sanitized_explanatory_only_and_tags_query_and_claim() -> None:
    client = FakeGuardrail(
        {
            "usage": {"automatedReasoningPolicyUnits": 1},
            "outputs": [{"text": "must never be persisted"}],
            "assessments": [
                {
                    "automatedReasoningPolicy": {
                        "findings": [
                            {
                                "invalid": {
                                    "translation": {
                                        "confidence": 0.91,
                                        "untranslatedPremises": [{"text": "x"}],
                                        "untranslatedClaims": [],
                                    },
                                    "contradictingRules": [
                                        {
                                            "identifier": "RULE_POLICY1",
                                            "policyVersionArn": "provider-policy-version",
                                        }
                                    ],
                                }
                            }
                        ]
                    }
                }
            ],
        }
    )
    reviewer = BedrockAutomatedReasoningReviewer(client, "guardrail-1", "1")

    result = await reviewer.review(query="Buyer has not approved.", claim="Purchase completed.")

    assert result.outcome == "CONTRADICTED"
    assert result.authority == "EXPLANATORY_ONLY"
    assert result.authoritative is False
    assert result.may_authorize is False
    assert result.findings[0].rule_ids == ("RULE_POLICY1",)
    assert result.findings[0].untranslated_premises == 1
    assert "must never" not in result.model_dump_json()
    assert client.calls[0]["source"] == "OUTPUT"
    assert client.calls[0]["outputScope"] == "FULL"
    assert client.calls[0]["content"][0]["text"]["qualifiers"] == ["query"]
    assert client.calls[0]["content"][1]["text"]["qualifiers"] == ["guard_content"]


@pytest.mark.parametrize(
    ("finding", "outcome"),
    [
        ("valid", "CONSISTENT"),
        ("satisfiable", "NEEDS_CONTEXT"),
        ("impossible", "IMPOSSIBLE"),
        ("translationAmbiguous", "AMBIGUOUS"),
        ("tooComplex", "TOO_COMPLEX"),
        ("noTranslations", "NOT_EVALUATED"),
    ],
)
async def test_review_maps_all_provider_findings(finding: str, outcome: str) -> None:
    response = {
        "usage": {"automatedReasoningPolicyUnits": 1},
        "assessments": [{"automatedReasoningPolicy": {"findings": [{finding: {}}]}}],
    }
    result = await BedrockAutomatedReasoningReviewer(
        FakeGuardrail(response), "guardrail-1", "2"
    ).review(query="A policy question", claim="A policy claim")
    assert result.outcome == outcome


async def test_zero_usage_is_explicitly_not_evaluated() -> None:
    result = await BedrockAutomatedReasoningReviewer(
        FakeGuardrail({"usage": {"automatedReasoningPolicyUnits": 0}}),
        "guardrail-1",
        "1",
    ).review(query="question", claim="claim")
    assert result.outcome == "NOT_EVALUATED"
    assert result.evaluated_units == 0


def test_reviewer_rejects_draft_and_unbounded_content() -> None:
    with pytest.raises(ValueError, match="DRAFT"):
        BedrockAutomatedReasoningReviewer(FakeGuardrail({}), "guardrail-1", "DRAFT")


async def test_safe_review_makes_provider_failure_visible_but_non_authoritative() -> None:
    class FailedGuardrail:
        def apply_guardrail(self, **_kwargs: Any) -> dict[str, Any]:
            raise TimeoutError("provider detail must not escape")

    result = await BedrockAutomatedReasoningReviewer(
        FailedGuardrail(), "guardrail-1", "1"
    ).review_safely(query="question", claim="claim")
    assert result.outcome == "ERROR"
    assert result.authoritative is False
    assert "provider detail" not in result.model_dump_json()
