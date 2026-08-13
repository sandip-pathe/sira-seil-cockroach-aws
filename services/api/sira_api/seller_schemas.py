"""Strict public contracts for the narrow seller Product Evidence workflow."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from domain.enums import (
    ActorRole,
    PackAuthority,
    SellerEvidenceState,
    SellerExportFormat,
    SellerReviewDecision,
)

from .schemas import HashValue, Identifier, StrictModel

ScalarEvidenceValue = str | int | bool | list[str] | None


class SellerCapability(StrEnum):
    CLAIM_PRODUCT = "CLAIM_PRODUCT"
    VIEW_OWN_DRAFT = "VIEW_OWN_DRAFT"
    EDIT_CLAIMS = "EDIT_CLAIMS"
    ADD_EVIDENCE = "ADD_EVIDENCE"
    SUBMIT_REVIEW = "SUBMIT_REVIEW"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    APPROVE_REVIEW = "APPROVE_REVIEW"
    REJECT_REVIEW = "REJECT_REVIEW"
    PUBLISH = "PUBLISH"
    SUSPEND = "SUSPEND"
    EXPORT = "EXPORT"
    VIEW_ACTIVITY_METRICS = "VIEW_ACTIVITY_METRICS"
    RETRY_PUBLICATION = "RETRY_PUBLICATION"


class SellerProductSearchItem(StrictModel):
    id: Identifier
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=120)
    publisher_authority: PackAuthority
    state: SellerEvidenceState
    public_summary: str = Field(min_length=1, max_length=1000)
    href: str = Field(pattern=r"^/", max_length=500)


class SellerProductSearchView(StrictModel):
    results: list[SellerProductSearchItem]


class SellerClaimCreate(StrictModel):
    authority_proof_reference: str = Field(min_length=3, max_length=500)
    requested_role: ActorRole = ActorRole.SELLER_EDITOR


class SellerClaimView(StrictModel):
    claim_id: Identifier
    product_id: Identifier
    state: SellerEvidenceState
    submitted_at: datetime
    safe_reason: str | None = Field(default=None, max_length=500)


class SellerPackHealth(StrictModel):
    status: Literal["HEALTHY", "NEEDS_ATTENTION", "BLOCKED"]
    required_claim_count: int = Field(ge=0)
    complete_claim_count: int = Field(ge=0)
    stale_claim_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)


class SellerValidationGap(StrictModel):
    id: Identifier
    field: str = Field(pattern=r"^[a-z][a-z0-9_.]{2,127}$")
    safe_message: str = Field(min_length=1, max_length=300)
    href: str = Field(pattern=r"^/", max_length=500)


class SellerValidation(StrictModel):
    status: Literal["NOT_RUN", "VALID", "HAS_GAPS", "CONFLICT"]
    gaps: list[SellerValidationGap]


class SellerReviewSummary(StrictModel):
    review_id: Identifier
    revision_hash: HashValue
    status: Literal["PENDING", "COMPLETED"]
    decision: SellerReviewDecision | None
    reviewer_role: Literal[ActorRole.SELLER_REVIEWER, ActorRole.PLATFORM_OPERATOR]
    reason: str | None = Field(default=None, max_length=500)
    recorded_at: datetime | None


class SellerReusableAnswers(StrictModel):
    published_version: int | None = Field(default=None, ge=1)
    published_answer_count: int = Field(ge=0)
    formats: list[SellerExportFormat]
    href: str | None = Field(default=None, pattern=r"^/", max_length=500)


class SellerActivityMetrics(StrictModel):
    window_start: datetime
    window_end: datetime
    answer_rendered_count: int = Field(ge=0)
    seller_handoff_requested_count: int = Field(ge=0)
    observed_self_service_count: int = Field(ge=0)
    measurement_label: Literal["OBSERVATIONAL_NOT_CAUSAL"] = "OBSERVATIONAL_NOT_CAUSAL"
    href: str = Field(pattern=r"^/", max_length=500)


class SellerEvidenceProduct(StrictModel):
    id: Identifier
    name: str = Field(min_length=1, max_length=200)
    seller_state: SellerEvidenceState
    current_version: int = Field(ge=1)
    href: str = Field(pattern=r"^/", max_length=500)


class SellerActor(StrictModel):
    role: Literal[ActorRole.SELLER_EDITOR, ActorRole.SELLER_REVIEWER, ActorRole.PLATFORM_OPERATOR]
    capabilities: list[SellerCapability]


class PublisherAuthorityProjection(StrictModel):
    value: PackAuthority
    label: str = Field(min_length=1, max_length=100)
    supporting_copy: str = Field(min_length=1, max_length=500)


class SellerVersionLinks(StrictModel):
    current: str = Field(pattern=r"^/", max_length=500)
    previous: str | None = Field(default=None, pattern=r"^/", max_length=500)


class SellerActionDescriptor(StrictModel):
    id: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")
    label: str = Field(min_length=1, max_length=100)
    method: Literal["GET", "POST", "PATCH"]
    href: str = Field(pattern=r"^/", max_length=500)
    requires_confirmation: bool


class SellerEvidenceView(StrictModel):
    product: SellerEvidenceProduct
    actor: SellerActor
    publisher_authority: PublisherAuthorityProjection
    pack_health: SellerPackHealth
    validation: SellerValidation
    review: SellerReviewSummary | None = None
    reusable_answers: SellerReusableAnswers
    activity_metrics: SellerActivityMetrics
    available_actions: list[SellerActionDescriptor]
    version_links: SellerVersionLinks


class SellerEvidenceClaim(StrictModel):
    field: str = Field(min_length=1, max_length=120)
    value: ScalarEvidenceValue
    evidence_ids: list[Identifier]


class SellerProofAdapterPrice(StrictModel):
    amount: str = Field(pattern=r"^(0|[1-9][0-9]*)\.[0-9]{2}$")
    currency: Literal["USD"] = "USD"


class SellerProofAdapterDraft(StrictModel):
    adapter_id: Identifier
    artifact_digest: HashValue
    protocol_version: Literal["TrialCase/v0"]
    capabilities: list[
        Literal["SUPPORT_SUMMARIZATION", "CUSTOMER_EMAIL_OUTPUT", "PII_REDACTION"]
    ] = Field(min_length=1)
    declared_region: Literal["EU", "IN", "US"]
    fixed_price: SellerProofAdapterPrice
    conformance_hash: HashValue


class SellerPackDraftView(StrictModel):
    id: Identifier
    product_id: Identifier
    revision: int = Field(ge=1)
    revision_hash: HashValue
    state: SellerEvidenceState
    publisher_authority: PackAuthority
    claims: list[SellerEvidenceClaim]
    fit_rules: list[SellerEvidenceClaim]
    anti_fit_rules: list[SellerEvidenceClaim]
    proof_adapter: SellerProofAdapterDraft | None = None
    validation: SellerValidation
    updated_at: datetime


class SellerPackDraftPatch(StrictModel):
    base_revision: int = Field(ge=1)
    claims: list[SellerEvidenceClaim] = Field(default_factory=list)
    fit_rules: list[SellerEvidenceClaim] = Field(default_factory=list)
    anti_fit_rules: list[SellerEvidenceClaim] = Field(default_factory=list)
    proof_adapter: SellerProofAdapterDraft | None = None


class SellerEvidenceAttachCreate(StrictModel):
    source_reference: str = Field(min_length=3, max_length=500)
    source_class: str = Field(min_length=2, max_length=80)
    claim_fields: list[str] = Field(min_length=1)
    observed_at: datetime | None = None


class SellerEvidenceAttachmentView(StrictModel):
    id: Identifier
    draft_id: Identifier
    verification_state: Literal["UNVERIFIED", "PENDING", "VERIFIED", "REJECTED"]
    source_reference_hash: HashValue
    object_checksum: HashValue | None = None
    content_type: str | None = Field(default=None, min_length=1, max_length=120)
    size_bytes: int | None = Field(default=None, ge=1)
    version_bound: bool = False


class SellerSubmitReviewCreate(StrictModel):
    revision_hash: HashValue


class SellerReviewDecisionCreate(StrictModel):
    decision: SellerReviewDecision
    revision_hash: HashValue
    reason: str = Field(min_length=3, max_length=1000)


class SellerReviewDecisionView(StrictModel):
    id: Identifier
    draft_id: Identifier
    decision: SellerReviewDecision
    revision_hash: HashValue
    actor_role: ActorRole
    reason: str
    occurred_at: datetime


class SellerPublishCreate(StrictModel):
    revision_hash: HashValue


class SellerPackVersionView(StrictModel):
    id: Identifier
    product_id: Identifier
    version: int = Field(ge=1)
    content_hash: HashValue
    publisher_authority: PackAuthority
    state: SellerEvidenceState
    published_at: datetime | None = None
    proof_adapter: SellerProofAdapterDraft | None = None


class SellerSuspendCreate(StrictModel):
    reason: str = Field(min_length=3, max_length=1000)
    effective_at: datetime


class SellerPackExport(StrictModel):
    format: SellerExportFormat
    pack_id: Identifier
    pack_version: int = Field(ge=1)
    publisher_authority: PackAuthority
    verification_summary: str = Field(min_length=1, max_length=300)
    generated_at: datetime
    content_hash: HashValue
    href: str = Field(pattern=r"^/", max_length=500)


class SellerPackExportsView(StrictModel):
    exports: list[SellerPackExport]
