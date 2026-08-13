from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import respx
from sqlalchemy import select

from domain import content_hash
from persistence.models import BrowserReturnBinding, PurchaseIntent


def idempotency(value: str) -> dict[str, str]:
    return {"Idempotency-Key": value}


def application_for(client: httpx.AsyncClient) -> Any:
    transport = cast(Any, client._transport)
    return transport.app


@pytest.mark.asyncio
async def test_health_and_frozen_demo_projection(api_client: httpx.AsyncClient) -> None:
    health = await api_client.get("/health")
    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "service": "sira-api",
        "version": "0.1.0",
        "database": "not_checked",
        "fixture_mode": True,
    }
    ready = await api_client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["database"] == "configured"

    summary = await api_client.get("/v1/purchase-requests/req_demo")
    assert summary.status_code == 200
    assert summary.json()["status"] == "DECISION_READY"

    decision = await api_client.get("/v1/purchase-requests/req_demo/decision-view")
    assert decision.status_code == 200, decision.text
    payload = decision.json()
    assert len(payload["solution_options"]) == 10
    assert payload["solution_options"][0]["action_type"] == "REPLACE"
    assert payload["solution_options"][0]["status"] == "SUPPORTED"
    assert payload["solution_options"][0]["preference_score"]["conservative"]["display"] == (
        "87.50"
    )
    assert {option["status"] for option in payload["solution_options"]} >= {
        "BLOCKED_BY_COMPANY_REQUIREMENT",
        "VENDOR_NOT_SUPPORTED",
    }
    assert payload["selected_action_plan"] is None
    assert payload["stack_change"] is None


