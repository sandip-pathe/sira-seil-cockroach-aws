"""Strict HTTP contracts for the qualified two-sided marketplace."""

from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator

Identifier = str


def _validate_exact_json(value: Any, *, path: str = "payload") -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        raise ValueError(f"{path} must not contain binary floating-point values")
    if isinstance(value, list):
        return [
            _validate_exact_json(item, path=f"{path}[{index}]") for index, item in enumerate(value)
        ]
    if isinstance(value, dict):
        if not all(isinstance(key, str) and key for key in value):
            raise ValueError(f"{path} keys must be non-empty strings")
        return {
            key: _validate_exact_json(item, path=f"{path}.{key}") for key, item in value.items()
        }
    raise ValueError(f"{path} contains an unsupported value")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RequirementCriterion(StrictModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    label: str = Field(min_length=1, max_length=200)
    requirement: str = Field(min_length=1, max_length=1000)
    priority: Literal["MUST", "SHOULD", "COULD"] = "MUST"


class RequirementBriefCreate(StrictModel):
    category: str = Field(min_length=2, max_length=80)
    goal: str = Field(min_length=10, max_length=2000)
    seller_visible_requirements: dict[str, Any] = Field(default_factory=dict)
    criteria: list[RequirementCriterion] = Field(min_length=1, max_length=30)

    @field_validator("seller_visible_requirements")
    @classmethod
    def exact_visible_requirements(cls, value: dict[str, Any]) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            _validate_exact_json(value, path="seller_visible_requirements"),
        )


class QualificationMissionCreate(StrictModel):
    buyer_context: dict[str, Any]
    company_context_item_ids: list[str] = Field(default_factory=list, max_length=100)
    requirement_brief: RequirementBriefCreate
    procurement_policy: dict[str, Any]

    @field_validator("buyer_context", "procurement_policy")
    @classmethod
    def exact_private_inputs(cls, value: dict[str, Any]) -> dict[str, Any]:
        return cast(dict[str, Any], _validate_exact_json(value))

    @field_validator("company_context_item_ids")
    @classmethod
    def unique_context_items(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("company context item IDs must be unique")
        return value


class CompanyContextCreate(StrictModel):
    kind: Literal["REQUIREMENT", "CONSTRAINT", "STACK", "POLICY", "PREFERENCE", "NOTE"]
    label: str = Field(min_length=2, max_length=160)
    payload: dict[str, Any]
    change_reason: str = Field(min_length=3, max_length=500)

    @field_validator("payload")
    @classmethod
    def exact_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("payload must not be empty")
        return cast(dict[str, Any], _validate_exact_json(value, path="payload"))


class CompanyContextUpdate(StrictModel):
    label: str = Field(min_length=2, max_length=160)
    payload: dict[str, Any]
    change_reason: str = Field(min_length=3, max_length=500)

    @field_validator("payload")
    @classmethod
    def exact_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("payload must not be empty")
        return cast(dict[str, Any], _validate_exact_json(value, path="payload"))


class CompanyContextList(StrictModel):
    items: list[dict[str, Any]]


class CompanyContextView(StrictModel):
    item: dict[str, Any]
    versions: list[dict[str, Any]]


class NotificationChannels(StrictModel):
    in_app: bool = True
    email: bool = False


class QuietHours(StrictModel):
    enabled: bool = False
    start: str = Field(default="22:00", pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    end: str = Field(default="07:00", pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    timezone: str = Field(default="Asia/Kolkata", min_length=3, max_length=80)


class DisclosureDefaults(StrictModel):
    allow_anonymized_requirement_preview: bool = True
    share_organization_name_after_consent: bool = False
    allow_outcome_follow_up: bool = True


class WorkspaceSettingsUpdate(StrictModel):
    notification_channels: NotificationChannels
    quiet_hours: QuietHours
    disclosure_defaults: DisclosureDefaults
    change_reason: str = Field(min_length=3, max_length=500)


class WorkspaceSettingsView(StrictModel):
    id: str | None
    party: Literal["BUYER", "SELLER"]
    current_version: int = Field(ge=0)
    current_hash: str
    etag: str
    persisted: bool
    notification_channels: NotificationChannels
    quiet_hours: QuietHours
    disclosure_defaults: DisclosureDefaults
    consent_boundary: Literal["BILATERAL_EXACT_FIELD_MATCH_REQUIRED"]
    updated_at: str | None


class QualificationApprovalCreate(StrictModel):
    action: Literal["APPROVE", "REJECT"]
    reason: str = Field(min_length=3, max_length=1000)


class QualificationSellerResponseCreate(StrictModel):
    response: Literal["FIT", "ANTI_FIT", "NEEDS_INFO"]
    cited_evidence_ids: list[str] = Field(default_factory=list, max_length=30)
    message: str | None = Field(default=None, max_length=2000)

    @field_validator("cited_evidence_ids")
    @classmethod
    def unique_citations(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("cited evidence IDs must be unique")
        return value


class QualificationConsentCreate(StrictModel):
    shared_fields: dict[str, Any]

    @field_validator("shared_fields")
    @classmethod
    def exact_shared_fields(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("shared_fields must not be empty")
        return cast(dict[str, Any], _validate_exact_json(value, path="shared_fields"))


class QualificationIntroductionCreate(QualificationConsentCreate):
    pass


class QualificationMissionView(StrictModel):
    mission: dict[str, Any]
    attempts: list[dict[str, Any]]
    decision: dict[str, Any] | None
    engagement: dict[str, Any] | None
    integrity: dict[str, Any]


class QualificationEngagementView(StrictModel):
    engagement: dict[str, Any]
    seller_response: dict[str, Any] | None
    consents: list[dict[str, Any]]
    introduction: dict[str, Any] | None


class QualificationMutationView(StrictModel):
    resource_type: str
    resource_id: str
    state: str
    input_digest: str | None = None
    replayed: bool = False


class QualificationEventFeed(StrictModel):
    events: list[dict[str, Any]]
    next_cursor: str | None


class QualificationIntegrityView(StrictModel):
    mission_id: str
    verdict: Literal["PASS", "FAIL", "PENDING"]
    checks: list[dict[str, Any]]
    checked_at: str


class QualificationInboxView(StrictModel):
    workspace: Literal["BUYER", "SELLER"]
    items: list[dict[str, Any]]
    next_cursor: str | None = None


class PublicMarketplaceSearchView(StrictModel):
    category: str
    query_model_id: str
    results: list[dict[str, Any]]


class PublicMarketplaceProductView(StrictModel):
    product: dict[str, Any]
