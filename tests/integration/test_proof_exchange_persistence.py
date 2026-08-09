from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sira_api.fixtures import DemoFixtureBundle
from sira_api.proof_persistence import ProofPersistenceBindings, persist_proof_evidence
from sira_api.service import WorkflowService
from sqlalchemy import select

from domain.hashing import content_hash
from persistence.database import Database, DatabaseSettings
from persistence.models import (
    AgentExperiment,
    AgentMission,
    Base,
    BuyerProofAdapterProjection,
    DecisionSourceSnapshot,
    EvaluationRun,
    Organization,
    ProofApproval,
)
from persistence.proof_repository import ProofExchangeRepository
from proof.constants import (
    ALLOWED_REGIONS_PROPERTY_URN,
    PROFILE_DATASET_URN,
    ROOT_DATASET_URN,
    SUPPORT_OWNER_URN,
)
from proof.exchange import candidate_release, exact_approval_subject, project_published_adapter
from proof.manifest_v0 import compile_manifest, evaluate_campaign
from proof.models import DependencyRow, EnvironmentObservation


async def _database() -> Database:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.transaction("org_buyer") as session:
        session.add_all(
            (
                Organization(id="org_buyer", name="Buyer", version=1),
                Organization(id="org_seller", name="Seller", version=1),
            )
        )
    return database


def _projection() -> dict[str, object]:
    return project_published_adapter(
        source_seller_organization_id="org_seller",
        source_pack_version_id="pack-a-v1",
        source_pack_content_hash="sha256:" + "a" * 64,
        publication_event_key="seller-pack-published:pack-a-v1",
        published_payload={
            "proof_adapter": {
                "adapter_id": "adapter-a",
                "artifact_digest": "sha256:" + "b" * 64,
                "protocol_version": "TrialCase/v0",
                "capabilities": ["SUPPORT_SUMMARIZATION"],
                "declared_region": "EU",
                "fixed_price": {"amount": "0.02", "currency": "USD"},
                "conformance_hash": "sha256:" + "c" * 64,
            },
            "evidence": [],
        },
    )


@pytest.mark.asyncio
async def test_publication_projection_and_approval_are_idempotent_and_tenant_scoped() -> None:
    database = await _database()
    try:
        projection = _projection()
        release = candidate_release(projection)
        now = datetime(2030, 1, 1, tzinfo=UTC)
        subject = exact_approval_subject(
            manifest_hash="sha256:" + "d" * 64,
            environment_fingerprint="sha256:" + "e" * 64,
            decision_hash="sha256:" + "f" * 64,
            release=release,
            datahub_owner_urn="urn:li:corpGroup:support-data-owners",
            actor_id="seeded_support_owner",
            actor_role="DATA_OWNER",
            expires_at=now + timedelta(minutes=15),
        )
        async with database.transaction("org_buyer") as session:
            repository = ProofExchangeRepository(session, "org_buyer")
            first = await repository.materialize_projection(projection)
            second = await repository.materialize_projection(projection)
            first_approval = await repository.create_approval(
                subject=subject,
            )
            second_approval = await repository.create_approval(
                subject=subject,
            )
            assert first.id == second.id
            assert first_approval.id == second_approval.id

        async with database.transaction("org_seller") as session:
            seller_projections = list(
                (
                    await session.execute(
                        select(BuyerProofAdapterProjection).where(
                            BuyerProofAdapterProjection.organization_id == "org_seller"
                        )
                    )
                ).scalars()
            )
            seller_approvals = list(
                (
                    await session.execute(
                        select(ProofApproval).where(ProofApproval.organization_id == "org_seller")
                    )
                ).scalars()
            )
            assert seller_projections == []
            assert seller_approvals == []
    finally:
        await database.close()


