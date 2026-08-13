"""Transactional correctness kernel for qualified marketplace decisions."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from domain import content_hash

from .models import OutboxEvent
from .qualification_models import (
    ActiveProductBundle,
    AttemptCheckpoint,
    AttemptDependency,
    ConsumerReceipt,
    DecisionDependency,
    MarketplaceConsent,
    MarketplaceEngagement,
    ProductBundle,
    ProductBundleMember,
    QualificationAttempt,
    QualificationDecision,
    QualificationEffect,
    QualificationMission,
    QualificationMissionBundle,
    QualifiedIntroduction,
)
from .repositories import PersistenceConflict, RecordNotFound


@dataclass(frozen=True, slots=True)
class DependencySnapshot:
    kind: str
    organization_id: str
    identifier: str
    version: str
    digest: str


@dataclass(frozen=True, slots=True)
class AttemptLease:
    attempt_id: str
    generation: int
    lease_owner: str
    lease_expires_at: datetime


@dataclass(frozen=True, slots=True)
class FinalizationResult:
    state: str
    attempt_id: str
    decision_id: str | None = None
    replacement_attempt_id: str | None = None


@dataclass(frozen=True, slots=True)
class BundleInvalidationResult:
    product_id: str
    invalidated_decision_ids: tuple[str, ...]
    replacement_attempt_ids: tuple[str, ...]


class QualificationRepository:
    """Apply the P0 invariants inside one caller-owned transaction."""

    def __init__(self, session: AsyncSession, organization_id: str) -> None:
        self.session = session
        self.organization_id = organization_id

    async def activate_bundle(
        self,
        *,
        bundle_id: str,
        actor_id: str,
        expected_digest: str,
    ) -> ProductBundle:
        bundle = await self.session.scalar(
            select(ProductBundle).where(
                ProductBundle.organization_id == self.organization_id,
                ProductBundle.id == bundle_id,
            )
        )
        if bundle is None:
            raise RecordNotFound("product bundle was not found")
        if bundle.digest != expected_digest:
            raise PersistenceConflict("product bundle digest changed")
        if bundle.state not in {"READY", "ACTIVE"}:
            raise PersistenceConflict("product bundle is not ready")
        members = (
            await self.session.scalars(
                select(ProductBundleMember)
                .where(
                    ProductBundleMember.organization_id == self.organization_id,
                    ProductBundleMember.bundle_id == bundle.id,
                )
                .order_by(ProductBundleMember.ordinal)
            )
        ).all()
        computed_digest = content_hash(
            [
                {
                    "ordinal": member.ordinal,
                    "kind": member.member_kind,
                    "id": member.member_id,
                    "hash": member.member_hash,
                }
                for member in members
            ]
        )
        if not members or computed_digest != bundle.digest:
            raise PersistenceConflict("product bundle membership is incomplete or corrupt")

        active = await self.session.scalar(
            select(ActiveProductBundle).where(
                ActiveProductBundle.organization_id == self.organization_id,
                ActiveProductBundle.product_id == bundle.product_id,
            )
        )
        now = datetime.now(UTC)
        if active is None:
            self.session.add(
                ActiveProductBundle(
                    product_id=bundle.product_id,
                    bundle_id=bundle.id,
                    bundle_digest=bundle.digest,
                    generation=1,
                    organization_id=self.organization_id,
                )
            )
        elif active.bundle_id != bundle.id:
            previous = await self.session.get(ProductBundle, active.bundle_id)
            if previous is not None and previous.state == "ACTIVE":
                previous.state = "SUPERSEDED"
            active.bundle_id = bundle.id
            active.bundle_digest = bundle.digest
            active.generation += 1
        bundle.state = "ACTIVE"
        bundle.activated_at = now
        self._outbox(
            event_type="PRODUCT_BUNDLE_ACTIVATED",
            aggregate_type="PRODUCT_BUNDLE",
            aggregate_id=bundle.id,
            event_key=f"bundle-activated:{bundle.id}:{bundle.digest}",
            payload={
                "bundle_id": bundle.id,
                "product_id": bundle.product_id,
                "bundle_digest": bundle.digest,
                "actor_id": actor_id,
            },
        )
        return bundle

    async def invalidate_decisions_for_active_bundle(
        self, *, product_id: str
    ) -> BundleInvalidationResult:
        """Re-read the active pointer and retire buyer decisions pinned to older truth.

        The CDC payload is intentionally ignored. This method runs in each buyer tenant,
        relies on Cockroach's public active-pointer read policy, and leaves already-issued
        commercial effects as immutable history. Any replacement still travels through the
        normal queue, snapshot, Bedrock and fenced-finalization path.
        """

        rows = (
            await self.session.execute(
                select(QualificationDecision, DecisionDependency)
                .join(
                    DecisionDependency,
                    (DecisionDependency.organization_id == QualificationDecision.organization_id)
                    & (DecisionDependency.decision_id == QualificationDecision.id),
                )
                .where(
                    QualificationDecision.organization_id == self.organization_id,
                    QualificationDecision.current.is_(True),
                    DecisionDependency.dependency_kind == "PRODUCT_BUNDLE",
                    DecisionDependency.dependency_id == product_id,
                )
                .order_by(QualificationDecision.id)
            )
        ).all()
        invalidated: list[str] = []
        replacements: list[str] = []
        for decision, dependency in rows:
            active = await self.session.scalar(
                select(ActiveProductBundle).where(
                    ActiveProductBundle.organization_id == dependency.dependency_organization_id,
                    ActiveProductBundle.product_id == product_id,
                )
            )
            if (
                active is not None
                and active.bundle_id == dependency.dependency_version
                and active.bundle_digest == dependency.dependency_hash
            ):
                continue
            decision.current = False
            decision.approval_state = "INVALIDATED"
            invalidated.append(decision.id)
            engagements = (
                await self.session.scalars(
                    select(MarketplaceEngagement).where(
                        MarketplaceEngagement.buyer_organization_id == self.organization_id,
                        MarketplaceEngagement.decision_id == decision.id,
                        MarketplaceEngagement.state.notin_(("INTRODUCED", "EXPIRED")),
                    )
                )
            ).all()
            for engagement in engagements:
                engagement.state = "INVALIDATED"
            if active is None:
                continue
            attempt = await self.session.scalar(
                select(QualificationAttempt).where(
                    QualificationAttempt.organization_id == self.organization_id,
                    QualificationAttempt.id == decision.attempt_id,
                )
            )
            mission = await self.session.scalar(
                select(QualificationMission).where(
                    QualificationMission.organization_id == self.organization_id,
                    QualificationMission.id == decision.mission_id,
                )
            )
            if attempt is None or mission is None or mission.state in {"FAILED", "CANCELLED"}:
                continue
            replacement = await self._replacement_for(attempt)
            mission.state = "READY"
            replacements.append(replacement.id)
            self._outbox(
                event_type="QUALIFICATION_MISSION_READY",
                aggregate_type="QUALIFICATION_MISSION",
                aggregate_id=mission.id,
                event_key=(
                    f"qualification-mission-ready:{mission.id}:"
                    f"bundle:{product_id}:{active.generation}"
                ),
                payload={
                    "mission_id": mission.id,
                    "trace_id": mission.trace_id,
                    "organization_id": self.organization_id,
                    "reason": "ACTIVE_PRODUCT_BUNDLE_CHANGED",
                    "product_id": product_id,
                    "replacement_attempt_id": replacement.id,
                },
            )
        if invalidated:
            await self.session.flush()
        return BundleInvalidationResult(product_id, tuple(invalidated), tuple(replacements))

    async def claim_attempt(
        self,
        *,
        attempt_id: str,
        lease_owner: str,
        lease_seconds: int = 60,
    ) -> AttemptLease:
        if lease_seconds < 1 or lease_seconds > 600:
            raise ValueError("lease_seconds must be between 1 and 600")
        now = await self.session.scalar(select(func.now()))
        if not isinstance(now, datetime):
            raise PersistenceConflict("database time is unavailable")
        expires_at = now + timedelta(seconds=lease_seconds)
        statement = (
            update(QualificationAttempt)
            .where(
                QualificationAttempt.organization_id == self.organization_id,
                QualificationAttempt.id == attempt_id,
                QualificationAttempt.state.in_(("QUEUED", "RUNNING", "SNAPSHOT_COMPLETE")),
                (
                    (QualificationAttempt.lease_owner.is_(None))
                    | (QualificationAttempt.lease_expires_at <= now)
                    | (QualificationAttempt.lease_owner == lease_owner)
                ),
            )
            .values(
                state="RUNNING",
                lease_owner=lease_owner,
                lease_expires_at=expires_at,
                generation=QualificationAttempt.generation + 1,
            )
            .returning(QualificationAttempt.generation)
        )
        generation = await self.session.scalar(statement)
        if generation is None:
            raise PersistenceConflict("attempt lease is held by another worker or is terminal")
        return AttemptLease(attempt_id, int(generation), lease_owner, expires_at)

    async def snapshot_attempt(self, *, lease: AttemptLease) -> tuple[DependencySnapshot, ...]:
        attempt = await self._fenced_attempt(lease, allowed_states={"RUNNING", "SNAPSHOT_COMPLETE"})
        mission = await self.session.scalar(
            select(QualificationMission).where(
                QualificationMission.organization_id == self.organization_id,
                QualificationMission.id == attempt.mission_id,
            )
        )
        if mission is None:
            raise RecordNotFound("qualification mission was not found")
        bundles = (
            await self.session.scalars(
                select(QualificationMissionBundle)
                .where(
                    QualificationMissionBundle.organization_id == self.organization_id,
                    QualificationMissionBundle.attempt_id == attempt.id,
                )
                .order_by(QualificationMissionBundle.product_id)
            )
        ).all()
        if len(bundles) < 1:
            raise PersistenceConflict("qualification mission has no product bundles")
        bundle_members: dict[str, Sequence[ProductBundleMember]] = {}
        for bundle in bundles:
            bundle_members[bundle.bundle_id] = (
                await self.session.scalars(
                    select(ProductBundleMember)
                    .where(
                        ProductBundleMember.organization_id == bundle.seller_organization_id,
                        ProductBundleMember.bundle_id == bundle.bundle_id,
                    )
                    .order_by(ProductBundleMember.ordinal)
                )
            ).all()
            if not bundle_members[bundle.bundle_id]:
                raise PersistenceConflict("qualification product bundle has no members")
        dependencies = (
            DependencySnapshot(
                "BUYER_CONTEXT",
                self.organization_id,
                mission.buyer_context_version_id,
                mission.buyer_context_version_id,
                mission.buyer_context_hash,
            ),
            DependencySnapshot(
                "REQUIREMENT_BRIEF",
                self.organization_id,
                mission.requirement_brief_version_id,
                mission.requirement_brief_version_id,
                mission.requirement_brief_hash,
            ),
            DependencySnapshot(
                "PROCUREMENT_POLICY",
                self.organization_id,
                mission.procurement_policy_version,
                mission.procurement_policy_version,
                mission.procurement_policy_hash,
            ),
            *(
                DependencySnapshot(
                    "PRODUCT_BUNDLE",
                    bundle.seller_organization_id,
                    bundle.product_id,
                    bundle.bundle_id,
                    bundle.bundle_digest,
                )
                for bundle in bundles
            ),
            *(
                DependencySnapshot(
                    member.member_kind,
                    bundle.seller_organization_id,
                    member.member_id,
                    bundle.bundle_id,
                    member.member_hash,
                )
                for bundle in bundles
                for member in bundle_members[bundle.bundle_id]
            ),
        )
        digest = content_hash(
            [
                {
                    "kind": item.kind,
                    "organization_id": item.organization_id,
                    "id": item.identifier,
                    "version": item.version,
                    "digest": item.digest,
                }
                for item in dependencies
            ]
        )
        existing = (
            await self.session.scalars(
                select(AttemptDependency).where(
                    AttemptDependency.organization_id == self.organization_id,
                    AttemptDependency.attempt_id == attempt.id,
                )
            )
        ).all()
        if existing:
            if attempt.input_digest != digest:
                raise PersistenceConflict("attempt snapshot is immutable")
            return dependencies
        for item in dependencies:
            self.session.add(
                AttemptDependency(
                    id=f"dep_{uuid4().hex}",
                    attempt_id=attempt.id,
                    dependency_kind=item.kind,
                    dependency_organization_id=item.organization_id,
                    dependency_id=item.identifier,
                    dependency_version=item.version,
                    dependency_hash=item.digest,
                    organization_id=self.organization_id,
                )
            )
        attempt.input_digest = digest
        attempt.state = "SNAPSHOT_COMPLETE"
        self.session.add(
            AttemptCheckpoint(
                id=f"chk_{uuid4().hex}",
                attempt_id=attempt.id,
                generation=attempt.generation,
                sequence=1,
                kind="SNAPSHOT_COMPLETE",
                payload={"input_digest": digest, "dependency_count": len(dependencies)},
                organization_id=self.organization_id,
            )
        )
        # Sessions deliberately disable autoflush so model work never causes
        # incidental writes. Make this method's committed snapshot visible to
        # an immediate idempotent replay in the same caller-owned transaction.
        await self.session.flush()
        return dependencies

    async def checkpoint_attempt(
        self,
        *,
        lease: AttemptLease,
        sequence: int,
        kind: str,
        payload: dict[str, Any],
    ) -> AttemptCheckpoint:
        attempt = await self._fenced_attempt(lease, allowed_states={"RUNNING", "SNAPSHOT_COMPLETE"})
        checkpoint = AttemptCheckpoint(
            id=f"chk_{uuid4().hex}",
            attempt_id=attempt.id,
            generation=attempt.generation,
            sequence=sequence,
            kind=kind,
            payload=payload,
            organization_id=self.organization_id,
        )
        self.session.add(checkpoint)
        return checkpoint

    async def finalize_attempt(
        self,
        *,
        lease: AttemptLease,
        recommended_product_id: str,
        payload: dict[str, Any],
        cited_dependency_ids: frozenset[str],
    ) -> FinalizationResult:
        attempt = await self._fenced_attempt(lease, allowed_states={"SNAPSHOT_COMPLETE"})
        dependencies = (
            await self.session.scalars(
                select(AttemptDependency).where(
                    AttemptDependency.organization_id == self.organization_id,
                    AttemptDependency.attempt_id == attempt.id,
                )
            )
        ).all()
        changed = await self._changed_product_bundles(dependencies)
        if changed:
            attempt.state = "STALE"
            attempt.stale_reason = ",".join(changed)
            replacement = await self._replacement_for(attempt)
            self._outbox(
                event_type="QUALIFICATION_ATTEMPT_STALE",
                aggregate_type="QUALIFICATION_ATTEMPT",
                aggregate_id=attempt.id,
                event_key=f"attempt-stale:{attempt.id}:{attempt.generation}",
                payload={
                    "attempt_id": attempt.id,
                    "replacement_attempt_id": replacement.id,
                    "changed_dependencies": changed,
                },
            )
            return FinalizationResult("STALE", attempt.id, replacement_attempt_id=replacement.id)
        dependency_ids = {item.dependency_id for item in dependencies}
        if not cited_dependency_ids <= dependency_ids:
            raise PersistenceConflict("decision cites evidence outside the committed snapshot")
        if recommended_product_id not in {
            item.dependency_id for item in dependencies if item.dependency_kind == "PRODUCT_BUNDLE"
        }:
            raise PersistenceConflict("recommended product is outside the committed snapshot")
        if attempt.input_digest is None:
            raise PersistenceConflict("attempt has no committed input digest")
        decision_payload = {
            "attempt_id": attempt.id,
            "input_digest": attempt.input_digest,
            "recommended_product_id": recommended_product_id,
            "payload": payload,
        }
        decision = QualificationDecision(
            id=f"qdec_{uuid4().hex}",
            mission_id=attempt.mission_id,
            attempt_id=attempt.id,
            input_digest=attempt.input_digest,
            decision_digest=content_hash(decision_payload),
            recommended_product_id=recommended_product_id,
            payload=payload,
            approval_state="PENDING",
            current=True,
            organization_id=self.organization_id,
        )
        self.session.add(decision)
        await self.session.flush()
        for item in dependencies:
            self.session.add(
                DecisionDependency(
                    id=f"ddep_{uuid4().hex}",
                    decision_id=decision.id,
                    dependency_kind=item.dependency_kind,
                    dependency_organization_id=item.dependency_organization_id,
                    dependency_id=item.dependency_id,
                    dependency_version=item.dependency_version,
                    dependency_hash=item.dependency_hash,
                    cited=item.dependency_id in cited_dependency_ids,
                    organization_id=self.organization_id,
                )
            )
        attempt.state = "COMPLETED"
        self._outbox(
            event_type="QUALIFICATION_DECISION_CREATED",
            aggregate_type="QUALIFICATION_DECISION",
            aggregate_id=decision.id,
            event_key=f"decision-created:{decision.id}",
            payload={
                "decision_id": decision.id,
                "mission_id": decision.mission_id,
                "attempt_id": attempt.id,
                "input_digest": attempt.input_digest,
            },
        )
        return FinalizationResult("COMPLETED", attempt.id, decision_id=decision.id)

    async def introduce(
        self,
        *,
        engagement_id: str,
        decision_id: str,
        input_digest: str,
        shared_fields: dict[str, Any],
    ) -> QualifiedIntroduction:
        shared_fields_hash = content_hash(shared_fields)
        now = await self.session.scalar(select(func.now()))
        engagement = await self.session.scalar(
            select(MarketplaceEngagement).where(
                MarketplaceEngagement.id == engagement_id,
                MarketplaceEngagement.decision_id == decision_id,
                MarketplaceEngagement.input_digest == input_digest,
                MarketplaceEngagement.buyer_organization_id == self.organization_id,
            )
        )
        if engagement is None:
            raise RecordNotFound("marketplace engagement was not found")
        existing = await self.session.scalar(
            select(QualifiedIntroduction).where(
                QualifiedIntroduction.engagement_id == engagement.id
            )
        )
        if existing is not None:
            if (
                existing.input_digest != input_digest
                or existing.shared_fields_hash != shared_fields_hash
            ):
                raise PersistenceConflict(
                    "existing introduction binds another digest or shared field set"
                )
            return existing
        decision = await self.session.scalar(
            select(QualificationDecision).where(
                QualificationDecision.organization_id == self.organization_id,
                QualificationDecision.id == decision_id,
                QualificationDecision.input_digest == input_digest,
                QualificationDecision.current.is_(True),
                QualificationDecision.approval_state == "APPROVED",
            )
        )
        if decision is None:
            raise PersistenceConflict("decision is not current and approved")
        if not isinstance(now, datetime) or engagement.expires_at <= now:
            raise PersistenceConflict("engagement has expired")
        consents = (
            await self.session.scalars(
                select(MarketplaceConsent).where(
                    MarketplaceConsent.engagement_id == engagement.id,
                    MarketplaceConsent.input_digest == input_digest,
                    MarketplaceConsent.state == "GRANTED",
                    MarketplaceConsent.expires_at > now,
                )
            )
        ).all()
        by_party = {consent.party: consent for consent in consents}
        if set(by_party) != {"BUYER", "SELLER"}:
            raise PersistenceConflict("current buyer and seller consent are required")
        if by_party["BUYER"].actor_id == by_party["SELLER"].actor_id:
            raise PersistenceConflict("buyer and seller consent require distinct humans")
        if any(consent.approved_fields_hash != shared_fields_hash for consent in by_party.values()):
            raise PersistenceConflict("buyer and seller must approve the exact shared fields")
        receipt = {
            "engagement_id": engagement.id,
            "decision_id": decision.id,
            "input_digest": input_digest,
            "buyer_consent_id": by_party["BUYER"].id,
            "seller_consent_id": by_party["SELLER"].id,
            "shared_fields_hash": shared_fields_hash,
            "shared_fields": shared_fields,
        }
        introduction = QualifiedIntroduction(
            id=f"intro_{uuid4().hex}",
            engagement_id=engagement.id,
            decision_id=decision.id,
            buyer_organization_id=engagement.buyer_organization_id,
            seller_organization_id=engagement.seller_organization_id,
            input_digest=input_digest,
            shared_fields_hash=shared_fields_hash,
            receipt_payload=receipt,
        )
        self.session.add(introduction)
        self.session.add(
            QualificationEffect(
                id=f"effect_{uuid4().hex}",
                effect_kind="QUALIFIED_INTRODUCTION",
                semantic_key=f"introduction:{engagement.id}:{input_digest}",
                state="RESERVED",
                payload=receipt,
                result_ref=introduction.id,
                organization_id=self.organization_id,
            )
        )
        engagement.state = "INTRODUCED"
        self._outbox(
            event_type="QUALIFIED_INTRODUCTION_CREATED",
            aggregate_type="QUALIFIED_INTRODUCTION",
            aggregate_id=introduction.id,
            event_key=f"introduction-created:{engagement.id}:{input_digest}",
            payload=receipt,
        )
        return introduction

    async def record_consumer_receipt(
        self,
        *,
        consumer_name: str,
        message_id: str,
        payload_hash: str,
        result_ref: str,
    ) -> tuple[ConsumerReceipt, bool]:
        existing = await self.session.scalar(
            select(ConsumerReceipt).where(
                ConsumerReceipt.organization_id == self.organization_id,
                ConsumerReceipt.consumer_name == consumer_name,
                ConsumerReceipt.message_id == message_id,
            )
        )
        if existing is not None:
            if existing.payload_hash != payload_hash:
                raise PersistenceConflict("consumer message ID was reused with another payload")
            return existing, True
        receipt = ConsumerReceipt(
            id=f"consumer_{uuid4().hex}",
            consumer_name=consumer_name,
            message_id=message_id,
            payload_hash=payload_hash,
            result_ref=result_ref,
            organization_id=self.organization_id,
        )
        self.session.add(receipt)
        return receipt, False

    async def _fenced_attempt(
        self, lease: AttemptLease, *, allowed_states: set[str]
    ) -> QualificationAttempt:
        now = await self.session.scalar(select(func.now()))
        attempt = await self.session.scalar(
            select(QualificationAttempt).where(
                QualificationAttempt.organization_id == self.organization_id,
                QualificationAttempt.id == lease.attempt_id,
                QualificationAttempt.generation == lease.generation,
                QualificationAttempt.lease_owner == lease.lease_owner,
                QualificationAttempt.lease_expires_at > now,
                QualificationAttempt.state.in_(allowed_states),
            )
        )
        if attempt is None:
            raise PersistenceConflict("attempt lease or generation fence was lost")
        return attempt

    async def _changed_product_bundles(
        self, dependencies: Sequence[AttemptDependency]
    ) -> list[str]:
        changed: list[str] = []
        for item in dependencies:
            if item.dependency_kind != "PRODUCT_BUNDLE":
                continue
            active = await self.session.scalar(
                select(ActiveProductBundle).where(
                    ActiveProductBundle.organization_id == item.dependency_organization_id,
                    ActiveProductBundle.product_id == item.dependency_id,
                    ActiveProductBundle.bundle_id == item.dependency_version,
                    ActiveProductBundle.bundle_digest == item.dependency_hash,
                )
            )
            if active is None:
                changed.append(item.dependency_id)
        return sorted(changed)

    async def _replacement_for(self, attempt: QualificationAttempt) -> QualificationAttempt:
        existing = await self.session.scalar(
            select(QualificationAttempt).where(
                QualificationAttempt.organization_id == self.organization_id,
                QualificationAttempt.predecessor_attempt_id == attempt.id,
            )
        )
        if existing is not None:
            return existing
        if attempt.replacement_depth >= 3:
            raise PersistenceConflict("qualification replacement chain exhausted")
        replacement = QualificationAttempt(
            id=f"qattempt_{uuid4().hex}",
            mission_id=attempt.mission_id,
            root_attempt_id=attempt.root_attempt_id,
            predecessor_attempt_id=attempt.id,
            replacement_depth=attempt.replacement_depth + 1,
            state="QUEUED",
            generation=0,
            organization_id=self.organization_id,
        )
        self.session.add(replacement)
        return replacement

    def _outbox(
        self,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        event_key: str,
        payload: dict[str, Any],
    ) -> None:
        self.session.add(
            OutboxEvent(
                id=f"outbox_{uuid4().hex}",
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                event_type=event_type,
                event_key=event_key,
                payload=payload,
                organization_id=self.organization_id,
            )
        )
