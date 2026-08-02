from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

EDITOR = {
    "X-Actor-Id": "seller_fixture_d",
    "X-Actor-Party": "SELLER",
    "X-Actor-Roles": "seller_editor",
    "X-Step-Up-Verified": "true",
}
REVIEWER = {
    "X-Actor-Id": "seller_reviewer_fixture_d",
    "X-Actor-Party": "SELLER",
    "X-Actor-Roles": "seller_reviewer",
    "X-Step-Up-Verified": "true",
}


def _idem(value: str) -> dict[str, str]:
    return {"Idempotency-Key": value}


async def _prepare_reviewable_draft(client: httpx.AsyncClient) -> dict[str, Any]:
    evidence = await client.post(
        "/v1/seller/pack-drafts/draft_fixture_d/evidence",
        headers={**EDITOR, **_idem("seller-evidence-current-0001")},
        json={
            "source_reference": "https://vendor.example/evidence/current-retention",
            "source_class": "VENDOR_DOCUMENTATION",
            "claim_fields": ["data_retention_days", "public_summary"],
            "observed_at": datetime.now(UTC).isoformat(),
        },
    )
    assert evidence.status_code == 201, evidence.text
    evidence_id = evidence.json()["id"]

    patched = await client.patch(
        "/v1/seller/pack-drafts/draft_fixture_d",
        headers={**EDITOR, **_idem("seller-draft-patch-0001")},
        json={
            "base_revision": 2,
            "claims": [
                {"field": "product_name", "value": "Fixture D", "evidence_ids": []},
                {
                    "field": "public_summary",
                    "value": "Meeting intelligence for governed enterprise workflows.",
                    "evidence_ids": [evidence_id],
                },
                {
                    "field": "data_retention_days",
                    "value": 30,
                    "evidence_ids": [evidence_id],
                },
                {"field": "supported_regions", "value": ["US"], "evidence_ids": []},
                {"field": "sso_supported", "value": True, "evidence_ids": []},
            ],
            "fit_rules": [{"field": "employee_count_min", "value": 25, "evidence_ids": []}],
            "anti_fit_rules": [
                {
                    "field": "regulated_data_prohibited",
                    "value": True,
                    "evidence_ids": [],
                }
            ],
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["validation"] == {"status": "VALID", "gaps": []}
    return patched.json()


@pytest.mark.asyncio
async def test_seller_search_is_role_scoped_and_public_safe(
    api_client: httpx.AsyncClient,
) -> None:
    buyer = await api_client.get("/v1/seller/products/search?q=fixture")
    assert buyer.status_code == 403
    assert buyer.json()["error"]["code"] == "SELLER_IDENTITY_REQUIRED"

    no_role = await api_client.get(
        "/v1/seller/products/search?q=fixture",
        headers={
            "X-Actor-Id": "seller_fixture_d",
            "X-Actor-Party": "SELLER",
            "X-Actor-Roles": "requester",
        },
    )
    assert no_role.status_code == 403
    assert no_role.json()["error"]["code"] == "SELLER_ROLE_REQUIRED"

    result = await api_client.get("/v1/seller/products/search?q=fixture", headers=EDITOR)
    assert result.status_code == 200, result.text
    payload = result.json()
    assert {row["id"] for row in payload["results"]} == {
        "product_fixture_d",
        "product_fixture_unclaimed",
    }
    rendered = result.text.casefold()
    for prohibited in (
        "buyer_passport",
        "hidden_budget",
        "buyer_contact",
        "organization_id",
        "owner_actor_id",
        "authority_proof_reference",
    ):
        assert prohibited not in rendered
    assert "no production seller integration is implied" in rendered

    other_tenant = await api_client.get(
        "/v1/seller/products/search?q=fixture",
        headers={**EDITOR, "X-Organization-Id": "org_other"},
    )
    assert other_tenant.status_code == 200
    assert other_tenant.json() == {"results": []}


@pytest.mark.asyncio
async def test_product_claim_is_hash_bound_and_idempotent(
    api_client: httpx.AsyncClient,
) -> None:
    headers = {
        **EDITOR,
        "X-Actor-Id": "seller_claimant",
        **_idem("seller-product-claim-0001"),
    }
    body = {
        "authority_proof_reference": "registry-proof-fixture-only",
        "requested_role": "SELLER_EDITOR",
    }
    created = await api_client.post(
        "/v1/seller/products/product_fixture_unclaimed/claim",
        headers=headers,
        json=body,
    )
    assert created.status_code == 201, created.text
    assert created.json()["state"] == "CLAIM_PENDING"
    assert "authority_proof" not in created.text

    replay = await api_client.post(
        "/v1/seller/products/product_fixture_unclaimed/claim",
        headers=headers,
        json=body,
    )
    assert replay.status_code == 201
    assert replay.json() == created.json()

    conflicting = await api_client.post(
        "/v1/seller/products/product_fixture_unclaimed/claim",
        headers=headers,
        json={**body, "authority_proof_reference": "different-proof"},
    )
    assert conflicting.status_code == 409
    assert conflicting.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


@pytest.mark.asyncio
async def test_seller_review_publish_suspend_and_exports_are_exact_and_separated(
    api_client: httpx.AsyncClient,
) -> None:
    draft = await _prepare_reviewable_draft(api_client)
    revision_hash = draft["revision_hash"]

    submitted = await api_client.post(
        "/v1/seller/pack-drafts/draft_fixture_d/submit-review",
        headers={**EDITOR, **_idem("seller-submit-review-0001")},
        json={"revision_hash": revision_hash},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["state"] == "IN_REVIEW"

    same_actor_reviewer = await api_client.post(
        "/v1/seller/pack-drafts/draft_fixture_d/review-decisions",
        headers={
            **REVIEWER,
            "X-Actor-Id": "seller_fixture_d",
            **_idem("seller-self-review-0001"),
        },
        json={
            "decision": "APPROVE",
            "revision_hash": revision_hash,
            "reason": "Self review must fail.",
        },
    )
    assert same_actor_reviewer.status_code == 403
    assert (
        same_actor_reviewer.json()["error"]["code"] == "SELLER_EDITOR_REVIEWER_SEPARATION_REQUIRED"
    )

    review_headers = {**REVIEWER, **_idem("seller-review-approve-0001")}
    review_body = {
        "decision": "APPROVE",
        "revision_hash": revision_hash,
        "reason": "Required fields and seller evidence are complete.",
    }
    approved = await api_client.post(
        "/v1/seller/pack-drafts/draft_fixture_d/review-decisions",
        headers=review_headers,
        json=review_body,
    )
    assert approved.status_code == 201, approved.text
    assert approved.json()["decision"] == "APPROVE"
    replayed_approval = await api_client.post(
        "/v1/seller/pack-drafts/draft_fixture_d/review-decisions",
        headers=review_headers,
        json=review_body,
    )
    assert replayed_approval.json() == approved.json()

    publish_headers = {**REVIEWER, **_idem("seller-publish-0001")}
    published = await api_client.post(
        "/v1/seller/pack-drafts/draft_fixture_d/publish",
        headers=publish_headers,
        json={"revision_hash": revision_hash},
    )
    assert published.status_code == 201, published.text
    assert published.json()["state"] == "PUBLISHED"
    assert published.json()["publisher_authority"] == "SELLER_SEALED"
    pack_id = published.json()["id"]
    replayed_publish = await api_client.post(
        "/v1/seller/pack-drafts/draft_fixture_d/publish",
        headers=publish_headers,
        json={"revision_hash": revision_hash},
    )
    assert replayed_publish.json() == published.json()

    frozen = await api_client.patch(
        "/v1/seller/pack-drafts/draft_fixture_d",
        headers={**EDITOR, **_idem("seller-edit-published-0001")},
        json={"base_revision": draft["revision"]},
    )
    assert frozen.status_code == 409
    assert frozen.json()["error"]["code"] == "SELLER_DRAFT_FROZEN"

    exports = await api_client.get(f"/v1/seller/pack-versions/{pack_id}/exports", headers=REVIEWER)
    assert exports.status_code == 200, exports.text
    assert {item["format"] for item in exports.json()["exports"]} == {
        "JSON",
        "HTML",
        "REUSABLE_ANSWER",
    }
    hashes_before = {item["format"]: item["content_hash"] for item in exports.json()["exports"]}

    suspended = await api_client.post(
        f"/v1/seller/pack-versions/{pack_id}/suspend",
        headers={**REVIEWER, **_idem("seller-suspend-0001")},
        json={
            "reason": "Fixture safety suspension for audit coverage.",
            "effective_at": datetime.now(UTC).isoformat(),
        },
    )
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["content_hash"] == published.json()["content_hash"]
    exports_after = await api_client.get(
        f"/v1/seller/pack-versions/{pack_id}/exports", headers=REVIEWER
    )
    assert {
        item["format"]: item["content_hash"] for item in exports_after.json()["exports"]
    } == hashes_before


@pytest.mark.asyncio
async def test_revision_hash_and_publication_allowlist_fail_closed(
    api_client: httpx.AsyncClient,
) -> None:
    forbidden = await api_client.patch(
        "/v1/seller/pack-drafts/draft_fixture_d",
        headers={**EDITOR, **_idem("seller-private-field-0001")},
        json={
            "base_revision": 2,
            "claims": [
                {
                    "field": "buyer_hidden_budget",
                    "value": "must never publish",
                    "evidence_ids": [],
                }
            ],
        },
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "SELLER_PUBLICATION_FIELD_FORBIDDEN"

    wrong_hash = await api_client.post(
        "/v1/seller/pack-drafts/draft_fixture_d/submit-review",
        headers={**EDITOR, **_idem("seller-wrong-hash-0001")},
        json={"revision_hash": "sha256:" + "0" * 64},
    )
    assert wrong_hash.status_code == 409
    assert wrong_hash.json()["error"]["code"] == "SELLER_REVISION_HASH_MISMATCH"


@pytest.mark.asyncio
async def test_activity_metric_is_deduplicated_and_non_causal(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get(
        "/v1/seller/products/product_fixture_d/activity-metrics", headers=EDITOR
    )
    assert response.status_code == 200, response.text
    metrics = response.json()
    assert metrics["answer_rendered_count"] == 4
    assert metrics["seller_handoff_requested_count"] == 1
    assert metrics["observed_self_service_count"] == 2
    assert metrics["measurement_label"] == "OBSERVATIONAL_NOT_CAUSAL"
    assert "deflection" not in response.text.casefold()


@pytest.mark.asyncio
async def test_demo_reset_clears_and_reseeds_seller_state(
    api_client: httpx.AsyncClient,
) -> None:
    claimed = await api_client.post(
        "/v1/seller/products/product_fixture_unclaimed/claim",
        headers={
            **EDITOR,
            "X-Actor-Id": "seller_claimant",
            **_idem("seller-reset-claim-0001"),
        },
        json={
            "authority_proof_reference": "fixture-proof-before-reset",
            "requested_role": "SELLER_EDITOR",
        },
    )
    assert claimed.status_code == 201

    reset = await api_client.post("/v1/demo/reset")
    assert reset.status_code == 200, reset.text

    search = await api_client.get("/v1/seller/products/search?q=fixture", headers=EDITOR)
    assert search.status_code == 200, search.text
    states = {row["id"]: row["state"] for row in search.json()["results"]}
    assert states["product_fixture_unclaimed"] == "UNCLAIMED"
    draft = await api_client.get("/v1/seller/pack-drafts/draft_fixture_d", headers=EDITOR)
    assert draft.status_code == 200
    assert draft.json()["revision"] == 2
    assert draft.json()["state"] == "SELLER_DRAFT"
