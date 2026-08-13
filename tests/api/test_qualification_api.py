from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import httpx
import pytest

from domain import content_hash
from persistence.database import Database
from persistence.qualification_models import (
    ActiveProductBundle,
    CatalogProjectionVersion,
    DecisionDependency,
    ProductBundle,
    ProductTwinVersion,
    QualificationAttempt,
    QualificationDecision,
    QualificationMission,
    QualificationMissionBundle,
)


def _database_for(client: httpx.AsyncClient) -> Database:
    transport = cast(httpx.ASGITransport, client._transport)
    return cast(Database, transport.app.state.database)


def _mission_body() -> dict[str, object]:
    return {
        "buyer_context": {
            "company": "Northstar Labs",
            "budget": "25000",
            "incumbent": "Manual research",
        },
        "requirement_brief": {
            "category": "meeting intelligence",
            "goal": "Select an EU-hosted meeting intelligence platform for sales.",
            "seller_visible_requirements": {
                "hosting_region": "EU",
                "seat_count": 40,
            },
            "criteria": [
                {
                    "id": "eu_hosting",
                    "label": "EU hosting",
                    "requirement": "Customer data remains in the EU.",
                    "priority": "MUST",
                }
            ],
        },
        "procurement_policy": {
            "human_approval": True,
            "maximum_annual_cost": "25000",
        },
    }


@pytest.mark.asyncio
async def test_qualification_mission_contract_and_idempotency(
    api_client: httpx.AsyncClient,
) -> None:
    headers = {"Idempotency-Key": "qualification-create-1"}
    first = await api_client.post(
        "/v1/qualification/missions", headers=headers, json=_mission_body()
    )
    replay = await api_client.post(
        "/v1/qualification/missions", headers=headers, json=_mission_body()
    )

    assert first.status_code == replay.status_code == 201
    assert replay.json()["resource_id"] == first.json()["resource_id"]
    assert replay.json()["replayed"] is True
    assert first.headers["location"].endswith(first.json()["resource_id"])

    mission = await api_client.get(first.headers["location"])
    assert mission.status_code == 200
    payload = mission.json()
    assert payload["mission"]["state"] == "READY"
    assert payload["mission"]["buyer_context"]["company"] == "Northstar Labs"
    assert payload["attempts"] == []
    assert payload["decision"] is None
    assert payload["integrity"]["verdict"] == "PENDING"

    integrity = await api_client.get(f"{first.headers['location']}/integrity")
    assert integrity.status_code == 200
    assert integrity.json()["checks"][0]["name"] == "mission_input_hashes"

    openapi = (await api_client.get("/openapi.json")).json()
    assert "/v1/qualification/engagements/{engagement_id}/introduction" in openapi["paths"]
    parameters = openapi["paths"]["/v1/qualification/decisions/{decision_id}/approval"]["post"][
        "parameters"
    ]
    assert any(
        parameter["name"] == "If-Match"
        and parameter["in"] == "header"
        and parameter["required"] is True
        for parameter in parameters
    )


@pytest.mark.asyncio
async def test_qualification_contract_rejects_float_and_seller_mission_access(
    api_client: httpx.AsyncClient,
) -> None:
    body = _mission_body()
    buyer_context = body["buyer_context"]
    assert isinstance(buyer_context, dict)
    buyer_context["budget"] = 25000.5
    invalid = await api_client.post(
        "/v1/qualification/missions",
        headers={"Idempotency-Key": "qualification-invalid-1"},
        json=body,
    )
    assert invalid.status_code == 422

    seller = await api_client.post(
        "/v1/qualification/missions",
        headers={
            "Idempotency-Key": "qualification-seller-1",
            "X-Actor-Party": "SELLER",
            "X-Actor-Roles": "seller_editor,can_submit_request",
        },
        json=_mission_body(),
    )
    assert seller.status_code == 403
    assert seller.json()["error"]["code"] == "SELLER_ROUTE_FORBIDDEN"


