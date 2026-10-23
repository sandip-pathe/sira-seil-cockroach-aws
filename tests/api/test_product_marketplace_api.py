from datetime import UTC, datetime

import httpx
from fastapi import FastAPI
from openai import AuthenticationError
from tests.integration.test_product_marketplace import SearchProvider

from persistence.models import SellerProduct

EDITOR = {
    "X-Actor-Party": "SELLER",
    "X-Actor-Roles": "seller_editor",
    "X-Actor-Id": "product_owner",
}


async def test_invalid_search_credentials_fail_without_inserting_products(
    api_client: httpx.AsyncClient,
    api_application: FastAPI,
) -> None:
    class RejectedProvider:
        async def search(self, query: str, *, limit: int = 5) -> object:
            raise AuthenticationError(
                "Rejected test key",
                response=httpx.Response(
                    401, request=httpx.Request("POST", "https://api.openai.com/v1/responses")
                ),
                body={"code": "invalid_api_key"},
            )

    api_application.state.product_marketplace.search_provider = RejectedProvider()
    response = await api_client.post("/v1/marketplace/research", json={"query": "calendar"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PRODUCT_SEARCH_CREDENTIALS_INVALID"
    assert (await api_client.get("/v1/workspace/catalog")).json() == []


async def test_real_catalog_endpoints_persist_research_without_seller_attestation(
    api_client: httpx.AsyncClient,
    api_application: FastAPI,
) -> None:
    api_application.state.product_marketplace.search_provider = SearchProvider()
    assert (await api_client.get("/v1/workspace/catalog")).json() == []
    researched = await api_client.post(
        "/v1/marketplace/research", json={"query": "calendar", "limit": 1}
    )
    assert researched.status_code == 200, researched.text
    product = researched.json()["results"][0]
    catalog = await api_client.get("/v1/workspace/catalog", params={"query": "calendar"})
    assert catalog.status_code == 200
    assert catalog.json()[0]["id"] == product["id"]
    assert catalog.json()[0]["seller_attested"] is False
    detail = await api_client.get(f"/v1/workspace/catalog/{product['id']}")
    assert detail.status_code == 200
    assert detail.json()["observations"][0]["origin"] == "PUBLIC_WEB"


async def test_seller_registration_requires_seller_identity_and_does_not_publish(
    api_client: httpx.AsyncClient,
) -> None:
    body = {
        "name": "Example Calendar",
        "seller_name": "Example",
        "website": "https://example.com/calendar",
        "edition": "Team",
        "category": "Scheduling",
        "summary": "A private draft",
    }
    denied = await api_client.post(
        "/v1/seller/products", json=body, headers={"Idempotency-Key": "register-product-denied"}
    )
    assert denied.status_code == 403
    saved = await api_client.post(
        "/v1/seller/products",
        json=body,
        headers={**EDITOR, "Idempotency-Key": "register-product-owner"},
    )
    assert saved.status_code == 201, saved.text
    record = saved.json()["results"][0]
    assert record["state"] == "SELLER_DRAFT"
    detail = await api_client.get(f"/v1/seller/products/{record['id']}/view", headers=EDITOR)
    assert detail.status_code == 200, detail.text
    assert (await api_client.get("/v1/workspace/catalog")).json() == []


async def test_reviewed_publication_reaches_catalog_and_suspension_withdraws_it(
    api_client: httpx.AsyncClient,
    api_application: FastAPI,
) -> None:
    registered = await api_client.post(
        "/v1/seller/products",
        headers={**EDITOR, "Idempotency-Key": "new-product-publication"},
        json={
            "name": "Calendar",
            "seller_name": "Example",
            "website": "https://example.com/calendar",
            "category": "scheduling",
            "summary": "Initial private summary",
        },
    )
    assert registered.status_code == 201, registered.text
    product_id = registered.json()["results"][0]["id"]
    async with api_application.state.database.transaction("org_consultco") as session:
        product = await session.get(SellerProduct, product_id)
        draft_id = product.current_draft_id
    path = f"/v1/seller/pack-drafts/{draft_id}"
    evidence = await api_client.post(
        path + "/evidence",
        headers={**EDITOR, "Idempotency-Key": "attach-calendar-evidence"},
        json={
            "source_reference": "https://example.com/privacy/retention",
            "source_class": "VENDOR_DOCUMENTATION",
            "claim_fields": ["data_retention_days"],
            "observed_at": datetime.now(UTC).isoformat(),
        },
    )
    assert evidence.status_code == 201, evidence.text
    patched = await api_client.patch(
        path,
        headers={**EDITOR, "Idempotency-Key": "edit-calendar-draft"},
        json={
            "base_revision": 1,
            "claims": [
                {"field": "product_name", "value": "Calendar", "evidence_ids": []},
                {"field": "public_summary", "value": "Reviewed public summary", "evidence_ids": []},
                {"field": "supported_regions", "value": ["EU"], "evidence_ids": []},
                {
                    "field": "data_retention_days",
                    "value": 30,
                    "evidence_ids": [evidence.json()["id"]],
                },
            ],
            "fit_rules": [{"field": "employee_count_min", "value": 1, "evidence_ids": []}],
            "anti_fit_rules": [
                {"field": "regulated_data_prohibited", "value": True, "evidence_ids": []}
            ],
        },
    )
    assert patched.status_code == 200, patched.text
    digest = patched.json()["revision_hash"]
    submitted = await api_client.post(
        path + "/submit-review",
        headers={**EDITOR, "Idempotency-Key": "submit-calendar-draft"},
        json={"revision_hash": digest},
    )
    assert submitted.status_code == 200, submitted.text
    reviewer = {
        "X-Actor-Party": "SELLER",
        "X-Actor-Roles": "seller_reviewer",
        "X-Actor-Id": "independent_reviewer",
        "X-Step-Up-Verified": "true",
    }
    approved = await api_client.post(
        path + "/review-decisions",
        headers={**reviewer, "Idempotency-Key": "review-calendar-draft"},
        json={"revision_hash": digest, "decision": "APPROVE", "reason": "Evidence reviewed"},
    )
    assert approved.status_code == 201, approved.text
    assert (await api_client.get("/v1/workspace/catalog")).json() == []
    published = await api_client.post(
        path + "/publish",
        headers={**reviewer, "Idempotency-Key": "publish-calendar-draft"},
        json={"revision_hash": digest},
    )
    assert published.status_code == 201, published.text
    public = (await api_client.get("/v1/workspace/catalog")).json()
    assert len(public) == 1
    assert public[0]["seller_attested"] is True
    assert public[0]["summary"] == "Reviewed public summary"
    assert "Initial private summary" not in str(public)
    assert any(ref["url"].endswith("/privacy/retention") for ref in public[0]["source_refs"])
    pack_id = published.json()["id"]
    suspended = await api_client.post(
        f"/v1/seller/pack-versions/{pack_id}/suspend",
        headers={**reviewer, "Idempotency-Key": "withdraw-calendar-pack"},
        json={"reason": "Seller withdrew evidence", "effective_at": datetime.now(UTC).isoformat()},
    )
    assert suspended.status_code == 200, suspended.text
    assert (await api_client.get("/v1/workspace/catalog")).json() == []
