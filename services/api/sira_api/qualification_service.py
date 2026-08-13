"""Application service for qualified buyer/seller marketplace decisions."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any, Literal

from sira_agents.bedrock_runtime import TitanEmbeddingClient
from sira_worker.qualification import retrieve_qualification_candidates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domain import content_hash
from persistence.database import Database
from persistence.models import Organization, OutboxEvent
from persistence.qualification_models import (
    ActiveProductBundle,
    AttemptCheckpoint,
    AttemptDependency,
    BuyerEngagementProjection,
    CatalogProjectionVersion,
    CompanyContextItem,
    CompanyContextVersion,
    DecisionDependency,
    MarketplaceConsent,
    MarketplaceEngagement,
    ProductBundleMember,
    QualificationAttempt,
    QualificationDecision,
    QualificationEffect,
    QualificationMission,
    QualificationMissionBundle,
    QualifiedIntroduction,
    SellerEngagementProjection,
    SellerResponse,
    WorkspaceSettings,
    WorkspaceSettingsVersion,
)
from persistence.qualification_repository import QualificationRepository
from persistence.repositories import PersistenceConflict, WorkflowRepository, new_id

from .errors import ApiProblem


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _etag_value(value: str) -> str:
    return f'"{value}"'


def _verify_match(provided: str, expected: str) -> None:
    value = provided.strip()
    if value.startswith("W/") or value.strip('"') != expected:
        raise ApiProblem(
            code="PRECONDITION_FAILED",
            message="The resource changed; reload before applying this action.",
            status_code=412,
            next_action="reload_resource",
            details={"current_etag": _etag_value(expected)},
        )


def _default_workspace_settings() -> dict[str, Any]:
    return {
        "notification_channels": {"in_app": True, "email": False},
        "quiet_hours": {
            "enabled": False,
            "start": "22:00",
            "end": "07:00",
            "timezone": "Asia/Kolkata",
        },
        "disclosure_defaults": {
            "allow_anonymized_requirement_preview": True,
            "share_organization_name_after_consent": False,
            "allow_outcome_follow_up": True,
        },
    }


class QualificationService:
    def __init__(
        self,
        database: Database,
        *,
        catalog_database: Database | None = None,
        embedding_client: TitanEmbeddingClient | None = None,
        allow_development_tenant_bootstrap: bool = False,
    ) -> None:
        self.database = database
        self.catalog_database = catalog_database
        self.embedding_client = embedding_client
        self.allow_development_tenant_bootstrap = allow_development_tenant_bootstrap

    async def workspace_settings(
        self, organization_id: str, *, party: Literal["BUYER", "SELLER"]
    ) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            settings = await session.scalar(
                select(WorkspaceSettings).where(
                    WorkspaceSettings.organization_id == organization_id,
                    WorkspaceSettings.party == party,
                )
            )
            if settings is None:
                payload = _default_workspace_settings()
                digest = content_hash(payload)
                return self._settings_payload(
                    party=party,
                    settings_id=None,
                    version=0,
                    digest=digest,
                    payload=payload,
                    updated_at=None,
                )
            version = await session.scalar(
                select(WorkspaceSettingsVersion).where(
                    WorkspaceSettingsVersion.organization_id == organization_id,
                    WorkspaceSettingsVersion.settings_id == settings.id,
                    WorkspaceSettingsVersion.id == settings.current_version_id,
                    WorkspaceSettingsVersion.content_hash == settings.current_hash,
                )
            )
            if version is None:
                raise PersistenceConflict("workspace settings head has no immutable version")
            return self._settings_payload(
                party=party,
                settings_id=settings.id,
                version=settings.current_version,
                digest=settings.current_hash,
                payload=dict(version.payload),
                updated_at=settings.updated_at,
            )

    async def update_workspace_settings(
        self,
        *,
        organization_id: str,
        actor_id: str,
        party: Literal["BUYER", "SELLER"],
        if_match: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        payload = {
            "notification_channels": body["notification_channels"],
            "quiet_hours": body["quiet_hours"],
            "disclosure_defaults": body["disclosure_defaults"],
        }
        digest = content_hash(payload)
        request_hash = content_hash({"party": party, "payload": payload})

        async def write(session: AsyncSession) -> tuple[int, dict[str, Any]]:
            settings = await session.scalar(
                select(WorkspaceSettings).where(
                    WorkspaceSettings.organization_id == organization_id,
                    WorkspaceSettings.party == party,
                )
            )
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation=f"qualification.workspace_settings.update:{party}",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                replay = dict(claim.record.response_payload or {})
                replay["replayed"] = True
                return int(claim.record.response_status or 200), replay
            expected_hash = (
                settings.current_hash
                if settings is not None
                else content_hash(_default_workspace_settings())
            )
            _verify_match(if_match, expected_hash)
            if settings is not None and digest == settings.current_hash:
                raise ApiProblem(
                    code="WORKSPACE_SETTINGS_UNCHANGED",
                    message="The proposed settings are identical to the current version.",
                    status_code=409,
                    next_action="change_settings_or_cancel",
                )
            settings_id = settings.id if settings is not None else new_id("wsettings")
            version_number = settings.current_version + 1 if settings is not None else 1
            version_id = new_id("wsetver")
            if settings is None:
                settings = WorkspaceSettings(
                    id=settings_id,
                    party=party,
                    current_version_id=version_id,
                    current_version=version_number,
                    current_hash=digest,
                    organization_id=organization_id,
                )
                session.add(settings)
            else:
                settings.current_version_id = version_id
                settings.current_version = version_number
                settings.current_hash = digest
            session.add(
                WorkspaceSettingsVersion(
                    id=version_id,
                    settings_id=settings_id,
                    version=version_number,
                    content_hash=digest,
                    payload=payload,
                    changed_by_actor_id=actor_id,
                    change_reason=body["change_reason"],
                    organization_id=organization_id,
                )
            )
            await repository.add_outbox(
                aggregate_type="WORKSPACE_SETTINGS",
                aggregate_id=settings_id,
                event_type="WORKSPACE_SETTINGS_VERSION_PUBLISHED",
                event_key=f"workspace-settings-version:{version_id}",
                payload={"party": party, "version_id": version_id, "content_hash": digest},
            )
            response = {
                "resource_type": "workspace_settings",
                "resource_id": settings_id,
                "state": "ACTIVE",
                "input_digest": digest,
                "replayed": False,
            }
            await repository.complete_idempotency(
                claim.record,
                response_status=200,
                response_payload=response,
                response_reference=settings_id,
            )
            return 200, response

        return await self.database.run_retryable(organization_id, write)

    async def search_marketplace(
        self,
        organization_id: str,
        *,
        category: str,
        query: str,
        limit: int,
    ) -> dict[str, Any]:
        if self.catalog_database is None or self.embedding_client is None:
            raise ApiProblem(
                code="MARKETPLACE_SEARCH_UNAVAILABLE",
                message="Semantic marketplace search is not configured.",
                status_code=503,
                next_action="configure_catalog_and_bedrock",
            )
        retrieval = await retrieve_qualification_candidates(
            catalog_database=self.catalog_database,
            embedding_client=self.embedding_client,
            organization_id=organization_id,
            category=category,
            query=query,
            visibility="PUBLIC",
            limit=limit,
        )
        results: list[dict[str, Any]] = []
        async with self.catalog_database.transaction(organization_id) as session:
            for candidate in retrieval.candidates:
                catalog_member = await session.scalar(
                    select(ProductBundleMember).where(
                        ProductBundleMember.organization_id == candidate.organization_id,
                        ProductBundleMember.bundle_id == candidate.bundle_id,
                        ProductBundleMember.member_kind == "CATALOG_PROJECTION",
                    )
                )
                projection = (
                    await session.scalar(
                        select(CatalogProjectionVersion).where(
                            CatalogProjectionVersion.organization_id == candidate.organization_id,
                            CatalogProjectionVersion.id == catalog_member.member_id,
                        )
                    )
                    if catalog_member is not None
                    else None
                )
                payload = dict(projection.buyer_safe_payload) if projection else {}
                results.append(
                    {
                        "product_id": candidate.product_id,
                        "bundle_id": candidate.bundle_id,
                        "bundle_digest": candidate.bundle_digest,
                        "name": payload.get("name") or candidate.product_id,
                        "summary": payload.get("summary") or payload.get("public_summary"),
                        "seller": payload.get("seller") or payload.get("seller_name"),
                        "category": category,
                        "cosine_distance": format(candidate.cosine_distance, ".8f"),
                        "evidence_status": "PUBLISHED",
                        "href": f"/marketplace/products/{candidate.product_id}",
                    }
                )
        return {
            "category": retrieval.category,
            "query_model_id": retrieval.query_model_id,
            "results": results,
        }

    async def marketplace_product(self, organization_id: str, product_id: str) -> dict[str, Any]:
        if self.catalog_database is None:
            raise ApiProblem(
                code="MARKETPLACE_SEARCH_UNAVAILABLE",
                message="Published marketplace access is not configured.",
                status_code=503,
                next_action="configure_catalog_database",
            )
        async with self.catalog_database.transaction(organization_id) as session:
            active = await session.scalar(
                select(ActiveProductBundle).where(ActiveProductBundle.product_id == product_id)
            )
            if active is None:
                raise self._not_found("MARKETPLACE_PRODUCT", "Published product was not found.")
            catalog_member = await session.scalar(
                select(ProductBundleMember).where(
                    ProductBundleMember.organization_id == active.organization_id,
                    ProductBundleMember.bundle_id == active.bundle_id,
                    ProductBundleMember.member_kind == "CATALOG_PROJECTION",
                )
            )
            projection = (
                await session.scalar(
                    select(CatalogProjectionVersion).where(
                        CatalogProjectionVersion.organization_id == active.organization_id,
                        CatalogProjectionVersion.id == catalog_member.member_id,
                    )
                )
                if catalog_member is not None
                else None
            )
            if projection is None:
                raise self._not_found(
                    "MARKETPLACE_PRODUCT", "Published product projection was not found."
                )
            return {
                "product": {
                    "product_id": product_id,
                    "bundle_id": active.bundle_id,
                    "bundle_digest": active.bundle_digest,
                    "generation": active.generation,
                    "evidence_status": "PUBLISHED",
                    "payload": projection.buyer_safe_payload,
                    "projection_hash": projection.content_hash,
                }
            }

    async def inbox(
        self,
        organization_id: str,
        *,
        party: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        if party == "SELLER":
            async with self.database.transaction(organization_id) as session:
                projections = (
                    await session.scalars(
                        select(SellerEngagementProjection)
                        .where(SellerEngagementProjection.organization_id == organization_id)
                        .order_by(SellerEngagementProjection.created_at.desc())
                        .limit(limit)
                    )
                ).all()
                engagements = {
                    item.id: item
                    for item in (
                        await session.scalars(
                            select(MarketplaceEngagement).where(
                                MarketplaceEngagement.id.in_(
                                    [projection.engagement_id for projection in projections]
                                )
                            )
                        )
                    ).all()
                }
                return {
                    "workspace": "SELLER",
                    "items": [
                        self._inbox_item(engagements[projection.engagement_id], projection.payload)
                        for projection in projections
                        if projection.engagement_id in engagements
                    ],
                    "next_cursor": None,
                }
        async with self.database.transaction(organization_id) as session:
            missions = (
                await session.scalars(
                    select(QualificationMission)
                    .where(QualificationMission.organization_id == organization_id)
                    .order_by(QualificationMission.updated_at.desc())
                    .limit(limit)
                )
            ).all()
            decisions = (
                await session.scalars(
                    select(QualificationDecision).where(
                        QualificationDecision.organization_id == organization_id,
                        QualificationDecision.mission_id.in_([mission.id for mission in missions]),
                        QualificationDecision.current.is_(True),
                    )
                )
            ).all()
            by_mission = {decision.mission_id: decision for decision in decisions}
            return {
                "workspace": "BUYER",
                "items": [
                    self._buyer_inbox_item(mission, by_mission.get(mission.id))
                    for mission in missions
                ],
                "next_cursor": None,
            }

    async def workspace_analytics(
        self,
        organization_id: str,
        *,
        party: Literal["BUYER", "SELLER"],
        days: int,
    ) -> dict[str, Any]:
        """Derive a bounded, tenant-private operational view from canonical records/events."""

        cutoff = datetime.now().astimezone() - timedelta(days=days)
        async with self.database.transaction(organization_id) as session:
            events = (
                await session.scalars(
                    select(OutboxEvent)
                    .where(
                        OutboxEvent.organization_id == organization_id,
                        OutboxEvent.occurred_at >= cutoff,
                    )
                    .order_by(OutboxEvent.occurred_at)
                )
            ).all()
            event_counts: dict[str, int] = {}
            daily: dict[str, int] = {}
            for event in events:
                event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1
                day = event.occurred_at.date().isoformat()
                daily[day] = daily.get(day, 0) + 1

            if party == "SELLER":
                opportunity_count = int(
                    await session.scalar(
                        select(func.count()).select_from(SellerEngagementProjection)
                    )
                    or 0
                )
                response_count = int(
                    await session.scalar(select(func.count()).select_from(SellerResponse)) or 0
                )
                active_count = int(
                    await session.scalar(
                        select(func.count())
                        .select_from(MarketplaceEngagement)
                        .where(
                            MarketplaceEngagement.seller_organization_id == organization_id,
                            MarketplaceEngagement.state.in_(
                                ("OPEN", "RESPONDED", "CONSENT_PENDING")
                            ),
                        )
                    )
                    or 0
                )
                funnel = {
                    "opportunities_received": opportunity_count,
                    "responses_recorded": response_count,
                    "consents_granted": event_counts.get("SELLER_CONSENT_GRANTED", 0),
                }
                current_state = {
                    "active_opportunities": active_count,
                    "published_setting_versions": event_counts.get(
                        "WORKSPACE_SETTINGS_VERSION_PUBLISHED", 0
                    ),
                }
            else:
                mission_count = int(
                    await session.scalar(select(func.count()).select_from(QualificationMission))
                    or 0
                )
                decision_count = int(
                    await session.scalar(select(func.count()).select_from(QualificationDecision))
                    or 0
                )
                introduction_count = int(
                    await session.scalar(select(func.count()).select_from(QualifiedIntroduction))
                    or 0
                )
                active_count = int(
                    await session.scalar(
                        select(func.count())
                        .select_from(QualificationMission)
                        .where(
                            QualificationMission.state.not_in(
                                ("COMPLETED", "REJECTED", "INVALIDATED")
                            )
                        )
                    )
                    or 0
                )
                funnel = {
                    "missions_created": mission_count,
                    "decisions_created": decision_count,
                    "decisions_approved": event_counts.get("QUALIFICATION_DECISION_APPROVED", 0),
                    "introductions_created": introduction_count,
                }
                current_state = {
                    "active_missions": active_count,
                    "stale_attempts_detected": event_counts.get("QUALIFICATION_ATTEMPT_STALE", 0),
                    "published_setting_versions": event_counts.get(
                        "WORKSPACE_SETTINGS_VERSION_PUBLISHED", 0
                    ),
                }
            return {
                "workspace": party,
                "window_days": days,
                "generated_at": _timestamp(datetime.now().astimezone()),
                "measurement_label": "OBSERVATIONAL_NOT_CAUSAL",
                "funnel": funnel,
                "current_state": current_state,
                "daily_events": [
                    {"date": day, "count": count} for day, count in sorted(daily.items())
                ],
            }

    async def list_company_context(
        self, organization_id: str, *, include_retired: bool = False
    ) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            query = select(CompanyContextItem).where(
                CompanyContextItem.organization_id == organization_id
            )
            if not include_retired:
                query = query.where(CompanyContextItem.state == "ACTIVE")
            items = (
                await session.scalars(
                    query.order_by(CompanyContextItem.kind, CompanyContextItem.label)
                )
            ).all()
            return {"items": [await self._context_payload(session, item) for item in items]}

    async def company_context_view(self, organization_id: str, item_id: str) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            item = await self._company_context_item(session, organization_id, item_id)
            versions = (
                await session.scalars(
                    select(CompanyContextVersion)
                    .where(
                        CompanyContextVersion.organization_id == organization_id,
                        CompanyContextVersion.item_id == item.id,
                    )
                    .order_by(CompanyContextVersion.version.desc())
                )
            ).all()
            return {
                "item": await self._context_payload(session, item),
                "versions": [self._context_version_payload(version) for version in versions],
            }

    async def create_company_context(
        self,
        *,
        organization_id: str,
        actor_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        request_hash = content_hash(body)

        async def write(session: AsyncSession) -> tuple[int, dict[str, Any]]:
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation="qualification.company_context.create",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                payload = dict(claim.record.response_payload or {})
                payload["replayed"] = True
                return int(claim.record.response_status or 201), payload
            item_id = new_id("ctxitem")
            version_id = new_id("ctxver")
            payload = dict(body["payload"])
            digest = content_hash(payload)
            item = CompanyContextItem(
                id=item_id,
                kind=body["kind"],
                label=body["label"],
                state="ACTIVE",
                current_version_id=version_id,
                current_version=1,
                current_hash=digest,
                organization_id=organization_id,
            )
            session.add(item)
            session.add(
                CompanyContextVersion(
                    id=version_id,
                    item_id=item_id,
                    version=1,
                    content_hash=digest,
                    payload=payload,
                    changed_by_actor_id=actor_id,
                    change_reason=body["change_reason"],
                    organization_id=organization_id,
                )
            )
            await repository.add_outbox(
                aggregate_type="COMPANY_CONTEXT_ITEM",
                aggregate_id=item_id,
                event_type="COMPANY_CONTEXT_VERSION_PUBLISHED",
                event_key=f"company-context-version:{version_id}",
                payload={"item_id": item_id, "version_id": version_id, "content_hash": digest},
            )
            response = {
                "resource_type": "company_context_item",
                "resource_id": item_id,
                "state": "ACTIVE",
                "input_digest": digest,
                "replayed": False,
            }
            await repository.complete_idempotency(
                claim.record,
                response_status=201,
                response_payload=response,
                response_reference=item_id,
            )
            return 201, response

        return await self.database.run_retryable(organization_id, write)

    async def update_company_context(
        self,
        *,
        organization_id: str,
        actor_id: str,
        item_id: str,
        if_match: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        request_hash = content_hash(body)

        async def write(session: AsyncSession) -> tuple[int, dict[str, Any]]:
            item = await self._company_context_item(session, organization_id, item_id)
            _verify_match(if_match, item.current_hash)
            if item.state != "ACTIVE":
                raise ApiProblem(
                    code="COMPANY_CONTEXT_RETIRED",
                    message="Retired context cannot be revised.",
                    status_code=409,
                    next_action="create_replacement_context",
                )
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation=f"qualification.company_context.update:{item_id}",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                payload = dict(claim.record.response_payload or {})
                payload["replayed"] = True
                return int(claim.record.response_status or 200), payload
            payload = dict(body["payload"])
            digest = content_hash(payload)
            if digest == item.current_hash and body["label"] == item.label:
                raise ApiProblem(
                    code="COMPANY_CONTEXT_UNCHANGED",
                    message="The proposed revision is identical to the current version.",
                    status_code=409,
                    next_action="change_context_or_cancel",
                )
            version_id = new_id("ctxver")
            version = item.current_version + 1
            session.add(
                CompanyContextVersion(
                    id=version_id,
                    item_id=item.id,
                    version=version,
                    content_hash=digest,
                    payload=payload,
                    changed_by_actor_id=actor_id,
                    change_reason=body["change_reason"],
                    organization_id=organization_id,
                )
            )
            item.label = body["label"]
            item.current_version_id = version_id
            item.current_version = version
            item.current_hash = digest
            await repository.add_outbox(
                aggregate_type="COMPANY_CONTEXT_ITEM",
                aggregate_id=item.id,
                event_type="COMPANY_CONTEXT_VERSION_PUBLISHED",
                event_key=f"company-context-version:{version_id}",
                payload={"item_id": item.id, "version_id": version_id, "content_hash": digest},
            )
            response = {
                "resource_type": "company_context_item",
                "resource_id": item.id,
                "state": item.state,
                "input_digest": digest,
                "replayed": False,
            }
            await repository.complete_idempotency(
                claim.record,
                response_status=200,
                response_payload=response,
                response_reference=item.id,
            )
            return 200, response

        return await self.database.run_retryable(organization_id, write)

    async def retire_company_context(
        self,
        *,
        organization_id: str,
        actor_id: str,
        item_id: str,
        if_match: str,
        idempotency_key: str,
    ) -> tuple[int, dict[str, Any]]:
        async def write(session: AsyncSession) -> tuple[int, dict[str, Any]]:
            item = await self._company_context_item(session, organization_id, item_id)
            _verify_match(if_match, item.current_hash)
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation=f"qualification.company_context.retire:{item_id}",
                idempotency_key=idempotency_key,
                request_hash=content_hash({"item_id": item_id, "digest": item.current_hash}),
            )
            if claim.replay:
                payload = dict(claim.record.response_payload or {})
                payload["replayed"] = True
                return int(claim.record.response_status or 200), payload
            item.state = "RETIRED"
            await repository.add_outbox(
                aggregate_type="COMPANY_CONTEXT_ITEM",
                aggregate_id=item.id,
                event_type="COMPANY_CONTEXT_RETIRED",
                event_key=f"company-context-retired:{item.id}:{item.current_hash}",
                payload={"item_id": item.id, "content_hash": item.current_hash},
            )
            response = {
                "resource_type": "company_context_item",
                "resource_id": item.id,
                "state": "RETIRED",
                "input_digest": item.current_hash,
                "replayed": False,
            }
            await repository.complete_idempotency(
                claim.record,
                response_status=200,
                response_payload=response,
                response_reference=item.id,
            )
            return 200, response

        return await self.database.run_retryable(organization_id, write)

    async def create_mission(
        self,
        *,
        organization_id: str,
        actor_id: str,
        idempotency_key: str,
        trace_id: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        request_hash = content_hash(body)

        async def write(session: AsyncSession) -> tuple[int, dict[str, Any]]:
            organization = await session.get(Organization, organization_id)
            if organization is None:
                if (
                    not self.allow_development_tenant_bootstrap
                    or self.database.engine.dialect.name != "sqlite"
                ):
                    raise ApiProblem(
                        code="ORGANIZATION_NOT_PROVISIONED",
                        message=(
                            "The verified organization is not provisioned in canonical state."
                        ),
                        status_code=403,
                    )
                session.add(
                    Organization(
                        id=organization_id,
                        name="Development qualification workspace",
                        version=1,
                    )
                )
                await session.flush()
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation="qualification.missions.create",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                payload = dict(claim.record.response_payload or {})
                payload["replayed"] = True
                return int(claim.record.response_status or 201), payload
            mission_id = new_id("qmission")
            buyer_context = dict(body["buyer_context"])
            context_item_ids = list(body.get("company_context_item_ids", []))
            if context_item_ids:
                context_items = (
                    await session.scalars(
                        select(CompanyContextItem).where(
                            CompanyContextItem.organization_id == organization_id,
                            CompanyContextItem.id.in_(context_item_ids),
                            CompanyContextItem.state == "ACTIVE",
                        )
                    )
                ).all()
                if {item.id for item in context_items} != set(context_item_ids):
                    raise ApiProblem(
                        code="COMPANY_CONTEXT_SELECTION_INVALID",
                        message="One or more selected context items are missing or retired.",
                        status_code=409,
                        next_action="reload_company_context",
                    )
                versions = (
                    await session.scalars(
                        select(CompanyContextVersion).where(
                            CompanyContextVersion.organization_id == organization_id,
                            CompanyContextVersion.id.in_(
                                [item.current_version_id for item in context_items]
                            ),
                        )
                    )
                ).all()
                by_id = {version.id: version for version in versions}
                buyer_context["company_memory"] = [
                    {
                        "item_id": item.id,
                        "kind": item.kind,
                        "label": item.label,
                        "version_id": item.current_version_id,
                        "version": item.current_version,
                        "content_hash": item.current_hash,
                        "payload": by_id[item.current_version_id].payload,
                    }
                    for item in sorted(context_items, key=lambda value: value.id)
                ]
            brief = dict(body["requirement_brief"])
            policy = dict(body["procurement_policy"])
            mission = QualificationMission(
                id=mission_id,
                buyer_context_version_id=new_id("buyerctx"),
                buyer_context_hash=content_hash(buyer_context),
                buyer_context_payload=buyer_context,
                requirement_brief_version_id=new_id("reqbrief"),
                requirement_brief_hash=content_hash(brief),
                requirement_brief_payload=brief,
                procurement_policy_version=new_id("policy"),
                procurement_policy_hash=content_hash(policy),
                procurement_policy_payload=policy,
                trace_id=trace_id,
                state="READY",
                version=1,
                organization_id=organization_id,
            )
            session.add(mission)
            await repository.add_outbox(
                aggregate_type="QUALIFICATION_MISSION",
                aggregate_id=mission.id,
                event_type="QUALIFICATION_MISSION_READY",
                event_key=f"qualification-mission-ready:{mission.id}",
                payload={
                    "mission_id": mission.id,
                    "trace_id": trace_id,
                    "organization_id": organization_id,
                },
            )
            response = {
                "resource_type": "qualification_mission",
                "resource_id": mission.id,
                "state": mission.state,
                "input_digest": None,
                "replayed": False,
            }
            await repository.complete_idempotency(
                claim.record,
                response_status=201,
                response_payload=response,
                response_reference=mission.id,
            )
            return 201, response

        return await self.database.run_retryable(organization_id, write)

    async def mission_view(self, organization_id: str, mission_id: str) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            mission = await self._mission(session, organization_id, mission_id)
            attempts = (
                await session.scalars(
                    select(QualificationAttempt)
                    .where(
                        QualificationAttempt.organization_id == organization_id,
                        QualificationAttempt.mission_id == mission.id,
                    )
                    .order_by(QualificationAttempt.replacement_depth)
                )
            ).all()
            attempt_views = [await self._attempt_view(session, item) for item in attempts]
            decision = await session.scalar(
                select(QualificationDecision).where(
                    QualificationDecision.organization_id == organization_id,
                    QualificationDecision.mission_id == mission.id,
                    QualificationDecision.current.is_(True),
                )
            )
            engagement = await session.scalar(
                select(MarketplaceEngagement).where(
                    MarketplaceEngagement.buyer_organization_id == organization_id,
                    MarketplaceEngagement.mission_id == mission.id,
                )
            )
            integrity = await self._integrity(session, mission, attempts, decision, engagement)
            return {
                "mission": self._mission_payload(mission),
                "attempts": attempt_views,
                "decision": (
                    await self._decision_view(session, decision) if decision is not None else None
                ),
                "engagement": (
                    self._engagement_payload(engagement) if engagement is not None else None
                ),
                "integrity": integrity,
            }

    async def mission_events(
        self, organization_id: str, mission_id: str, *, after: str | None, limit: int
    ) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            await self._mission(session, organization_id, mission_id)
            attempt_ids = list(
                await session.scalars(
                    select(QualificationAttempt.id).where(
                        QualificationAttempt.organization_id == organization_id,
                        QualificationAttempt.mission_id == mission_id,
                    )
                )
            )
            decision_ids = list(
                await session.scalars(
                    select(QualificationDecision.id).where(
                        QualificationDecision.organization_id == organization_id,
                        QualificationDecision.mission_id == mission_id,
                    )
                )
            )
            engagement_ids = list(
                await session.scalars(
                    select(MarketplaceEngagement.id).where(
                        MarketplaceEngagement.buyer_organization_id == organization_id,
                        MarketplaceEngagement.mission_id == mission_id,
                    )
                )
            )
            aggregate_ids = [mission_id, *attempt_ids, *decision_ids, *engagement_ids]
            statement = (
                select(OutboxEvent)
                .where(
                    OutboxEvent.organization_id == organization_id,
                    OutboxEvent.aggregate_id.in_(aggregate_ids),
                )
                .order_by(OutboxEvent.occurred_at, OutboxEvent.id)
                .limit(limit + 1)
            )
            if after:
                cursor_event = await session.scalar(
                    select(OutboxEvent).where(
                        OutboxEvent.organization_id == organization_id,
                        OutboxEvent.id == after,
                    )
                )
                if cursor_event is None:
                    raise self._not_found("EVENT_CURSOR", "Event cursor was not found.")
                statement = statement.where(
                    (OutboxEvent.occurred_at > cursor_event.occurred_at)
                    | (
                        (OutboxEvent.occurred_at == cursor_event.occurred_at)
                        & (OutboxEvent.id > cursor_event.id)
                    )
                )
            rows = list((await session.scalars(statement)).all())
            has_more = len(rows) > limit
            rows = rows[:limit]
            return {
                "events": [
                    {
                        "id": item.id,
                        "type": item.event_type,
                        "aggregate_type": item.aggregate_type,
                        "aggregate_id": item.aggregate_id,
                        "payload": item.payload,
                        "occurred_at": _timestamp(item.occurred_at),
                        "published": item.published_at is not None,
                    }
                    for item in rows
                ],
                "next_cursor": rows[-1].id if rows and has_more else None,
            }

    async def decide_approval(
        self,
        *,
        organization_id: str,
        actor_id: str,
        decision_id: str,
        if_match: str,
        idempotency_key: str,
        action: Literal["APPROVE", "REJECT"],
        reason: str,
    ) -> tuple[int, dict[str, Any]]:
        request_hash = content_hash(
            {"decision_id": decision_id, "action": action, "reason": reason}
        )

        async def write(session: AsyncSession) -> tuple[int, dict[str, Any]]:
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation=f"qualification.decisions.{decision_id}.approval",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                payload = dict(claim.record.response_payload or {})
                payload["replayed"] = True
                return int(claim.record.response_status or 200), payload
            decision = await session.scalar(
                select(QualificationDecision)
                .where(
                    QualificationDecision.organization_id == organization_id,
                    QualificationDecision.id == decision_id,
                    QualificationDecision.current.is_(True),
                )
                .with_for_update()
            )
            if decision is None:
                raise self._not_found("QUALIFICATION_DECISION", "Decision was not found.")
            _verify_match(if_match, decision.decision_digest)
            if decision.approval_state != "PENDING":
                raise PersistenceConflict("qualification decision is no longer pending")
            mission = await self._mission(session, organization_id, decision.mission_id)
            if action == "REJECT":
                decision.approval_state = "REJECTED"
                mission.state = "COMPLETED"
                resource_id = decision.id
                state = decision.approval_state
                event_type = "QUALIFICATION_DECISION_REJECTED"
            else:
                product_dependencies = (
                    await session.scalars(
                        select(DecisionDependency).where(
                            DecisionDependency.organization_id == organization_id,
                            DecisionDependency.decision_id == decision.id,
                            DecisionDependency.dependency_kind == "PRODUCT_BUNDLE",
                        )
                    )
                ).all()
                if not product_dependencies:
                    raise PersistenceConflict("qualification decision has no product dependencies")
                for dependency in product_dependencies:
                    active = await session.scalar(
                        select(ActiveProductBundle.product_id).where(
                            ActiveProductBundle.organization_id
                            == dependency.dependency_organization_id,
                            ActiveProductBundle.product_id == dependency.dependency_id,
                            ActiveProductBundle.bundle_id == dependency.dependency_version,
                            ActiveProductBundle.bundle_digest == dependency.dependency_hash,
                        )
                    )
                    if active is None:
                        raise PersistenceConflict(
                            "qualification decision is stale; run a replacement attempt"
                        )
                decision.approval_state = "APPROVED"
                bundle = await session.scalar(
                    select(QualificationMissionBundle).where(
                        QualificationMissionBundle.organization_id == organization_id,
                        QualificationMissionBundle.attempt_id == decision.attempt_id,
                        QualificationMissionBundle.product_id == decision.recommended_product_id,
                    )
                )
                if bundle is None:
                    raise PersistenceConflict("recommended product bundle is missing")
                now = await self._database_now(session)
                visible = dict(
                    mission.requirement_brief_payload.get("seller_visible_requirements", {})
                )
                engagement = MarketplaceEngagement(
                    id=new_id("meng"),
                    mission_id=mission.id,
                    decision_id=decision.id,
                    buyer_organization_id=organization_id,
                    seller_organization_id=bundle.seller_organization_id,
                    product_id=decision.recommended_product_id,
                    input_digest=decision.input_digest,
                    buyer_safe_requirement=visible,
                    buyer_safe_hash=content_hash(visible),
                    state="OPEN",
                    expires_at=now + timedelta(days=7),
                )
                session.add(engagement)
                await session.flush()
                session.add(
                    BuyerEngagementProjection(
                        engagement_id=engagement.id,
                        projection_hash=content_hash(
                            {
                                "decision_id": decision.id,
                                "product_id": decision.recommended_product_id,
                                "input_digest": decision.input_digest,
                            }
                        ),
                        payload={
                            "decision_id": decision.id,
                            "product_id": decision.recommended_product_id,
                            "input_digest": decision.input_digest,
                        },
                        organization_id=organization_id,
                    )
                )
                resource_id = engagement.id
                state = engagement.state
                event_type = "QUALIFICATION_DECISION_APPROVED"
            await repository.add_outbox(
                aggregate_type="QUALIFICATION_DECISION",
                aggregate_id=decision.id,
                event_type=event_type,
                event_key=f"{event_type.lower()}:{decision.id}",
                payload={
                    "mission_id": mission.id,
                    "decision_id": decision.id,
                    "actor_id": actor_id,
                    "reason": reason,
                    "resource_id": resource_id,
                },
            )
            response = {
                "resource_type": "marketplace_engagement" if action == "APPROVE" else "decision",
                "resource_id": resource_id,
                "state": state,
                "input_digest": decision.input_digest,
                "replayed": False,
            }
            await repository.complete_idempotency(
                claim.record,
                response_status=200,
                response_payload=response,
                response_reference=resource_id,
            )
            return 200, response

        return await self.database.run_retryable(organization_id, write)

    async def engagement_view(self, organization_id: str, engagement_id: str) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            engagement = await self._engagement(session, organization_id, engagement_id)
            response = await session.scalar(
                select(SellerResponse)
                .where(SellerResponse.engagement_id == engagement.id)
                .order_by(SellerResponse.created_at.desc())
            )
            consents = (
                await session.scalars(
                    select(MarketplaceConsent)
                    .where(MarketplaceConsent.engagement_id == engagement.id)
                    .order_by(MarketplaceConsent.party)
                )
            ).all()
            introduction = await session.scalar(
                select(QualifiedIntroduction).where(
                    QualifiedIntroduction.engagement_id == engagement.id
                )
            )
            return {
                "engagement": self._engagement_payload(engagement),
                "seller_response": (
                    self._response_payload(response) if response is not None else None
                ),
                "consents": [self._consent_payload(item) for item in consents],
                "introduction": (
                    self._introduction_payload(introduction) if introduction is not None else None
                ),
            }

    async def respond(
        self,
        *,
        organization_id: str,
        actor_id: str,
        engagement_id: str,
        if_match: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        request_hash = content_hash({"engagement_id": engagement_id, **body})

        async def write(session: AsyncSession) -> tuple[int, dict[str, Any]]:
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation=f"qualification.engagements.{engagement_id}.respond",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                payload = dict(claim.record.response_payload or {})
                payload["replayed"] = True
                return int(claim.record.response_status or 201), payload
            engagement = await self._engagement(session, organization_id, engagement_id)
            if engagement.seller_organization_id != organization_id:
                raise self._forbidden("Only the selected seller may respond.")
            _verify_match(if_match, engagement.input_digest)
            if engagement.state not in {"OPEN", "RESPONDED"}:
                raise PersistenceConflict("engagement is not accepting seller responses")
            cited_ids = set(body["cited_evidence_ids"])
            if cited_ids:
                active = await session.scalar(
                    select(ActiveProductBundle).where(
                        ActiveProductBundle.organization_id == organization_id,
                        ActiveProductBundle.product_id == engagement.product_id,
                    )
                )
                if active is None:
                    raise PersistenceConflict("active seller bundle is unavailable")
                member_ids = set(
                    await session.scalars(
                        select(ProductBundleMember.member_id).where(
                            ProductBundleMember.organization_id == organization_id,
                            ProductBundleMember.bundle_id == active.bundle_id,
                            ProductBundleMember.member_kind == "EVIDENCE",
                        )
                    )
                )
                if not cited_ids <= member_ids:
                    raise PersistenceConflict("seller response cites evidence outside its bundle")
            response_record = SellerResponse(
                id=new_id("sresponse"),
                engagement_id=engagement.id,
                buyer_organization_id=engagement.buyer_organization_id,
                seller_organization_id=engagement.seller_organization_id,
                input_digest=engagement.input_digest,
                response=str(body["response"]),
                cited_evidence_ids=sorted(cited_ids),
                message=body.get("message"),
                actor_id=actor_id,
                organization_id=organization_id,
            )
            session.add(response_record)
            engagement.state = "RESPONDED"
            session.add(
                SellerEngagementProjection(
                    engagement_id=engagement.id,
                    projection_hash=content_hash(
                        {
                            "buyer_safe_hash": engagement.buyer_safe_hash,
                            "input_digest": engagement.input_digest,
                            "response": response_record.response,
                        }
                    ),
                    payload={
                        "buyer_safe_requirement": engagement.buyer_safe_requirement,
                        "input_digest": engagement.input_digest,
                        "response": response_record.response,
                    },
                    organization_id=organization_id,
                )
            )
            await repository.add_outbox(
                aggregate_type="MARKETPLACE_ENGAGEMENT",
                aggregate_id=engagement.id,
                event_type="SELLER_RESPONSE_RECORDED",
                event_key=f"seller-response-recorded:{response_record.id}",
                payload={
                    "engagement_id": engagement.id,
                    "response_id": response_record.id,
                    "input_digest": engagement.input_digest,
                },
            )
            response = {
                "resource_type": "seller_response",
                "resource_id": response_record.id,
                "state": response_record.response,
                "input_digest": engagement.input_digest,
                "replayed": False,
            }
            await repository.complete_idempotency(
                claim.record,
                response_status=201,
                response_payload=response,
                response_reference=response_record.id,
            )
            return 201, response

        return await self.database.run_retryable(organization_id, write)

    async def consent(
        self,
        *,
        organization_id: str,
        actor_id: str,
        party: Literal["BUYER", "SELLER"],
        engagement_id: str,
        if_match: str,
        idempotency_key: str,
        shared_fields: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        request_hash = content_hash(
            {"engagement_id": engagement_id, "party": party, "shared_fields": shared_fields}
        )

        async def write(session: AsyncSession) -> tuple[int, dict[str, Any]]:
            repository = WorkflowRepository(session, organization_id)
            claim = await repository.claim_idempotency(
                actor_id=actor_id,
                operation=f"qualification.engagements.{engagement_id}.consent.{party.lower()}",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                payload = dict(claim.record.response_payload or {})
                payload["replayed"] = True
                return int(claim.record.response_status or 201), payload
            engagement = await self._engagement(session, organization_id, engagement_id)
            expected_organization = (
                engagement.buyer_organization_id
                if party == "BUYER"
                else engagement.seller_organization_id
            )
            if organization_id != expected_organization:
                raise self._forbidden("The verified organization is not this consent party.")
            _verify_match(if_match, engagement.input_digest)
            now = await self._database_now(session)
            if engagement.expires_at <= now:
                raise PersistenceConflict("engagement has expired")
            approved_hash = content_hash(shared_fields)
            consent = MarketplaceConsent(
                id=new_id("mconsent"),
                engagement_id=engagement.id,
                party=party,
                buyer_organization_id=engagement.buyer_organization_id,
                seller_organization_id=engagement.seller_organization_id,
                actor_id=actor_id,
                input_digest=engagement.input_digest,
                approved_fields_hash=approved_hash,
                state="GRANTED",
                expires_at=min(engagement.expires_at, now + timedelta(days=1)),
            )
            session.add(consent)
            engagement.state = "CONSENT_PENDING"
            await repository.add_outbox(
                aggregate_type="MARKETPLACE_ENGAGEMENT",
                aggregate_id=engagement.id,
                event_type=f"{party}_CONSENT_GRANTED",
                event_key=f"{party.lower()}-consent-granted:{engagement.id}:{engagement.input_digest}",
                payload={
                    "engagement_id": engagement.id,
                    "consent_id": consent.id,
                    "party": party,
                    "input_digest": engagement.input_digest,
                    "approved_fields_hash": approved_hash,
                },
            )
            response = {
                "resource_type": "marketplace_consent",
                "resource_id": consent.id,
                "state": consent.state,
                "input_digest": engagement.input_digest,
                "replayed": False,
            }
            await repository.complete_idempotency(
                claim.record,
                response_status=201,
                response_payload=response,
                response_reference=consent.id,
            )
            return 201, response

        return await self.database.run_retryable(organization_id, write)

    async def introduce(
        self,
        *,
        organization_id: str,
        actor_id: str,
        engagement_id: str,
        if_match: str,
        idempotency_key: str,
        shared_fields: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        request_hash = content_hash(
            {"engagement_id": engagement_id, "shared_fields": shared_fields}
        )

        async def write(session: AsyncSession) -> tuple[int, dict[str, Any]]:
            workflow = WorkflowRepository(session, organization_id)
            claim = await workflow.claim_idempotency(
                actor_id=actor_id,
                operation=f"qualification.engagements.{engagement_id}.introduce",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if claim.replay:
                payload = dict(claim.record.response_payload or {})
                payload["replayed"] = True
                return int(claim.record.response_status or 201), payload
            engagement = await self._engagement(session, organization_id, engagement_id)
            if engagement.buyer_organization_id != organization_id:
                raise self._forbidden("Only the buyer may authorize the introduction.")
            _verify_match(if_match, engagement.input_digest)
            introduction = await QualificationRepository(session, organization_id).introduce(
                engagement_id=engagement.id,
                decision_id=engagement.decision_id,
                input_digest=engagement.input_digest,
                shared_fields=shared_fields,
            )
            mission = await self._mission(session, organization_id, engagement.mission_id)
            mission.state = "COMPLETED"
            response = {
                "resource_type": "qualified_introduction",
                "resource_id": introduction.id,
                "state": "INTRODUCED",
                "input_digest": introduction.input_digest,
                "replayed": False,
            }
            await workflow.complete_idempotency(
                claim.record,
                response_status=201,
                response_payload=response,
                response_reference=introduction.id,
            )
            return 201, response

        return await self.database.run_retryable(organization_id, write)

    async def integrity(self, organization_id: str, mission_id: str) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            mission = await self._mission(session, organization_id, mission_id)
            attempts = (
                await session.scalars(
                    select(QualificationAttempt).where(
                        QualificationAttempt.organization_id == organization_id,
                        QualificationAttempt.mission_id == mission_id,
                    )
                )
            ).all()
            decision = await session.scalar(
                select(QualificationDecision).where(
                    QualificationDecision.organization_id == organization_id,
                    QualificationDecision.mission_id == mission_id,
                    QualificationDecision.current.is_(True),
                )
            )
            engagement = await session.scalar(
                select(MarketplaceEngagement).where(
                    MarketplaceEngagement.buyer_organization_id == organization_id,
                    MarketplaceEngagement.mission_id == mission_id,
                )
            )
            return await self._integrity(session, mission, attempts, decision, engagement)

    async def _attempt_view(
        self, session: AsyncSession, attempt: QualificationAttempt
    ) -> dict[str, Any]:
        dependencies = (
            await session.scalars(
                select(AttemptDependency)
                .where(AttemptDependency.attempt_id == attempt.id)
                .order_by(AttemptDependency.dependency_kind, AttemptDependency.dependency_id)
            )
        ).all()
        checkpoints = (
            await session.scalars(
                select(AttemptCheckpoint)
                .where(AttemptCheckpoint.attempt_id == attempt.id)
                .order_by(AttemptCheckpoint.sequence)
            )
        ).all()
        bundles = (
            await session.scalars(
                select(QualificationMissionBundle)
                .where(QualificationMissionBundle.attempt_id == attempt.id)
                .order_by(QualificationMissionBundle.product_id)
            )
        ).all()
        return {
            "id": attempt.id,
            "state": attempt.state,
            "replacement_depth": attempt.replacement_depth,
            "predecessor_attempt_id": attempt.predecessor_attempt_id,
            "generation": attempt.generation,
            "input_digest": attempt.input_digest,
            "stale_reason": attempt.stale_reason,
            "bundles": [
                {
                    "product_id": item.product_id,
                    "seller_organization_id": item.seller_organization_id,
                    "bundle_id": item.bundle_id,
                    "bundle_digest": item.bundle_digest,
                }
                for item in bundles
            ],
            "dependencies": [
                {
                    "kind": item.dependency_kind,
                    "organization_id": item.dependency_organization_id,
                    "id": item.dependency_id,
                    "version": item.dependency_version,
                    "hash": item.dependency_hash,
                }
                for item in dependencies
            ],
            "checkpoints": [
                {
                    "sequence": item.sequence,
                    "generation": item.generation,
                    "kind": item.kind,
                    "payload": item.payload,
                    "occurred_at": _timestamp(item.occurred_at),
                }
                for item in checkpoints
            ],
        }

    async def _decision_view(
        self, session: AsyncSession, decision: QualificationDecision
    ) -> dict[str, Any]:
        dependencies = (
            await session.scalars(
                select(DecisionDependency)
                .where(DecisionDependency.decision_id == decision.id)
                .order_by(DecisionDependency.dependency_kind, DecisionDependency.dependency_id)
            )
        ).all()
        return {
            "id": decision.id,
            "attempt_id": decision.attempt_id,
            "input_digest": decision.input_digest,
            "decision_digest": decision.decision_digest,
            "etag": _etag_value(decision.decision_digest),
            "recommended_product_id": decision.recommended_product_id,
            "payload": decision.payload,
            "approval_state": decision.approval_state,
            "current": decision.current,
            "dependencies": [
                {
                    "kind": item.dependency_kind,
                    "organization_id": item.dependency_organization_id,
                    "id": item.dependency_id,
                    "version": item.dependency_version,
                    "hash": item.dependency_hash,
                    "cited": item.cited,
                }
                for item in dependencies
            ],
        }

    async def _integrity(
        self,
        session: AsyncSession,
        mission: QualificationMission,
        attempts: Sequence[QualificationAttempt],
        decision: QualificationDecision | None,
        engagement: MarketplaceEngagement | None,
    ) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []

        def add(name: str, passed: bool | None, detail: str) -> None:
            checks.append(
                {
                    "name": name,
                    "status": "PENDING" if passed is None else "PASS" if passed else "FAIL",
                    "detail": detail,
                }
            )

        add(
            "mission_input_hashes",
            mission.buyer_context_hash == content_hash(mission.buyer_context_payload)
            and mission.requirement_brief_hash == content_hash(mission.requirement_brief_payload)
            and mission.procurement_policy_hash == content_hash(mission.procurement_policy_payload),
            "Stored mission hashes bind the exact buyer context, brief, and policy.",
        )
        direct_successors = [
            item.predecessor_attempt_id for item in attempts if item.predecessor_attempt_id
        ]
        add(
            "single_direct_replacement",
            len(direct_successors) == len(set(direct_successors)),
            "Every stale attempt has at most one direct successor.",
        )
        if decision is None:
            add("current_decision", None, "No current decision has been committed yet.")
            add("active_bundle_binding", None, "Bundle binding is checked at finalization.")
        else:
            completed = next((item for item in attempts if item.id == decision.attempt_id), None)
            add(
                "current_decision",
                completed is not None
                and completed.state == "COMPLETED"
                and completed.input_digest == decision.input_digest,
                "The current decision binds one completed attempt and its input digest.",
            )
            product_dependencies = (
                await session.scalars(
                    select(DecisionDependency).where(
                        DecisionDependency.decision_id == decision.id,
                        DecisionDependency.dependency_kind == "PRODUCT_BUNDLE",
                    )
                )
            ).all()
            current_count = 0
            for dependency in product_dependencies:
                current = await session.scalar(
                    select(ActiveProductBundle.product_id).where(
                        ActiveProductBundle.organization_id
                        == dependency.dependency_organization_id,
                        ActiveProductBundle.product_id == dependency.dependency_id,
                        ActiveProductBundle.bundle_id == dependency.dependency_version,
                        ActiveProductBundle.bundle_digest == dependency.dependency_hash,
                    )
                )
                current_count += int(current is not None)
            add(
                "active_bundle_binding",
                current_count == len(product_dependencies) and current_count > 0,
                "Every product dependency still matches its active Product Bundle.",
            )
        effect_count = 0
        if engagement is not None:
            effect_count = int(
                await session.scalar(
                    select(func.count())
                    .select_from(QualificationEffect)
                    .where(
                        QualificationEffect.organization_id == mission.organization_id,
                        QualificationEffect.effect_kind == "QUALIFIED_INTRODUCTION",
                        QualificationEffect.semantic_key
                        == f"introduction:{engagement.id}:{engagement.input_digest}",
                    )
                )
                or 0
            )
        add(
            "single_introduction_effect",
            effect_count <= 1,
            "CockroachDB uniqueness permits at most one qualified introduction effect.",
        )
        if engagement is not None:
            add(
                "engagement_digest",
                decision is not None
                and engagement.decision_id == decision.id
                and engagement.input_digest == decision.input_digest,
                "The bilateral engagement preserves the approved decision digest.",
            )
        statuses = {item["status"] for item in checks}
        verdict = "FAIL" if "FAIL" in statuses else "PENDING" if "PENDING" in statuses else "PASS"
        now = await self._database_now(session)
        return {
            "mission_id": mission.id,
            "verdict": verdict,
            "checks": checks,
            "checked_at": _timestamp(now),
        }

    @staticmethod
    async def _database_now(session: AsyncSession) -> datetime:
        value = await session.scalar(select(func.now()))
        if not isinstance(value, datetime):
            raise PersistenceConflict("database time is unavailable")
        return value

    @staticmethod
    async def _mission(
        session: AsyncSession, organization_id: str, mission_id: str
    ) -> QualificationMission:
        mission = await session.scalar(
            select(QualificationMission).where(
                QualificationMission.organization_id == organization_id,
                QualificationMission.id == mission_id,
            )
        )
        if mission is None:
            raise QualificationService._not_found("QUALIFICATION_MISSION", "Mission was not found.")
        return mission

    @staticmethod
    async def _engagement(
        session: AsyncSession, organization_id: str, engagement_id: str
    ) -> MarketplaceEngagement:
        engagement = await session.scalar(
            select(MarketplaceEngagement).where(MarketplaceEngagement.id == engagement_id)
        )
        if engagement is None or organization_id not in {
            engagement.buyer_organization_id,
            engagement.seller_organization_id,
        }:
            raise QualificationService._not_found(
                "MARKETPLACE_ENGAGEMENT", "Engagement was not found."
            )
        return engagement

    @staticmethod
    def _mission_payload(mission: QualificationMission) -> dict[str, Any]:
        return {
            "id": mission.id,
            "state": mission.state,
            "version": mission.version,
            "trace_id": mission.trace_id,
            "buyer_context": mission.buyer_context_payload,
            "buyer_context_hash": mission.buyer_context_hash,
            "requirement_brief": mission.requirement_brief_payload,
            "requirement_brief_hash": mission.requirement_brief_hash,
            "procurement_policy": mission.procurement_policy_payload,
            "procurement_policy_hash": mission.procurement_policy_hash,
            "created_at": _timestamp(mission.created_at),
            "updated_at": _timestamp(mission.updated_at),
        }

    @staticmethod
    def _engagement_payload(engagement: MarketplaceEngagement) -> dict[str, Any]:
        return {
            "id": engagement.id,
            "mission_id": engagement.mission_id,
            "decision_id": engagement.decision_id,
            "buyer_organization_id": engagement.buyer_organization_id,
            "seller_organization_id": engagement.seller_organization_id,
            "product_id": engagement.product_id,
            "input_digest": engagement.input_digest,
            "etag": _etag_value(engagement.input_digest),
            "buyer_safe_requirement": engagement.buyer_safe_requirement,
            "buyer_safe_hash": engagement.buyer_safe_hash,
            "state": engagement.state,
            "expires_at": _timestamp(engagement.expires_at),
            "created_at": _timestamp(engagement.created_at),
            "updated_at": _timestamp(engagement.updated_at),
        }

    @staticmethod
    def _inbox_item(
        engagement: MarketplaceEngagement, projection: dict[str, Any]
    ) -> dict[str, Any]:
        needs_action = engagement.state in {"OPEN", "RESPONDED", "CONSENT_PENDING"}
        return {
            "id": engagement.id,
            "kind": "SELLER_OPPORTUNITY",
            "state": engagement.state,
            "title": str(projection.get("title") or "Qualified buyer opportunity"),
            "summary": str(
                projection.get("summary")
                or projection.get("buyer_safe_summary")
                or "Review the minimum-disclosure buyer requirement."
            ),
            "product_id": engagement.product_id,
            "requires_action": needs_action,
            "href": f"/seil/opportunities/{engagement.id}",
            "expires_at": _timestamp(engagement.expires_at),
            "updated_at": _timestamp(engagement.updated_at),
        }

    @staticmethod
    def _buyer_inbox_item(
        mission: QualificationMission, decision: QualificationDecision | None
    ) -> dict[str, Any]:
        if decision is not None and decision.approval_state == "PENDING":
            title = "Review the current recommendation"
            requires_action = True
            href = f"/sira/missions/{mission.id}"
        elif mission.state in {"FAILED", "CANCELLED"}:
            title = "Qualification mission needs attention"
            requires_action = True
            href = f"/sira/missions/{mission.id}"
        else:
            title = "Qualification mission update"
            requires_action = False
            href = f"/sira/missions/{mission.id}"
        goal = mission.requirement_brief_payload.get("goal")
        return {
            "id": mission.id,
            "kind": "BUYER_DECISION",
            "state": decision.approval_state if decision is not None else mission.state,
            "title": title,
            "summary": str(goal or "Evidence-backed qualification mission"),
            "requires_action": requires_action,
            "href": href,
            "updated_at": _timestamp(mission.updated_at),
        }

    @staticmethod
    def _response_payload(response: SellerResponse) -> dict[str, Any]:
        return {
            "id": response.id,
            "response": response.response,
            "cited_evidence_ids": response.cited_evidence_ids,
            "message": response.message,
            "actor_id": response.actor_id,
            "input_digest": response.input_digest,
            "created_at": _timestamp(response.created_at),
        }

    @staticmethod
    def _consent_payload(consent: MarketplaceConsent) -> dict[str, Any]:
        return {
            "id": consent.id,
            "party": consent.party,
            "actor_id": consent.actor_id,
            "input_digest": consent.input_digest,
            "approved_fields_hash": consent.approved_fields_hash,
            "state": consent.state,
            "expires_at": _timestamp(consent.expires_at),
        }

    @staticmethod
    def _introduction_payload(introduction: QualifiedIntroduction) -> dict[str, Any]:
        return {
            "id": introduction.id,
            "input_digest": introduction.input_digest,
            "shared_fields_hash": introduction.shared_fields_hash,
            "receipt": introduction.receipt_payload,
            "created_at": _timestamp(introduction.created_at),
        }

    async def _company_context_item(
        self, session: AsyncSession, organization_id: str, item_id: str
    ) -> CompanyContextItem:
        item = await session.scalar(
            select(CompanyContextItem).where(
                CompanyContextItem.organization_id == organization_id,
                CompanyContextItem.id == item_id,
            )
        )
        if item is None:
            raise self._not_found("COMPANY_CONTEXT", "Company context item was not found.")
        return item

    async def _context_payload(
        self, session: AsyncSession, item: CompanyContextItem
    ) -> dict[str, Any]:
        version = await session.scalar(
            select(CompanyContextVersion).where(
                CompanyContextVersion.organization_id == item.organization_id,
                CompanyContextVersion.id == item.current_version_id,
                CompanyContextVersion.content_hash == item.current_hash,
            )
        )
        if version is None:
            raise PersistenceConflict("company context head has no immutable version")
        return {
            "id": item.id,
            "kind": item.kind,
            "label": item.label,
            "state": item.state,
            "current_version_id": item.current_version_id,
            "current_version": item.current_version,
            "current_hash": item.current_hash,
            "etag": _etag_value(item.current_hash),
            "payload": version.payload,
            "created_at": _timestamp(item.created_at),
            "updated_at": _timestamp(item.updated_at),
        }

    @staticmethod
    def _context_version_payload(version: CompanyContextVersion) -> dict[str, Any]:
        return {
            "id": version.id,
            "version": version.version,
            "content_hash": version.content_hash,
            "payload": version.payload,
            "changed_by_actor_id": version.changed_by_actor_id,
            "change_reason": version.change_reason,
            "created_at": _timestamp(version.created_at),
        }

    @staticmethod
    def _settings_payload(
        *,
        party: Literal["BUYER", "SELLER"],
        settings_id: str | None,
        version: int,
        digest: str,
        payload: dict[str, Any],
        updated_at: datetime | None,
    ) -> dict[str, Any]:
        return {
            "id": settings_id,
            "party": party,
            "current_version": version,
            "current_hash": digest,
            "etag": _etag_value(digest),
            "persisted": settings_id is not None,
            **payload,
            # Preferences can only narrow what is requested. The existing
            # consent kernel remains the authority for any actual disclosure.
            "consent_boundary": "BILATERAL_EXACT_FIELD_MATCH_REQUIRED",
            "updated_at": _timestamp(updated_at) if updated_at is not None else None,
        }

    @staticmethod
    def _not_found(code: str, message: str) -> ApiProblem:
        return ApiProblem(code=f"{code}_NOT_FOUND", message=message, status_code=404)

    @staticmethod
    def _forbidden(message: str) -> ApiProblem:
        return ApiProblem(
            code="MARKETPLACE_PARTY_FORBIDDEN",
            message=message,
            status_code=403,
            next_action="use_authorized_party_identity",
        )
