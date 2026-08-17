"""Cockroach persistence for append-only party commands and projections."""

from __future__ import annotations

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

from .models import (
    BilateralExchangeCase,
    BilateralPartyCommand,
    BilateralPartyProjection,
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
