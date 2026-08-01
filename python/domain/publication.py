"""Deny-by-default buyer and seller publication boundaries."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from .errors import DomainValidationError

# Dotted fields intentionally describe the small first-category exchange.  A
# caller can provide a schema-version-specific allowlist, but cannot bypass the
# global denied-field families below.
DEFAULT_REQUIREMENT_BRIEF_ALLOWLIST = frozenset(
    {
        "schema_version",
        "requirement_brief_id",
        "request_id",
        "version",
        "visibility",
        "category_id",
        "jtbd_id",
        "intent",
        "desired_outcome",
        "desired_outcome.metric",
        "desired_outcome.target",
        "desired_outcome.checkpoint_days",
        "seat_count",
        "deadline",
        "region",
        "currency",
        "meeting_platforms",
        "required_capabilities",
        "workflow_requirements",
        "privacy_requirements",
        "privacy_requirements.customer_training_allowed",
        "privacy_requirements.residency",
        "privacy_requirements.retention",
        "privacy_requirements.recording_notice_required",
        "privacy_requirements.source_links_required",
        "identity_requirements",
        "integration_requirements",
        "implementation_constraints",
        "disclosed_stack_interfaces",
    }
)

DEFAULT_PACK_PUBLICATION_ALLOWLIST = frozenset(
    {
        "schema_version",
        "pack_id",
        "version",
        "status",
        "seller_id",
        "product_id",
        "offer_ids",
        "category_ids",
        "jtbd_ids",
        "identity",
        "jobs_and_segments",
        "capabilities",
        "requirements",
        "compatibility",
        "security_privacy",
        "deployment",
        "commercial",
        "contract",
        "facts",
        "fit_rules",
        "anti_fit_rules",
        "dependency_rules",
        "positioning_angles",
        "claims",
        "fulfillment_spec",
        "merchant_chain",
        "operations",
        "learning_policy",
        "published_at",
        "supersedes_version",
        "content_hash",
    }
)

_DENIED_SEGMENTS = frozenset(
    {
        "organization_name",
        "organization_id",
        "company_name",
        "company_identity",
        "buyer_identity",
        "hidden_budget",
        "hidden_maximum",
        "maximum_budget",
        "budget_envelope",
        "payer_identity",
        "employee",
        "employees",
        "contacts",
        "contact_details",
        "email",
        "phone",
        "private_failures",
        "prior_private_failures",
        "competing_bids",
        "competing_offers",
        "competitor_list",
        "unrestricted_stackfile",
        "raw_buyer_passport",
        "roadmap_notes",
        "negotiation_bounds",
        "seller_floor",
        "fulfillment_credentials",
        "provider_credentials",
        "source_material",
        "compilation_history",
    }
)

_DENIED_MARKERS = (
    "secret",
    "password",
    "credential",
    "dynamic_cvv",
    "hidden_budget",
    "hidden_maximum",
    "budget_envelope",
    "roadmap",
    "negotiation_bound",
    "seller_floor",
    "service_account",
    "private_failure",
    "competing_bid",
    "competing_offer",
    "competitor_list",
    "source_material",
    "compilation_history",
    "unpublished_constraint",
)


def _is_denied_segment(value: str) -> bool:
    lowered = value.lower()
    return lowered in _DENIED_SEGMENTS or any(marker in lowered for marker in _DENIED_MARKERS)


def _copy_path(source: Mapping[str, Any], target: dict[str, Any], path: str) -> None:
    segments = path.split(".")
    current: Any = source
    for segment in segments:
        if not isinstance(current, Mapping) or segment not in current:
            return
        current = current[segment]
    destination = target
    for segment in segments[:-1]:
        destination = destination.setdefault(segment, {})
    destination[segments[-1]] = deepcopy(current)


def forbidden_paths(payload: Any, prefix: str = "") -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            lowered = str(key).lower()
            path = f"{prefix}.{key}" if prefix else str(key)
            if _is_denied_segment(lowered):
                found.append(path)
            found.extend(forbidden_paths(value, path))
    elif isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            found.extend(forbidden_paths(value, f"{prefix}[{index}]"))
    return tuple(found)


def assert_public_payload(payload: Mapping[str, Any]) -> None:
    paths = forbidden_paths(payload)
    if paths:
        raise DomainValidationError(
            "publication payload contains denied fields: " + ", ".join(paths)
        )


def _allowlisted_copy(source: Mapping[str, Any], allowed_paths: Iterable[str]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for path in sorted(set(allowed_paths)):
        if any(_is_denied_segment(segment) for segment in path.split(".")):
            raise DomainValidationError(f"allowlist contains prohibited field: {path}")
        _copy_path(source, output, path)
    assert_public_payload(output)
    return output


def sanitize_requirement_brief(
    purchase_brief: Mapping[str, Any],
    *,
    allowlist: Iterable[str] = DEFAULT_REQUIREMENT_BRIEF_ALLOWLIST,
) -> dict[str, Any]:
    """Compile the minimum seller-visible brief; everything else is dropped."""

    return _allowlisted_copy(purchase_brief, allowlist)


def publish_seil_pack(
    product_passport: Mapping[str, Any],
    *,
    allowlist: Iterable[str] = DEFAULT_PACK_PUBLICATION_ALLOWLIST,
) -> dict[str, Any]:
    """Derive a reviewed public Pack without private seller passport fields."""

    return _allowlisted_copy(product_passport, allowlist)