@pytest.mark.asyncio
async def test_company_context_versions_retire_and_pin_into_mission(
    api_client: httpx.AsyncClient,
) -> None:
    created = await api_client.post(
        "/v1/qualification/company-context",
        headers={"Idempotency-Key": "context-create-1"},
        json={
            "kind": "CONSTRAINT",
            "label": "EU data boundary",
            "payload": {"hosting_region": "EU", "hard_requirement": True},
            "change_reason": "Initial procurement policy",
        },
    )
    assert created.status_code == 201
    item_id = created.json()["resource_id"]
    create_replay = await api_client.post(
        "/v1/qualification/company-context",
        headers={"Idempotency-Key": "context-create-1"},
        json={
            "kind": "CONSTRAINT",
            "label": "EU data boundary",
            "payload": {"hosting_region": "EU", "hard_requirement": True},
            "change_reason": "Initial procurement policy",
        },
    )
    assert create_replay.status_code == 201
    assert create_replay.json()["replayed"] is True

    active_list = await api_client.get("/v1/qualification/company-context")
    assert active_list.status_code == 200
    assert [item["id"] for item in active_list.json()["items"]] == [item_id]

    current = await api_client.get(f"/v1/qualification/company-context/{item_id}")
    assert current.status_code == 200
    assert current.json()["item"]["current_version"] == 1
    etag = current.headers["etag"]

    unchanged = await api_client.put(
        f"/v1/qualification/company-context/{item_id}",
        headers={"Idempotency-Key": "context-unchanged-1", "If-Match": etag},
        json={
            "label": "EU data boundary",
            "payload": {"hosting_region": "EU", "hard_requirement": True},
            "change_reason": "No material change",
        },
    )
    assert unchanged.status_code == 409
    assert unchanged.json()["error"]["code"] == "COMPANY_CONTEXT_UNCHANGED"

    revised = await api_client.put(
        f"/v1/qualification/company-context/{item_id}",
        headers={"Idempotency-Key": "context-update-1", "If-Match": etag},
        json={
            "label": "European data residency",
            "payload": {"hosting_region": "EU", "hard_requirement": True, "scope": "customer"},
            "change_reason": "Clarified the covered data class",
        },
    )
    assert revised.status_code == 200
    assert revised.json()["input_digest"] != created.json()["input_digest"]
    update_replay = await api_client.put(
        f"/v1/qualification/company-context/{item_id}",
        headers={"Idempotency-Key": "context-update-1", "If-Match": etag},
        json={
            "label": "European data residency",
            "payload": {"hosting_region": "EU", "hard_requirement": True, "scope": "customer"},
            "change_reason": "Clarified the covered data class",
        },
    )
    assert update_replay.status_code == 412

    history = await api_client.get(f"/v1/qualification/company-context/{item_id}")
    assert [version["version"] for version in history.json()["versions"]] == [2, 1]
    update_replay = await api_client.put(
        f"/v1/qualification/company-context/{item_id}",
        headers={
            "Idempotency-Key": "context-update-1",
            "If-Match": history.headers["etag"],
        },
        json={
            "label": "European data residency",
            "payload": {"hosting_region": "EU", "hard_requirement": True, "scope": "customer"},
            "change_reason": "Clarified the covered data class",
        },
    )
    assert update_replay.status_code == 200
    assert update_replay.json()["replayed"] is True

    body = _mission_body()
    body["company_context_item_ids"] = [item_id]
    mission = await api_client.post(
        "/v1/qualification/missions",
        headers={"Idempotency-Key": "mission-with-context-1"},
        json=body,
    )
    projection = await api_client.get(mission.headers["location"])
    memory = projection.json()["mission"]["buyer_context"]["company_memory"]
    assert memory[0]["item_id"] == item_id
    assert memory[0]["version"] == 2
    assert memory[0]["payload"]["scope"] == "customer"

    retired = await api_client.post(
        f"/v1/qualification/company-context/{item_id}/retire",
        headers={
            "Idempotency-Key": "context-retire-1",
            "If-Match": history.headers["etag"],
        },
    )
    assert retired.status_code == 200
    assert retired.json()["state"] == "RETIRED"
    retired_replay = await api_client.post(
        f"/v1/qualification/company-context/{item_id}/retire",
        headers={
            "Idempotency-Key": "context-retire-1",
            "If-Match": history.headers["etag"],
        },
    )
    assert retired_replay.status_code == 200
    assert retired_replay.json()["replayed"] is True

    retired_list = await api_client.get("/v1/qualification/company-context?include_retired=true")
    assert retired_list.status_code == 200
    assert retired_list.json()["items"][0]["state"] == "RETIRED"
    active_list = await api_client.get("/v1/qualification/company-context")
    assert active_list.json()["items"] == []

    retired_update = await api_client.put(
        f"/v1/qualification/company-context/{item_id}",
        headers={
            "Idempotency-Key": "context-retired-update-1",
            "If-Match": retired_list.json()["items"][0]["etag"],
        },
        json={
            "label": "Retired context",
            "payload": {"hosting_region": "US"},
            "change_reason": "Should fail",
        },
    )
    assert retired_update.status_code == 409
    assert retired_update.json()["error"]["code"] == "COMPANY_CONTEXT_RETIRED"

    missing = await api_client.get("/v1/qualification/company-context/ctxitem_missing")
    assert missing.status_code == 404

    invalid_body = _mission_body()
    invalid_body["company_context_item_ids"] = [item_id]
    invalid = await api_client.post(
        "/v1/qualification/missions",
        headers={"Idempotency-Key": "mission-retired-context-1"},
        json=invalid_body,
    )
    assert invalid.status_code == 409
    assert invalid.json()["error"]["code"] == "COMPANY_CONTEXT_SELECTION_INVALID"


