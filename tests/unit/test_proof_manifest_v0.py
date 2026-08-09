from dataclasses import replace

import pytest

from domain.hashing import content_hash
from proof import datahub_mcp
from proof.constants import (
    ALLOWED_REGIONS_PROPERTY_URN,
    PROFILE_DATASET_URN,
    ROOT_DATASET_URN,
    SUPPORT_OWNER_URN,
)
from proof.manifest_v0 import compile_manifest, evaluate_campaign
from proof.models import DependencyRow, EnvironmentObservation, ProofContractError


def _observation(*, pii_present: bool = True) -> EnvironmentObservation:
    dependencies = tuple(
        sorted(
            (
                DependencyRow(ROOT_DATASET_URN, "schemaMetadata", "fields", "sha256:root"),
                DependencyRow(
                    PROFILE_DATASET_URN,
                    "schemaMetadata",
                    "fields.email.tags.PII",
                    content_hash(pii_present),
                ),
                DependencyRow(
                    PROFILE_DATASET_URN,
                    "structuredProperties",
                    ALLOWED_REGIONS_PROPERTY_URN,
                    content_hash(("EU",)),
                ),
            )
        )
    )
    semantic = {
        "pii": pii_present,
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
        pii_present=pii_present,
        dependencies=dependencies,
        environment_fingerprint=content_hash(semantic),
        semantic_hash=content_hash(semantic),
        read_attempts=1,
    )


def _runtime(adapter_id: str, *, pii_passes: bool) -> dict[str, object]:
    return {
        "status": "completed",
        "artifactDigest": f"sha256:{adapter_id}",
        "resultHash": f"sha256:result-{adapter_id}-{pii_passes}",
        "gateResults": {
            "FUNCTIONAL_CANARY_PASSED": True,
            "EXECUTION_REGION_ALLOWED": True,
            "REQUIRED_SCHEMA_SUPPORTED": True,
            "RAW_PII_EGRESS_FORBIDDEN": pii_passes,
        },
    }


def test_pii_fact_is_the_only_rule_that_changes_between_manifests() -> None:
    present = compile_manifest(_observation(pii_present=True))
    absent = compile_manifest(_observation(pii_present=False))

    assert [gate.gate_id for gate in present.gates] == [
        "RAW_PII_EGRESS_FORBIDDEN",
        "EXECUTION_REGION_ALLOWED",
        "REQUIRED_SCHEMA_SUPPORTED",
    ]
    assert [gate.gate_id for gate in absent.gates] == [
        "EXECUTION_REGION_ALLOWED",
        "REQUIRED_SCHEMA_SUPPORTED",
    ]
    assert present.manifest_hash != absent.manifest_hash


def test_campaign_selects_b_with_pii_and_a_without_pii() -> None:
    with_pii = compile_manifest(_observation(pii_present=True))
    without_pii = compile_manifest(_observation(pii_present=False))
    runtime = {
        "adapter-a": _runtime("adapter-a", pii_passes=False),
        "adapter-b": _runtime("adapter-b", pii_passes=True),
    }

    pii_decision = evaluate_campaign(with_pii, runtime)
    no_pii_decision = evaluate_campaign(without_pii, runtime)

    assert pii_decision.winner_adapter_id == "adapter-b"
    assert no_pii_decision.winner_adapter_id == "adapter-a"
    assert pii_decision.decision_graph_selected_plan_id
    assert pii_decision.decision_graph_evaluation_hash.startswith("sha256:")


def test_compiler_fails_closed_when_owner_or_lineage_is_missing() -> None:
    observation = _observation()

    with pytest.raises(ProofContractError, match="governing owner"):
        compile_manifest(replace(observation, owner_urns=()))
    with pytest.raises(ProofContractError, match="lineage"):
        compile_manifest(replace(observation, upstream_urns=()))


def test_dependency_order_does_not_change_manifest_hash() -> None:
    observation = _observation()
    reordered = replace(observation, dependencies=tuple(reversed(observation.dependencies)))

    assert compile_manifest(observation).manifest_hash == compile_manifest(reordered).manifest_hash


def test_seller_safe_manifest_excludes_internal_graph_identity() -> None:
    manifest = compile_manifest(_observation())
    rendered = str(manifest.seller_safe_payload)

    assert "urn:li:" not in rendered
    assert "dependencies" not in rendered
    assert "observationHash" not in rendered


@pytest.mark.asyncio
async def test_stable_reader_fails_closed_when_decisive_context_keeps_changing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def changing_read(_session: object, *, attempts: int = 1) -> EnvironmentObservation:
        nonlocal calls
        calls += 1
        return replace(_observation(), semantic_hash=f"sha256:changing-{calls}")

    monkeypatch.setattr(datahub_mcp, "read_once", changing_read)

    with pytest.raises(ProofContractError, match="CONTEXT_UNSTABLE"):
        await datahub_mcp.read_stable(object(), max_attempts=2)  # type: ignore[arg-type]