@pytest.mark.asyncio
async def test_degraded_health_returns_typed_503(
    api_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = application_for(api_client).state.database

    async def unavailable() -> bool:
        return False

    monkeypatch.setattr(database, "is_ready", unavailable)
    health = await api_client.get("/health")
    ready = await api_client.get("/ready")

    assert health.status_code == 200
    assert health.json()["database"] == "not_checked"
    assert ready.status_code == 503
    assert ready.json() == {
        "status": "degraded",
        "service": "sira-api",
        "version": "0.1.0",
        "database": "unavailable",
        "fixture_mode": True,
    }
    openapi = (await api_client.get("/openapi.json")).json()
    assert openapi["paths"]["/ready"]["get"]["responses"]["503"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/HealthResponse"}


@pytest.mark.asyncio
async def test_context_and_execution_permissions_are_independent(
    api_client: httpx.AsyncClient,
) -> None:
    submit_only = {
        **idempotency("submit-only-request-0001"),
        "X-Actor-Roles": "can_submit_request",
        "X-Actor-Party": "BUYER",
    }
    created = await api_client.post(
        "/v1/purchase-requests",
        headers=submit_only,
        json={"intent": "Submit without inheriting private context or spend authority"},
    )
    assert created.status_code == 201, created.text

    request_read = await api_client.get(
        f"/v1/purchase-requests/{created.json()['id']}",
        headers={"X-Actor-Roles": "can_submit_request", "X-Actor-Party": "BUYER"},
    )
    assert request_read.status_code == 403
    assert request_read.json()["error"]["code"] == "PERMISSION_REQUIRED"

    private_view = await api_client.get(
        "/v1/purchase-requests/req_demo/decision-view",
        headers={"X-Actor-Roles": "can_submit_request", "X-Actor-Party": "BUYER"},
    )
    assert private_view.status_code == 403
    assert private_view.json()["error"]["code"] == "PERMISSION_REQUIRED"

    execution = await api_client.post(
        "/v1/purchase-intents/pi_missing/prava-sessions",
        headers={
            **idempotency("execute-without-step-up"),
            "X-Actor-Roles": "can_execute_purchase",
            "X-Actor-Party": "BUYER",
            "X-Step-Up-Verified": "false",
        },
        json={"return_url": "https://app.example.test/return"},
    )
    assert execution.status_code == 403
    assert execution.json()["error"]["code"] == "STEP_UP_REQUIRED"


@pytest.mark.asyncio
async def test_brief_privacy_and_ledger(api_client: httpx.AsyncClient) -> None:
    purchase_brief = await api_client.get("/v1/purchase-requests/req_demo/purchase-brief")
    assert purchase_brief.status_code == 200
    assert purchase_brief.json()["visibility"] == "SELECTIVE"

    requirement = await api_client.get("/v1/requirement-briefs/rb_consultco_v1")
    assert requirement.status_code == 200, requirement.text
    serialized = requirement.text.lower()
    forbidden = (
        "organization_id",
        "company_profile",
        "hidden_budget",
        "contact_email",
        "competing_offer",
        "private_failure",
        "employee",
    )
    assert not any(value in serialized for value in forbidden)

    ledger = await api_client.get("/v1/decisions/dec_consultco_v1")
    assert ledger.status_code == 200, ledger.text
    body = ledger.json()
    assert body["decision_hash"].startswith("sha256:")
    assert body["selected_solution_plan_id"] == "plan_5a682ec42084ae355a2d"
    assert body["evaluated_universe"]["canonical_product_count"] == 4
    assert body["evaluated_universe"]["evaluated_solution_plan_count"] == 10


@pytest.mark.asyncio
async def test_arbitrary_request_stays_unevaluated_in_fixture_mode(
    api_client: httpx.AsyncClient,
) -> None:
    created = await api_client.post(
        "/v1/purchase-requests",
        headers=idempotency("create-unbound-request-0001"),
        json={"intent": "Evaluate payroll software for a hundred-person manufacturer"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["evaluation_mode"] == "SCENARIO_SELECTION_REQUIRED"
    assert created.json()["fixture_label"] is None

    discovery = await api_client.post(
        f"/v1/purchase-requests/{created.json()['id']}/discover",
        headers=idempotency("discover-unbound-request-0001"),
    )
    assert discovery.status_code == 409, discovery.text
    assert discovery.json()["error"]["code"] == "DEMO_SCENARIO_REQUIRED"
    assert (
        discovery.json()["error"]["details"]["supported_scenario_id"]
        == "consultco_meeting_intelligence_v1"
    )


@pytest.mark.asyncio
async def test_create_discover_workflow_and_idempotent_replay(
    api_client: httpx.AsyncClient,
) -> None:
    body = {
        "intent": "Find meeting intelligence for another ten-person consulting team",
        "scenario_id": "consultco_meeting_intelligence_v1",
        "desired_outcome": {
            "metric": "decision_retrieval_time_seconds",
            "target": 90,
            "operator": "lte",
            "checkpoint_days": 45,
        },
    }
    first = await api_client.post(
        "/v1/purchase-requests",
        headers=idempotency("create-request-0001"),
        json=body,
    )
    replay = await api_client.post(
        "/v1/purchase-requests",
        headers=idempotency("create-request-0001"),
        json=body,
    )
    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    assert first.json()["evaluation_mode"] == "DEVELOPMENT_FIXTURE_NON_PRODUCTION"
    assert first.json()["fixture_label"] == "DEVELOPMENT_FIXTURE_NON_PRODUCTION"
    request_id = first.json()["id"]
    brief = await api_client.get(f"/v1/purchase-requests/{request_id}/purchase-brief")
    assert brief.json()["desired_outcome"] == {
        "jtbd_id": "capture_meeting_decisions",
        "statement": (
            "decision_retrieval_time_seconds lte 90 seconds at 45 days after verified fulfillment"
        ),
        "metric": "decision_retrieval_time_seconds",
        "target": 90,
        "operator": "lte",
        "unit": "seconds",
        "checkpoint_days": 45,
    }

    conflict = await api_client.post(
        "/v1/purchase-requests",
        headers=idempotency("create-request-0001"),
        json={"intent": "A materially different request body for the same idempotency key"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

    discovery = await api_client.post(
        f"/v1/purchase-requests/{request_id}/discover",
        headers=idempotency("discover-request-0001"),
    )
    assert discovery.status_code == 202, discovery.text
    workflow = discovery.json()
    polled = await api_client.get(workflow["status_url"])
    assert polled.status_code == 200
    assert polled.json()["status"] == "COMPLETED"
    events = await api_client.get(workflow["events_url"])
    assert events.status_code == 200
    assert "event: workflow" in events.text
    assert "Decision ready" in events.text

    view = await api_client.get(f"/v1/purchase-requests/{request_id}/decision-view")
    assert view.status_code == 200, view.text
    assert view.json()["request"]["id"] == request_id
    request_summary = await api_client.get(f"/v1/purchase-requests/{request_id}")
    decision_id = request_summary.json()["decision_id"]
    ledger = await api_client.get(f"/v1/decisions/{decision_id}")
    assert ledger.json()["purchase_brief_id"] == f"pb_{request_id}"
    assert ledger.json()["requirement_brief_id"] == f"rb_{request_id}"
    selected_plan = next(
        plan
        for plan in ledger.json()["solution_plans"]
        if plan["solution_plan_id"] == ledger.json()["selected_solution_plan_id"]
    )
    assert selected_plan["stack_patch_id"] == f"patch_{decision_id}"


@pytest.mark.asyncio
async def test_calibration_proposal_has_no_ranking_effect(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post(
        "/v1/purchase-requests/req_demo/calibration-runs",
        headers=idempotency("calibration-key-0001"),
        json={"proposed_changes": [{"criterion_id": "pref_admin_hours", "proposed_weight": 1}]},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["proposal"]["status"] == "PROPOSED"
    assert body["proposal_effective"] is False
    assert body["purchase_brief_version"] == 1
    assert [result["matches"] for result in body["results"]] == [True, True, True]

    unchanged = await api_client.get("/v1/purchase-requests/req_demo/decision-view")
    assert (
        unchanged.json()["solution_options"][0]["preference_score"]["conservative"]["display"]
        == "87.50"
    )

    dye_failure = await api_client.post(
        "/v1/purchase-requests/req_demo/calibration-runs",
        headers=idempotency("calibration-dye-failure"),
        json={
            "known_failure_candidate_id": "fixture_selected_fit",
            "current_approach_id": "missing_current_approach",
            "expected_qualifier_candidate_id": "fixture_low_price_policy_fail",
        },
    )
    assert dye_failure.status_code == 201, dye_failure.text
    assert [result["matches"] for result in dye_failure.json()["results"]] == [
        False,
        False,
        False,
    ]


@pytest.mark.asyncio
async def test_counterfactual_simulation_replay_and_proposal_decision(
    api_client: httpx.AsyncClient,
) -> None:
    counterfactual = await api_client.get("/v1/decisions/dec_consultco_v1/counterfactuals")
    assert counterfactual.status_code == 200, counterfactual.text
    assert counterfactual.json()["changed"] is True
    assert counterfactual.json()["generic_selected_candidate_id"] == (
        "fixture_low_price_policy_fail"
    )

    simulation = await api_client.post(
        "/v1/decisions/dec_consultco_v1/simulations",
        headers=idempotency("simulation-0001"),
        json={
            "context_mode": "COMPANY_AWARE",
            "preference_weight_overrides": {"pref_native_crm_sync": 5},
            "reason": "Check sensitivity to native CRM synchronization",
        },
    )
    assert simulation.status_code == 201, simulation.text
    assert simulation.json()["authoritative"] is False
    assert simulation.json()["ranking_effect"] is False

    replay = await api_client.post("/v1/evaluation-runs/dec_consultco_v1/replay")
    assert replay.status_code == 200, replay.text
    assert replay.json()["byte_stable"] is True

    calibration = await api_client.post(
        "/v1/purchase-requests/req_demo/calibration-runs",
        headers=idempotency("calibration-accept-0001"),
        json={"proposed_changes": [{"criterion_id": "pref_native_crm_sync", "proposed_weight": 2}]},
    )
    proposal_id = calibration.json()["proposal"]["proposal_id"]
    accepted = await api_client.post(
        f"/v1/purchase-briefs/pb_consultco_v1/proposals/{proposal_id}/accept",
        headers={
            **idempotency("proposal-accept-0001"),
            "X-Actor-Id": "usr_operations_owner",
            "X-Actor-Roles": "operations_owner,can_select_recommendation",
            "X-Step-Up-Verified": "true",
        },
        json={"reason": "Operations owner accepts the calibrated criterion"},
    )
    assert accepted.status_code == 200, accepted.text
    accepted_body = accepted.json()
    assert accepted_body["status"] == "ACCEPTED"
    assert accepted_body["resulting_version"] == 2
    assert accepted_body["resulting_decision_version"] == 2
    assert accepted_body["resulting_decision_id"] != "dec_consultco_v1"
    assert accepted_body["resulting_decision_hash"].startswith("sha256:")

    latest = await api_client.get("/v1/purchase-requests/req_demo/purchase-brief")
    assert latest.json()["version"] == 2

    latest_decision = await api_client.get(
        f"/v1/decisions/{accepted_body['resulting_decision_id']}"
    )
    assert latest_decision.status_code == 200, latest_decision.text
    latest_ledger = latest_decision.json()
    assert latest_ledger["decision_hash"] == accepted_body["resulting_decision_hash"]
    assert latest_ledger["purchase_brief_version"] == 2
    selected_plan = next(
        plan
        for plan in latest_ledger["solution_plans"]
        if plan["solution_plan_id"] == latest_ledger["selected_solution_plan_id"]
    )
    assert selected_plan["dimensions"]["preference"]["conservative"]["display"]

    replayed = await api_client.post(
        f"/v1/purchase-briefs/pb_consultco_v1/proposals/{proposal_id}/accept",
        headers={
            **idempotency("proposal-accept-0001"),
            "X-Actor-Id": "usr_operations_owner",
            "X-Actor-Roles": "operations_owner,can_select_recommendation",
            "X-Step-Up-Verified": "true",
        },
        json={"reason": "Operations owner accepts the calibrated criterion"},
    )
    assert replayed.status_code == 200, replayed.text
    assert replayed.json() == accepted_body

    stale_intent = await api_client.post(
        "/v1/decisions/dec_consultco_v1/purchase-intents",
        headers=idempotency("stale-decision-intent-0001"),
        json={},
    )
    assert stale_intent.status_code == 409, stale_intent.text
    assert stale_intent.json()["error"]["code"] == "DECISION_SUPERSEDED"


@pytest.mark.asyncio
async def test_browser_cannot_invent_approval_policy_or_consent_party(
    api_client: httpx.AsyncClient,
) -> None:
    intent_response = await api_client.post(
        "/v1/decisions/dec_consultco_v1/purchase-intents",
        headers=idempotency("lock-intent-policy-0001"),
        json={},
    )
    intent_id = intent_response.json()["purchase_intent_id"]
    injected_policy = await api_client.post(
        f"/v1/purchase-intents/{intent_id}/approval-requests",
        headers=idempotency("policy-injection-0001"),
        json={"required_roles": ["requester"]},
    )
    assert injected_policy.status_code == 422

    action = await api_client.post(
        "/v1/purchase-requests/req_demo/candidates/fixture_selected_fit/actions",
        headers={
            **idempotency("consent-separation-action"),
            "X-Actor-Id": "usr_same_party",
            "X-Actor-Party": "BUYER",
        },
        json={"action": "REQUEST_OFFER", "reason": "Verify party separation"},
    )
    engagement_id = action.json()["engagement_id"]
    buyer = await api_client.post(
        f"/v1/engagements/{engagement_id}/consent",
        headers={
            **idempotency("same-actor-buyer"),
            "X-Actor-Id": "usr_same_party",
            "X-Actor-Party": "BUYER",
        },
        json={"consent": True},
    )
    assert buyer.status_code == 200
    seller = await api_client.post(
        f"/v1/engagements/{engagement_id}/consent",
        headers={
            **idempotency("same-actor-seller"),
            "X-Actor-Id": "usr_same_party",
            "X-Actor-Party": "SELLER",
            "X-Organization-Id": "org_seller_fixture_d",
        },
        json={"consent": True},
    )
    assert seller.status_code == 403
    assert seller.json()["error"]["code"] == "CONSENT_ACTOR_MISMATCH"


@pytest.mark.asyncio
async def test_private_request_cannot_open_seller_outreach(
    api_client: httpx.AsyncClient,
) -> None:
    created = await api_client.post(
        "/v1/purchase-requests",
        headers=idempotency("private-request-0001"),
        json={
            "intent": "Privately review meeting intelligence without seller outreach",
            "scenario_id": "consultco_meeting_intelligence_v1",
            "visibility": "PRIVATE",
        },
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]

    outreach = await api_client.post(
        f"/v1/purchase-requests/{request_id}/candidates/fixture_selected_fit/actions",
        headers=idempotency("private-outreach-0001"),
        json={"action": "REQUEST_OFFER", "reason": "Ask for a current quote"},
    )
    assert outreach.status_code == 409, outreach.text
    assert outreach.json()["error"]["code"] == "PRIVATE_REQUEST_OUTREACH_FORBIDDEN"


@pytest.mark.asyncio
async def test_selective_engagement_requires_mutual_consent(
    api_client: httpx.AsyncClient,
) -> None:
    action = await api_client.post(
        "/v1/purchase-requests/req_demo/candidates/fixture_selected_fit/actions",
        headers={
            **idempotency("candidate-action-0001"),
            "X-Actor-Id": "usr_buyer_owner",
            "X-Actor-Party": "BUYER",
        },
        json={"action": "REQUEST_OFFER", "reason": "Ask for an exact supported offer"},
    )
    assert action.status_code == 201, action.text
    assert action.json()["contact_details_revealed"] is False
    engagement_id = action.json()["engagement_id"]

    seller_read_headers = {
        "X-Actor-Id": "seller_fixture_d",
        "X-Actor-Party": "SELLER",
        "X-Organization-Id": "org_seller_fixture_d",
    }
    seller_brief = await api_client.get(
        "/v1/requirement-briefs/rb_consultco_v1", headers=seller_read_headers
    )
    assert seller_brief.status_code == 200, seller_brief.text
    assert "organization_id" not in seller_brief.text.lower()
    wrong_seller_tenant = await api_client.get(
        "/v1/requirement-briefs/rb_consultco_v1",
        headers={
            "X-Actor-Id": "seller_fixture_d",
            "X-Actor-Party": "SELLER",
            "X-Organization-Id": "org_unrelated_seller",
        },
    )
    assert wrong_seller_tenant.status_code == 403
    assert wrong_seller_tenant.json()["error"]["code"] == ("REQUIREMENT_BRIEF_ENGAGEMENT_REQUIRED")
    unrelated_seller = await api_client.get(
        "/v1/requirement-briefs/rb_consultco_v1",
        headers={
            "X-Actor-Id": "seller_unrelated",
            "X-Actor-Party": "SELLER",
            "X-Organization-Id": "org_seller_fixture_d",
        },
    )
    assert unrelated_seller.status_code == 403, unrelated_seller.text
    assert unrelated_seller.json()["error"]["code"] == ("REQUIREMENT_BRIEF_ENGAGEMENT_REQUIRED")
    buyer_private_paths = (
        "/v1/purchase-requests/req_demo/decision-view",
        "/v1/purchase-requests/req_demo/purchase-brief",
        "/v1/organizations/org_consultco/stackfile",
        "/v1/workflows/wf_demo_discovery",
    )
    for path in buyer_private_paths:
        denied = await api_client.get(path, headers=seller_read_headers)
        assert denied.status_code == 403, denied.text
        assert denied.json()["error"]["code"] == "SELLER_ROUTE_FORBIDDEN"

    buyer = await api_client.post(
        f"/v1/engagements/{engagement_id}/consent",
        headers={
            **idempotency("buyer-consent-0001"),
            "X-Actor-Id": "usr_buyer_owner",
            "X-Actor-Party": "BUYER",
        },
        json={"consent": True, "scope": "CONTACT_EXCHANGE"},
    )
    assert buyer.status_code == 200
    assert buyer.json()["contact_details"] is None
    assert buyer.json()["status"] == "SELLER_CONSENT_PENDING"

    seller = await api_client.post(
        f"/v1/engagements/{engagement_id}/consent",
        headers={
            **idempotency("seller-consent-0001"),
            "X-Actor-Id": "seller_fixture_d",
            "X-Actor-Party": "SELLER",
            "X-Organization-Id": "org_seller_fixture_d",
        },
        json={"consent": True, "scope": "CONTACT_EXCHANGE"},
    )
    assert seller.status_code == 200
    assert seller.json()["status"] == "INTRODUCTION_READY"
    assert seller.json()["contact_details"] == {
        "buyer": "usr_buyer_owner",
        "seller": "seller_fixture_d",
    }


@pytest.mark.asyncio
async def test_consent_decline_never_reveals_contacts(api_client: httpx.AsyncClient) -> None:
    action = await api_client.post(
        "/v1/purchase-requests/req_demo/candidates/fixture_eligible_runner_up/actions",
        headers={
            **idempotency("candidate-action-decline"),
            "X-Actor-Party": "BUYER",
        },
        json={"action": "REQUEST_OFFER", "reason": "Test a declined introduction"},
    )
    engagement_id = action.json()["engagement_id"]
    declined = await api_client.post(
        f"/v1/engagements/{engagement_id}/consent",
        headers={
            **idempotency("consent-decline-0001"),
            "X-Actor-Party": "BUYER",
        },
        json={"consent": False, "scope": "CONTACT_EXCHANGE"},
    )
    assert declined.status_code == 200
    assert declined.json()["status"] == "DECLINED"
    assert declined.json()["contact_details"] is None


@pytest.mark.asyncio
async def test_decline_revokes_contact_and_stale_consent_replays_cannot_restore_it(
    api_client: httpx.AsyncClient,
) -> None:
    buyer_headers = {
        "X-Actor-Id": "usr_buyer_reconsideration",
        "X-Actor-Party": "BUYER",
    }
    seller_headers = {
        "X-Actor-Id": "seller_fixture_d",
        "X-Actor-Party": "SELLER",
        "X-Organization-Id": "org_seller_fixture_d",
    }
    action = await api_client.post(
        "/v1/purchase-requests/req_demo/candidates/fixture_selected_fit/actions",
        headers={**buyer_headers, **idempotency("candidate-action-reconsideration")},
        json={"action": "REQUEST_OFFER", "reason": "Exercise consent revocation"},
    )
    assert action.status_code == 201, action.text
    engagement_id = action.json()["engagement_id"]
    consent_url = f"/v1/engagements/{engagement_id}/consent"
    consent_body = {"consent": True, "scope": "CONTACT_EXCHANGE"}

    buyer_consent_headers = {
        **buyer_headers,
        **idempotency("buyer-consent-before-decline"),
    }
    buyer = await api_client.post(consent_url, headers=buyer_consent_headers, json=consent_body)
    assert buyer.status_code == 200, buyer.text

    seller_consent_headers = {
        **seller_headers,
        **idempotency("seller-consent-before-decline"),
    }
    mutual = await api_client.post(consent_url, headers=seller_consent_headers, json=consent_body)
    assert mutual.status_code == 200, mutual.text
    assert mutual.json()["status"] == "INTRODUCTION_READY"
    assert mutual.json()["contact_details"] is not None

    declined = await api_client.post(
        consent_url,
        headers={**buyer_headers, **idempotency("buyer-declines-after-mutual")},
        json={"consent": False, "scope": "CONTACT_EXCHANGE"},
    )
    assert declined.status_code == 200, declined.text
    assert declined.json() == {
        "id": engagement_id,
        "status": "DECLINED",
        "buyer_consented": False,
        "seller_consented": True,
        "contact_details": None,
    }

    other_party_replay = await api_client.post(
        consent_url, headers=seller_consent_headers, json=consent_body
    )
    assert other_party_replay.status_code == 200, other_party_replay.text
    assert other_party_replay.json() == declined.json()

    declining_party_stale_replay = await api_client.post(
        consent_url, headers=buyer_consent_headers, json=consent_body
    )
    assert declining_party_stale_replay.status_code == 200
    assert declining_party_stale_replay.json() == declined.json()

    fresh_reconsideration = await api_client.post(
        consent_url,
        headers={**buyer_headers, **idempotency("buyer-fresh-reconsideration")},
        json=consent_body,
    )
    assert fresh_reconsideration.status_code == 200, fresh_reconsideration.text
    assert fresh_reconsideration.json()["status"] == "INTRODUCTION_READY"
    assert fresh_reconsideration.json()["contact_details"] is not None


async def lock_intent_and_start_approval(
    api_client: httpx.AsyncClient,
) -> tuple[dict[str, Any], dict[str, Any]]:
    intent_response = await api_client.post(
        "/v1/decisions/dec_consultco_v1/purchase-intents",
        headers=idempotency("lock-intent-0001"),
        json={},
    )
    assert intent_response.status_code == 201, intent_response.text
    intent = intent_response.json()
    approval_response = await api_client.post(
        f"/v1/purchase-intents/{intent['purchase_intent_id']}/approval-requests",
        headers=idempotency("start-approval-0001"),
        json={},
    )
    assert approval_response.status_code == 201, approval_response.text
    return intent, approval_response.json()


@pytest.mark.asyncio
async def test_fixture_quote_keeps_canonical_hash_while_runtime_ttl_advances(
    api_client: httpx.AsyncClient,
) -> None:
    first_intent, first_approval = await lock_intent_and_start_approval(api_client)
    first_expiry = datetime.fromisoformat(first_approval["expires_at"].replace("Z", "+00:00"))
    assert first_expiry > datetime.now(UTC) + timedelta(minutes=59)
    assert first_intent["locked_at"] == "2026-08-02T01:10:00Z"

    await asyncio.sleep(0.05)
    reset = await api_client.post("/v1/demo/reset")
    assert reset.status_code == 200, reset.text
    second_intent, second_approval = await lock_intent_and_start_approval(api_client)
    second_expiry = datetime.fromisoformat(second_approval["expires_at"].replace("Z", "+00:00"))
    assert second_expiry > first_expiry

    database = application_for(api_client).state.database
    async with database.transaction("org_consultco") as session:
        record = (
            await session.execute(
                select(PurchaseIntent).where(
                    PurchaseIntent.id == second_intent["purchase_intent_id"]
                )
            )
        ).scalar_one()
        assert record.intent_hash == record.payload["intent_hash"]
        assert record.intent_hash == content_hash(
            {key: value for key, value in record.payload.items() if key != "intent_hash"}
        )


@pytest.mark.asyncio
async def test_decision_change_supersedes_pending_exact_hash_approval(
    api_client: httpx.AsyncClient,
) -> None:
    intent, approval = await lock_intent_and_start_approval(api_client)
    calibration = await api_client.post(
        "/v1/purchase-requests/req_demo/calibration-runs",
        headers=idempotency("calibration-supersede-0001"),
        json={"proposed_changes": [{"criterion_id": "pref_native_crm_sync", "proposed_weight": 2}]},
    )
    assert calibration.status_code == 201, calibration.text
    proposal_id = calibration.json()["proposal"]["proposal_id"]
    accepted = await api_client.post(
        f"/v1/purchase-briefs/pb_consultco_v1/proposals/{proposal_id}/accept",
        headers={
            **idempotency("proposal-supersede-0001"),
            "X-Actor-Id": "usr_operations_owner",
            "X-Actor-Roles": "operations_owner,can_select_recommendation",
            "X-Step-Up-Verified": "true",
        },
        json={"reason": "Use the new approved rule version"},
    )
    assert accepted.status_code == 200, accepted.text

    status = await api_client.get(f"/v1/purchase-intents/{intent['purchase_intent_id']}/status")
    assert status.status_code == 200, status.text
    assert status.json()["approval_status"] == "SUPERSEDED"

    stale_approval = await api_client.post(
        f"/v1/approval-requests/{approval['id']}/approve",
        headers={
            **idempotency("approve-superseded-0001"),
            "X-Actor-Id": "usr_operations_owner",
            "X-Actor-Roles": "operations_owner,can_approve_purchase",
            "X-Step-Up-Verified": "true",
        },
        json={
            "intent_hash": approval["intent_hash"],
            "actor_role": "operations_owner",
        },
    )
    assert stale_approval.status_code == 409, stale_approval.text
    assert stale_approval.json()["error"]["code"] == "DECISION_SUPERSEDED"

    restart = await api_client.post(
        f"/v1/purchase-intents/{intent['purchase_intent_id']}/approval-requests",
        headers=idempotency("restart-superseded-0001"),
        json={},
    )
    assert restart.status_code == 409, restart.text
    assert restart.json()["error"]["code"] == "DECISION_SUPERSEDED"


@pytest.mark.asyncio
async def test_service_identity_cannot_approve_even_with_role_and_step_up(
    api_client: httpx.AsyncClient,
) -> None:
    _intent, approval = await lock_intent_and_start_approval(api_client)
    response = await api_client.post(
        f"/v1/approval-requests/{approval['id']}/approve",
        headers={
            **idempotency("service-identity-approval"),
            "X-Actor-Id": "svc_budget_automation",
            "X-Actor-Roles": "budget_owner,can_approve_purchase",
            "X-Step-Up-Verified": "true",
            "X-Identity-Kind": "SERVICE",
        },
        json={
            "intent_hash": approval["intent_hash"],
            "actor_role": "budget_owner",
        },
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "HUMAN_IDENTITY_REQUIRED"


@pytest.mark.asyncio
async def test_approval_stages_are_serial_and_rejection_is_exact_hash_bound(
    api_client: httpx.AsyncClient,
) -> None:
    intent, approval = await lock_intent_and_start_approval(api_client)

    out_of_order = await api_client.post(
        f"/v1/approval-requests/{approval['id']}/approve",
        headers={
            **idempotency("approve-out-of-order-0001"),
            "X-Actor-Id": "usr_budget_owner",
            "X-Actor-Roles": "budget_owner,can_approve_purchase",
            "X-Step-Up-Verified": "true",
        },
        json={"intent_hash": approval["intent_hash"], "actor_role": "budget_owner"},
    )
    assert out_of_order.status_code == 409, out_of_order.text
    assert out_of_order.json()["error"]["code"] == "APPROVAL_STAGE_OUT_OF_ORDER"
    assert out_of_order.json()["error"]["details"]["required_role"] == "operations_owner"

    wrong_hash = await api_client.post(
        f"/v1/approval-requests/{approval['id']}/reject",
        headers={
            **idempotency("reject-wrong-hash-0001"),
            "X-Actor-Id": "usr_operations_owner",
            "X-Actor-Roles": "operations_owner,can_approve_purchase",
            "X-Step-Up-Verified": "true",
        },
        json={
            "intent_hash": "sha256:" + "0" * 64,
            "actor_role": "operations_owner",
            "reason": "The approved operating plan is incomplete",
        },
    )
    assert wrong_hash.status_code == 409, wrong_hash.text

    rejected = await api_client.post(
        f"/v1/approval-requests/{approval['id']}/reject",
        headers={
            **idempotency("reject-current-stage-0001"),
            "X-Actor-Id": "usr_operations_owner",
            "X-Actor-Roles": "operations_owner,can_approve_purchase",
            "X-Step-Up-Verified": "true",
        },
        json={
            "intent_hash": approval["intent_hash"],
            "actor_role": "operations_owner",
            "reason": "The approved operating plan is incomplete",
        },
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "REJECTED"

    status = await api_client.get(f"/v1/purchase-intents/{intent['purchase_intent_id']}/status")
    assert status.status_code == 200, status.text
    assert status.json()["approval_status"] == "REJECTED"
    assert status.json()["payment_status"] == "NOT_STARTED"


@pytest.mark.asyncio
async def test_exact_hash_approval_and_separate_states(api_client: httpx.AsyncClient) -> None:
    intent, approval = await lock_intent_and_start_approval(api_client)

    wrong_hash = "sha256:" + "0" * 64
    mismatch = await api_client.post(
        f"/v1/approval-requests/{approval['id']}/approve",
        headers={
            **idempotency("approve-mismatch-0001"),
            "X-Actor-Id": "usr_wrong_hash",
            "X-Actor-Roles": "operations_owner,can_approve_purchase",
            "X-Step-Up-Verified": "true",
        },
        json={
            "intent_hash": wrong_hash,
            "actor_role": "operations_owner",
        },
    )
    assert mismatch.status_code == 409

    roles = [
        "operations_owner",
        "security_privacy_owner",
        "legal_owner",
        "budget_owner",
    ]
    for index, role in enumerate(roles):
        response = await api_client.post(
            f"/v1/approval-requests/{approval['id']}/approve",
            headers={
                **idempotency(f"approve-role-{index:04d}"),
                "X-Actor-Id": f"usr_{role}",
                "X-Actor-Roles": f"{role},can_approve_purchase",
                "X-Step-Up-Verified": "true",
            },
            json={
                "intent_hash": approval["intent_hash"],
                "actor_role": role,
            },
        )
        assert response.status_code == 200, response.text
    assert response.json()["status"] == "APPROVED"

    status_response = await api_client.get(
        f"/v1/purchase-intents/{intent['purchase_intent_id']}/status"
    )
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["approval_status"] == "APPROVED"
    assert status_body["payment_status"] == "NOT_STARTED"
    assert status_body["fulfillment_status"] == "NOT_STARTED"
    assert status_body["deployment_state"] == "NOT_STARTED"
    assert status_body["outcome_state"] == "NOT_MEASURED"


@pytest.mark.asyncio
async def test_approved_authority_can_be_revoked_before_checkout(
    api_client: httpx.AsyncClient,
) -> None:
    intent, approval = await lock_intent_and_start_approval(api_client)
    roles = [
        "operations_owner",
        "security_privacy_owner",
        "legal_owner",
        "budget_owner",
    ]
    for index, role in enumerate(roles):
        approved = await api_client.post(
            f"/v1/approval-requests/{approval['id']}/approve",
            headers={
                **idempotency(f"revoke-setup-{index}"),
                "X-Actor-Id": f"usr_{role}",
                "X-Actor-Roles": f"{role},can_approve_purchase",
                "X-Step-Up-Verified": "true",
            },
            json={"intent_hash": approval["intent_hash"], "actor_role": role},
        )
        assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"

    wrong_hash = await api_client.post(
        f"/v1/approval-requests/{approval['id']}/revoke",
        headers={
            **idempotency("revoke-wrong-hash"),
            "X-Actor-Id": "usr_operations_owner",
            "X-Actor-Roles": "operations_owner,can_approve_purchase",
            "X-Step-Up-Verified": "true",
        },
        json={
            "intent_hash": "sha256:" + "0" * 64,
            "actor_role": "operations_owner",
            "reason": "The purchase authority must be withdrawn",
        },
    )
    assert wrong_hash.status_code == 409

    headers = {
        **idempotency("revoke-approved-intent"),
        "X-Actor-Id": "usr_operations_owner",
        "X-Actor-Roles": "operations_owner,can_approve_purchase",
        "X-Step-Up-Verified": "true",
    }
    body = {
        "intent_hash": approval["intent_hash"],
        "actor_role": "operations_owner",
        "reason": "Company approval was explicitly withdrawn",
    }
    revoked = await api_client.post(
        f"/v1/approval-requests/{approval['id']}/revoke",
        headers=headers,
        json=body,
    )
    replay = await api_client.post(
        f"/v1/approval-requests/{approval['id']}/revoke",
        headers=headers,
        json=body,
    )
    assert revoked.status_code == replay.status_code == 200
    assert revoked.json() == replay.json()
    assert revoked.json()["status"] == "REVOKED"

    status = await api_client.get(f"/v1/purchase-intents/{intent['purchase_intent_id']}/status")
    assert status.status_code == 200
    assert status.json()["approval_status"] == "REVOKED"
    assert status.json()["payment_status"] == "NOT_STARTED"

    reapprove = await api_client.post(
        f"/v1/approval-requests/{approval['id']}/approve",
        headers={
            **idempotency("approve-after-revoke"),
            "X-Actor-Id": "usr_operations_owner",
            "X-Actor-Roles": "operations_owner,can_approve_purchase",
            "X-Step-Up-Verified": "true",
        },
        json={"intent_hash": approval["intent_hash"], "actor_role": "operations_owner"},
    )
    assert reapprove.status_code == 409


@pytest.mark.asyncio
async def test_prava_setup_blocker_and_no_fake_receipt(api_client: httpx.AsyncClient) -> None:
    intent, _approval = await lock_intent_and_start_approval(api_client)
    intent_id = intent["purchase_intent_id"]
    provider = await api_client.post(
        f"/v1/purchase-intents/{intent_id}/prava-sessions",
        headers=idempotency("prava-session-0001"),
        json={"return_url": "https://localhost:3000/purchase/return"},
    )
    assert provider.status_code == 503
    error = provider.json()["error"]
    assert error["code"] == "PROVIDER_SETUP_BLOCKED"
    assert "PRAVA_SECRET_KEY" in error["details"]["missing_configuration"]
    assert "credential" not in provider.text.lower()

    receipt = await api_client.get(f"/v1/purchases/{intent_id}/receipt")
    assert receipt.status_code == 404
    assert receipt.json()["error"]["code"] == "RECEIPT_NOT_AVAILABLE"


@pytest.mark.asyncio
async def test_configured_prava_session_uses_real_adapter_and_updates_canonical_state(
    api_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    intent, approval = await lock_intent_and_start_approval(api_client)
    for index, role in enumerate(
        ["operations_owner", "security_privacy_owner", "legal_owner", "budget_owner"]
    ):
        approved = await api_client.post(
            f"/v1/approval-requests/{approval['id']}/approve",
            headers={
                **idempotency(f"provider-approve-{index:04d}"),
                "X-Actor-Id": f"usr_provider_{role}",
                "X-Actor-Roles": f"{role},can_approve_purchase",
                "X-Step-Up-Verified": "true",
            },
            json={"intent_hash": approval["intent_hash"], "actor_role": role},
        )
        assert approved.status_code == 200, approved.text

    environment = {
        "PRAVA_BASE_URL": "https://api.prava.test",
        "PRAVA_SECRET_KEY": "x",
        "PRAVA_MERCHANT_URL": "https://merchant-d.example.test",
        "PRAVA_CALLBACK_URL": "https://api.example.test/prava/callback",
        "PRAVA_USER_EMAIL": "fixture-user@example.test",
        "PRAVA_HOSTED_CHECKOUT_HOSTS": "checkout.prava.test",
        "PRAVA_MERCHANT_COUNTRY": "US",
        "CONTROLLED_MERCHANT_BASE_URL": "https://merchant-d.example.test",
        "CONTROLLED_MERCHANT_API_KEY": "x",
        "CONTROLLED_MERCHANT_ID": "merchant_fixture_d",
        "WEB_BASE_URL": "https://app.example.test",
    }
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    provider_started_at = datetime.now(UTC)
    with respx.mock(assert_all_called=True) as mock:
        mock.post("https://api.prava.test/v1/sessions").mock(
            return_value=httpx.Response(
                201,
                json={
                    "session_id": "ses_real_contract_1",
                    "order_id": "ord_real_contract_1",
                    "iframe_url": "https://checkout.prava.test/session/1",
                    "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                },
            )
        )
        response = await api_client.post(
            f"/v1/purchase-intents/{intent['purchase_intent_id']}/prava-sessions",
            headers=idempotency("configured-prava-session"),
            json={"return_url": "https://app.example.test/purchase/return"},
        )
        provider_request = json.loads(mock.calls[0].request.content)
        callback_url = provider_request["callback_url"]
        state = parse_qs(urlsplit(callback_url).query)["state"][0]
    provider_finished_at = datetime.now(UTC)

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "SESSION_CREATED"
    assert response.json()["production_verified"] is False
    assert response.json()["hosted_url"].startswith("https://checkout.prava.test/")
    assert "state" not in response.json()
    assert urlsplit(callback_url)._replace(query="").geturl() == environment["PRAVA_CALLBACK_URL"]
    database = application_for(api_client).state.database
    async with database.transaction("org_consultco") as session:
        binding = (
            await session.execute(
                select(BrowserReturnBinding).where(
                    BrowserReturnBinding.purchase_intent_id == intent["purchase_intent_id"]
                )
            )
        ).scalar_one()
        binding_expiry = binding.expires_at
        if binding_expiry.tzinfo is None:
            binding_expiry = binding_expiry.replace(tzinfo=UTC)
        assert binding_expiry >= provider_started_at + timedelta(seconds=599)
        assert binding_expiry <= provider_finished_at + timedelta(seconds=601)

    tampered_state = f"{state[:-1]}{'A' if state[-1] != 'A' else 'B'}"
    tampered = await api_client.post(
        "/v1/prava/browser-return",
        json={
            "state": tampered_state,
            "return_url": "https://app.example.test/purchase/return",
        },
    )
    assert tampered.status_code == 400
    wrong_actor = await api_client.post(
        "/v1/prava/browser-return",
        headers={"X-Actor-Id": "usr_different_cardholder"},
        json={
            "state": state,
            "return_url": "https://app.example.test/purchase/return",
        },
    )
    assert wrong_actor.status_code == 403
    wrong_return = await api_client.post(
        "/v1/prava/browser-return",
        json={
            "state": state,
            "return_url": "https://app.example.test/purchase/different",
        },
    )
    assert wrong_return.status_code == 403

    browser_return = await api_client.post(
        "/v1/prava/browser-return",
        json={
            "state": state,
            "return_url": "https://app.example.test/purchase/return",
        },
    )
    assert browser_return.status_code == 202, browser_return.text
    workflow = browser_return.json()
    assert workflow["workflow_id"] == f"wf_checkout_{intent['purchase_intent_id']}"
    assert workflow["status_url"].endswith(workflow["workflow_id"])
    workflow_status = await api_client.get(workflow["status_url"])
    assert workflow_status.status_code == 200
    assert workflow_status.json()["status"] == "PENDING"

    replay = await api_client.post(
        "/v1/prava/browser-return",
        json={
            "state": state,
            "return_url": "https://app.example.test/purchase/return",
        },
    )
    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == "CALLBACK_STATE_REPLAYED"
    status_response = await api_client.get(
        f"/v1/purchase-intents/{intent['purchase_intent_id']}/status"
    )
    assert status_response.json()["payment_status"] == "CARDHOLDER_PENDING"


@pytest.mark.asyncio
async def test_prava_session_create_can_retry_after_uncertain_provider_failure(
    api_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    intent, approval = await lock_intent_and_start_approval(api_client)
    for index, role in enumerate(
        ["operations_owner", "security_privacy_owner", "legal_owner", "budget_owner"]
    ):
        approved = await api_client.post(
            f"/v1/approval-requests/{approval['id']}/approve",
            headers={
                **idempotency(f"retry-provider-approve-{index:04d}"),
                "X-Actor-Id": f"usr_retry_provider_{role}",
                "X-Actor-Roles": f"{role},can_approve_purchase",
                "X-Step-Up-Verified": "true",
            },
            json={"intent_hash": approval["intent_hash"], "actor_role": role},
        )
        assert approved.status_code == 200, approved.text

    environment = {
        "PRAVA_BASE_URL": "https://api.prava.test",
        "PRAVA_SECRET_KEY": "x",
        "PRAVA_MERCHANT_URL": "https://merchant-d.example.test",
        "PRAVA_CALLBACK_URL": "https://api.example.test/prava/callback",
        "PRAVA_USER_EMAIL": "fixture-user@example.test",
        "PRAVA_HOSTED_CHECKOUT_HOSTS": "checkout.prava.test",
        "PRAVA_MERCHANT_COUNTRY": "US",
        "CONTROLLED_MERCHANT_BASE_URL": "https://merchant-d.example.test",
        "CONTROLLED_MERCHANT_API_KEY": "x",
        "CONTROLLED_MERCHANT_ID": "merchant_fixture_d",
        "WEB_BASE_URL": "https://app.example.test",
    }
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    with respx.mock(assert_all_called=True) as mock:
        mock.post("https://api.prava.test/v1/sessions").mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(
                    201,
                    json={
                        "session_id": "ses_recovered_contract",
                        "order_id": "ord_recovered_contract",
                        "iframe_url": "https://checkout.prava.test/session/recovered",
                        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                    },
                ),
            ]
        )
        first = await api_client.post(
            f"/v1/purchase-intents/{intent['purchase_intent_id']}/prava-sessions",
            headers=idempotency("retry-configured-prava-session"),
            json={"return_url": "https://app.example.test/purchase/return"},
        )
        status = await api_client.get(f"/v1/purchase-intents/{intent['purchase_intent_id']}/status")
        second = await api_client.post(
            f"/v1/purchase-intents/{intent['purchase_intent_id']}/prava-sessions",
            headers=idempotency("retry-configured-prava-session"),
            json={"return_url": "https://app.example.test/purchase/return"},
        )

    assert first.status_code == 503
    assert first.json()["error"]["next_action"] == "retry_provider_session"
    assert status.json()["payment_status"] == "NOT_STARTED"
    assert second.status_code == 201, second.text
    assert second.json()["status"] == "SESSION_CREATED"


@pytest.mark.asyncio
async def test_stackfile_is_current_plus_proposed_not_active(
    api_client: httpx.AsyncClient,
) -> None:
    stackfile = await api_client.get("/v1/organizations/org_consultco/stackfile")
    assert stackfile.status_code == 200, stackfile.text
    payload = stackfile.json()
    assert payload["current"]["lock"]["snapshot"] == 1
    proposed = payload["proposed_patch"]
    assert proposed["status"] == "PROPOSED"
    assert proposed["operations"][0]["instance"]["lifecycle"] == "staged"
    assert all(
        instance["lifecycle"] == "active" for instance in payload["current"]["lock"]["instances"]
    )


@pytest.mark.asyncio
async def test_unknown_request_fields_use_stable_error_envelope(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.post(
        "/v1/purchase-requests",
        headers=idempotency("invalid-request-0001"),
        json={"intent": "A sufficiently long request", "hidden_budget": "9999"},
    )
    assert response.status_code == 422
    payload = response.json()["error"]
    assert payload["code"] == "VALIDATION_ERROR"
    assert payload["retryable"] is False
    assert "9999" not in response.text
