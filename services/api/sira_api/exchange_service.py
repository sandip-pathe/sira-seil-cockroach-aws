"""Authenticated application service for minimum-disclosure bilateral cases."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import select

from domain import content_hash
from domain.bilateral_exchange import CoordinatorState, ExchangeParty, PartyCommand
from domain.exchange_contracts import (
    ExchangeEnvelope,
    OfferApproval,
    OfferLine,
    OfferVersion,
    ReleaseManifest,
)
from domain.exchange_route import ExchangeRoute, ExchangeRouteCodec, ExchangeRouteError
from persistence.bilateral_repository import BilateralRepository
from persistence.database import Database
from persistence.models import BilateralOfferVersion, RequirementBriefVersion
from persistence.repositories import PersistenceConflict, RecordNotFound

from .errors import ApiProblem

_SELLER_SAFE_FIELDS = (
    "category_id",
    "intent",
    "desired_outcome",
    "team",
    "data_profile",
    "hard_requirements",
    "preferences",
    "allowed_stack_context",
    "seller_questions",
)


def _stable_id(prefix: str, *parts: str) -> str:
    digest = content_hash({"parts": parts}).removeprefix("sha256:")[:32]
    return f"{prefix}_{digest}"


def _projection(record: Any) -> dict[str, Any]:
    return {
        "case_id": record.case_id,
        "party": record.party,
        "state": record.state,
        "version": record.version,
        "released": record.released,
        "projection_hash": record.projection_hash,
    }


class ExchangeService:
    def __init__(
        self,
        database: Database,
        route_codec: ExchangeRouteCodec,
        *,
        clock: Any | None = None,
    ) -> None:
        self.database = database
        self.route_codec = route_codec
        self._clock = clock or (lambda: datetime.now(UTC))

    def _decode_route(
        self,
        *,
        organization_id: str,
        party: str | None,
        case_id: str,
        route_capability: str,
    ) -> ExchangeRoute:
        if party not in {"BUYER", "SELLER"}:
            raise ApiProblem(
                code="VERIFIED_PARTY_REQUIRED",
                message="A verified buyer or seller identity is required.",
                status_code=403,
            )
        try:
            route = self.route_codec.decode(
                route_capability,
                organization_id=organization_id,
                now=self._clock(),
            )
        except ExchangeRouteError as error:
            raise ApiProblem(
                code="EXCHANGE_ROUTE_INVALID",
                message="This exchange link is invalid or expired.",
                status_code=403,
            ) from error
        if route.case_id != case_id:
            raise ApiProblem(
                code="EXCHANGE_ROUTE_MISMATCH",
                message="This exchange link belongs to another case.",
                status_code=403,
            )
        expected = (
            route.buyer_organization_id if party == "BUYER" else route.seller_organization_id
        )
        if organization_id != expected:
            raise ApiProblem(
                code="EXCHANGE_PARTY_MISMATCH",
                message="This identity is not the authorized exchange participant.",
                status_code=403,
            )
        return route

    async def _publish_compiled(self, route: ExchangeRoute, compiled: Any) -> None:
        async with self.database.transaction(route.seller_organization_id) as session:
            await BilateralRepository(
                session, route.seller_organization_id
            ).publish_projection(compiled.seller_projection)

    @staticmethod
    def _api_conflict(error: Exception) -> ApiProblem:
        return ApiProblem(
            code="EXCHANGE_CONFLICT",
            message="The exchange changed or this action is no longer valid.",
            status_code=409,
            next_action="refresh_exchange",
            details={"reason": str(error)},
        )

    async def create_case(
        self,
        *,
        organization_id: str,
        actor_id: str,
        party: str | None,
        idempotency_key: str,
        purchase_request_id: str,
        seller_organization_id: str,
    ) -> dict[str, Any]:
        if party != "BUYER":
            raise ApiProblem(
                code="BUYER_IDENTITY_REQUIRED",
                message="Only the buyer may release a Requirement Brief.",
                status_code=403,
            )
        if seller_organization_id == organization_id:
            raise ApiProblem(
                code="DISTINCT_SELLER_REQUIRED",
                message="The seller must belong to a different organization.",
                status_code=409,
            )
        now = self._clock()
        case_id = _stable_id(
            "xcase", organization_id, purchase_request_id, seller_organization_id, idempotency_key
        )
        compiled: Any | None = None
        async with self.database.transaction(organization_id) as session:
            repository = BilateralRepository(session, organization_id)
            existing = await repository.create_case(
                case_id=case_id,
                seller_organization_id=seller_organization_id,
            )
            if existing.version > 1:
                buyer_projection = await repository.latest_projection(case_id, party="BUYER")
                expires_at = now + timedelta(hours=24)
            else:
                requirement = await session.scalar(
                    select(RequirementBriefVersion)
                    .where(
                        RequirementBriefVersion.organization_id == organization_id,
                        RequirementBriefVersion.purchase_request_id == purchase_request_id,
                    )
                    .order_by(RequirementBriefVersion.version.desc())
                    .limit(1)
                )
                if requirement is None:
                    raise ApiProblem(
                        code="REQUIREMENT_BRIEF_MISSING",
                        message=(
                            "Create and approve a Requirement Brief before contacting a seller."
                        ),
                        status_code=409,
                    )
                raw_expiry = requirement.payload.get("expires_at")
                if not isinstance(raw_expiry, str):
                    raise ApiProblem(
                        code="REQUIREMENT_BRIEF_EXPIRY_MISSING",
                        message="The Requirement Brief has no valid sharing expiry.",
                        status_code=409,
                    )
                expires_at = datetime.fromisoformat(raw_expiry.replace("Z", "+00:00"))
                if expires_at <= now + timedelta(seconds=1):
                    raise ApiProblem(
                        code="REQUIREMENT_BRIEF_EXPIRED",
                        message="Refresh the Requirement Brief before sharing it with a seller.",
                        status_code=409,
                        next_action="refresh_requirement_brief",
                    )
                source = {
                    field: requirement.payload[field]
                    for field in _SELLER_SAFE_FIELDS
                    if field in requirement.payload
                }
                if set(source) != set(_SELLER_SAFE_FIELDS):
                    raise ApiProblem(
                        code="REQUIREMENT_BRIEF_INCOMPLETE",
                        message="The Requirement Brief is missing seller-safe decision fields.",
                        status_code=409,
                    )
                public_source = (
                    f"reqbrief_{requirement.content_hash.removeprefix('sha256:')[:16]}"
                )
                approval_payload = {
                    "case_id": case_id,
                    "owner": ExchangeParty.BUYER,
                    "recipient": ExchangeParty.SELLER,
                    "purpose": "Evaluate fit and respond to the buyer's stated requirements.",
                    "fields": _SELLER_SAFE_FIELDS,
                    "transformations": {},
                    "source_versions": {public_source: requirement.version},
                    "expires_at": expires_at,
                }
                manifest = ReleaseManifest(
                    manifest_id=_stable_id("manifest", case_id, requirement.content_hash),
                    case_id=case_id,
                    owner=ExchangeParty.BUYER,
                    recipient=ExchangeParty.SELLER,
                    purpose=approval_payload["purpose"],
                    fields=_SELLER_SAFE_FIELDS,
                    transformations={},
                    source_versions={public_source: requirement.version},
                    expires_at=expires_at,
                    approval_id=_stable_id("releaseapproval", case_id, actor_id),
                    approved_payload_hash=content_hash(approval_payload),
                )
                released = manifest.release(source, now=now)
                envelope = ExchangeEnvelope(
                    envelope_id=_stable_id("envelope", case_id, manifest.manifest_hash),
                    case_id=case_id,
                    sender=ExchangeParty.BUYER,
                    recipient=ExchangeParty.SELLER,
                    sequence=1,
                    causation_id=manifest.approval_id,
                    manifest_hash=manifest.manifest_hash,
                    payload=released,
                    expires_at=expires_at - timedelta(seconds=1),
                )
                command = PartyCommand(
                    id=_stable_id("command", case_id, idempotency_key),
                    case_id=case_id,
                    party=ExchangeParty.BUYER,
                    actor_id=actor_id,
                    command_type="RELEASE_REQUIREMENT",
                    expected_version=1,
                    idempotency_key=idempotency_key,
                    payload={
                        "manifest_hash": manifest.manifest_hash,
                        "envelope_hash": envelope.payload_hash,
                        "requirement": released,
                    },
                )
                await repository.store_release_manifest(manifest)
                await repository.store_envelope(envelope)
                await repository.append_command(command)
                compiled = await repository.apply_command(
                    existing,
                    command,
                    command_organization_id=organization_id,
                )
                buyer_projection = await repository.publish_projection(
                    compiled.buyer_projection
                )

        if compiled is not None:
            async with self.database.transaction(seller_organization_id) as session:
                await BilateralRepository(session, seller_organization_id).publish_projection(
                    compiled.seller_projection
                )
        route = ExchangeRoute(
            case_id=case_id,
            buyer_organization_id=organization_id,
            seller_organization_id=seller_organization_id,
            expires_at=expires_at,
        )
        return {
            "case_id": case_id,
            "route_capability": self.route_codec.encode(route),
            "expires_at": expires_at,
            "projection": _projection(buyer_projection),
        }

    async def view_case(
        self,
        *,
        organization_id: str,
        party: str | None,
        case_id: str,
        route_capability: str,
    ) -> dict[str, Any]:
        self._decode_route(
            organization_id=organization_id,
            party=party,
            case_id=case_id,
            route_capability=route_capability,
        )
        async with self.database.transaction(organization_id) as session:
            projection = await BilateralRepository(
                session, organization_id
            ).latest_projection(case_id, party=cast(str, party))
        return _projection(projection)

    async def publish_evidence(
        self,
        *,
        organization_id: str,
        actor_id: str,
        party: str | None,
        case_id: str,
        route_capability: str,
        idempotency_key: str,
        expected_version: int,
        evidence_hash: str,
        summary: str,
        published_span_ids: list[str],
    ) -> dict[str, Any]:
        route = self._decode_route(
            organization_id=organization_id,
            party=party,
            case_id=case_id,
            route_capability=route_capability,
        )
        if party != "SELLER":
            raise ApiProblem(
                code="SELLER_IDENTITY_REQUIRED",
                message="Only the seller may publish evidence into this exchange.",
                status_code=403,
            )
        command = PartyCommand(
            id=_stable_id("command", case_id, idempotency_key),
            case_id=case_id,
            party=ExchangeParty.SELLER,
            actor_id=actor_id,
            command_type="PUBLISH_EVIDENCE",
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            payload={
                "evidence_hash": evidence_hash,
                "summary": summary,
                "published_span_ids": published_span_ids,
            },
        )
        async with self.database.transaction(organization_id) as session:
            await BilateralRepository(session, organization_id).append_command(command)
        try:
            async with self.database.transaction(route.buyer_organization_id) as session:
                repository = BilateralRepository(session, route.buyer_organization_id)
                exchange = await repository.get_case(case_id, lock=True)
                compiled = await repository.apply_command(
                    exchange,
                    command,
                    command_organization_id=organization_id,
                )
                await repository.publish_projection(compiled.buyer_projection)
        except (PersistenceConflict, RecordNotFound, ValueError) as error:
            raise self._api_conflict(error) from error
        await self._publish_compiled(route, compiled)
        return _projection(compiled.seller_projection)

    async def propose_offer(
        self,
        *,
        organization_id: str,
        actor_id: str,
        party: str | None,
        case_id: str,
        route_capability: str,
        idempotency_key: str,
        expected_version: int,
        currency: str,
        lines: list[dict[str, Any]],
        total: Decimal,
        rationale: str,
        changed_terms: list[str],
        expires_at: datetime,
    ) -> dict[str, Any]:
        route = self._decode_route(
            organization_id=organization_id,
            party=party,
            case_id=case_id,
            route_capability=route_capability,
        )
        party_value = ExchangeParty(str(party))
        try:
            async with self.database.transaction(route.buyer_organization_id) as session:
                repository = BilateralRepository(session, route.buyer_organization_id)
                exchange = await repository.get_case(case_id, lock=True)
                state = CoordinatorState.model_validate(exchange.coordinator_state)
                latest_record = await session.scalar(
                    select(BilateralOfferVersion)
                    .where(
                        BilateralOfferVersion.organization_id
                        == route.buyer_organization_id,
                        BilateralOfferVersion.case_id == case_id,
                    )
                    .order_by(BilateralOfferVersion.version.desc())
                    .limit(1)
                )
                if state.state.value == "EVIDENCE_RELEASED" and party_value is ExchangeParty.BUYER:
                    command_type = "PROPOSE_OFFER"
                    offer_version = 1
                    predecessor_hash = None
                elif state.state.value == "OFFERED" and party_value is ExchangeParty.SELLER:
                    if latest_record is None:
                        raise PersistenceConflict("the current offer is unavailable")
                    command_type = "COUNTER_OFFER"
                    offer_version = latest_record.version + 1
                    predecessor_hash = latest_record.offer_hash
                else:
                    raise PersistenceConflict("this party cannot propose at the current stage")
                requirement = state.requirement or {}
                evidence = state.evidence or {}
                offer = OfferVersion(
                    offer_id=_stable_id("offer", case_id),
                    case_id=case_id,
                    version=offer_version,
                    proposer=party_value,
                    recipient=(
                        ExchangeParty.SELLER
                        if party_value is ExchangeParty.BUYER
                        else ExchangeParty.BUYER
                    ),
                    predecessor_hash=predecessor_hash,
                    changed_terms=tuple(changed_terms),
                    rationale=rationale,
                    currency=currency,
                    lines=tuple(OfferLine.model_validate(line) for line in lines),
                    total=total,
                    expires_at=expires_at,
                    requirement_hash=str(requirement.get("envelope_hash", "")),
                    evidence_hash=str(evidence.get("evidence_hash", "")),
                )
                command = PartyCommand(
                    id=_stable_id("command", case_id, idempotency_key),
                    case_id=case_id,
                    party=party_value,
                    actor_id=actor_id,
                    command_type=command_type,
                    expected_version=expected_version,
                    idempotency_key=idempotency_key,
                    payload=offer.model_dump(mode="json"),
                )
                await repository.store_offer(offer)
                await repository.append_command(command)
                compiled = await repository.apply_command(
                    exchange,
                    command,
                    command_organization_id=organization_id,
                )
                await repository.publish_projection(compiled.buyer_projection)
        except (PersistenceConflict, RecordNotFound, ValueError) as error:
            raise self._api_conflict(error) from error
        await self._publish_compiled(route, compiled)
        selected = compiled.buyer_projection if party == "BUYER" else compiled.seller_projection
        return _projection(selected)

    async def accept_offer(
        self,
        *,
        organization_id: str,
        actor_id: str,
        party: str | None,
        case_id: str,
        route_capability: str,
        idempotency_key: str,
        expected_version: int,
        offer_hash: str,
    ) -> dict[str, Any]:
        route = self._decode_route(
            organization_id=organization_id,
            party=party,
            case_id=case_id,
            route_capability=route_capability,
        )
        party_value = ExchangeParty(str(party))
        try:
            async with self.database.transaction(route.buyer_organization_id) as session:
                repository = BilateralRepository(session, route.buyer_organization_id)
                exchange = await repository.get_case(case_id, lock=True)
                state = CoordinatorState.model_validate(exchange.coordinator_state)
                latest_record = await session.scalar(
                    select(BilateralOfferVersion)
                    .where(
                        BilateralOfferVersion.organization_id
                        == route.buyer_organization_id,
                        BilateralOfferVersion.case_id == case_id,
                    )
                    .order_by(BilateralOfferVersion.version.desc())
                    .limit(1)
                    .with_for_update()
                )
                if latest_record is None or latest_record.offer_hash != offer_hash:
                    raise PersistenceConflict("the accepted offer is not current")
                offer = OfferVersion.model_validate(latest_record.terms)
                offer.assert_actionable(actor=party_value, now=self._clock())
                command_type = (
                    "ACCEPT_OFFER" if state.state.value == "OFFERED" else "ACCEPT_COUNTER"
                )
                command = PartyCommand(
                    id=_stable_id("command", case_id, idempotency_key),
                    case_id=case_id,
                    party=party_value,
                    actor_id=actor_id,
                    command_type=command_type,
                    expected_version=expected_version,
                    idempotency_key=idempotency_key,
                    payload={"offer_hash": offer_hash},
                )
                await repository.append_command(command)
                compiled = await repository.apply_command(
                    exchange,
                    command,
                    command_organization_id=organization_id,
                )
                await repository.publish_projection(compiled.buyer_projection)
        except (PersistenceConflict, RecordNotFound, ValueError) as error:
            raise self._api_conflict(error) from error
        await self._publish_compiled(route, compiled)
        selected = compiled.buyer_projection if party == "BUYER" else compiled.seller_projection
        return _projection(selected)

    async def approve_offer(
        self,
        *,
        organization_id: str,
        actor_id: str,
        party: str | None,
        case_id: str,
        route_capability: str,
        idempotency_key: str,
        expected_version: int,
        offer_hash: str,
        approval_expires_at: datetime,
    ) -> dict[str, Any]:
        route = self._decode_route(
            organization_id=organization_id,
            party=party,
            case_id=case_id,
            route_capability=route_capability,
        )
        if party != "BUYER":
            raise ApiProblem(
                code="BUYER_APPROVAL_REQUIRED",
                message="Only an authorized buyer may approve exact commercial terms.",
                status_code=403,
            )
        now = self._clock()
        try:
            async with self.database.transaction(route.buyer_organization_id) as session:
                repository = BilateralRepository(session, route.buyer_organization_id)
                exchange = await repository.get_case(case_id, lock=True)
                approval = OfferApproval(
                    approval_id=_stable_id("offerapproval", case_id, idempotency_key),
                    case_id=case_id,
                    offer_hash=offer_hash,
                    approver_id=actor_id,
                    approved_at=now,
                    expires_at=approval_expires_at,
                )
                await repository.approve_offer(approval, now=now)
                command = PartyCommand(
                    id=_stable_id("command", case_id, idempotency_key),
                    case_id=case_id,
                    party=ExchangeParty.SYSTEM,
                    actor_id=actor_id,
                    command_type="APPROVE_HANDOFF",
                    expected_version=expected_version,
                    idempotency_key=idempotency_key,
                    payload={
                        "offer_hash": offer_hash,
                        "approval_id": approval.approval_id,
                        "approval_hash": content_hash(approval.model_dump(mode="json")),
                    },
                )
                await repository.append_command(command)
                compiled = await repository.apply_command(
                    exchange,
                    command,
                    command_organization_id=organization_id,
                )
                await repository.publish_projection(compiled.buyer_projection)
        except (PersistenceConflict, RecordNotFound, ValueError) as error:
            raise self._api_conflict(error) from error
        await self._publish_compiled(route, compiled)
        return _projection(compiled.buyer_projection)
