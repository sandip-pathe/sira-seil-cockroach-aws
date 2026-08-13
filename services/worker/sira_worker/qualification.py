"""Qualification worker orchestration across CockroachDB DVI and Bedrock."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from hashlib import sha256
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sira_agents.bedrock_runtime import (
    BedrockClient,
    BedrockConverseRuntime,
    BedrockGuardrail,
    BedrockTool,
    TitanEmbeddingClient,
)
from sira_agents.runtime import AgentRole, AgentRunContext, AgentRunRequest, AuthorityMode
from sqlalchemy import select

from persistence.database import Database
from persistence.models import OutboxEvent
from persistence.qualification_catalog import VectorCandidate, search_published_candidates
from persistence.qualification_models import (
    AttemptDependency,
    CatalogProjectionVersion,
    EvidenceVersion,
    ProductBundleMember,
    QualificationAttempt,
    QualificationMission,
    QualificationMissionBundle,
)
from persistence.qualification_repository import (
    AttemptLease,
    FinalizationResult,
    QualificationRepository,
)
from persistence.repositories import PersistenceConflict, RecordNotFound


class QualificationCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion: str = Field(min_length=1, max_length=160)
    result: Literal["PASS", "PARTIAL", "FAIL", "UNKNOWN"]
    rationale: str | None = Field(default=None, max_length=1000)
    cited_dependency_ids: list[str] = Field(default_factory=list, max_length=20)


class QualificationAgentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommended_product_id: str = Field(min_length=1, max_length=64)
    summary: str = Field(min_length=1, max_length=2000)
    cited_dependency_ids: list[str] = Field(min_length=1, max_length=30)
    criteria: list[QualificationCriterion] = Field(default_factory=list, max_length=30)
    confidence: Decimal = Field(ge=0, le=1, decimal_places=4)

    @field_validator("cited_dependency_ids")
    @classmethod
    def citations_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("cited dependency IDs must be unique")
        return value


@dataclass(frozen=True, slots=True)
class MissionInput:
    mission_id: str
    organization_id: str
    trace_id: str
    buyer_context: Mapping[str, Any]
    brief: Mapping[str, Any]
    policy: Mapping[str, Any]

    def retrieval_text(self) -> str:
        seller_visible = self.brief.get("seller_visible_requirements", {})
        return "\n".join(
            (
                str(self.brief.get("category", "")),
                str(self.brief.get("goal", "")),
                str(seller_visible),
            )
        ).strip()


@dataclass(frozen=True, slots=True)
class QualificationRunResult:
    mission_id: str
    state: str
    attempts: tuple[str, ...]
    decision_id: str | None


@dataclass(slots=True)
class QualificationWorker:
    """Execute model work outside transactions and finalize through a generation fence."""

    worker_database: Database = field(repr=False)
    catalog_database: Database = field(repr=False)
    embedding_client: TitanEmbeddingClient = field(repr=False)
    bedrock_client: BedrockClient = field(repr=False)
    model_id: str
    lease_owner: str
    guardrail: BedrockGuardrail | None = None
    candidate_limit: int = 10
    selected_candidates: int = 2

    async def run_mission(self, *, organization_id: str, mission_id: str) -> QualificationRunResult:
        attempted: list[str] = []
        for _replacement in range(4):
            mission_input = await self._load_mission(organization_id, mission_id)
            embedding = await self.embedding_client.embed(mission_input.retrieval_text())
            category = str(mission_input.brief.get("category", ""))
            async with self.catalog_database.transaction(organization_id) as session:
                candidates = await search_published_candidates(
                    session,
                    category=category,
                    visibility="BUYER_SAFE",
                    query_vector=embedding.vector,
                    limit=self.candidate_limit,
                )
            selected = _unique_products(candidates, self.selected_candidates)
            if len(selected) < self.selected_candidates:
                raise PersistenceConflict("qualification mission has too few current candidates")
            attempt_id = await self._prepare_attempt(mission_input, selected)
            attempted.append(attempt_id)
            lease = await self._claim_and_snapshot(organization_id, attempt_id)
            decision = await self._evaluate(mission_input, lease, selected)
            result = await self._finalize(organization_id, lease, decision)
            if result.state == "COMPLETED":
                return QualificationRunResult(
                    mission_id=mission_id,
                    state=result.state,
                    attempts=tuple(attempted),
                    decision_id=result.decision_id,
                )
            if result.state != "STALE" or result.replacement_attempt_id is None:
                raise PersistenceConflict("qualification attempt ended without a decision")
        raise PersistenceConflict("qualification replacement chain exhausted")

    async def _load_mission(self, organization_id: str, mission_id: str) -> MissionInput:
        async with self.worker_database.transaction(organization_id) as session:
            mission = await session.scalar(
                select(QualificationMission).where(
                    QualificationMission.organization_id == organization_id,
                    QualificationMission.id == mission_id,
                )
            )
            if mission is None:
                raise RecordNotFound("qualification mission was not found")
            if mission.state in {"FAILED", "CANCELLED", "COMPLETED"}:
                raise PersistenceConflict("qualification mission is terminal")
            return MissionInput(
                mission_id=mission.id,
                organization_id=str(mission.organization_id),
                trace_id=mission.trace_id,
                buyer_context=dict(mission.buyer_context_payload),
                brief=dict(mission.requirement_brief_payload),
                policy=dict(mission.procurement_policy_payload),
            )

    async def _prepare_attempt(
        self, mission_input: MissionInput, candidates: Sequence[VectorCandidate]
    ) -> str:
        async with self.worker_database.transaction(mission_input.organization_id) as session:
            mission = await session.scalar(
                select(QualificationMission).where(
                    QualificationMission.organization_id == mission_input.organization_id,
                    QualificationMission.id == mission_input.mission_id,
                )
            )
            if mission is None:
                raise RecordNotFound("qualification mission was not found")
            attempt = await session.scalar(
                select(QualificationAttempt)
                .where(
                    QualificationAttempt.organization_id == mission_input.organization_id,
                    QualificationAttempt.mission_id == mission_input.mission_id,
                    QualificationAttempt.state == "QUEUED",
                )
                .order_by(QualificationAttempt.replacement_depth, QualificationAttempt.created_at)
            )
            if attempt is None:
                existing = await session.scalar(
                    select(QualificationAttempt.id).where(
                        QualificationAttempt.organization_id == mission_input.organization_id,
                        QualificationAttempt.mission_id == mission_input.mission_id,
                    )
                )
                if existing is not None:
                    raise PersistenceConflict("qualification mission has no claimable attempt")
                attempt_id = _stable_id("qattempt", mission_input.mission_id)
                attempt = QualificationAttempt(
                    id=attempt_id,
                    mission_id=mission_input.mission_id,
                    root_attempt_id=attempt_id,
                    predecessor_attempt_id=None,
                    replacement_depth=0,
                    state="QUEUED",
                    generation=0,
                    organization_id=mission_input.organization_id,
                )
                session.add(attempt)
                await session.flush()
            existing_bundles = (
                await session.scalars(
                    select(QualificationMissionBundle).where(
                        QualificationMissionBundle.organization_id
                        == mission_input.organization_id,
                        QualificationMissionBundle.attempt_id == attempt.id,
                    )
                )
            ).all()
            if not existing_bundles:
                for ordinal, candidate in enumerate(candidates):
                    session.add(
                        QualificationMissionBundle(
                            id=_stable_id("qbundle", f"{attempt.id}:{ordinal}"),
                            mission_id=mission_input.mission_id,
                            attempt_id=attempt.id,
                            product_id=candidate.product_id,
                            seller_organization_id=candidate.organization_id,
                            bundle_id=candidate.bundle_id,
                            bundle_digest=candidate.bundle_digest,
                            organization_id=mission_input.organization_id,
                        )
                    )
            mission.state = "RUNNING"
            outbox_id = _stable_id("outbox", f"attempt-ready:{attempt.id}")
            if await session.get(OutboxEvent, outbox_id) is None:
                session.add(
                    OutboxEvent(
                        id=outbox_id,
                        aggregate_type="QUALIFICATION_ATTEMPT",
                        aggregate_id=attempt.id,
                        event_type="QUALIFICATION_ATTEMPT_READY",
                        event_key=f"qualification-attempt-ready:{attempt.id}",
                        payload={"mission_id": mission.id, "attempt_id": attempt.id},
                        organization_id=mission_input.organization_id,
                    )
                )
            return attempt.id

    async def _claim_and_snapshot(
        self, organization_id: str, attempt_id: str
    ) -> AttemptLease:
        async with self.worker_database.transaction(organization_id) as session:
            repository = QualificationRepository(session, organization_id)
            lease = await repository.claim_attempt(
                attempt_id=attempt_id,
                lease_owner=self.lease_owner,
                lease_seconds=300,
            )
            await repository.snapshot_attempt(lease=lease)
            return lease

    async def _evaluate(
        self,
        mission_input: MissionInput,
        lease: AttemptLease,
        candidates: Sequence[VectorCandidate],
    ) -> QualificationAgentDecision:
        allowed_products = frozenset(candidate.product_id for candidate in candidates)
        retrieved_products: set[str] = set()

        async def retrieve(
            tool_input: Mapping[str, Any], _context: AgentRunContext | None
        ) -> Mapping[str, Any]:
            product_id = str(tool_input.get("product_id", ""))
            if product_id not in allowed_products:
                raise PersistenceConflict("model requested evidence outside candidate set")
            retrieved_products.add(product_id)
            return await self._evidence_for_product(
                mission_input.organization_id,
                lease.attempt_id,
                product_id,
            )

        runtime = BedrockConverseRuntime(
            client=self.bedrock_client,
            model_id=self.model_id,
            guardrail=self.guardrail,
            tools={
                "retrieve_product_evidence": BedrockTool(
                    name="retrieve_product_evidence",
                    description=(
                        "Retrieve buyer-safe facts pinned to this qualification attempt."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {"product_id": {"type": "string"}},
                        "required": ["product_id"],
                        "additionalProperties": False,
                    },
                    handler=retrieve,
                )
            },
        )
        result = await runtime.run(
            AgentRunRequest(
                role=AgentRole.SIRA,
                instructions=(
                    "Compare every candidate against the requirement and policy. "
                    "Call retrieve_product_evidence once for every candidate. "
                    "Cite only dependency IDs returned by the tool."
                ),
                prompt="Produce the best current qualification decision.",
                model_context={
                    "requirement_brief": mission_input.brief,
                    "procurement_policy": mission_input.policy,
                    "candidate_product_ids": sorted(allowed_products),
                },
                run_context=AgentRunContext(
                    organization_id=mission_input.organization_id,
                    actor_id=self.lease_owner,
                    actor_roles=frozenset({"qualification_worker"}),
                    request_id=mission_input.trace_id,
                ),
                allowed_tools=("retrieve_product_evidence",),
                output_type=QualificationAgentDecision,
                authority_mode=AuthorityMode.ADVISORY,
            )
        )
        if not isinstance(result.output, QualificationAgentDecision):
            raise PersistenceConflict("Bedrock returned an invalid qualification decision")
        if (
            retrieved_products != allowed_products
            or len(result.tool_calls) != len(allowed_products)
            or set(result.tool_calls) != {"retrieve_product_evidence"}
        ):
            raise PersistenceConflict("Bedrock did not inspect pinned product evidence")
        return result.output

    async def _evidence_for_product(
        self, organization_id: str, attempt_id: str, product_id: str
    ) -> Mapping[str, Any]:
        async with self.worker_database.transaction(organization_id) as session:
            bundle = await session.scalar(
                select(QualificationMissionBundle).where(
                    QualificationMissionBundle.organization_id == organization_id,
                    QualificationMissionBundle.attempt_id == attempt_id,
                    QualificationMissionBundle.product_id == product_id,
                )
            )
            if bundle is None:
                raise RecordNotFound("candidate bundle was not pinned")
            dependencies = (
                await session.scalars(
                    select(AttemptDependency).where(
                        AttemptDependency.organization_id == organization_id,
                        AttemptDependency.attempt_id == attempt_id,
                        AttemptDependency.dependency_organization_id
                        == bundle.seller_organization_id,
                    )
                )
            ).all()
            dependency_ids = {dependency.dependency_id for dependency in dependencies}
            members = (
                await session.scalars(
                    select(ProductBundleMember).where(
                        ProductBundleMember.organization_id == bundle.seller_organization_id,
                        ProductBundleMember.bundle_id == bundle.bundle_id,
                    )
                )
            ).all()
            catalog_ids = [
                member.member_id
                for member in members
                if member.member_kind == "CATALOG_PROJECTION"
                and member.member_id in dependency_ids
            ]
            evidence_ids = [
                member.member_id
                for member in members
                if member.member_kind == "EVIDENCE" and member.member_id in dependency_ids
            ]
            catalogs = (
                await session.scalars(
                    select(CatalogProjectionVersion).where(
                        CatalogProjectionVersion.organization_id
                        == bundle.seller_organization_id,
                        CatalogProjectionVersion.id.in_(catalog_ids),
                    )
                )
            ).all()
            evidence = (
                await session.scalars(
                    select(EvidenceVersion).where(
                        EvidenceVersion.organization_id == bundle.seller_organization_id,
                        EvidenceVersion.id.in_(evidence_ids),
                        EvidenceVersion.eligible.is_(True),
                    )
                )
            ).all()
            return {
                "product_id": product_id,
                "bundle_id": bundle.bundle_id,
                "bundle_digest": bundle.bundle_digest,
                "catalog": [
                    {
                        "dependency_id": item.id,
                        "content_hash": item.content_hash,
                        "facts": item.buyer_safe_payload,
                    }
                    for item in catalogs
                ],
                "evidence": [
                    {
                        "dependency_id": item.id,
                        "content_hash": item.content_hash,
                        "facts": item.facts,
                    }
                    for item in evidence
                ],
            }

    async def _finalize(
        self,
        organization_id: str,
        lease: AttemptLease,
        decision: QualificationAgentDecision,
    ) -> FinalizationResult:
        async with self.worker_database.transaction(organization_id) as session:
            repository = QualificationRepository(session, organization_id)
            result = await repository.finalize_attempt(
                lease=lease,
                recommended_product_id=decision.recommended_product_id,
                payload=decision.model_dump(mode="json"),
                cited_dependency_ids=frozenset(decision.cited_dependency_ids),
            )
            if result.state == "COMPLETED":
                attempt = await session.get(QualificationAttempt, lease.attempt_id)
                if attempt is None:
                    raise RecordNotFound("qualification attempt was not found")
                mission = await session.get(QualificationMission, attempt.mission_id)
                if mission is None:
                    raise RecordNotFound("qualification mission was not found")
                mission.state = "AWAITING_APPROVAL"
            return result


def _unique_products(
    candidates: Sequence[VectorCandidate], limit: int
) -> tuple[VectorCandidate, ...]:
    selected: list[VectorCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate.product_id in seen:
            continue
        selected.append(candidate)
        seen.add(candidate.product_id)
        if len(selected) == limit:
            break
    return tuple(selected)


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}_{sha256(value.encode('utf-8')).hexdigest()[:32]}"
