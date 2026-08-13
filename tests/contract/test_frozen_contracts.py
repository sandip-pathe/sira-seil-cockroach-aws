from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema.validators import validator_for
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "contracts" / "jsonschema"
DEMO = ROOT / "fixtures" / "demo"

ENUMS = {
    "ComponentStatus": [
        "ELIGIBLE",
        "ELIGIBLE_WITH_EXCEPTION",
        "CONDITIONAL",
        "SIRA_INELIGIBLE",
        "SEIL_PASS",
        "UNAVAILABLE",
        "STALE_EVIDENCE",
        "INSUFFICIENT_EVIDENCE",
        "CONFLICTING_EVIDENCE",
        "AUTHORITY_REQUIRED",
        "ADVISORY_ONLY",
    ],
    "SolutionOptionStatus": [
        "SUPPORTED",
        "SUPPORTED_WITH_EXCEPTION",
        "NEEDS_CONDITION",
        "BLOCKED_BY_COMPANY_REQUIREMENT",
        "VENDOR_NOT_SUPPORTED",
        "UNAVAILABLE",
        "NEEDS_EVIDENCE",
        "EVIDENCE_CONFLICT",
        "AUTHORITY_REQUIRED",
        "RESEARCH_ONLY",
    ],
    "DecisionOutcome": ["SELECTED_SOLUTION_PLAN", "NO_ELIGIBLE_SUPPORTED_ACTION"],
    "RankStability": ["STABLE", "UNSTABLE", "UNDETERMINED"],
    "PackAuthority": ["SELLER_SEALED", "PLATFORM_COMPILED", "EXTERNAL_UNSEALED"],
    "SolutionActionType": [
        "REUSE_EXISTING",
        "CONFIGURE_EXISTING",
        "NO_ACTION",
        "BUY",
        "RENEW",
        "RESIZE",
        "REPLACE",
        "CONSOLIDATE",
        "CANCEL",
    ],
    "SolutionPlanLifecycle": ["CANDIDATE", "RESOLUTION_PENDING", "EXECUTABLE", "BLOCKED"],
    "PlanSelectionState": ["SELECTED", "SUPERSEDED", "CANCELLED"],
    "DecisionStage": ["NEED", "COMPANY_FIT", "OPTIONS", "ACTION", "RESULT"],
    "StageStatus": [
        "NOT_STARTED",
        "READY",
        "CURRENT",
        "WAITING",
        "BLOCKED",
        "COMPLETED",
        "SUPERSEDED",
    ],
    "DecisionVersionState": ["CURRENT", "SUPERSEDED"],
    "OperationStatus": [
        "QUEUED",
        "RUNNING",
        "WAITING_FOR_HUMAN",
        "RETRYABLE_ERROR",
        "UNCERTAIN",
        "COMPLETED",
        "FAILED_FINAL",
    ],
    "ExecutionStepType": ["REVIEW", "REQUIRED_AUTHORITY", "EXECUTE_OR_ASSIGN", "VERIFY"],
    "ExecutionStepStatus": [
        "NOT_REACHED",
        "AVAILABLE",
        "CURRENT",
        "BLOCKED",
        "COMPLETED",
        "SKIPPED",
        "FAILED_RETRYABLE",
        "FAILED_FINAL",
    ],
    "ApprovalStatus": [
        "NOT_REQUIRED",
        "NOT_REQUESTED",
        "PENDING",
        "APPROVED",
        "REJECTED",
        "REVOKED",
        "EXPIRED",
        "SUPERSEDED",
    ],
    "PaymentStatus": [
        "NOT_REQUIRED",
        "NOT_STARTED",
        "SESSION_CREATED",
        "CARDHOLDER_PENDING",
        "CHECKOUT_PENDING",
        "MERCHANT_APPROVED",
        "REPORTING",
        "PRAVA_COMPLETED",
        "DECLINED",
        "EXPIRED",
        "UNCERTAIN",
        "FAILED",
    ],
    "FulfillmentStatus": [
        "NOT_REQUIRED",
        "NOT_STARTED",
        "PENDING",
        "PARTIAL",
        "VERIFIED",
        "FAILED_RETRYABLE",
        "FAILED_FINAL",
        "REVOKED",
    ],
    "RequestVisibility": ["PRIVATE", "SELECTIVE", "OPEN_RFP"],
    "ActorRole": [
        "REQUESTER",
        "DECISION_MAKER",
        "POLICY_REVIEWER",
        "BUDGET_OWNER",
        "PROCUREMENT",
        "CARDHOLDER",
        "IT_OPERATIONS",
        "AUDITOR",
        "SELLER_EDITOR",
        "SELLER_REVIEWER",
        "PLATFORM_OPERATOR",
    ],
    "UIActionCapability": [
        "VIEW_DECISION",
        "EDIT_REQUEST",
        "ANSWER_TASK",
        "VIEW_PRIVATE_COMPANY_FACTS",
        "KEEP_OPTION",
        "ELIMINATE_OPTION",
        "ASK_VENDOR",
        "SAVE_OPTION",
        "REQUEST_EVIDENCE",
        "SELECT_PLAN",
        "ACCEPT_EXCEPTION",
        "APPROVE_POLICY",
        "APPROVE_BUDGET",
        "AUTHORIZE_PAYMENT",
        "EXECUTE_CONFIGURATION",
        "VERIFY_FULFILLMENT",
        "PROVIDE_OUTCOME",
        "EXPORT_AUDIT",
        "EDIT_PRODUCT_EVIDENCE",
        "REVIEW_PRODUCT_EVIDENCE",
        "PUBLISH_PRODUCT_EVIDENCE",
        "SUSPEND_PRODUCT_EVIDENCE",
    ],
    "OptionFeedbackAction": [
        "KEEP_FOR_COMPARISON",
        "ELIMINATE",
        "ASK_VENDOR",
        "SAVE",
        "NEED_EVIDENCE",
    ],
    "EngagementStatus": [
        "NOT_STARTED",
        "SELLER_REVIEWING",
        "SELLER_PASSED",
        "OFFER_AVAILABLE",
        "BUYER_CONSENT_PENDING",
        "SELLER_CONSENT_PENDING",
        "INTRODUCTION_READY",
        "DECLINED",
        "EXPIRED",
    ],
    "SellerEvidenceState": [
        "UNCLAIMED",
        "CLAIM_PENDING",
        "CLAIM_DENIED",
        "SELLER_DRAFT",
        "VALIDATION_CONFLICT",
        "IN_REVIEW",
        "CHANGES_REQUESTED",
        "PUBLISH_READY",
        "PUBLISHED",
        "SUPERSEDED",
        "PUBLICATION_FAILED",
    ],
    "SellerReviewDecision": ["REQUEST_CHANGES", "APPROVE", "REJECT"],
    "SellerExportFormat": ["JSON", "HTML", "REUSABLE_ANSWER"],
    "ResultArtifactType": [
        "DECISION_RECORD",
        "CONFIGURATION_CHANGE",
        "CONTRACT_CONFIRMATION",
        "CANCELLATION_CONFIRMATION",
        "ORDER",
        "ENTITLEMENT",
        "MIGRATION_RECORD",
        "STACK_PATCH",
        "OUTCOME_CHECKPOINT",
    ],
}


