from __future__ import annotations

from copy import deepcopy

import pytest

from domain.hashing import content_hash
from proof.causal_demo import _run_record
from proof.constants import PROFILE_DATASET_URN, ROOT_DATASET_URN, SUPPORT_OWNER_URN
from proof.exchange_demo import _buyer_decision_evidence_core
from proof.models import (
    CampaignDecision,
    CandidateVerdict,
    DependencyRow,
    EnvironmentObservation,
    EvaluationManifest,
    ManifestGate,
    ProofContractError,
)


def _hash(label: object) -> str:
    return content_hash({"label": label})


def _observation() -> EnvironmentObservation:
    dependencies = (
        DependencyRow(ROOT_DATASET_URN, "ownership", "owners", _hash("owners")),
        DependencyRow(
            PROFILE_DATASET_URN,
            "schemaMetadata",
            "fields.email.tags.PII",
            _hash("pii-present"),
        ),
    )
    safe_context = {
        "root": ROOT_DATASET_URN,
        "profile": PROFILE_DATASET_URN,
        "dependencies": [row.to_dict() for row in dependencies],
    }
    return EnvironmentObservation(
        root_urn=ROOT_DATASET_URN,
        profile_urn=PROFILE_DATASET_URN,
        root_fields=("body", "customer_email", "ticket_id"),
        profile_fields=("customer_id", "email", "region"),
        upstream_urns=(PROFILE_DATASET_URN,),
        owner_urns=(SUPPORT_OWNER_URN,),
        allowed_regions=("EU",),
        pii_present=True,
        dependencies=dependencies,
        environment_fingerprint=_hash("environment"),
        semantic_hash=_hash(safe_context),
        read_attempts=2,
    )


def test_causal_run_exposes_safe_datahub_context_and_source_details() -> None:
    observation = _observation()
    manifest = EvaluationManifest(
        compiler_version="manifest-v0.1",
        policy_version="support-agent-admission/v1",
        environment_fingerprint=observation.environment_fingerprint,
        observation_hash=observation.semantic_hash,
        gates=(ManifestGate("rule-pii", "RAW_PII_EGRESS_FORBIDDEN", ("PII",)),),
        allowed_execution_regions=("EU",),
        required_input_fields=("body", "customer_email", "ticket_id"),
        activation_owner_urn=SUPPORT_OWNER_URN,
        seller_safe_payload={"requiredGateIds": ["RAW_PII_EGRESS_FORBIDDEN"]},
        manifest_hash=_hash("manifest"),
    )
    verdict = CandidateVerdict(
        adapter_id="adapter-b",
        eligible=True,
        failed_gate_ids=(),
        declared_price="0.05",
        result_hash=_hash("result-b"),
        artifact_digest=_hash("digest-b"),
    )
    decision = CampaignDecision(
        manifest_hash=manifest.manifest_hash,
        winner_adapter_id="adapter-b",
        verdicts=(verdict,),
        decision_graph_selected_plan_id="plan-b",
        decision_graph_evaluation_hash=_hash("evaluation-b"),
        decision_hash=_hash("decision-b"),
    )

    record = _run_record(
        "baseline-pii-present",
        observation,
        manifest,
        decision,
        {"results": {"adapter-b": {"status": "completed"}}},
    )

    safe_observation = record["environmentObservation"]
    assert safe_observation["safeContext"] == observation.semantic_payload()
    assert safe_observation["semanticHash"] == record["observationHash"]
    assert safe_observation["readAttempts"] == 2
    assert {detail["fact"] for detail in safe_observation["sourceDetails"]} == {
        "allowedRegions",
        "emailPiiTagged",
        "ownerUrns",
        "schemaFields",
        "upstreamDatasets",
    }
    assert all(
        "urn" in detail and "label" in detail for detail in safe_observation["sourceDetails"]
    )


