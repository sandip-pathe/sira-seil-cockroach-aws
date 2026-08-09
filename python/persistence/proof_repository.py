"""Tenant-scoped persistence for the narrow proof exchange authority boundary."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proof.exchange import ExactApprovalSubject
from proof.models import ProofContractError

from .models import BuyerProofAdapterProjection, ProofApproval
from .repositories import new_id


class ProofExchangeRepository:
    def __init__(self, session: AsyncSession, organization_id: str) -> None:
        self.session = session
        self.organization_id = organization_id

    async def materialize_projection(
        self, projection: dict[str, Any]
    ) -> BuyerProofAdapterProjection:
        """Idempotently consume an allowlisted publication event without seller-table reads."""

        event_key = str(projection["publicationEventKey"])
        existing = (
            await self.session.execute(
                select(BuyerProofAdapterProjection).where(
                    BuyerProofAdapterProjection.organization_id == self.organization_id,
                    BuyerProofAdapterProjection.publication_event_key == event_key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.projection_hash != projection.get("projectionHash"):
                raise ProofContractError("PROOF_PROJECTION_EVENT_HASH_CONFLICT")
            return existing
        record = BuyerProofAdapterProjection(
            id=new_id("bpap"),
            organization_id=self.organization_id,
            source_seller_organization_id=str(projection["sourceSellerOrganizationId"]),
            source_pack_version_id=str(projection["sourcePackVersionId"]),
            source_pack_content_hash=str(projection["sourcePackContentHash"]),
            publication_event_key=event_key,
            adapter_id=str(projection["adapterId"]),
            artifact_digest=str(projection["artifactDigest"]),
            protocol_version=str(projection["protocolVersion"]),
            capabilities=list(projection["capabilities"]),
            declared_region=str(projection["declaredRegion"]),
            fixed_price=dict(projection["fixedPrice"]),
            public_evidence_references=list(projection["publicEvidenceReferences"]),
            conformance_hash=str(projection["conformanceHash"]),
            projection_hash=str(projection["projectionHash"]),
            state="AVAILABLE",
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def create_approval(
        self,
        *,
        subject: ExactApprovalSubject,
    ) -> ProofApproval:
        existing = (
            await self.session.execute(
                select(ProofApproval).where(
                    ProofApproval.organization_id == self.organization_id,
                    ProofApproval.subject_hash == subject.subject_hash,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        record = ProofApproval(
            id=new_id("papr"),
            organization_id=self.organization_id,
            subject_hash=subject.subject_hash,
            manifest_hash=subject.manifest_hash,
            environment_fingerprint=subject.environment_fingerprint,
            decision_hash=subject.decision_hash,
            adapter_projection_hash=subject.adapter_projection_hash,
            adapter_digest=subject.adapter_digest,
            datahub_owner_urn=subject.datahub_owner_urn,
            actor_id=subject.actor_id,
            actor_role=subject.actor_role,
            status="ACTIVE",
            expires_at=subject.expires_at,
            revoked_at=None,
            consumed_effect_id=None,
        )
        self.session.add(record)
        await self.session.flush()
        return record
