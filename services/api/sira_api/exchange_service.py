"""Authenticated application service for minimum-disclosure bilateral cases."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from domain import content_hash
from domain.bilateral_exchange import ExchangeParty, PartyCommand
from domain.exchange_contracts import ExchangeEnvelope, ReleaseManifest
from domain.exchange_route import ExchangeRoute, ExchangeRouteCodec, ExchangeRouteError
from persistence.bilateral_repository import BilateralRepository
from persistence.database import Database
from persistence.models import RequirementBriefVersion

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
        async with self.database.transaction(organization_id) as session:
            projection = await BilateralRepository(
                session, organization_id
            ).latest_projection(case_id, party=party)
        return _projection(projection)
