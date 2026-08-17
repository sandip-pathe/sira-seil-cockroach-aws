"""Cockroach persistence for append-only party commands and projections."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domain import content_hash
from domain.bilateral_exchange import (
    CompiledTransition,
    CoordinatorState,
    PartyCommand,
    PartyProjection,
    compile_party_command,
)
from domain.exchange_contracts import (
    ExchangeEnvelope,
    ExchangePaymentHandoff,
    ExchangeReceipt,
    OfferApproval,
    OfferVersion,
    ReleaseManifest,
    validate_counteroffer,
)

from .models import (
    BilateralExchangeCase,
    BilateralExchangeEnvelope,
    BilateralExchangeHandoff,
    BilateralExchangeReceipt,
    BilateralOfferApproval,
    BilateralOfferVersion,
    BilateralPartyCommand,
    BilateralPartyProjection,
    BilateralReleaseManifest,
    BilateralTransition,
)
from .repositories import PersistenceConflict, RecordNotFound, new_id


class BilateralRepository:
    def __init__(self, session: AsyncSession, organization_id: str) -> None:
        self.session = session
        self.organization_id = organization_id

    async def create_case(
        self, *, case_id: str, seller_organization_id: str
    ) -> BilateralExchangeCase:
        existing = await self.session.get(BilateralExchangeCase, case_id)
        if existing is not None:
            if existing.organization_id != self.organization_id:
                raise PersistenceConflict("exchange case belongs to another buyer tenant")
            return existing
        state = CoordinatorState(case_id=case_id)
        record = BilateralExchangeCase(
            id=case_id,
            organization_id=self.organization_id,
            seller_organization_id=seller_organization_id,
            state=state.state.value,
            version=state.version,
            coordinator_state=state.model_dump(mode="json"),
            state_hash=content_hash(state.model_dump(mode="json")),
            last_command_id=None,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def append_command(self, command: PartyCommand) -> BilateralPartyCommand:
        existing = await self.session.scalar(
            select(BilateralPartyCommand).where(
                BilateralPartyCommand.organization_id == self.organization_id,
                BilateralPartyCommand.party == command.party.value,
                BilateralPartyCommand.idempotency_key == command.idempotency_key,
            )
        )
        payload_hash = content_hash(command.payload)
        if existing is not None:
            if (
                existing.payload_hash != payload_hash
                or existing.command_type != command.command_type
            ):
                raise PersistenceConflict("party command idempotency key was reused")
            return existing
        record = BilateralPartyCommand(
            id=command.id,
            organization_id=self.organization_id,
            case_id=command.case_id,
            party=command.party.value,
            actor_id=command.actor_id,
            command_type=command.command_type,
            expected_version=command.expected_version,
            idempotency_key=command.idempotency_key,
            payload=command.payload,
            payload_hash=payload_hash,
            status="PENDING",
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_case(self, case_id: str, *, lock: bool = False) -> BilateralExchangeCase:
        statement = select(BilateralExchangeCase).where(
            BilateralExchangeCase.organization_id == self.organization_id,
            BilateralExchangeCase.id == case_id,
        )
        if lock:
            statement = statement.with_for_update()
        record = await self.session.scalar(statement)
        if record is None:
            raise RecordNotFound("bilateral exchange case was not found")
        return record

    async def apply_command(
        self,
        exchange: BilateralExchangeCase,
        command: PartyCommand,
        *,
        command_organization_id: str,
    ) -> CompiledTransition:
        existing = await self.session.scalar(
            select(BilateralTransition).where(
                BilateralTransition.organization_id == self.organization_id,
                BilateralTransition.case_id == exchange.id,
                BilateralTransition.command_id == command.id,
            )
        )
        if existing is not None:
            raise PersistenceConflict("party command was already applied")
        state = CoordinatorState.model_validate(exchange.coordinator_state)
        compiled = compile_party_command(state, command)
        next_payload = compiled.next_state.model_dump(mode="json")
        sequence = (
            int(
                await self.session.scalar(
                    select(func.coalesce(func.max(BilateralTransition.sequence), 0)).where(
                        BilateralTransition.organization_id == self.organization_id,
                        BilateralTransition.case_id == exchange.id,
                    )
                )
                or 0
            )
            + 1
        )
        transition_payload = {
            "case_id": exchange.id,
            "sequence": sequence,
            "command_id": command.id,
            "command_organization_id": command_organization_id,
            "previous_state": compiled.previous_state.value,
            "next_state": compiled.next_state.state.value,
            "state_hash": content_hash(next_payload),
        }
        self.session.add(
            BilateralTransition(
                id=new_id("btrans"),
                organization_id=self.organization_id,
                case_id=exchange.id,
                sequence=sequence,
                command_id=command.id,
                command_organization_id=command_organization_id,
                previous_state=compiled.previous_state.value,
                next_state=compiled.next_state.state.value,
                transition_hash=content_hash(transition_payload),
            )
        )
        exchange.state = compiled.next_state.state.value
        exchange.version = compiled.next_state.version
        exchange.coordinator_state = next_payload
        exchange.state_hash = content_hash(next_payload)
        exchange.last_command_id = command.id
        await self.session.flush()
        return compiled

    async def publish_projection(self, projection: PartyProjection) -> BilateralPartyProjection:
        existing = await self.session.scalar(
            select(BilateralPartyProjection).where(
                BilateralPartyProjection.organization_id == self.organization_id,
                BilateralPartyProjection.case_id == projection.case_id,
                BilateralPartyProjection.party == projection.party,
                BilateralPartyProjection.version == projection.version,
            )
        )
        if existing is not None:
            if existing.projection_hash != projection.projection_hash:
                raise PersistenceConflict("projection version already has another payload")
            return existing
        record = BilateralPartyProjection(
            id=new_id("bproj"),
            organization_id=self.organization_id,
            case_id=projection.case_id,
            party=projection.party,
            version=projection.version,
            state=projection.state.value,
            released=projection.released,
            source_command_id=projection.source_command_id,
            projection_hash=projection.projection_hash,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def latest_projection(self, case_id: str, *, party: str) -> BilateralPartyProjection:
        record = await self.session.scalar(
            select(BilateralPartyProjection)
            .where(
                BilateralPartyProjection.organization_id == self.organization_id,
                BilateralPartyProjection.case_id == case_id,
                BilateralPartyProjection.party == party,
            )
            .order_by(BilateralPartyProjection.version.desc())
            .limit(1)
        )
        if record is None:
            raise RecordNotFound("party projection was not found")
        return record

    async def store_release_manifest(
        self, manifest: ReleaseManifest
    ) -> BilateralReleaseManifest:
        existing = await self.session.get(BilateralReleaseManifest, manifest.manifest_id)
        if existing is not None:
            if (
                existing.organization_id != self.organization_id
                or existing.manifest_hash != manifest.manifest_hash
            ):
                raise PersistenceConflict("release manifest id was reused")
            return existing
        record = BilateralReleaseManifest(
            id=manifest.manifest_id,
            organization_id=self.organization_id,
            case_id=manifest.case_id,
            owner_party=manifest.owner.value,
            recipient_party=manifest.recipient.value,
            purpose=manifest.purpose,
            payload=manifest.model_dump(mode="json"),
            approved_payload_hash=manifest.approved_payload_hash,
            approval_id=manifest.approval_id,
            status=manifest.status.value,
            expires_at=manifest.expires_at,
            manifest_hash=manifest.manifest_hash,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def store_envelope(self, envelope: ExchangeEnvelope) -> BilateralExchangeEnvelope:
        existing = await self.session.get(BilateralExchangeEnvelope, envelope.envelope_id)
        if existing is not None:
            if (
                existing.organization_id != self.organization_id
                or existing.payload_hash != envelope.payload_hash
            ):
                raise PersistenceConflict("exchange envelope id was reused")
            return existing
        manifest = await self.session.scalar(
            select(BilateralReleaseManifest).where(
                BilateralReleaseManifest.organization_id == self.organization_id,
                BilateralReleaseManifest.manifest_hash == envelope.manifest_hash,
            )
        )
        if manifest is None:
            raise RecordNotFound("release manifest was not found")
        manifest_expiry = manifest.expires_at
        if manifest_expiry.tzinfo is None:
            # SQLite drops timezone metadata in tests; CockroachDB preserves it.
            manifest_expiry = manifest_expiry.replace(tzinfo=UTC)
        if (
            manifest.case_id != envelope.case_id
            or manifest.owner_party != envelope.sender.value
            or manifest.recipient_party != envelope.recipient.value
            or manifest.status != "ACTIVE"
            or manifest_expiry <= envelope.expires_at
        ):
            raise PersistenceConflict("envelope exceeds its release authorization")
        record = BilateralExchangeEnvelope(
            id=envelope.envelope_id,
            organization_id=self.organization_id,
            case_id=envelope.case_id,
            sender_party=envelope.sender.value,
            recipient_party=envelope.recipient.value,
            sequence=envelope.sequence,
            causation_id=envelope.causation_id,
            manifest_hash=envelope.manifest_hash,
            payload=envelope.payload,
            payload_hash=envelope.payload_hash,
            expires_at=envelope.expires_at,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def acknowledge_envelope(
        self, receipt: ExchangeReceipt
    ) -> BilateralExchangeReceipt:
        existing = await self.session.scalar(
            select(BilateralExchangeReceipt).where(
                BilateralExchangeReceipt.organization_id == self.organization_id,
                BilateralExchangeReceipt.envelope_id == receipt.envelope_id,
            )
        )
        if existing is not None:
            if (
                existing.envelope_hash != receipt.envelope_hash
                or existing.recipient_party != receipt.recipient.value
            ):
                raise PersistenceConflict("exchange receipt conflicts with prior acknowledgement")
            return existing
        envelope = await self.session.get(BilateralExchangeEnvelope, receipt.envelope_id)
        if envelope is None or envelope.organization_id != self.organization_id:
            raise RecordNotFound("exchange envelope was not found")
        if (
            envelope.case_id != receipt.case_id
            or envelope.recipient_party != receipt.recipient.value
            or envelope.payload_hash != receipt.envelope_hash
        ):
            raise PersistenceConflict("receipt does not bind the received envelope")
        record = BilateralExchangeReceipt(
            id=receipt.receipt_id,
            organization_id=self.organization_id,
            envelope_id=receipt.envelope_id,
            case_id=receipt.case_id,
            recipient_party=receipt.recipient.value,
            envelope_hash=receipt.envelope_hash,
            received_at=receipt.received_at,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def store_offer(self, offer: OfferVersion) -> BilateralOfferVersion:
        existing = await self.session.scalar(
            select(BilateralOfferVersion).where(
                BilateralOfferVersion.organization_id == self.organization_id,
                BilateralOfferVersion.offer_hash == offer.offer_hash,
            )
        )
        if existing is not None:
            return existing
        latest = await self.session.scalar(
            select(BilateralOfferVersion)
            .where(
                BilateralOfferVersion.organization_id == self.organization_id,
                BilateralOfferVersion.case_id == offer.case_id,
            )
            .order_by(BilateralOfferVersion.version.desc())
            .limit(1)
            .with_for_update()
        )
        if latest is None:
            if offer.version != 1:
                raise PersistenceConflict("negotiation must begin with offer version 1")
        else:
            previous = OfferVersion.model_validate(latest.terms)
            try:
                validate_counteroffer(previous, offer)
            except ValueError as error:
                raise PersistenceConflict(str(error)) from error
            if latest.approval_status == "APPROVED":
                raise PersistenceConflict("an approved offer cannot be countered")
            latest.approval_status = "SUPERSEDED"
        record = BilateralOfferVersion(
            id=f"{offer.offer_id}:v{offer.version}",
            organization_id=self.organization_id,
            case_id=offer.case_id,
            version=offer.version,
            proposer_party=offer.proposer.value,
            recipient_party=offer.recipient.value,
            predecessor_hash=offer.predecessor_hash,
            terms=offer.model_dump(mode="json"),
            offer_hash=offer.offer_hash,
            approval_status=offer.approval_status.value,
            expires_at=offer.expires_at,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def approve_offer(
        self, approval: OfferApproval, *, now: datetime
    ) -> BilateralOfferApproval:
        existing = await self.session.scalar(
            select(BilateralOfferApproval).where(
                BilateralOfferApproval.organization_id == self.organization_id,
                BilateralOfferApproval.case_id == approval.case_id,
                BilateralOfferApproval.offer_hash == approval.offer_hash,
            )
        )
        if existing is not None:
            return existing
        offer_record = await self.session.scalar(
            select(BilateralOfferVersion)
            .where(
                BilateralOfferVersion.organization_id == self.organization_id,
                BilateralOfferVersion.case_id == approval.case_id,
            )
            .order_by(BilateralOfferVersion.version.desc())
            .limit(1)
            .with_for_update()
        )
        if offer_record is None:
            raise RecordNotFound("offer was not found")
        offer = OfferVersion.model_validate(offer_record.terms)
        approval.authorize(offer, now=now)
        approval_payload = approval.model_dump(mode="json")
        record = BilateralOfferApproval(
            id=approval.approval_id,
            organization_id=self.organization_id,
            case_id=approval.case_id,
            offer_hash=approval.offer_hash,
            approver_id=approval.approver_id,
            approved_at=approval.approved_at,
            expires_at=approval.expires_at,
            approval_hash=content_hash(approval_payload),
        )
        self.session.add(record)
        offer_record.approval_status = "APPROVED"
        await self.session.flush()
        return record

    async def store_handoff(
        self, handoff: ExchangePaymentHandoff
    ) -> BilateralExchangeHandoff:
        existing = await self.session.scalar(
            select(BilateralExchangeHandoff).where(
                BilateralExchangeHandoff.organization_id == self.organization_id,
                BilateralExchangeHandoff.case_id == handoff.case_id,
                BilateralExchangeHandoff.offer_hash == handoff.offer_hash,
            )
        )
        if existing is not None:
            if existing.handoff_hash != handoff.handoff_hash:
                raise PersistenceConflict("approved offer is bound to another handoff")
            return existing
        record = BilateralExchangeHandoff(
            id=handoff.handoff_id,
            organization_id=self.organization_id,
            case_id=handoff.case_id,
            offer_hash=handoff.offer_hash,
            approval_hash=handoff.approval_hash,
            handoff_hash=handoff.handoff_hash,
            destination_url=handoff.destination_url,
            recipient=handoff.recipient,
            amount=handoff.amount,
            currency=handoff.currency,
            reference=handoff.reference,
            status=handoff.status.value,
            expires_at=handoff.expires_at,
            opened_at=handoff.opened_at,
            created_at=handoff.created_at,
            updated_at=handoff.created_at,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def open_handoff(
        self,
        handoff_id: str,
        *,
        expected_hash: str,
        now: datetime,
    ) -> BilateralExchangeHandoff:
        record = await self.session.scalar(
            select(BilateralExchangeHandoff)
            .where(
                BilateralExchangeHandoff.organization_id == self.organization_id,
                BilateralExchangeHandoff.id == handoff_id,
            )
            .with_for_update()
        )
        if record is None:
            raise RecordNotFound("exchange handoff was not found")
        if record.handoff_hash != expected_hash:
            raise PersistenceConflict("exchange handoff hash does not match")
        created_at = record.created_at
        expires_at = record.expires_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        current = ExchangePaymentHandoff(
            handoff_id=record.id,
            case_id=record.case_id,
            offer_hash=record.offer_hash,
            approval_hash=record.approval_hash,
            handoff_hash=record.handoff_hash,
            destination_url=record.destination_url,
            recipient=record.recipient,
            amount=record.amount,
            currency=record.currency,
            reference=record.reference,
            created_at=created_at,
            expires_at=expires_at,
            status=record.status,
            opened_at=(
                record.opened_at.replace(tzinfo=UTC)
                if record.opened_at is not None and record.opened_at.tzinfo is None
                else record.opened_at
            ),
        )
        opened = current.open(now=now)
        record.status = opened.status.value
        record.opened_at = opened.opened_at
        await self.session.flush()
        return record
