"""Tenant-scoped persistence for the narrow proof exchange authority boundary."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.hashing import content_hash
from proof.exchange import ExactApprovalSubject
from proof.models import ProofContractError
from proof.receipt import ProofReceipt

from .models import AgentEffect, BuyerProofAdapterProjection, ProofApproval, ProofReceiptCore
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

    async def record_effect(
        self,
        *,
        mission_id: str,
        effect_type: str,
        idempotency_key: str,
        request_payload: dict[str, Any],
        status: str,
        approval_reference: str | None = None,
        provider_reference: str | None = None,
        safe_error_code: str | None = None,
    ) -> AgentEffect:
        """Create or advance one idempotent external-effect attempt."""

        request_hash = content_hash(request_payload)
        record = (
            await self.session.execute(
                select(AgentEffect).where(
                    AgentEffect.organization_id == self.organization_id,
                    AgentEffect.mission_id == mission_id,
                    AgentEffect.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if record is None:
            record = AgentEffect(
                id=new_id("aef"),
                organization_id=self.organization_id,
                mission_id=mission_id,
                task_id=None,
                capability_grant_id=None,
                effect_type=effect_type,
                status=status,
                idempotency_key=idempotency_key,
                request_payload=request_payload,
                request_hash=request_hash,
                approval_reference=approval_reference,
                provider_reference=provider_reference,
                result_artifact_id=None,
                safe_error_code=safe_error_code,
            )
            self.session.add(record)
        else:
            if record.request_hash != request_hash or record.effect_type != effect_type:
                raise ProofContractError("PROOF_EFFECT_IDEMPOTENCY_CONFLICT")
            record.status = status
            record.approval_reference = approval_reference
            record.provider_reference = provider_reference
            record.safe_error_code = safe_error_code
        await self.session.flush()
        return record

    async def consume_approval_with_receipt(
        self,
        *,
        approval_subject_hash: str,
        verified_effect_id: str,
        receipt: ProofReceipt,
    ) -> ProofReceiptCore:
        """Atomically consume exact authority only after effect and receipt verification."""

        approval = (
            await self.session.execute(
                select(ProofApproval).where(
                    ProofApproval.organization_id == self.organization_id,
                    ProofApproval.subject_hash == approval_subject_hash,
                )
            )
        ).scalar_one_or_none()
        effect = (
            await self.session.execute(
                select(AgentEffect).where(
                    AgentEffect.organization_id == self.organization_id,
                    AgentEffect.id == verified_effect_id,
                )
            )
        ).scalar_one_or_none()
        if approval is None or effect is None:
            raise ProofContractError("PROOF_RECEIPT_AUTHORITY_OR_EFFECT_MISSING")
        if effect.status != "VERIFIED" or effect.approval_reference != approval_subject_hash:
            raise ProofContractError("PROOF_RECEIPT_EFFECT_NOT_VERIFIED")
        authority = receipt.payload.get("authority", {})
        verified = receipt.payload.get("verifiedEffect", {})
        if (
            authority.get("approvalSubjectHash") != approval_subject_hash
            or authority.get("approvedAdapterDigest") != approval.adapter_digest
            or verified.get("activeAdapterDigest") != approval.adapter_digest
        ):
            raise ProofContractError("PROOF_RECEIPT_APPROVAL_MISMATCH")
        existing = (
            await self.session.execute(
                select(ProofReceiptCore).where(
                    ProofReceiptCore.organization_id == self.organization_id,
                    ProofReceiptCore.core_hash == receipt.core_hash,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        if approval.status != "ACTIVE":
            raise ProofContractError("PROOF_APPROVAL_NOT_ACTIVE")
        projection = receipt.payload["dataHubProjection"]
        record = ProofReceiptCore(
            id=new_id("prc"),
            organization_id=self.organization_id,
            approval_subject_hash=approval_subject_hash,
            verified_adapter_digest=str(verified["activeAdapterDigest"]),
            route_state_at_verification=str(verified["routeStateAtVerification"]),
            datahub_anchor_urn=str(projection["anchorUrn"]),
            datahub_projection_hash=str(projection["projectionHash"]),
            payload=receipt.payload,
            core_hash=receipt.core_hash,
        )
        self.session.add(record)
        await self.session.flush()
        approval.status = "CONSUMED"
        approval.consumed_effect_id = effect.id
        await self.session.flush()
        return record
