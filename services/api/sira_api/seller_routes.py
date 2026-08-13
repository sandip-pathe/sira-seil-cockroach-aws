"""HTTP surface for seller-owned Product Evidence."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status

from integrations.aws_services import MAX_EVIDENCE_BYTES

from .dependencies import (
    RequestContext,
    enforce_api_security,
    get_request_context,
    require_human_identity,
    require_idempotency_key,
)
from .errors import ApiProblem
from .seller_schemas import (
    SellerActivityMetrics,
    SellerClaimCreate,
    SellerClaimView,
    SellerEvidenceAttachCreate,
    SellerEvidenceAttachmentView,
    SellerEvidenceView,
    SellerPackDraftPatch,
    SellerPackDraftView,
    SellerPackExportsView,
    SellerPackVersionView,
    SellerProductSearchView,
    SellerPublishCreate,
    SellerReviewDecisionCreate,
    SellerReviewDecisionView,
    SellerSubmitReviewCreate,
    SellerSuspendCreate,
)
from .seller_service import SellerActorRole, SellerEvidenceService

seller_router = APIRouter(dependencies=[Depends(enforce_api_security)])
ContextDependency = Annotated[RequestContext, Depends(get_request_context)]
IdempotencyDependency = Annotated[str, Depends(require_idempotency_key)]


def get_seller_service(request: Request) -> SellerEvidenceService:
    return cast(SellerEvidenceService, request.app.state.seller_evidence_service)


SellerServiceDependency = Annotated[SellerEvidenceService, Depends(get_seller_service)]


def _seller_role(context: RequestContext) -> SellerActorRole:
    roles = {role.strip().lower() for role in context.roles}
    if "platform_operator" in roles:
        return "PLATFORM_OPERATOR"
    if context.party != "SELLER":
        raise ApiProblem(
            code="SELLER_IDENTITY_REQUIRED",
            message="A verified seller identity is required for Product Evidence.",
            status_code=403,
            next_action="use_authorized_seller_identity",
        )
    if "seller_reviewer" in roles:
        return "SELLER_REVIEWER"
    if "seller_editor" in roles:
        return "SELLER_EDITOR"
    if "seller_viewer" in roles:
        return "SELLER_EDITOR"
    raise ApiProblem(
        code="SELLER_ROLE_REQUIRED",
        message="The seller identity has no Product Evidence role.",
        status_code=403,
        next_action="request_seller_role",
    )


def _require_verified_seller(context: RequestContext) -> None:
    require_human_identity(context)
    if context.guest_identity:
        raise ApiProblem(
            code="VERIFIED_SELLER_REQUIRED",
            message="Sign in with a verified account to change Product Evidence.",
            status_code=403,
            next_action="link_guest_account",
        )


def _require_step_up(context: RequestContext) -> None:
    if not context.step_up_verified:
        raise ApiProblem(
            code="STEP_UP_REQUIRED",
            message=(
                "Publishing or suspending Product Evidence requires recent step-up authentication."
            ),
            status_code=403,
            next_action="complete_step_up_authentication",
        )


@seller_router.get(
    "/v1/seller/products/search",
    response_model=SellerProductSearchView,
    tags=["seller product evidence"],
    name="seller_evidence_search_products",
)
async def search_seller_products(
    context: ContextDependency,
    service: SellerServiceDependency,
    query: Annotated[str | None, Query(alias="q", min_length=2, max_length=200)] = None,
) -> dict[str, object]:
    return await service.search_products(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_role=_seller_role(context),
        query=query,
    )


@seller_router.post(
    "/v1/seller/products/{product_id}/claim",
    response_model=SellerClaimView,
    status_code=status.HTTP_201_CREATED,
    tags=["seller product evidence"],
    name="seller_evidence_claim_product",
)
async def claim_seller_product(
    product_id: str,
    body: SellerClaimCreate,
    response: Response,
    context: ContextDependency,
    service: SellerServiceDependency,
    idempotency_key: IdempotencyDependency,
) -> dict[str, object]:
    _require_verified_seller(context)
    code, payload = await service.claim_product(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_role=_seller_role(context),
        product_id=product_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="python"),
    )
    response.status_code = code
    return payload


@seller_router.get(
    "/v1/seller/products/{product_id}/view",
    response_model=SellerEvidenceView,
    tags=["seller product evidence"],
    name="seller_evidence_product_view",
)
async def get_seller_product_view(
    product_id: str,
    context: ContextDependency,
    service: SellerServiceDependency,
) -> dict[str, object]:
    return await service.get_product_view(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_role=_seller_role(context),
        product_id=product_id,
    )


@seller_router.get(
    "/v1/seller/pack-drafts/{draft_id}",
    response_model=SellerPackDraftView,
    tags=["seller product evidence"],
    name="seller_evidence_get_draft",
)
async def get_seller_pack_draft(
    draft_id: str,
    context: ContextDependency,
    service: SellerServiceDependency,
) -> dict[str, object]:
    return await service.get_draft(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_role=_seller_role(context),
        draft_id=draft_id,
    )


@seller_router.patch(
    "/v1/seller/pack-drafts/{draft_id}",
    response_model=SellerPackDraftView,
    tags=["seller product evidence"],
    name="seller_evidence_patch_draft",
)
async def patch_seller_pack_draft(
    draft_id: str,
    body: SellerPackDraftPatch,
    response: Response,
    context: ContextDependency,
    service: SellerServiceDependency,
    idempotency_key: IdempotencyDependency,
) -> dict[str, object]:
    _require_verified_seller(context)
    code, payload = await service.patch_draft(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_role=_seller_role(context),
        draft_id=draft_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="python"),
        provided_fields=frozenset(body.model_fields_set),
    )
    response.status_code = code
    return payload


@seller_router.post(
    "/v1/seller/pack-drafts/{draft_id}/evidence",
    response_model=SellerEvidenceAttachmentView,
    status_code=status.HTTP_201_CREATED,
    tags=["seller product evidence"],
    name="seller_evidence_attach_evidence",
)
async def attach_seller_evidence(
    draft_id: str,
    body: SellerEvidenceAttachCreate,
    response: Response,
    context: ContextDependency,
    service: SellerServiceDependency,
    idempotency_key: IdempotencyDependency,
) -> dict[str, object]:
    _require_verified_seller(context)
    code, payload = await service.attach_evidence(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_role=_seller_role(context),
        draft_id=draft_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="python"),
    )
    response.status_code = code
    return payload


@seller_router.post(
    "/v1/seller/pack-drafts/{draft_id}/evidence/upload",
    response_model=SellerEvidenceAttachmentView,
    status_code=status.HTTP_201_CREATED,
    tags=["seller product evidence"],
    name="seller_evidence_upload_evidence",
)
async def upload_seller_evidence(
    draft_id: str,
    response: Response,
    context: ContextDependency,
    service: SellerServiceDependency,
    idempotency_key: IdempotencyDependency,
    evidence_file: Annotated[UploadFile, File(description="Private source evidence, max 25 MiB")],
    source_class: Annotated[str, Form(min_length=2, max_length=80)],
    claim_fields_json: Annotated[str, Form(min_length=4, max_length=2000)],
    observed_at: Annotated[datetime | None, Form()] = None,
) -> dict[str, object]:
    _require_verified_seller(context)
    try:
        parsed_fields = json.loads(claim_fields_json)
    except json.JSONDecodeError as exc:
        raise ApiProblem(
            code="SELLER_EVIDENCE_FIELDS_INVALID",
            message="claim_fields_json must be a JSON array of field names.",
            status_code=422,
        ) from exc
    if not isinstance(parsed_fields, list) or not all(
        isinstance(item, str) and item for item in parsed_fields
    ):
        raise ApiProblem(
            code="SELLER_EVIDENCE_FIELDS_INVALID",
            message="claim_fields_json must be a JSON array of field names.",
            status_code=422,
        )
    body = await evidence_file.read(MAX_EVIDENCE_BYTES + 1)
    await evidence_file.close()
    if len(body) > MAX_EVIDENCE_BYTES:
        raise ApiProblem(
            code="SELLER_EVIDENCE_OBJECT_INVALID",
            message="Evidence object exceeds the 25 MiB ingestion limit.",
            status_code=413,
        )
    code, payload = await service.upload_evidence(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_role=_seller_role(context),
        draft_id=draft_id,
        idempotency_key=idempotency_key,
        body=body,
        content_type=evidence_file.content_type or "application/octet-stream",
        source_class=source_class,
        claim_fields=cast(list[str], parsed_fields),
        observed_at=observed_at,
    )
    response.status_code = code
    return payload


@seller_router.post(
    "/v1/seller/pack-drafts/{draft_id}/submit-review",
    response_model=SellerPackDraftView,
    tags=["seller product evidence"],
    name="seller_evidence_submit_review",
)
async def submit_seller_pack_review(
    draft_id: str,
    body: SellerSubmitReviewCreate,
    response: Response,
    context: ContextDependency,
    service: SellerServiceDependency,
    idempotency_key: IdempotencyDependency,
) -> dict[str, object]:
    _require_verified_seller(context)
    code, payload = await service.submit_review(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_role=_seller_role(context),
        draft_id=draft_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="python"),
    )
    response.status_code = code
    return payload


@seller_router.post(
    "/v1/seller/pack-drafts/{draft_id}/review-decisions",
    response_model=SellerReviewDecisionView,
    status_code=status.HTTP_201_CREATED,
    tags=["seller product evidence"],
    name="seller_evidence_review_decision",
)
async def record_seller_review_decision(
    draft_id: str,
    body: SellerReviewDecisionCreate,
    response: Response,
    context: ContextDependency,
    service: SellerServiceDependency,
    idempotency_key: IdempotencyDependency,
) -> dict[str, object]:
    _require_verified_seller(context)
    code, payload = await service.review_decision(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_role=_seller_role(context),
        draft_id=draft_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="python"),
    )
    response.status_code = code
    return payload


@seller_router.post(
    "/v1/seller/pack-drafts/{draft_id}/publish",
    response_model=SellerPackVersionView,
    status_code=status.HTTP_201_CREATED,
    tags=["seller product evidence"],
    name="seller_evidence_publish",
)
async def publish_seller_pack(
    draft_id: str,
    body: SellerPublishCreate,
    response: Response,
    context: ContextDependency,
    service: SellerServiceDependency,
    idempotency_key: IdempotencyDependency,
) -> dict[str, object]:
    _require_verified_seller(context)
    _require_step_up(context)
    code, payload = await service.publish(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_role=_seller_role(context),
        draft_id=draft_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="python"),
    )
    response.status_code = code
    return payload


@seller_router.post(
    "/v1/seller/pack-versions/{version_id}/suspend",
    response_model=SellerPackVersionView,
    tags=["seller product evidence"],
    name="seller_evidence_suspend",
)
async def suspend_seller_pack(
    version_id: str,
    body: SellerSuspendCreate,
    response: Response,
    context: ContextDependency,
    service: SellerServiceDependency,
    idempotency_key: IdempotencyDependency,
) -> dict[str, object]:
    _require_verified_seller(context)
    _require_step_up(context)
    code, payload = await service.suspend(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_role=_seller_role(context),
        version_id=version_id,
        idempotency_key=idempotency_key,
        body=body.model_dump(mode="python"),
    )
    response.status_code = code
    return payload


@seller_router.get(
    "/v1/seller/pack-versions/{version_id}/exports",
    response_model=SellerPackExportsView,
    tags=["seller product evidence"],
    name="seller_evidence_exports",
)
async def get_seller_pack_exports(
    version_id: str,
    context: ContextDependency,
    service: SellerServiceDependency,
) -> dict[str, object]:
    return await service.get_exports(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_role=_seller_role(context),
        version_id=version_id,
    )


@seller_router.get(
    "/v1/seller/products/{product_id}/activity-metrics",
    response_model=SellerActivityMetrics,
    tags=["seller product evidence"],
    name="seller_evidence_activity_metrics",
)
async def get_seller_activity_metrics(
    product_id: str,
    context: ContextDependency,
    service: SellerServiceDependency,
) -> dict[str, object]:
    return await service.activity_metrics(
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        actor_role=_seller_role(context),
        product_id=product_id,
    )