def _causal_payload() -> dict[str, object]:
    source_details = [
        {
            "urn": PROFILE_DATASET_URN,
            "label": "Customer email classification",
            "fact": "emailPiiTagged",
            "value": True,
        }
    ]
    safe_context = {"profileUrn": PROFILE_DATASET_URN, "piiPresent": True}

    def run(label: str, *, winner: str, pii_present: bool, suffix: str) -> dict[str, object]:
        verdicts = [
            {
                "adapter_id": adapter_id,
                "artifact_digest": _hash(f"digest-{adapter_id}"),
                "eligible": adapter_id == winner or not pii_present,
                "failed_gate_ids": [] if adapter_id == winner else ["RAW_PII_EGRESS_FORBIDDEN"],
                "result_hash": _hash(f"result-{adapter_id}-{suffix}"),
            }
            for adapter_id in ("adapter-a", "adapter-b")
        ]
        return {
            "label": label,
            "piiPresent": pii_present,
            "winnerAdapterId": winner,
            "observationHash": _hash(f"observation-{suffix}"),
            "environmentFingerprint": _hash(f"environment-{suffix}"),
            "manifestHash": _hash(f"manifest-{suffix}"),
            "decisionHash": _hash(f"decision-{suffix}"),
            "decisionGraphSelectedPlanId": f"plan-{winner}",
            "decisionGraphEvaluationHash": _hash(f"evaluation-{suffix}"),
            "emittedGateIds": ["RAW_PII_EGRESS_FORBIDDEN"],
            "environmentObservation": {
                "safeContext": safe_context,
                "sourceDetails": source_details,
                "semanticHash": _hash(f"observation-{suffix}"),
            },
            "verdicts": verdicts,
        }

    baseline = run("baseline-pii-present", winner="adapter-b", pii_present=True, suffix="b")
    restored = deepcopy(baseline)
    restored["label"] = "pii-restored"
    mutation = run("pii-removed", winner="adapter-a", pii_present=False, suffix="a")
    return {
        "status": "PASS",
        "causalSequence": ["adapter-b", "adapter-a", "adapter-b"],
        "negativeControl": {
            "tagObservedBeforeEvaluation": True,
            "acceptedFingerprintUnchanged": True,
            "manifestHashUnchanged": True,
            "decisionHashUnchanged": True,
        },
        "runs": [baseline, mutation, restored],
    }


def _projections() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "adapterId": adapter_id,
            "sourceSellerOrganizationId": f"org-{adapter_id}",
            "sourcePackVersionId": f"pack-{adapter_id}",
            "projectionHash": _hash(f"projection-{adapter_id}"),
            "artifactDigest": _hash(f"digest-{adapter_id}"),
            "capabilities": ["SUPPORT_SUMMARIZATION"],
            "fixedPrice": {"amount": price, "currency": "USD"},
        }
        for adapter_id, price in (("adapter-a", "0.02"), ("adapter-b", "0.05"))
    )


def test_buyer_decision_core_binds_restored_b_and_counterfactual_a() -> None:
    causal = _causal_payload()
    core = _buyer_decision_evidence_core(causal, _projections())
    restored = causal["runs"][2]  # type: ignore[index]
    mutation = causal["runs"][1]  # type: ignore[index]

    assert core["decisionHash"] == restored["decisionHash"]
    assert core["recommendation"]["adapterId"] == "adapter-b"
    assert core["counterfactual"]["alternativeAdapterId"] == "adapter-a"
    assert core["counterfactual"]["decisionHash"] == mutation["decisionHash"]
    assert core["causalVerification"]["restoredBaselineMatched"] is True
    assert {item["adapterId"] for item in core["sellerEvidence"]} == {
        "adapter-a",
        "adapter-b",
    }


def test_buyer_decision_core_fails_closed_on_unbound_restoration() -> None:
    causal = _causal_payload()
    causal["runs"][2]["decisionHash"] = _hash("drifted")  # type: ignore[index]

    with pytest.raises(ProofContractError, match="restored baseline does not match"):
        _buyer_decision_evidence_core(causal, _projections())
