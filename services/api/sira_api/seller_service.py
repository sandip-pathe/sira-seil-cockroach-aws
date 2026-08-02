"""Tenant-scoped seller Product Evidence application service."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from html import escape
from typing import Any, Literal, cast
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain import content_hash
from domain.enums import ActorRole, PackAuthority, SellerEvidenceState
from persistence.database import Database
from persistence.models import (
    Organization,
    SellerActivityEvent,
    SellerEvidenceAttachment,
    SellerPackDraft,
    SellerPackDraftRevision,
    SellerPackExportArtifact,
    SellerPackSuspension,
    SellerPackVersion,
    SellerProduct,
    SellerProductClaim,
    SellerReviewDecisionRecord,
    SellerReviewSubmission,
)
from persistence.repositories import WorkflowRepository, new_id

from .errors import ApiProblem

SellerActorRole = Literal["SELLER_EDITOR", "SELLER_REVIEWER", "PLATFORM_OPERATOR"]

DEMO_ORGANIZATION_ID = "org_consultco"
DEMO_FIXTURE_LABEL = "DEVELOPMENT_FIXTURE_NON_PRODUCTION"
AUTHORITY_COPY = (
    "Publisher authority identifies who stands behind this package; it does not mean "
    "every claim was independently verified."
)

_ALLOWED_CLAIM_FIELDS = frozenset(
    {
        "product_name",
        "public_summary",
        "data_retention_days",
        "supported_regions",
        "sso_supported",
        "security_certifications",
        "deployment_modes",
        "public_documentation_url",
        "annual_price_usd",
        "reusable_answer",
    }
)
_ALLOWED_FIT_FIELDS = frozenset(
    {
        "employee_count_min",
        "employee_count_max",
        "supported_regions",
        "supported_categories",
        "supported_deployment_modes",
        "required_integrations",
    }
)
_ALLOWED_ANTI_FIT_FIELDS = frozenset(
    {
        "regulated_data_prohibited",
        "region_exclusions",
        "unsupported_integrations",
        "unsupported_deployment_modes",
        "employee_count_max",
    }
)
_REQUIRED_CLAIMS = (
    "product_name",
    "public_summary",
    "data_retention_days",
    "supported_regions",
)
_SOURCE_CLASSES = frozenset(
    {
        "VENDOR_DOCUMENTATION",
        "SECURITY_ATTESTATION",
        "CONTRACT",
        "PUBLIC_WEB",
        "SELLER_ASSERTION",
    }
)
_EDITABLE_STATES = frozenset(
    {
        SellerEvidenceState.SELLER_DRAFT.value,
        SellerEvidenceState.VALIDATION_CONFLICT.value,
        SellerEvidenceState.CHANGES_REQUESTED.value,
    }
)


def _now() -> datetime:
    return datetime.now(UTC)


def _timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _public_source_url(source_reference: str) -> str | None:
    """Return only a credential-free HTTPS reference suitable for publication."""

    try:
        parsed = urlsplit(source_reference)
    except ValueError:
        return None
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
    ):
        return None
    return urlunsplit(("https", parsed.netloc.lower(), parsed.path or "/", "", ""))


def _claim_payload(
    claims: list[dict[str, Any]],
    fit_rules: list[dict[str, Any]],
    anti_fit_rules: list[dict[str, Any]],
    *,
    product_id: str,
    publisher_authority: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "product_id": product_id,
        "publisher_authority": publisher_authority,
        "claims": claims,
        "fit_rules": fit_rules,
        "anti_fit_rules": anti_fit_rules,
    }


def _authority_label(authority: str) -> str:
    return {
        PackAuthority.SELLER_SEALED.value: "Published by vendor",
        PackAuthority.PLATFORM_COMPILED.value: "Compiled by Seilnsara",
        PackAuthority.EXTERNAL_UNSEALED.value: "External, not claimed",
    }[authority]


class SellerEvidenceService:
    """Canonical seller workflow with no dependency on provider or agent runtimes."""

    def __init__(self, database: Database, *, development_fixture_mode: bool) -> None:
        self.database = database
        self.development_fixture_mode = development_fixture_mode

    async def search_products(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_role: SellerActorRole,
        query: str | None,
    ) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            await self._ensure_demo(session, organization_id)
            statement = select(SellerProduct).where(
                SellerProduct.organization_id == organization_id
            )
            products = list((await session.execute(statement)).scalars())

            term = (query or "").strip().casefold()
            rows: list[dict[str, Any]] = []
            for product in products:
                if actor_role == "SELLER_EDITOR" and product.state != "UNCLAIMED":
                    if product.owner_actor_id != actor_id:
                        continue
                if term and term not in f"{product.name} {product.category}".casefold():
                    continue
                rows.append(self._search_item(product))
            rows.sort(key=lambda item: (str(item["name"]).casefold(), str(item["id"])))
            return {"results": rows}

    async def claim_product(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_role: SellerActorRole,
        product_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        requested_role = str(body.get("requested_role", "SELLER_EDITOR"))
        if requested_role not in {"SELLER_EDITOR", "SELLER_REVIEWER"}:
            raise self._problem(
                "SELLER_CLAIM_ROLE_INVALID", "The requested seller role is invalid."
            )
        if actor_role != "PLATFORM_OPERATOR" and requested_role != actor_role:
            raise self._forbidden("SELLER_CLAIM_ROLE_MISMATCH")

        request_hash = content_hash({"product_id": product_id, **body})
        async with self.database.transaction(organization_id) as session:
            await self._ensure_demo(session, organization_id)
            repository = WorkflowRepository(session, organization_id)
            idem = await repository.claim_idempotency(
                actor_id=actor_id,
                operation=f"seller.products.{product_id}.claim",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if idem.replay:
                return int(idem.record.response_status or 201), dict(
                    idem.record.response_payload or {}
                )

            product = await self._product(session, organization_id, product_id, lock=True)
            if product.state not in {"UNCLAIMED", "CLAIM_DENIED"}:
                raise self._problem(
                    "SELLER_PRODUCT_ALREADY_CLAIMED",
                    "This product is not available for a new seller claim.",
                    status_code=409,
                )
            now = _now()
            proof_hash = content_hash(
                {
                    "product_id": product_id,
                    "claimant_actor_id": actor_id,
                    "authority_proof_reference": body["authority_proof_reference"],
                }
            )
            record = SellerProductClaim(
                id=new_id("sclaim"),
                organization_id=organization_id,
                product_id=product_id,
                claimant_actor_id=actor_id,
                requested_role=requested_role,
                authority_proof_hash=proof_hash,
                state=SellerEvidenceState.CLAIM_PENDING.value,
                safe_reason=None,
                decided_by_actor_id=None,
                decided_at=None,
                created_at=now,
                updated_at=now,
            )
            session.add(record)
            product.state = SellerEvidenceState.CLAIM_PENDING.value
            product.owner_actor_id = actor_id
            product.updated_at = now
            response = {
                "claim_id": record.id,
                "product_id": product_id,
                "state": record.state,
                "submitted_at": _timestamp(now),
                "safe_reason": None,
            }
            await repository.add_outbox(
                aggregate_type="seller_product",
                aggregate_id=product_id,
                event_type="seller_product.claim_submitted",
                event_key=f"seller-claim:{record.id}",
                payload={
                    "claim_id": record.id,
                    "product_id": product_id,
                    "authority_proof_hash": proof_hash,
                },
            )
            await repository.complete_idempotency(
                idem.record,
                response_status=201,
                response_payload=response,
                response_reference=record.id,
            )
            return 201, response

    async def get_product_view(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_role: SellerActorRole,
        product_id: str,
    ) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            await self._ensure_demo(session, organization_id)
            product = await self._product(session, organization_id, product_id)
            self._require_product_access(product, actor_id, actor_role, allow_unclaimed=True)
            draft = await self._draft_for_product(session, organization_id, product_id)
            revision = (
                await self._revision(session, organization_id, draft) if draft is not None else None
            )
            submission = (
                await self._latest_submission(session, organization_id, draft.id)
                if draft is not None
                else None
            )
            review = (
                await self._decision_for_submission(session, organization_id, submission.id)
                if submission is not None
                else None
            )
            pack = await self._current_pack(session, organization_id, product)
            metrics = await self._activity_metrics(session, organization_id, product_id)
            validation = (
                dict(draft.validation) if draft is not None else {"status": "NOT_RUN", "gaps": []}
            )
            health = await self._pack_health(session, organization_id, draft, revision, validation)
            capabilities = self._capabilities(product, draft, actor_id, actor_role)
            actions = self._actions(product, draft, actor_id, actor_role)
            formats = ["JSON", "HTML", "REUSABLE_ANSWER"] if pack is not None else []
            answer_count = len(cast(list[object], pack.payload.get("claims", []))) if pack else 0
            return {
                "product": {
                    "id": product.id,
                    "name": product.name,
                    "seller_state": product.state,
                    "current_version": product.current_version,
                    "href": f"/seller/product-evidence/{product.id}",
                },
                "actor": {"role": actor_role, "capabilities": capabilities},
                "publisher_authority": {
                    "value": product.publisher_authority,
                    "label": _authority_label(product.publisher_authority),
                    "supporting_copy": AUTHORITY_COPY,
                },
                "pack_health": health,
                "validation": validation,
                "review": self._review_summary(submission, review),
                "reusable_answers": {
                    "published_version": pack.version if pack else None,
                    "published_answer_count": answer_count,
                    "formats": formats,
                    "href": (f"/v1/seller/pack-versions/{pack.id}/exports" if pack else None),
                },
                "activity_metrics": metrics,
                "available_actions": actions,
                "version_links": {
                    "current": (
                        f"/seller/product-evidence/{product.id}/versions/{product.current_version}"
                    ),
                    "previous": (
                        f"/seller/product-evidence/{product.id}/versions/"
                        f"{product.current_version - 1}"
                        if product.current_version > 1
                        else None
                    ),
                },
            }

    async def get_draft(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_role: SellerActorRole,
        draft_id: str,
    ) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            await self._ensure_demo(session, organization_id)
            draft = await self._draft(session, organization_id, draft_id)
            product = await self._product(session, organization_id, draft.product_id)
            self._require_product_access(product, actor_id, actor_role)
            revision = await self._revision(session, organization_id, draft)
            return self._draft_view(draft, revision)

    async def patch_draft(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_role: SellerActorRole,
        draft_id: str,
        idempotency_key: str,
        body: dict[str, Any],
        provided_fields: frozenset[str],
    ) -> tuple[int, dict[str, Any]]:
        if actor_role not in {"SELLER_EDITOR", "PLATFORM_OPERATOR"}:
            raise self._forbidden("SELLER_EDIT_ROLE_REQUIRED")
        request_hash = content_hash({"draft_id": draft_id, **body})
        async with self.database.transaction(organization_id) as session:
            await self._ensure_demo(session, organization_id)
            repository = WorkflowRepository(session, organization_id)
            idem = await repository.claim_idempotency(
                actor_id=actor_id,
                operation=f"seller.pack_drafts.{draft_id}.patch",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if idem.replay:
                return int(idem.record.response_status or 200), dict(
                    idem.record.response_payload or {}
                )
            draft = await self._draft(session, organization_id, draft_id, lock=True)
            product = await self._product(session, organization_id, draft.product_id)
            self._require_product_access(product, actor_id, actor_role)
            if draft.state not in _EDITABLE_STATES:
                raise self._problem(
                    "SELLER_DRAFT_FROZEN",
                    "This revision is read-only in its current review or publication state.",
                    status_code=409,
                )
            if int(body["base_revision"]) != draft.current_revision:
                raise self._problem(
                    "SELLER_DRAFT_REVISION_CONFLICT",
                    "The draft changed; reload the latest revision before editing.",
                    status_code=409,
                )
            current = await self._revision(session, organization_id, draft)
            claims = list(body["claims"]) if "claims" in provided_fields else list(current.claims)
            fit_rules = (
                list(body["fit_rules"])
                if "fit_rules" in provided_fields
                else list(current.fit_rules)
            )
            anti_fit_rules = (
                list(body["anti_fit_rules"])
                if "anti_fit_rules" in provided_fields
                else list(current.anti_fit_rules)
            )
            self._validate_publication_fields(claims, fit_rules, anti_fit_rules)
            evidence = await self._evidence_map(session, organization_id, draft.id)
            self._validate_evidence_links(claims + fit_rules + anti_fit_rules, evidence)
            validation = self._validate_revision(
                product.id, claims, fit_rules, anti_fit_rules, evidence, now=_now()
            )
            revision_number = draft.current_revision + 1
            revision_payload = _claim_payload(
                claims,
                fit_rules,
                anti_fit_rules,
                product_id=product.id,
                publisher_authority=draft.publisher_authority,
            )
            revision_hash = content_hash(revision_payload)
            now = _now()
            snapshot = SellerPackDraftRevision(
                id=new_id("sdrev"),
                organization_id=organization_id,
                draft_id=draft.id,
                revision=revision_number,
                revision_hash=revision_hash,
                claims=claims,
                fit_rules=fit_rules,
                anti_fit_rules=anti_fit_rules,
                validation=validation,
                created_by_actor_id=actor_id,
                created_at=now,
                frozen_at=None,
            )
            session.add(snapshot)
            draft.current_revision = revision_number
            draft.current_revision_hash = revision_hash
            draft.validation = validation
            draft.state = SellerEvidenceState.SELLER_DRAFT.value
            draft.submitted_at = None
            draft.frozen_at = None
            draft.updated_at = now
            product.state = draft.state
            product.current_version += 1
            product.updated_at = now
            response = self._draft_view(draft, snapshot)
            await repository.add_outbox(
                aggregate_type="seller_pack_draft",
                aggregate_id=draft.id,
                event_type="seller_pack_draft.revised",
                event_key=f"seller-draft-revised:{draft.id}:{revision_number}",
                payload={
                    "draft_id": draft.id,
                    "revision": revision_number,
                    "revision_hash": revision_hash,
                },
            )
            await repository.complete_idempotency(
                idem.record,
                response_status=200,
                response_payload=response,
                response_reference=draft.id,
            )
            return 200, response

    async def attach_evidence(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_role: SellerActorRole,
        draft_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        if actor_role not in {"SELLER_EDITOR", "PLATFORM_OPERATOR"}:
            raise self._forbidden("SELLER_EVIDENCE_ROLE_REQUIRED")
        source_class = str(body["source_class"]).upper()
        if source_class not in _SOURCE_CLASSES:
            raise self._problem(
                "SELLER_EVIDENCE_SOURCE_CLASS_INVALID",
                "The evidence source class is not supported.",
            )
        claim_fields = sorted(set(cast(list[str], body["claim_fields"])))
        if len(claim_fields) != len(cast(list[str], body["claim_fields"])):
            raise self._problem(
                "SELLER_EVIDENCE_FIELDS_DUPLICATED",
                "Evidence claim fields must be unique.",
            )
        allowed = _ALLOWED_CLAIM_FIELDS | _ALLOWED_FIT_FIELDS | _ALLOWED_ANTI_FIT_FIELDS
        if any(field not in allowed for field in claim_fields):
            raise self._problem(
                "SELLER_PUBLICATION_FIELD_FORBIDDEN",
                "Evidence may reference only approved Product Evidence fields.",
                status_code=403,
            )
        request_hash = content_hash({"draft_id": draft_id, **body, "source_class": source_class})
        async with self.database.transaction(organization_id) as session:
            await self._ensure_demo(session, organization_id)
            repository = WorkflowRepository(session, organization_id)
            idem = await repository.claim_idempotency(
                actor_id=actor_id,
                operation=f"seller.pack_drafts.{draft_id}.evidence",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if idem.replay:
                return int(idem.record.response_status or 201), dict(
                    idem.record.response_payload or {}
                )
            draft = await self._draft(session, organization_id, draft_id, lock=True)
            product = await self._product(session, organization_id, draft.product_id)
            self._require_product_access(product, actor_id, actor_role)
            if draft.state not in _EDITABLE_STATES:
                raise self._problem(
                    "SELLER_DRAFT_FROZEN",
                    "Evidence cannot be changed while this revision is frozen.",
                    status_code=409,
                )
            source_reference = str(body["source_reference"])
            source_hash = content_hash({"source_reference": source_reference})
            existing = (
                await session.execute(
                    select(SellerEvidenceAttachment).where(
                        SellerEvidenceAttachment.organization_id == organization_id,
                        SellerEvidenceAttachment.draft_id == draft.id,
                        SellerEvidenceAttachment.source_reference_hash == source_hash,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                if existing.source_class != source_class or existing.claim_fields != claim_fields:
                    raise self._problem(
                        "SELLER_EVIDENCE_SOURCE_CONFLICT",
                        "This evidence reference is already attached with different metadata.",
                        status_code=409,
                    )
                response = self._evidence_view(existing)
                await repository.complete_idempotency(
                    idem.record,
                    response_status=200,
                    response_payload=response,
                    response_reference=existing.id,
                )
                return 200, response
            now = _now()
            record = SellerEvidenceAttachment(
                id=new_id("sevd"),
                organization_id=organization_id,
                draft_id=draft.id,
                attached_revision=draft.current_revision,
                source_reference_hash=source_hash,
                public_source_url=_public_source_url(source_reference),
                source_class=source_class,
                claim_fields=claim_fields,
                observed_at=body.get("observed_at"),
                verification_state="UNVERIFIED",
                verification_actor_id=None,
                verification_method=None,
                added_by_actor_id=actor_id,
                created_at=now,
                updated_at=now,
            )
            session.add(record)
            response = self._evidence_view(record)
            await repository.add_outbox(
                aggregate_type="seller_pack_draft",
                aggregate_id=draft.id,
                event_type="seller_evidence.attached",
                event_key=f"seller-evidence-attached:{record.id}",
                payload={
                    "draft_id": draft.id,
                    "evidence_id": record.id,
                    "source_reference_hash": source_hash,
                    "verification_state": record.verification_state,
                },
            )
            await repository.complete_idempotency(
                idem.record,
                response_status=201,
                response_payload=response,
                response_reference=record.id,
            )
            return 201, response

    async def submit_review(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_role: SellerActorRole,
        draft_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        if actor_role not in {"SELLER_EDITOR", "PLATFORM_OPERATOR"}:
            raise self._forbidden("SELLER_SUBMIT_ROLE_REQUIRED")
        request_hash = content_hash({"draft_id": draft_id, **body})
        failure: ApiProblem | None = None
        response: dict[str, Any] = {}
        async with self.database.transaction(organization_id) as session:
            await self._ensure_demo(session, organization_id)
            repository = WorkflowRepository(session, organization_id)
            idem = await repository.claim_idempotency(
                actor_id=actor_id,
                operation=f"seller.pack_drafts.{draft_id}.submit_review",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if idem.replay:
                return int(idem.record.response_status or 200), dict(
                    idem.record.response_payload or {}
                )
            draft = await self._draft(session, organization_id, draft_id, lock=True)
            product = await self._product(session, organization_id, draft.product_id)
            self._require_product_access(product, actor_id, actor_role)
            if draft.state not in _EDITABLE_STATES:
                raise self._problem(
                    "SELLER_DRAFT_NOT_SUBMITTABLE",
                    "This draft cannot be submitted from its current state.",
                    status_code=409,
                )
            self._require_exact_hash(draft.current_revision_hash, str(body["revision_hash"]))
            revision = await self._revision(session, organization_id, draft)
            evidence = await self._evidence_map(session, organization_id, draft.id)
            validation = self._validate_revision(
                product.id,
                list(revision.claims),
                list(revision.fit_rules),
                list(revision.anti_fit_rules),
                evidence,
                now=_now(),
            )
            if validation["status"] != "VALID":
                draft.validation = validation
                draft.state = SellerEvidenceState.VALIDATION_CONFLICT.value
                product.state = draft.state
                draft.updated_at = _now()
                response = self._draft_view(draft, revision)
                failure = ApiProblem(
                    code="SELLER_DRAFT_VALIDATION_FAILED",
                    message="Resolve the safe validation gaps before review.",
                    status_code=409,
                    next_action="resolve_product_evidence_gaps",
                    details={"validation": validation},
                )
            else:
                now = _now()
                submission = SellerReviewSubmission(
                    id=new_id("sreview"),
                    organization_id=organization_id,
                    draft_id=draft.id,
                    revision=draft.current_revision,
                    revision_hash=draft.current_revision_hash,
                    submitted_by_actor_id=actor_id,
                    reviewer_role=ActorRole.SELLER_REVIEWER.value,
                    status="PENDING",
                    submitted_at=now,
                    completed_at=None,
                )
                session.add(submission)
                revision.frozen_at = now
                draft.validation = validation
                draft.state = SellerEvidenceState.IN_REVIEW.value
                draft.submitted_at = now
                draft.frozen_at = now
                draft.updated_at = now
                product.state = draft.state
                product.updated_at = now
                response = self._draft_view(draft, revision)
                await repository.add_outbox(
                    aggregate_type="seller_pack_draft",
                    aggregate_id=draft.id,
                    event_type="seller_pack_draft.review_submitted",
                    event_key=f"seller-review-submitted:{submission.id}",
                    payload={
                        "draft_id": draft.id,
                        "review_id": submission.id,
                        "revision_hash": submission.revision_hash,
                    },
                )
                await repository.complete_idempotency(
                    idem.record,
                    response_status=200,
                    response_payload=response,
                    response_reference=submission.id,
                )
        if failure is not None:
            raise failure
        return 200, response

    async def review_decision(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_role: SellerActorRole,
        draft_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        if actor_role not in {"SELLER_REVIEWER", "PLATFORM_OPERATOR"}:
            raise self._forbidden("SELLER_REVIEW_ROLE_REQUIRED")
        request_hash = content_hash({"draft_id": draft_id, **body})
        async with self.database.transaction(organization_id) as session:
            await self._ensure_demo(session, organization_id)
            repository = WorkflowRepository(session, organization_id)
            idem = await repository.claim_idempotency(
                actor_id=actor_id,
                operation=f"seller.pack_drafts.{draft_id}.review_decision",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if idem.replay:
                return int(idem.record.response_status or 201), dict(
                    idem.record.response_payload or {}
                )
            draft = await self._draft(session, organization_id, draft_id, lock=True)
            product = await self._product(session, organization_id, draft.product_id)
            self._require_product_access(product, actor_id, actor_role)
            if draft.state != SellerEvidenceState.IN_REVIEW.value:
                raise self._problem(
                    "SELLER_REVIEW_NOT_PENDING",
                    "There is no frozen revision awaiting a review decision.",
                    status_code=409,
                )
            self._require_exact_hash(draft.current_revision_hash, str(body["revision_hash"]))
            submission = await self._latest_submission(
                session, organization_id, draft.id, lock=True
            )
            if submission is None or submission.status != "PENDING":
                raise self._problem(
                    "SELLER_REVIEW_NOT_PENDING",
                    "There is no frozen revision awaiting a review decision.",
                    status_code=409,
                )
            if actor_id in {draft.editor_actor_id, submission.submitted_by_actor_id}:
                raise self._forbidden("SELLER_EDITOR_REVIEWER_SEPARATION_REQUIRED")
            decision_value = str(body["decision"])
            now = _now()
            event = SellerReviewDecisionRecord(
                id=new_id("srdec"),
                organization_id=organization_id,
                submission_id=submission.id,
                draft_id=draft.id,
                decision=decision_value,
                revision_hash=draft.current_revision_hash,
                actor_id=actor_id,
                actor_role=actor_role,
                reason=str(body["reason"]),
                event_key=f"seller-review-decision:{idem.record.id}",
                occurred_at=now,
            )
            session.add(event)
            submission.status = "COMPLETED"
            submission.completed_at = now
            draft.state = (
                SellerEvidenceState.PUBLISH_READY.value
                if decision_value == "APPROVE"
                else SellerEvidenceState.CHANGES_REQUESTED.value
            )
            draft.updated_at = now
            product.state = draft.state
            product.updated_at = now
            response = {
                "id": event.id,
                "draft_id": draft.id,
                "decision": decision_value,
                "revision_hash": event.revision_hash,
                "actor_role": actor_role,
                "reason": event.reason,
                "occurred_at": _timestamp(now),
            }
            await repository.add_outbox(
                aggregate_type="seller_pack_draft",
                aggregate_id=draft.id,
                event_type="seller_pack_draft.review_decided",
                event_key=f"outbox:{event.event_key}",
                payload={
                    "review_decision_id": event.id,
                    "draft_id": draft.id,
                    "decision": decision_value,
                    "revision_hash": event.revision_hash,
                },
            )
            await repository.complete_idempotency(
                idem.record,
                response_status=201,
                response_payload=response,
                response_reference=event.id,
            )
            return 201, response

    async def publish(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_role: SellerActorRole,
        draft_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        if actor_role not in {"SELLER_REVIEWER", "PLATFORM_OPERATOR"}:
            raise self._forbidden("SELLER_PUBLISH_ROLE_REQUIRED")
        request_hash = content_hash({"draft_id": draft_id, **body})
        async with self.database.transaction(organization_id) as session:
            await self._ensure_demo(session, organization_id)
            repository = WorkflowRepository(session, organization_id)
            idem = await repository.claim_idempotency(
                actor_id=actor_id,
                operation=f"seller.pack_drafts.{draft_id}.publish",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if idem.replay:
                return int(idem.record.response_status or 201), dict(
                    idem.record.response_payload or {}
                )
            draft = await self._draft(session, organization_id, draft_id, lock=True)
            product = await self._product(session, organization_id, draft.product_id, lock=True)
            self._require_product_access(product, actor_id, actor_role)
            if draft.state != SellerEvidenceState.PUBLISH_READY.value:
                raise self._problem(
                    "SELLER_DRAFT_NOT_PUBLISH_READY",
                    "Only an independently approved frozen revision can be published.",
                    status_code=409,
                )
            self._require_exact_hash(draft.current_revision_hash, str(body["revision_hash"]))
            submission = await self._latest_submission(session, organization_id, draft.id)
            decision = (
                await self._decision_for_submission(session, organization_id, submission.id)
                if submission is not None
                else None
            )
            if decision is None or decision.decision != "APPROVE":
                raise self._problem(
                    "SELLER_REVIEW_APPROVAL_REQUIRED",
                    "A matching immutable reviewer approval is required.",
                    status_code=409,
                )
            revision = await self._revision(session, organization_id, draft)
            evidence = await self._evidence_map(session, organization_id, draft.id)
            version_number = await self._next_pack_version(session, organization_id, product.id)
            now = _now()
            published_payload = self._published_payload(
                product,
                draft,
                revision,
                evidence,
                version_number=version_number,
                published_at=now,
            )
            pack_hash = content_hash(published_payload)
            pack = SellerPackVersion(
                id=new_id("pack"),
                organization_id=organization_id,
                product_id=product.id,
                source_draft_id=draft.id,
                source_revision=draft.current_revision,
                source_revision_hash=draft.current_revision_hash,
                version=version_number,
                content_hash=pack_hash,
                publisher_authority=draft.publisher_authority,
                payload=published_payload,
                published_by_actor_id=actor_id,
                published_at=now,
                superseded_by_version_id=None,
            )
            session.add(pack)
            previous = await self._current_pack(session, organization_id, product)
            if previous is not None:
                previous.superseded_by_version_id = pack.id
            await session.flush()
            await self._create_exports(session, organization_id, pack)
            product.current_pack_version_id = pack.id
            product.state = SellerEvidenceState.PUBLISHED.value
            product.publisher_authority = PackAuthority.SELLER_SEALED.value
            product.current_version += 1
            product.updated_at = now
            draft.state = SellerEvidenceState.PUBLISHED.value
            draft.updated_at = now
            response = self._pack_view(pack)
            await repository.add_outbox(
                aggregate_type="seller_pack_version",
                aggregate_id=pack.id,
                event_type="seller_pack_version.published",
                event_key=f"seller-pack-published:{pack.id}",
                payload={
                    "pack_version_id": pack.id,
                    "product_id": product.id,
                    "version": version_number,
                    "content_hash": pack_hash,
                    "publisher_authority": pack.publisher_authority,
                },
            )
            await repository.complete_idempotency(
                idem.record,
                response_status=201,
                response_payload=response,
                response_reference=pack.id,
            )
            return 201, response

    async def suspend(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_role: SellerActorRole,
        version_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        if actor_role not in {"SELLER_REVIEWER", "PLATFORM_OPERATOR"}:
            raise self._forbidden("SELLER_SUSPEND_ROLE_REQUIRED")
        request_hash = content_hash({"version_id": version_id, **body})
        async with self.database.transaction(organization_id) as session:
            await self._ensure_demo(session, organization_id)
            repository = WorkflowRepository(session, organization_id)
            idem = await repository.claim_idempotency(
                actor_id=actor_id,
                operation=f"seller.pack_versions.{version_id}.suspend",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if idem.replay:
                return int(idem.record.response_status or 200), dict(
                    idem.record.response_payload or {}
                )
            pack = await self._pack(session, organization_id, version_id)
            product = await self._product(session, organization_id, pack.product_id)
            self._require_product_access(product, actor_id, actor_role)
            now = _now()
            record = SellerPackSuspension(
                id=new_id("ssusp"),
                organization_id=organization_id,
                pack_version_id=pack.id,
                reason=str(body["reason"]),
                effective_at=cast(datetime, body["effective_at"]),
                actor_id=actor_id,
                event_key=f"seller-pack-suspended:{idem.record.id}",
                created_at=now,
            )
            session.add(record)
            response = self._pack_view(pack)
            await repository.add_outbox(
                aggregate_type="seller_pack_version",
                aggregate_id=pack.id,
                event_type="seller_pack_version.suspended",
                event_key=f"outbox:{record.event_key}",
                payload={
                    "pack_version_id": pack.id,
                    "suspension_id": record.id,
                    "effective_at": _timestamp(record.effective_at),
                    "reason_hash": content_hash({"reason": record.reason}),
                },
            )
            await repository.complete_idempotency(
                idem.record,
                response_status=200,
                response_payload=response,
                response_reference=record.id,
            )
            return 200, response

    async def get_exports(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_role: SellerActorRole,
        version_id: str,
    ) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            await self._ensure_demo(session, organization_id)
            pack = await self._pack(session, organization_id, version_id)
            product = await self._product(session, organization_id, pack.product_id)
            self._require_product_access(product, actor_id, actor_role)
            artifacts = list(
                (
                    await session.execute(
                        select(SellerPackExportArtifact)
                        .where(
                            SellerPackExportArtifact.organization_id == organization_id,
                            SellerPackExportArtifact.pack_version_id == pack.id,
                        )
                        .order_by(SellerPackExportArtifact.format)
                    )
                ).scalars()
            )
            summary = self._verification_summary(pack.payload)
            return {
                "exports": [
                    {
                        "format": artifact.format,
                        "pack_id": pack.id,
                        "pack_version": pack.version,
                        "publisher_authority": pack.publisher_authority,
                        "verification_summary": summary,
                        "generated_at": _timestamp(artifact.generated_at),
                        "content_hash": artifact.content_hash,
                        "href": (
                            f"/v1/seller/pack-versions/{pack.id}/exports?format={artifact.format}"
                        ),
                    }
                    for artifact in artifacts
                ]
            }

    async def activity_metrics(
        self,
        *,
        organization_id: str,
        actor_id: str,
        actor_role: SellerActorRole,
        product_id: str,
    ) -> dict[str, Any]:
        async with self.database.transaction(organization_id) as session:
            await self._ensure_demo(session, organization_id)
            product = await self._product(session, organization_id, product_id)
            self._require_product_access(product, actor_id, actor_role)
            return await self._activity_metrics(session, organization_id, product_id)

    async def _ensure_demo(self, session: AsyncSession, organization_id: str) -> None:
        if not self.development_fixture_mode or organization_id != DEMO_ORGANIZATION_ID:
            return
        existing = await session.get(SellerProduct, "product_fixture_d")
        if existing is not None:
            return
        organization = await session.get(Organization, organization_id)
        if organization is None:
            session.add(
                Organization(id=organization_id, name="ConsultCo (fictional fixture)", version=1)
            )
            await session.flush()

        now = _now()
        product = SellerProduct(
            id="product_fixture_d",
            organization_id=organization_id,
            name="Fixture D",
            category="meeting-intelligence",
            public_summary=(
                "Fictional development Product Evidence fixture; no production seller "
                "integration is implied."
            ),
            publisher_authority=PackAuthority.SELLER_SEALED.value,
            state=SellerEvidenceState.SELLER_DRAFT.value,
            owner_actor_id="seller_fixture_d",
            current_draft_id="draft_fixture_d",
            current_pack_version_id="pack_fixture_d_v1",
            current_version=2,
            fixture_label=DEMO_FIXTURE_LABEL,
            created_at=now,
            updated_at=now,
        )
        unclaimed = SellerProduct(
            id="product_fixture_unclaimed",
            organization_id=organization_id,
            name="Fixture Research One",
            category="meeting-intelligence",
            public_summary=(
                "Fictional provisional development record; not a successful production claim."
            ),
            publisher_authority=PackAuthority.PLATFORM_COMPILED.value,
            state=SellerEvidenceState.UNCLAIMED.value,
            owner_actor_id=None,
            current_draft_id=None,
            current_pack_version_id=None,
            current_version=1,
            fixture_label=DEMO_FIXTURE_LABEL,
            created_at=now,
            updated_at=now,
        )
        initial_claims: list[dict[str, Any]] = [
            {"field": "product_name", "value": "Fixture D", "evidence_ids": []},
            {
                "field": "public_summary",
                "value": "Meeting intelligence for governed enterprise workflows.",
                "evidence_ids": ["sevd_fixture_d_stale"],
            },
            {"field": "supported_regions", "value": ["US"], "evidence_ids": []},
            {"field": "sso_supported", "value": True, "evidence_ids": []},
        ]
        fit_rules: list[dict[str, Any]] = [
            {"field": "employee_count_min", "value": 25, "evidence_ids": []}
        ]
        anti_fit_rules: list[dict[str, Any]] = [
            {"field": "regulated_data_prohibited", "value": True, "evidence_ids": []}
        ]
        revision_payload = _claim_payload(
            initial_claims,
            fit_rules,
            anti_fit_rules,
            product_id=product.id,
            publisher_authority=PackAuthority.SELLER_SEALED.value,
        )
        revision_hash = content_hash(revision_payload)
        validation = {
            "status": "HAS_GAPS",
            "gaps": [
                {
                    "id": "gap_data_retention_days",
                    "field": "data_retention_days",
                    "safe_message": "Add a current retention value and supporting evidence.",
                    "href": "/seller/product-evidence/product_fixture_d?field=data_retention_days",
                },
                {
                    "id": "gap_public_summary_stale",
                    "field": "public_summary",
                    "safe_message": "Replace stale supporting evidence for this published field.",
                    "href": "/seller/product-evidence/product_fixture_d?field=public_summary",
                },
            ],
        }
        draft = SellerPackDraft(
            id="draft_fixture_d",
            organization_id=organization_id,
            product_id=product.id,
            editor_actor_id="seller_fixture_d",
            state=SellerEvidenceState.SELLER_DRAFT.value,
            publisher_authority=PackAuthority.SELLER_SEALED.value,
            current_revision=2,
            current_revision_hash=revision_hash,
            validation=validation,
            submitted_at=None,
            frozen_at=None,
            based_on_pack_version_id="pack_fixture_d_v1",
            created_at=now,
            updated_at=now,
        )
        revision = SellerPackDraftRevision(
            id="sdrev_fixture_d_2",
            organization_id=organization_id,
            draft_id=draft.id,
            revision=2,
            revision_hash=revision_hash,
            claims=initial_claims,
            fit_rules=fit_rules,
            anti_fit_rules=anti_fit_rules,
            validation=validation,
            created_by_actor_id="seller_fixture_d",
            created_at=now,
            frozen_at=None,
        )
        stale_evidence = SellerEvidenceAttachment(
            id="sevd_fixture_d_stale",
            organization_id=organization_id,
            draft_id=draft.id,
            attached_revision=2,
            source_reference_hash=content_hash(
                {"source_reference": "https://example.invalid/fixture-d/overview"}
            ),
            public_source_url="https://example.invalid/fixture-d/overview",
            source_class="PUBLIC_WEB",
            claim_fields=["public_summary"],
            observed_at=now - timedelta(days=500),
            verification_state="UNVERIFIED",
            verification_actor_id=None,
            verification_method=None,
            added_by_actor_id="seller_fixture_d",
            created_at=now,
            updated_at=now,
        )
        published_payload = {
            "schema_version": "1.0.0",
            "product_id": product.id,
            "version": 1,
            "publisher_authority": PackAuthority.SELLER_SEALED.value,
            "claims": [
                {"field": "product_name", "value": "Fixture D", "evidence_ids": []},
                {
                    "field": "public_summary",
                    "value": "Fictional development Product Evidence fixture.",
                    "evidence_ids": [],
                },
            ],
            "fit_rules": fit_rules,
            "anti_fit_rules": anti_fit_rules,
            "evidence": [],
            "published_at": _timestamp(now - timedelta(days=60)),
            "fixture_label": DEMO_FIXTURE_LABEL,
        }
        pack = SellerPackVersion(
            id="pack_fixture_d_v1",
            organization_id=organization_id,
            product_id=product.id,
            source_draft_id=draft.id,
            source_revision=1,
            source_revision_hash=content_hash(
                {"fixture": "fixture_d", "revision": 1, "published": True}
            ),
            version=1,
            content_hash=content_hash(published_payload),
            publisher_authority=PackAuthority.SELLER_SEALED.value,
            payload=published_payload,
            published_by_actor_id="seller_reviewer_fixture_d",
            published_at=now - timedelta(days=60),
            superseded_by_version_id=None,
        )
        session.add_all([product, unclaimed, draft, revision, stale_evidence, pack])
        await session.flush()
        await self._create_exports(session, organization_id, pack)
        events = [
            ("sact_fixture_answer_a1", "ANSWER_RENDERED", "session_a", "sha256:q1", 5),
            ("sact_fixture_answer_a2", "ANSWER_RENDERED", "session_a", "sha256:q1", 4),
            ("sact_fixture_answer_b", "ANSWER_RENDERED", "session_b", "sha256:q2", 3),
            ("sact_fixture_handoff_b", "SELLER_HANDOFF_REQUESTED", "session_b", None, 2),
            ("sact_fixture_answer_c", "ANSWER_RENDERED", "session_c", "sha256:q3", 1),
        ]
        for event_id, event_type, session_id, fingerprint, days_ago in events:
            session.add(
                SellerActivityEvent(
                    id=event_id,
                    organization_id=organization_id,
                    product_id=product.id,
                    event_type=event_type,
                    session_id=session_id,
                    question_fingerprint=fingerprint,
                    occurred_at=now - timedelta(days=days_ago),
                    fixture_label=DEMO_FIXTURE_LABEL,
                )
            )
        await session.flush()

    async def _product(
        self,
        session: AsyncSession,
        organization_id: str,
        product_id: str,
        *,
        lock: bool = False,
    ) -> SellerProduct:
        statement = select(SellerProduct).where(
            SellerProduct.organization_id == organization_id,
            SellerProduct.id == product_id,
        )
        if lock:
            statement = statement.with_for_update()
        product = (await session.execute(statement)).scalar_one_or_none()
        if product is None:
            raise self._not_found("SELLER_PRODUCT")
        return product

    async def _draft(
        self,
        session: AsyncSession,
        organization_id: str,
        draft_id: str,
        *,
        lock: bool = False,
    ) -> SellerPackDraft:
        statement = select(SellerPackDraft).where(
            SellerPackDraft.organization_id == organization_id,
            SellerPackDraft.id == draft_id,
        )
        if lock:
            statement = statement.with_for_update()
        draft = (await session.execute(statement)).scalar_one_or_none()
        if draft is None:
            raise self._not_found("SELLER_PACK_DRAFT")
        return draft

    async def _draft_for_product(
        self, session: AsyncSession, organization_id: str, product_id: str
    ) -> SellerPackDraft | None:
        return (
            await session.execute(
                select(SellerPackDraft).where(
                    SellerPackDraft.organization_id == organization_id,
                    SellerPackDraft.product_id == product_id,
                )
            )
        ).scalar_one_or_none()

    async def _revision(
        self,
        session: AsyncSession,
        organization_id: str,
        draft: SellerPackDraft,
    ) -> SellerPackDraftRevision:
        revision = (
            await session.execute(
                select(SellerPackDraftRevision).where(
                    SellerPackDraftRevision.organization_id == organization_id,
                    SellerPackDraftRevision.draft_id == draft.id,
                    SellerPackDraftRevision.revision == draft.current_revision,
                    SellerPackDraftRevision.revision_hash == draft.current_revision_hash,
                )
            )
        ).scalar_one_or_none()
        if revision is None:
            raise self._not_found("SELLER_PACK_DRAFT_REVISION")
        return revision

    async def _latest_submission(
        self,
        session: AsyncSession,
        organization_id: str,
        draft_id: str,
        *,
        lock: bool = False,
    ) -> SellerReviewSubmission | None:
        statement = (
            select(SellerReviewSubmission)
            .where(
                SellerReviewSubmission.organization_id == organization_id,
                SellerReviewSubmission.draft_id == draft_id,
            )
            .order_by(SellerReviewSubmission.submitted_at.desc())
            .limit(1)
        )
        if lock:
            statement = statement.with_for_update()
        return (await session.execute(statement)).scalar_one_or_none()

    async def _decision_for_submission(
        self, session: AsyncSession, organization_id: str, submission_id: str
    ) -> SellerReviewDecisionRecord | None:
        return (
            await session.execute(
                select(SellerReviewDecisionRecord).where(
                    SellerReviewDecisionRecord.organization_id == organization_id,
                    SellerReviewDecisionRecord.submission_id == submission_id,
                )
            )
        ).scalar_one_or_none()

    async def _current_pack(
        self, session: AsyncSession, organization_id: str, product: SellerProduct
    ) -> SellerPackVersion | None:
        if product.current_pack_version_id is None:
            return None
        return (
            await session.execute(
                select(SellerPackVersion).where(
                    SellerPackVersion.organization_id == organization_id,
                    SellerPackVersion.id == product.current_pack_version_id,
                    SellerPackVersion.product_id == product.id,
                )
            )
        ).scalar_one_or_none()

    async def _pack(
        self, session: AsyncSession, organization_id: str, version_id: str
    ) -> SellerPackVersion:
        pack = (
            await session.execute(
                select(SellerPackVersion).where(
                    SellerPackVersion.organization_id == organization_id,
                    SellerPackVersion.id == version_id,
                )
            )
        ).scalar_one_or_none()
        if pack is None:
            raise self._not_found("SELLER_PACK_VERSION")
        return pack

    async def _next_pack_version(
        self, session: AsyncSession, organization_id: str, product_id: str
    ) -> int:
        rows = (
            await session.execute(
                select(SellerPackVersion.version).where(
                    SellerPackVersion.organization_id == organization_id,
                    SellerPackVersion.product_id == product_id,
                )
            )
        ).scalars()
        return max(rows, default=0) + 1

    async def _evidence_map(
        self, session: AsyncSession, organization_id: str, draft_id: str
    ) -> dict[str, SellerEvidenceAttachment]:
        records = (
            await session.execute(
                select(SellerEvidenceAttachment).where(
                    SellerEvidenceAttachment.organization_id == organization_id,
                    SellerEvidenceAttachment.draft_id == draft_id,
                )
            )
        ).scalars()
        return {record.id: record for record in records}

    def _validate_publication_fields(
        self,
        claims: list[dict[str, Any]],
        fit_rules: list[dict[str, Any]],
        anti_fit_rules: list[dict[str, Any]],
    ) -> None:
        for rows, allowed in (
            (claims, _ALLOWED_CLAIM_FIELDS),
            (fit_rules, _ALLOWED_FIT_FIELDS),
            (anti_fit_rules, _ALLOWED_ANTI_FIT_FIELDS),
        ):
            for row in rows:
                field = str(row.get("field", ""))
                if field not in allowed:
                    raise self._problem(
                        "SELLER_PUBLICATION_FIELD_FORBIDDEN",
                        "Only approved Product Evidence fields may enter a published Pack.",
                        status_code=403,
                    )

    def _validate_evidence_links(
        self,
        rows: list[dict[str, Any]],
        evidence: dict[str, SellerEvidenceAttachment],
    ) -> None:
        for row in rows:
            field = str(row["field"])
            for evidence_id in cast(list[str], row.get("evidence_ids", [])):
                attachment = evidence.get(evidence_id)
                if attachment is None or field not in attachment.claim_fields:
                    raise self._problem(
                        "SELLER_EVIDENCE_SCOPE_MISMATCH",
                        "Evidence must belong to this draft and explicitly support the field.",
                        status_code=409,
                    )

    def _validate_revision(
        self,
        product_id: str,
        claims: list[dict[str, Any]],
        fit_rules: list[dict[str, Any]],
        anti_fit_rules: list[dict[str, Any]],
        evidence: dict[str, SellerEvidenceAttachment],
        *,
        now: datetime,
    ) -> dict[str, Any]:
        gaps: list[dict[str, Any]] = []
        by_field: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in claims:
            by_field[str(row["field"])].append(row)
        for field in _REQUIRED_CLAIMS:
            rows = by_field.get(field, [])
            if not rows or all(row.get("value") is None or row.get("value") == "" for row in rows):
                gaps.append(self._gap(product_id, field, f"Add the required {field} value."))
        if not fit_rules:
            gaps.append(self._gap(product_id, "fit_rules", "Add at least one typed fit rule."))
        if not anti_fit_rules:
            gaps.append(
                self._gap(product_id, "anti_fit_rules", "Add at least one typed anti-fit rule.")
            )

        conflicts = False
        for field, rows in by_field.items():
            values = {content_hash({"value": row.get("value")}) for row in rows}
            if len(values) > 1:
                conflicts = True
                gaps.append(
                    self._gap(product_id, field, "Resolve conflicting values for this field.")
                )

        retention_rows = by_field.get("data_retention_days", [])
        if retention_rows:
            ids = cast(list[str], retention_rows[-1].get("evidence_ids", []))
            if not ids:
                gaps.append(
                    self._gap(
                        product_id,
                        "data_retention_days",
                        "Add supporting evidence for the retention value.",
                    )
                )
        referenced: dict[str, str] = {}
        for row in claims + fit_rules + anti_fit_rules:
            for evidence_id in cast(list[str], row.get("evidence_ids", [])):
                referenced[evidence_id] = str(row["field"])
        for evidence_id, field in referenced.items():
            attachment = evidence.get(evidence_id)
            if attachment is None or attachment.verification_state == "REJECTED":
                gaps.append(self._gap(product_id, field, "Replace rejected or missing evidence."))
                continue
            if attachment.observed_at is not None and _utc(
                attachment.observed_at
            ) < now - timedelta(days=365):
                gaps.append(
                    self._gap(
                        product_id,
                        field,
                        "Replace stale supporting evidence for this published field.",
                        suffix="stale",
                    )
                )

        deduplicated = {str(gap["id"]): gap for gap in gaps}
        ordered = [deduplicated[key] for key in sorted(deduplicated)]
        status = "CONFLICT" if conflicts else ("HAS_GAPS" if ordered else "VALID")
        return {"status": status, "gaps": ordered}

    @staticmethod
    def _gap(
        product_id: str, field: str, message: str, *, suffix: str = "required"
    ) -> dict[str, Any]:
        safe_field = field.replace(".", "_")
        return {
            "id": f"gap_{safe_field}_{suffix}",
            "field": field,
            "safe_message": message,
            "href": f"/seller/product-evidence/{product_id}?field={field}",
        }

    async def _pack_health(
        self,
        session: AsyncSession,
        organization_id: str,
        draft: SellerPackDraft | None,
        revision: SellerPackDraftRevision | None,
        validation: dict[str, Any],
    ) -> dict[str, Any]:
        del session, organization_id
        if draft is None or revision is None:
            return {
                "status": "NEEDS_ATTENTION",
                "required_claim_count": 6,
                "complete_claim_count": 0,
                "stale_claim_count": 0,
                "conflict_count": 0,
            }
        claim_fields = {
            str(row["field"]) for row in revision.claims if row.get("value") is not None
        }
        complete = len(set(_REQUIRED_CLAIMS) & claim_fields)
        complete += 1 if revision.fit_rules else 0
        complete += 1 if revision.anti_fit_rules else 0
        gaps = cast(list[dict[str, Any]], validation.get("gaps", []))
        stale = sum("stale" in str(gap["id"]) for gap in gaps)
        conflicts = sum("conflicting" in str(gap["safe_message"]).casefold() for gap in gaps)
        status = "HEALTHY" if validation.get("status") == "VALID" else "NEEDS_ATTENTION"
        if validation.get("status") == "CONFLICT":
            status = "BLOCKED"
        return {
            "status": status,
            "required_claim_count": 6,
            "complete_claim_count": complete,
            "stale_claim_count": stale,
            "conflict_count": conflicts,
        }

    def _published_payload(
        self,
        product: SellerProduct,
        draft: SellerPackDraft,
        revision: SellerPackDraftRevision,
        evidence: dict[str, SellerEvidenceAttachment],
        *,
        version_number: int,
        published_at: datetime,
    ) -> dict[str, Any]:
        referenced_ids = {
            evidence_id
            for row in list(revision.claims)
            + list(revision.fit_rules)
            + list(revision.anti_fit_rules)
            for evidence_id in cast(list[str], row.get("evidence_ids", []))
        }
        public_evidence = []
        for evidence_id in sorted(referenced_ids):
            item = evidence[evidence_id]
            public_evidence.append(
                {
                    "id": item.id,
                    "source_class": item.source_class,
                    "observed_at": _timestamp(item.observed_at),
                    "verification_state": item.verification_state,
                    "source_url": item.public_source_url,
                    "claim_fields": sorted(item.claim_fields),
                }
            )
        return {
            "schema_version": "1.0.0",
            "product_id": product.id,
            "version": version_number,
            "publisher_authority": PackAuthority.SELLER_SEALED.value,
            "claims": list(revision.claims),
            "fit_rules": list(revision.fit_rules),
            "anti_fit_rules": list(revision.anti_fit_rules),
            "evidence": public_evidence,
            "published_at": _timestamp(published_at),
            "source_revision_hash": draft.current_revision_hash,
            "fixture_label": product.fixture_label,
        }

    async def _create_exports(
        self, session: AsyncSession, organization_id: str, pack: SellerPackVersion
    ) -> None:
        generated_at = pack.published_at
        claims = cast(list[dict[str, Any]], pack.payload.get("claims", []))
        evidence = cast(list[dict[str, Any]], pack.payload.get("evidence", []))
        source_links = {
            str(item["id"]): item.get("source_url") for item in evidence if item.get("source_url")
        }
        reusable = {
            "pack_id": pack.id,
            "pack_version": pack.version,
            "answers": [
                {
                    "field": claim["field"],
                    "answer": claim.get("value"),
                    "source_links": [
                        source_links[evidence_id]
                        for evidence_id in cast(list[str], claim.get("evidence_ids", []))
                        if evidence_id in source_links
                    ],
                }
                for claim in claims
            ],
        }
        html_body = (
            "<article>"
            + "".join(
                f"<section><h2>{escape(str(claim['field']))}</h2>"
                f"<p>{escape(str(claim.get('value')))}</p></section>"
                for claim in claims
            )
            + "</article>"
        )
        documents: dict[str, dict[str, Any]] = {
            "JSON": dict(pack.payload),
            "HTML": {
                "content_type": "text/html; charset=utf-8",
                "body": html_body,
                "pack_id": pack.id,
                "pack_version": pack.version,
            },
            "REUSABLE_ANSWER": reusable,
        }
        for format_name, payload in documents.items():
            session.add(
                SellerPackExportArtifact(
                    id=new_id("sexport"),
                    organization_id=organization_id,
                    pack_version_id=pack.id,
                    format=format_name,
                    content_hash=content_hash(payload),
                    payload=payload,
                    generated_at=generated_at,
                )
            )
        await session.flush()

    async def _activity_metrics(
        self, session: AsyncSession, organization_id: str, product_id: str
    ) -> dict[str, Any]:
        window_end = _now()
        window_start = window_end - timedelta(days=30)
        events = list(
            (
                await session.execute(
                    select(SellerActivityEvent)
                    .where(
                        SellerActivityEvent.organization_id == organization_id,
                        SellerActivityEvent.product_id == product_id,
                        SellerActivityEvent.occurred_at >= window_start,
                        SellerActivityEvent.occurred_at <= window_end,
                    )
                    .order_by(SellerActivityEvent.occurred_at, SellerActivityEvent.id)
                )
            ).scalars()
        )
        answers = [event for event in events if event.event_type == "ANSWER_RENDERED"]
        handoffs = [event for event in events if event.event_type == "SELLER_HANDOFF_REQUESTED"]
        handoff_times: dict[str, list[datetime]] = defaultdict(list)
        for event in handoffs:
            handoff_times[event.session_id].append(_utc(event.occurred_at))
        grouped: dict[tuple[str, str], list[datetime]] = defaultdict(list)
        for event in answers:
            event_time = _utc(event.occurred_at)
            if any(time >= event_time for time in handoff_times.get(event.session_id, [])):
                continue
            fingerprint = event.question_fingerprint or "missing_fingerprint"
            grouped[(event.session_id, fingerprint)].append(event_time)
        observed = 0
        for occurrences in grouped.values():
            last_counted: datetime | None = None
            for occurred_at in sorted(occurrences):
                if last_counted is None or occurred_at > last_counted + timedelta(hours=24):
                    observed += 1
                    last_counted = occurred_at
        return {
            "window_start": _timestamp(window_start),
            "window_end": _timestamp(window_end),
            "answer_rendered_count": len(answers),
            "seller_handoff_requested_count": len(handoffs),
            "observed_self_service_count": observed,
            "measurement_label": "OBSERVATIONAL_NOT_CAUSAL",
            "href": f"/v1/seller/products/{product_id}/activity-metrics",
        }

    @staticmethod
    def _search_item(product: SellerProduct) -> dict[str, Any]:
        return {
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "publisher_authority": product.publisher_authority,
            "state": product.state,
            "public_summary": product.public_summary,
            "href": f"/seller/product-evidence/{product.id}",
        }

    @staticmethod
    def _draft_view(draft: SellerPackDraft, revision: SellerPackDraftRevision) -> dict[str, Any]:
        return {
            "id": draft.id,
            "product_id": draft.product_id,
            "revision": draft.current_revision,
            "revision_hash": draft.current_revision_hash,
            "state": draft.state,
            "publisher_authority": draft.publisher_authority,
            "claims": list(revision.claims),
            "fit_rules": list(revision.fit_rules),
            "anti_fit_rules": list(revision.anti_fit_rules),
            "validation": dict(draft.validation),
            "updated_at": _timestamp(draft.updated_at),
        }

    @staticmethod
    def _evidence_view(record: SellerEvidenceAttachment) -> dict[str, Any]:
        return {
            "id": record.id,
            "draft_id": record.draft_id,
            "verification_state": record.verification_state,
            "source_reference_hash": record.source_reference_hash,
        }

    @staticmethod
    def _pack_view(pack: SellerPackVersion) -> dict[str, Any]:
        return {
            "id": pack.id,
            "product_id": pack.product_id,
            "version": pack.version,
            "content_hash": pack.content_hash,
            "publisher_authority": pack.publisher_authority,
            # Suspension is an append-only safety event because the frozen enum has no
            # SUSPENDED value. The immutable published content remains PUBLISHED.
            "state": SellerEvidenceState.PUBLISHED.value,
            "published_at": _timestamp(pack.published_at),
        }

    @staticmethod
    def _review_summary(
        submission: SellerReviewSubmission | None,
        decision: SellerReviewDecisionRecord | None,
    ) -> dict[str, Any] | None:
        if submission is None:
            return None
        return {
            "review_id": submission.id,
            "revision_hash": submission.revision_hash,
            "status": submission.status,
            "decision": decision.decision if decision else None,
            "reviewer_role": decision.actor_role if decision else submission.reviewer_role,
            "reason": decision.reason[:500] if decision else None,
            "recorded_at": _timestamp(decision.occurred_at) if decision else None,
        }

    @staticmethod
    def _verification_summary(payload: dict[str, Any]) -> str:
        evidence = cast(list[dict[str, Any]], payload.get("evidence", []))
        verified = sum(item.get("verification_state") == "VERIFIED" for item in evidence)
        asserted = sum(item.get("verification_state") == "UNVERIFIED" for item in evidence)
        stale = 0
        return f"{verified} verified, {asserted} seller-asserted, {stale} stale"

    @staticmethod
    def _capabilities(
        product: SellerProduct,
        draft: SellerPackDraft | None,
        actor_id: str,
        actor_role: SellerActorRole,
    ) -> list[str]:
        capabilities: set[str] = {"VIEW_ACTIVITY_METRICS"}
        if product.current_pack_version_id:
            capabilities.add("EXPORT")
        if actor_role == "PLATFORM_OPERATOR":
            capabilities.update(
                {
                    "CLAIM_PRODUCT",
                    "VIEW_OWN_DRAFT",
                    "EDIT_CLAIMS",
                    "ADD_EVIDENCE",
                    "SUBMIT_REVIEW",
                    "REQUEST_CHANGES",
                    "APPROVE_REVIEW",
                    "REJECT_REVIEW",
                    "PUBLISH",
                    "SUSPEND",
                }
            )
        elif actor_role == "SELLER_EDITOR":
            if product.state in {"UNCLAIMED", "CLAIM_DENIED"}:
                capabilities.add("CLAIM_PRODUCT")
            if product.owner_actor_id == actor_id and draft is not None:
                capabilities.add("VIEW_OWN_DRAFT")
                if draft.state in _EDITABLE_STATES:
                    capabilities.update({"EDIT_CLAIMS", "ADD_EVIDENCE", "SUBMIT_REVIEW"})
        elif actor_role == "SELLER_REVIEWER":
            if draft is not None and draft.state == "IN_REVIEW":
                capabilities.update({"REQUEST_CHANGES", "APPROVE_REVIEW", "REJECT_REVIEW"})
            if draft is not None and draft.state == "PUBLISH_READY":
                capabilities.add("PUBLISH")
            if product.current_pack_version_id:
                capabilities.add("SUSPEND")
        return sorted(capabilities)

    @staticmethod
    def _actions(
        product: SellerProduct,
        draft: SellerPackDraft | None,
        actor_id: str,
        actor_role: SellerActorRole,
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        if product.state in {"UNCLAIMED", "CLAIM_DENIED"} and actor_role in {
            "SELLER_EDITOR",
            "PLATFORM_OPERATOR",
        }:
            actions.append(
                {
                    "id": "CLAIM_PRODUCT",
                    "label": "Claim this product",
                    "method": "POST",
                    "href": f"/v1/seller/products/{product.id}/claim",
                    "requires_confirmation": True,
                }
            )
        if draft is not None and (
            actor_role == "PLATFORM_OPERATOR"
            or (actor_role == "SELLER_EDITOR" and product.owner_actor_id == actor_id)
        ):
            if draft.state in _EDITABLE_STATES:
                actions.extend(
                    [
                        {
                            "id": "EDIT_PRODUCT_EVIDENCE",
                            "label": "Edit Product Evidence",
                            "method": "PATCH",
                            "href": f"/v1/seller/pack-drafts/{draft.id}",
                            "requires_confirmation": False,
                        },
                        {
                            "id": "SUBMIT_REVIEW",
                            "label": "Submit for review",
                            "method": "POST",
                            "href": f"/v1/seller/pack-drafts/{draft.id}/submit-review",
                            "requires_confirmation": True,
                        },
                    ]
                )
        if draft is not None and actor_role in {"SELLER_REVIEWER", "PLATFORM_OPERATOR"}:
            if draft.state == "IN_REVIEW":
                actions.append(
                    {
                        "id": "REVIEW_PRODUCT_EVIDENCE",
                        "label": "Record review decision",
                        "method": "POST",
                        "href": f"/v1/seller/pack-drafts/{draft.id}/review-decisions",
                        "requires_confirmation": True,
                    }
                )
            if draft.state == "PUBLISH_READY":
                actions.append(
                    {
                        "id": "PUBLISH_PRODUCT_EVIDENCE",
                        "label": "Publish version",
                        "method": "POST",
                        "href": f"/v1/seller/pack-drafts/{draft.id}/publish",
                        "requires_confirmation": True,
                    }
                )
        return actions

    @staticmethod
    def _require_product_access(
        product: SellerProduct,
        actor_id: str,
        actor_role: SellerActorRole,
        *,
        allow_unclaimed: bool = False,
    ) -> None:
        if actor_role in {"SELLER_REVIEWER", "PLATFORM_OPERATOR"}:
            return
        if allow_unclaimed and product.state in {"UNCLAIMED", "CLAIM_DENIED"}:
            return
        if product.owner_actor_id != actor_id:
            raise SellerEvidenceService._forbidden("SELLER_PRODUCT_SCOPE_REQUIRED")

    @staticmethod
    def _require_exact_hash(expected: str, supplied: str) -> None:
        if expected != supplied:
            raise ApiProblem(
                code="SELLER_REVISION_HASH_MISMATCH",
                message="The seller action was not bound to the current frozen revision hash.",
                status_code=409,
                next_action="reload_seller_draft",
                details={"current_revision_hash": expected},
            )

    @staticmethod
    def _problem(code: str, message: str, *, status_code: int = 400) -> ApiProblem:
        return ApiProblem(code=code, message=message, status_code=status_code)

    @staticmethod
    def _forbidden(code: str) -> ApiProblem:
        return ApiProblem(
            code=code,
            message=(
                "This seller identity is not authorized for the requested Product Evidence action."
            ),
            status_code=403,
            next_action="use_authorized_seller_identity",
        )

    @staticmethod
    def _not_found(kind: str) -> ApiProblem:
        return ApiProblem(
            code=f"{kind}_NOT_FOUND",
            message="The tenant-scoped seller resource is unavailable.",
            status_code=404,
        )