@pytest.mark.asyncio
async def test_qualification_bilateral_lifecycle_is_idempotent_and_private(
    api_client: httpx.AsyncClient,
) -> None:
    created = await api_client.post(
        "/v1/qualification/missions",
        headers={"Idempotency-Key": "lifecycle-create-1"},
        json=_mission_body(),
    )
    assert created.status_code == 201
    mission_id = created.json()["resource_id"]
    attempt_id = "qattempt_api_lifecycle"
    decision_id = "qdecision_api_lifecycle"
    product_id = "product_api_lifecycle"
    bundle_id = "bundle_api_lifecycle"
    bundle_digest = content_hash({"bundle": bundle_id})
    input_digest = content_hash({"attempt": attempt_id})
    decision_payload = {
        "recommended_product_id": product_id,
        "summary": "The pinned seller bundle satisfies the buyer requirement.",
        "cited_dependency_ids": [product_id],
        "criteria": [{"criterion": "eu_hosting", "result": "PASS"}],
        "confidence": "0.91",
    }
    decision_digest = content_hash(
        {
            "attempt_id": attempt_id,
            "input_digest": input_digest,
            "recommended_product_id": product_id,
            "payload": decision_payload,
        }
    )
    database = _database_for(api_client)
    twin_id = "twin_api_lifecycle"
    catalog_id = "catalog_api_lifecycle"
    twin_digest = content_hash({"twin": twin_id})
    catalog_digest = content_hash({"catalog": catalog_id})
    async with database.transaction("org_seller_a") as session:
        session.add_all(
            [
                ProductTwinVersion(
                    id=twin_id,
                    product_id=product_id,
                    version=1,
                    content_hash=twin_digest,
                    payload={"hosting_region": "EU"},
                    published_by_actor_id="seller-human",
                    published_at=datetime.now(UTC),
                    organization_id="org_seller_a",
                ),
                CatalogProjectionVersion(
                    id=catalog_id,
                    product_id=product_id,
                    version=1,
                    content_hash=catalog_digest,
                    buyer_safe_payload={"hosting_region": "EU"},
                    organization_id="org_seller_a",
                ),
            ]
        )
        await session.flush()
        session.add(
            ProductBundle(
                id=bundle_id,
                product_id=product_id,
                version=1,
                product_twin_version_id=twin_id,
                catalog_projection_version_id=catalog_id,
                disclosure_policy_version="buyer-safe-v1",
                embedding_profile="titan-v2:1024:normalize",
                digest=bundle_digest,
                state="ACTIVE",
                activated_at=datetime.now(UTC),
                organization_id="org_seller_a",
            )
        )
        await session.flush()
        session.add(
            ActiveProductBundle(
                product_id=product_id,
                bundle_id=bundle_id,
                bundle_digest=bundle_digest,
                generation=1,
                organization_id="org_seller_a",
            )
        )
    async with database.transaction("org_consultco") as session:
        mission = await session.get(QualificationMission, mission_id)
        assert mission is not None
        mission.state = "AWAITING_APPROVAL"
        session.add(
            QualificationAttempt(
                id=attempt_id,
                mission_id=mission_id,
                root_attempt_id=attempt_id,
                predecessor_attempt_id=None,
                replacement_depth=0,
                state="COMPLETED",
                generation=1,
                input_digest=input_digest,
                organization_id="org_consultco",
            )
        )
        await session.flush()
        session.add_all(
            [
                QualificationMissionBundle(
                    id="qmission_bundle_api_lifecycle",
                    mission_id=mission_id,
                    attempt_id=attempt_id,
                    product_id=product_id,
                    seller_organization_id="org_seller_a",
                    bundle_id=bundle_id,
                    bundle_digest=bundle_digest,
                    organization_id="org_consultco",
                ),
                QualificationDecision(
                    id=decision_id,
                    mission_id=mission_id,
                    attempt_id=attempt_id,
                    input_digest=input_digest,
                    decision_digest=decision_digest,
                    recommended_product_id=product_id,
                    payload=decision_payload,
                    approval_state="PENDING",
                    current=True,
                    organization_id="org_consultco",
                ),
            ]
        )
        await session.flush()
        session.add(
            DecisionDependency(
                id="qdecision_dependency_api_lifecycle",
                decision_id=decision_id,
                dependency_kind="PRODUCT_BUNDLE",
                dependency_organization_id="org_seller_a",
                dependency_id=product_id,
                dependency_version=bundle_id,
                dependency_hash=bundle_digest,
                cited=True,
                organization_id="org_consultco",
            )
        )

    mission = await api_client.get(f"/v1/qualification/missions/{mission_id}")
    assert mission.status_code == 200
    assert mission.headers["etag"] == f'"{decision_digest}"'
    events = await api_client.get(f"/v1/qualification/missions/{mission_id}/events?limit=1")
    assert events.status_code == 200
    assert len(events.json()["events"]) == 1

    stale = await api_client.post(
        f"/v1/qualification/decisions/{decision_id}/approval",
        headers={
            "Idempotency-Key": "lifecycle-stale-1",
            "If-Match": f'"sha256:{"0" * 64}"',
        },
        json={"action": "APPROVE", "reason": "Review completed."},
    )
    assert stale.status_code == 412

    approval_headers = {
        "Idempotency-Key": "lifecycle-approve-1",
        "If-Match": f'"{decision_digest}"',
    }
    approved = await api_client.post(
        f"/v1/qualification/decisions/{decision_id}/approval",
        headers=approval_headers,
        json={"action": "APPROVE", "reason": "Evidence and policy checks passed."},
    )
    approval_replay = await api_client.post(
        f"/v1/qualification/decisions/{decision_id}/approval",
        headers=approval_headers,
        json={"action": "APPROVE", "reason": "Evidence and policy checks passed."},
    )
    assert approved.status_code == approval_replay.status_code == 200, (
        approved.text,
        approval_replay.text,
    )
    assert approval_replay.json()["replayed"] is True
    engagement_id = approved.json()["resource_id"]

    seller_headers = {
        "X-Organization-Id": "org_seller_a",
        "X-Actor-Id": "seller-human",
        "X-Actor-Party": "SELLER",
        "X-Actor-Roles": "seller_editor,can_view_context",
        "X-Step-Up-Verified": "true",
    }
    seller_view = await api_client.get(
        f"/v1/qualification/engagements/{engagement_id}", headers=seller_headers
    )
    assert seller_view.status_code == 200
    assert "buyer_context" not in seller_view.json()["engagement"]
    engagement_etag = seller_view.headers["etag"]

    seller_response = await api_client.post(
        f"/v1/qualification/engagements/{engagement_id}/responses",
        headers={
            **seller_headers,
            "Idempotency-Key": "lifecycle-response-1",
            "If-Match": engagement_etag,
        },
        json={"response": "FIT", "cited_evidence_ids": [], "message": "We fit."},
    )
    assert seller_response.status_code == 201

    shared_fields = {
        "buyer_email": "buyer@example.test",
        "seller_email": "seller@example.test",
    }
    buyer_consent = await api_client.post(
        f"/v1/qualification/engagements/{engagement_id}/consents",
        headers={
            "Idempotency-Key": "lifecycle-buyer-consent-1",
            "If-Match": engagement_etag,
        },
        json={"shared_fields": shared_fields},
    )
    seller_consent = await api_client.post(
        f"/v1/qualification/engagements/{engagement_id}/consents",
        headers={
            **seller_headers,
            "Idempotency-Key": "lifecycle-seller-consent-1",
            "If-Match": engagement_etag,
        },
        json={"shared_fields": shared_fields},
    )
    assert buyer_consent.status_code == seller_consent.status_code == 201

    introduced = await api_client.post(
        f"/v1/qualification/engagements/{engagement_id}/introduction",
        headers={
            "Idempotency-Key": "lifecycle-introduction-1",
            "If-Match": engagement_etag,
        },
        json={"shared_fields": shared_fields},
    )
    replay = await api_client.post(
        f"/v1/qualification/engagements/{engagement_id}/introduction",
        headers={
            "Idempotency-Key": "lifecycle-introduction-1",
            "If-Match": engagement_etag,
        },
        json={"shared_fields": shared_fields},
    )
    assert introduced.status_code == replay.status_code == 201
    assert replay.json()["replayed"] is True

    final_view = await api_client.get(
        f"/v1/qualification/engagements/{engagement_id}", headers=seller_headers
    )
    assert final_view.json()["introduction"]["receipt"]["shared_fields"] == shared_fields
    integrity = await api_client.get(f"/v1/qualification/missions/{mission_id}/integrity")
    assert integrity.status_code == 200
    assert integrity.json()["verdict"] == "PASS"