def _observation() -> EnvironmentObservation:
    dependencies = (
        DependencyRow(ROOT_DATASET_URN, "schemaMetadata", "fields", content_hash("root")),
        DependencyRow(PROFILE_DATASET_URN, "schemaMetadata", "fields", content_hash("profile")),
        DependencyRow(
            PROFILE_DATASET_URN,
            "structuredProperties",
            ALLOWED_REGIONS_PROPERTY_URN,
            content_hash(("EU",)),
        ),
    )
    semantic_hash = content_hash({"dependencies": [item.to_dict() for item in dependencies]})
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
        environment_fingerprint=semantic_hash,
        semantic_hash=semantic_hash,
        read_attempts=1,
    )


@pytest.mark.asyncio
async def test_accepted_source_trials_and_decision_use_existing_immutable_records() -> None:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        await WorkflowService(database, DemoFixtureBundle.load()).reset_demo("org_consultco")
        async with database.transaction("org_consultco") as session:
            session.add(
                AgentMission(
                    id="mission_proof_k2",
                    organization_id="org_consultco",
                    actor_id="usr_policy_owner",
                    mode="SIRA",
                    goal="Qualify proof adapters against governed DataHub context",
                    state="EXPERIMENTING",
                    version=1,
                    budget={},
                    plan={},
                    world_model={},
                    current_checkpoint_id=None,
                    stop_reason=None,
                    last_error_code=None,
                )
            )
        observation = _observation()
        manifest = compile_manifest(observation)
        runtime_results = {
            adapter_id: {
                "status": "completed",
                "artifactDigest": content_hash({"adapter": adapter_id}),
                "resultHash": content_hash({"result": adapter_id}),
                "declaredExecutionRegion": "EU",
                "gateResults": {
                    "FUNCTIONAL_CANARY_PASSED": True,
                    "EXECUTION_REGION_ALLOWED": True,
                    "REQUIRED_SCHEMA_SUPPORTED": True,
                    "RAW_PII_EGRESS_FORBIDDEN": adapter_id == "adapter-b",
                },
            }
            for adapter_id in ("adapter-a", "adapter-b")
        }
        decision = evaluate_campaign(manifest, runtime_results)
        bindings = ProofPersistenceBindings(
            organization_id="org_consultco",
            purchase_request_id="req_demo",
            purchase_brief_id="pb_consultco_v1",
            purchase_brief_version=1,
            requirement_brief_id="rb_consultco_v1",
            requirement_brief_version=1,
            company_profile_version=1,
            stack_snapshot_id="stack_consultco_v1",
            stack_snapshot_version=1,
            mission_id="mission_proof_k2",
            accepted_by_actor_id="usr_policy_owner",
            decision_id="decision_proof_k2",
            decision_version=1,
        )
        async with database.transaction("org_consultco") as session:
            first = await persist_proof_evidence(
                session,
                bindings=bindings,
                observation=observation,
                manifest=manifest,
                decision=decision,
                runtime_results=runtime_results,
            )
        async with database.transaction("org_consultco") as session:
            second = await persist_proof_evidence(
                session,
                bindings=bindings,
                observation=observation,
                manifest=manifest,
                decision=decision,
                runtime_results=runtime_results,
            )
            assert first == second
            proof_sources = list(
                (
                    await session.execute(
                        select(DecisionSourceSnapshot).where(
                            DecisionSourceSnapshot.id == first.decision_source_snapshot_id
                        )
                    )
                ).scalars()
            )
            proof_experiments = list(
                (
                    await session.execute(
                        select(AgentExperiment).where(
                            AgentExperiment.mission_id == "mission_proof_k2"
                        )
                    )
                ).scalars()
            )
            proof_evaluations = list(
                (
                    await session.execute(
                        select(EvaluationRun).where(EvaluationRun.id == first.evaluation_run_id)
                    )
                ).scalars()
            )
            assert len(proof_sources) == 1
            assert len(proof_experiments) == 2
            assert len(proof_evaluations) == 1
    finally:
        await database.close()