def load(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(result, dict)
    return result


def registry_and_schemas() -> tuple[Registry, dict[str, dict[str, Any]]]:
    schemas = {path.name: load(path) for path in sorted(SCHEMAS.glob("*.json"))}
    resources = [(schema["$id"], Resource.from_contents(schema)) for schema in schemas.values()]
    return Registry().with_resources(resources), schemas


def test_every_schema_is_valid_draft_2020_12() -> None:
    _registry, schemas = registry_and_schemas()
    assert len(schemas) == 23
    assert len({schema["$id"] for schema in schemas.values()}) == len(schemas)
    for schema in schemas.values():
        validator_for(schema).check_schema(schema)


def test_every_schema_reference_resolves() -> None:
    registry, schemas = registry_and_schemas()

    def resolve_references(value: Any, base_uri: str) -> None:
        if isinstance(value, dict):
            reference = value.get("$ref")
            if isinstance(reference, str):
                registry.resolver(base_uri=base_uri).lookup(reference)
            for child in value.values():
                resolve_references(child, base_uri)
        elif isinstance(value, list):
            for child in value:
                resolve_references(child, base_uri)

    for schema in schemas.values():
        resolve_references(schema, str(schema["$id"]))


def test_every_declared_object_shape_is_closed() -> None:
    _registry, schemas = registry_and_schemas()
    for name, schema in schemas.items():
        if schema.get("type") == "object" and "properties" in schema:
            assert schema.get("additionalProperties") is False, name
        for definition_name, definition in schema.get("$defs", {}).items():
            if definition.get("type") == "object" and "properties" in definition:
                assert definition.get("additionalProperties") is False, (
                    f"{name}#/$defs/{definition_name}"
                )


def test_every_demo_document_validates_against_frozen_schema() -> None:
    registry, schemas = registry_and_schemas()
    assignments: list[tuple[Path, str]] = [
        (DEMO / "buyer_passport.json", "buyer-passport.schema.json"),
        (DEMO / "purchase_brief.json", "purchase-brief.schema.json"),
        (DEMO / "requirement_brief.json", "requirement-brief.schema.json"),
        (DEMO / "stackfile.lock.json", "stackfile-lock.schema.json"),
        (DEMO / "evidence.json", "evidence-bundle.schema.json"),
        (DEMO / "offers.json", "offer.schema.json"),
        (DEMO / "live_quote.json", "offer.schema.json"),
        (DEMO / "approval_plan.json", "approval-plan.schema.json"),
        (DEMO / "procurement_plan.json", "procurement-plan.schema.json"),
        (DEMO / "expected_approval.json", "approval.schema.json"),
        (DEMO / "expected_calibration_run.json", "calibration.schema.json"),
        (DEMO / "expected_decision_ledger.json", "decision-ledger.schema.json"),
        (DEMO / "expected_decision_view.json", "decision-view.schema.json"),
        (DEMO / "expected_entitlement.json", "entitlement.schema.json"),
        (DEMO / "expected_seat_entitlement.json", "entitlement.schema.json"),
        (DEMO / "expected_purchase_intent.json", "purchase-intent.schema.json"),
        (DEMO / "expected_receipt.json", "receipt.schema.json"),
        (DEMO / "expected_selective_engagement.json", "engagement.schema.json"),
        (DEMO / "expected_stack_patch.json", "stack-patch.schema.json"),
    ]
    optional_new_fixtures = [
        (DEMO / "expected_action_run.json", "action-run.schema.json"),
        (DEMO / "expected_seller_evidence_view.json", "seller-evidence-view.schema.json"),
    ]
    assignments.extend(item for item in optional_new_fixtures if item[0].exists())
    assignments.extend(
        (path, "product-passport.schema.json")
        for path in sorted((DEMO / "product_passports").glob("*.json"))
    )
    assignments.extend(
        (path, "seil-pack.schema.json") for path in sorted((DEMO / "packs").glob("*.json"))
    )
    assert len(assignments) >= 27

    for document_path, schema_name in assignments:
        schema = schemas[schema_name]
        validator = validator_for(schema)(schema, registry=registry)
        validator.validate(load(document_path))


def test_shared_enums_match_json_schema_and_openapi_exactly() -> None:
    from sira_api.main import app

    enum_schema = load(SCHEMAS / "enums.schema.json")["$defs"]
    openapi = app.openapi()
    for name, expected in ENUMS.items():
        assert enum_schema[name]["enum"] == expected
        assert openapi["components"]["schemas"][name]["enum"] == expected


def test_decision_view_is_action_neutral_and_server_owned() -> None:
    schema = load(SCHEMAS / "decision-view.schema.json")
    assert schema["additionalProperties"] is False
    assert "candidates" not in schema["properties"]
    assert {
        "workflow",
        "solution_options",
        "rank_stability",
        "selected_action_plan",
        "stack_change",
        "approval",
        "payment",
        "fulfillment",
        "result_artifacts",
    } <= set(schema["required"])
    assert schema["$defs"]["SolutionOption"]["properties"]["action_type"] == {
        "$ref": "enums.schema.json#/$defs/SolutionActionType"
    }
    assert schema["$defs"]["PreferenceScoreBounds"]["required"] == [
        "conservative",
        "optimistic",
    ]
    assert schema["$defs"]["WorkflowView"]["required"] == [
        "current_stage",
        "actor",
        "available_actions",
        "blocking_tasks",
        "active_operation",
        "stage_history",
        "version_links",
    ]


def test_fee_contract_is_one_versioned_buyer_line_item() -> None:
    common = load(SCHEMAS / "common.schema.json")
    fee_rule = common["$defs"]["LineItem"]["allOf"][0]["then"]["properties"]
    assert fee_rule["unit_amount"]["const"] == "10.00"
    assert fee_rule["total_amount"]["const"] == "10.00"
    assert fee_rule["schedule_version"]["const"] == "buyer_txn_demo_v1"

    for name in ("purchase-intent.schema.json", "receipt.schema.json"):
        schema = load(SCHEMAS / name)
        assert schema["properties"]["amount"]["const"] == "990.00"
        assert schema["properties"]["currency"]["const"] == "USD"
        line_items = schema["properties"]["line_items"]
        fee_constraints = line_items.get("allOf", [line_items])
        assert any(item.get("maxContains") == 1 for item in fee_constraints)


def test_required_api_paths_are_frozen_in_openapi() -> None:
    from sira_api.main import app

    required = {
        "/health": {"get"},
        "/ready": {"get"},
        "/v1/demo/reset": {"post"},
        "/v1/decision-requests": {"get", "post"},
        "/v1/decision-requests/{request_id}": {"get"},
        "/v1/decision-requests/{request_id}/discover": {"post"},
        "/v1/decision-requests/{request_id}/decision-view": {"get"},
        "/v1/decision-requests/{request_id}/decision-rules": {"get"},
        "/v1/requirement-briefs/{brief_id}": {"get"},
        "/v1/decision-requests/{request_id}/calibration-runs": {"post"},
        "/v1/decision-requests/{request_id}/solution-options/{solution_plan_id}/actions": {"post"},
        "/v1/engagements/{engagement_id}/consent": {"post"},
        "/v1/decisions/{decision_id}": {"get"},
        "/v1/decisions/{decision_id}/counterfactuals": {"get"},
        "/v1/decisions/{decision_id}/simulations": {"post"},
        "/v1/evaluation-runs/{evaluation_run_id}/replay": {"post"},
        "/v1/decision-rules/{rules_id}/proposals/{proposal_id}/accept": {"post"},
        "/v1/decision-rules/{rules_id}/proposals/{proposal_id}/reject": {"post"},
        "/v1/decisions/{decision_id}/plan-selections": {"post"},
        "/v1/decisions/{decision_id}/action-runs": {"post"},
        "/v1/action-runs/{action_run_id}": {"get"},
        "/v1/seller/products/search": {"get"},
        "/v1/seller/products/{product_id}/claim": {"post"},
        "/v1/seller/products/{product_id}/view": {"get"},
        "/v1/seller/pack-drafts/{draft_id}": {"get", "patch"},
        "/v1/seller/pack-drafts/{draft_id}/evidence": {"post"},
        "/v1/seller/pack-drafts/{draft_id}/submit-review": {"post"},
        "/v1/seller/pack-drafts/{draft_id}/review-decisions": {"post"},
        "/v1/seller/pack-drafts/{draft_id}/publish": {"post"},
        "/v1/seller/pack-versions/{version_id}/suspend": {"post"},
        "/v1/seller/pack-versions/{version_id}/exports": {"get"},
        "/v1/seller/products/{product_id}/activity-metrics": {"get"},
        "/v1/decisions/{decision_id}/purchase-intents": {"post"},
        "/v1/purchase-intents/{intent_id}/approval-requests": {"post"},
        "/v1/approval-requests/{approval_id}/approve": {"post"},
        "/v1/approval-requests/{approval_id}/reject": {"post"},
        "/v1/approval-requests/{approval_id}/revoke": {"post"},
        "/v1/purchase-intents/{intent_id}/prava-sessions": {"post"},
        "/v1/prava/browser-return": {"get"},
        "/v1/purchase-intents/{intent_id}/status": {"get"},
        "/v1/purchase-intents/{intent_id}/reversals": {"post"},
        "/v1/purchase-intents/{intent_id}/outcome-checkpoints": {"post"},
        "/v1/purchases/{purchase_id}/receipt": {"get"},
        "/v1/organizations/{organization_id}/stackfile": {"get"},
    }
    paths = app.openapi()["paths"]
    assert set(required) <= set(paths)
    for path, methods in required.items():
        assert methods <= set(paths[path])


def test_checked_in_openapi_has_no_drift() -> None:
    from sira_api.main import app

    checked_in = load(ROOT / "contracts" / "openapi" / "openapi.json")
    assert checked_in == app.openapi()


def test_fixture_labels_cannot_claim_production_success() -> None:
    for name in (
        "expected_entitlement.json",
        "expected_seat_entitlement.json",
        "expected_receipt.json",
    ):
        document = load(DEMO / name)
        serialized = json.dumps(document, sort_keys=True)
        assert "DEVELOPMENT_FIXTURE_NOT_PRODUCTION" in serialized
        assert document.get("production_success", False) is False
