from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, cast

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import func, select

from integrations.evidence_store import StoredEvidenceObject
from persistence.models import SellerProduct
from persistence.qualification_models import EvidenceSourceVersion, EvidenceSpan

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


async def _register_product(client: httpx.AsyncClient, suffix: str) -> str:
    response = await client.post(
        "/v1/seller/products",
        headers={**EDITOR, **_idem(f"seller-registration-{suffix}-0001")},
        json={
            "name": f"Test Product {suffix}",
            "seller_name": "Test Vendor",
            "website": f"https://vendor.example/products/{suffix}",
            "edition": "Test",
            "category": "Test software",
            "summary": "A locally registered product for an isolated API test.",
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["results"][0]["id"])


@pytest_asyncio.fixture
async def seller_product(api_client: httpx.AsyncClient, api_application: FastAPI) -> dict[str, str]:
    product_id = await _register_product(api_client, "primary")
    async with api_application.state.database.transaction("org_consultco") as session:
        product = await session.get(SellerProduct, product_id)
        assert product is not None and product.current_draft_id is not None
        return {"product_id": product.id, "draft_id": product.current_draft_id}


@dataclass
class FakeEvidenceStore:
    calls: list[dict[str, Any]] = field(default_factory=list)
    fail: bool = False

    async def put(
        self, *, organization_id: str, body: bytes, content_type: str
    ) -> StoredEvidenceObject:
        self.calls.append(
            {
                "organization_id": organization_id,
                "body": body,
                "content_type": content_type,
            }
        )
        if not body:
            raise ValueError("evidence object must not be empty")
        if self.fail:
            raise RuntimeError("simulated provider failure")
        digest = "sha256:" + sha256(body).hexdigest()
        return StoredEvidenceObject(
            bucket="private-versioned-evidence",
            key=f"organizations/{organization_id}/evidence/{digest.removeprefix('sha256:')}",
            version_id="version-42",
            sha256=digest,
            size_bytes=len(body),
            content_type=content_type,
        )


@pytest.mark.asyncio
async def test_private_evidence_upload_is_version_bound_and_idempotent(
    api_client: httpx.AsyncClient,
    api_application: FastAPI,
    seller_product: dict[str, str],
) -> None:
    draft_id = seller_product["draft_id"]
    store = FakeEvidenceStore()
    api_application.state.seller_evidence_service.evidence_store = store
    content = b"signed retention policy\nretention_days=30\n"
    headers = {**EDITOR, **_idem("seller-object-evidence-0001")}
    files = {"evidence_file": ("retention.txt", content, "text/plain")}
    data = {
        "source_class": "VENDOR_DOCUMENTATION",
        "claim_fields_json": '["data_retention_days", "public_summary"]',
        "observed_at": datetime.now(UTC).isoformat(),
    }

    created = await api_client.post(
        f"/v1/seller/pack-drafts/{draft_id}/evidence/upload",
        headers=headers,
        files=files,
        data=data,
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["object_checksum"] == "sha256:" + sha256(content).hexdigest()
    assert payload["content_type"] == "text/plain"
    assert payload["size_bytes"] == len(content)
    assert payload["version_bound"] is True
    assert "private-versioned-evidence" not in created.text
    assert "version-42" not in created.text
    assert len(store.calls) == 1
    database = api_application.state.seller_evidence_service.database
    async with database.transaction("org_consultco") as session:
        source = await session.scalar(
            select(EvidenceSourceVersion).where(
                EvidenceSourceVersion.object_checksum == payload["object_checksum"]
            )
        )
        assert source is not None
        span_count = await session.scalar(
            select(func.count(EvidenceSpan.id)).where(EvidenceSpan.source_version_id == source.id)
        )
    assert span_count == 1

    replay = await api_client.post(
        f"/v1/seller/pack-drafts/{draft_id}/evidence/upload",
        headers=headers,
        files=files,
        data=data,
    )
    assert replay.status_code == 201
    assert replay.json() == payload
    assert len(store.calls) == 1

    same_object = await api_client.post(
        f"/v1/seller/pack-drafts/{draft_id}/evidence/upload",
        headers={**EDITOR, **_idem("seller-object-evidence-0002")},
        files=files,
        data=data,
    )
    assert same_object.status_code == 200
    assert same_object.json() == payload
    assert len(store.calls) == 1

    conflict = await api_client.post(
        f"/v1/seller/pack-drafts/{draft_id}/evidence/upload",
        headers={**EDITOR, **_idem("seller-object-evidence-0003")},
        files=files,
        data={**data, "claim_fields_json": '["public_summary"]'},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "SELLER_EVIDENCE_SOURCE_CONFLICT"
    assert len(store.calls) == 1


@pytest.mark.asyncio
async def test_private_evidence_upload_uses_local_store_and_fails_closed_at_boundaries(
    api_client: httpx.AsyncClient,
    api_application: FastAPI,
    seller_product: dict[str, str],
) -> None:
    endpoint = f"/v1/seller/pack-drafts/{seller_product['draft_id']}/evidence/upload"
    base_data = {
        "source_class": "VENDOR_DOCUMENTATION",
        "claim_fields_json": '["data_retention_days"]',
    }
    local = await api_client.post(
        endpoint,
        headers={**EDITOR, **_idem("seller-object-unavailable-0001")},
        files={"evidence_file": ("policy.txt", b"evidence", "text/plain")},
        data=base_data,
    )
    assert local.status_code == 201
    assert local.json()["version_bound"] is True
    assert local.json()["object_checksum"].startswith("sha256:")

    store = FakeEvidenceStore()
    api_application.state.seller_evidence_service.evidence_store = store
    invalid_fields = await api_client.post(
        endpoint,
        headers={**EDITOR, **_idem("seller-object-invalid-fields-0001")},
        files={"evidence_file": ("policy.txt", b"evidence", "text/plain")},
        data={**base_data, "claim_fields_json": "not-json"},
    )
    assert invalid_fields.status_code == 422
    assert invalid_fields.json()["error"]["code"] == "SELLER_EVIDENCE_FIELDS_INVALID"
    assert store.calls == []

    empty = await api_client.post(
        endpoint,
        headers={**EDITOR, **_idem("seller-object-empty-0001")},
        files={"evidence_file": ("empty.txt", b"", "text/plain")},
        data=base_data,
    )
    assert empty.status_code == 400
    assert empty.json()["error"]["code"] == "SELLER_EVIDENCE_OBJECT_INVALID"

    store.fail = True
    provider_failure = await api_client.post(
        endpoint,
        headers={**EDITOR, **_idem("seller-object-provider-fail-0001")},
        files={"evidence_file": ("policy.txt", b"provider fails", "text/plain")},
        data=base_data,
    )
    assert provider_failure.status_code == 502
    assert provider_failure.json()["error"]["code"] == "SELLER_EVIDENCE_STORAGE_FAILED"


@pytest.mark.asyncio
async def test_private_evidence_upload_rejects_metadata_and_storage_integrity_mismatches(
    api_client: httpx.AsyncClient,
    api_application: FastAPI,
    seller_product: dict[str, str],
) -> None:
    endpoint = f"/v1/seller/pack-drafts/{seller_product['draft_id']}/evidence/upload"
    store = FakeEvidenceStore()
    api_application.state.seller_evidence_service.evidence_store = store

    async def upload(key: str, source_class: str, fields: str) -> httpx.Response:
        return await api_client.post(
            endpoint,
            headers={**EDITOR, **_idem(key)},
            files={"evidence_file": ("policy.txt", b"evidence", "text/plain")},
            data={"source_class": source_class, "claim_fields_json": fields},
        )

    invalid_source = await upload(
        "seller-object-invalid-source-0001", "UNTRUSTED_UPLOAD", '["public_summary"]'
    )
    assert invalid_source.status_code == 400
    assert invalid_source.json()["error"]["code"] == "SELLER_EVIDENCE_SOURCE_CLASS_INVALID"

    duplicate_fields = await upload(
        "seller-object-duplicate-fields-0001",
        "VENDOR_DOCUMENTATION",
        '["public_summary", "public_summary"]',
    )
    assert duplicate_fields.status_code == 400
    assert duplicate_fields.json()["error"]["code"] == "SELLER_EVIDENCE_FIELDS_DUPLICATED"

    forbidden_field = await upload(
        "seller-object-forbidden-field-0001",
        "VENDOR_DOCUMENTATION",
        '["buyer_private_budget"]',
    )
    assert forbidden_field.status_code == 403
    assert forbidden_field.json()["error"]["code"] == "SELLER_PUBLICATION_FIELD_FORBIDDEN"
    assert store.calls == []

    original_put = store.put

    async def corrupt_put(
        *, organization_id: str, body: bytes, content_type: str
    ) -> StoredEvidenceObject:
        stored = await original_put(
            organization_id=organization_id, body=body, content_type=content_type
        )
        return StoredEvidenceObject(
            bucket=stored.bucket,
            key=stored.key,
            version_id=stored.version_id,
            sha256="sha256:" + "0" * 64,
            size_bytes=stored.size_bytes,
            content_type=stored.content_type,
        )

    store.put = corrupt_put  # type: ignore[method-assign]
    corrupted = await upload(
        "seller-object-corrupt-store-0001", "VENDOR_DOCUMENTATION", '["public_summary"]'
    )
    assert corrupted.status_code == 502
    assert corrupted.json()["error"]["code"] == "SELLER_EVIDENCE_STORAGE_INTEGRITY_FAILED"


async def _prepare_reviewable_draft(client: httpx.AsyncClient, draft_id: str) -> dict[str, Any]:
    evidence = await client.post(
        f"/v1/seller/pack-drafts/{draft_id}/evidence",
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
        f"/v1/seller/pack-drafts/{draft_id}",
        headers={**EDITOR, **_idem("seller-draft-patch-0001")},
        json={
            "base_revision": 1,
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
            "proof_adapter": {
                "adapter_id": "adapter-a",
                "artifact_digest": "sha256:" + "a" * 64,
                "protocol_version": "TrialCase/v0",
                "capabilities": ["SUPPORT_SUMMARIZATION", "CUSTOMER_EMAIL_OUTPUT"],
                "declared_region": "EU",
                "fixed_price": {"amount": "0.02", "currency": "USD"},
                "conformance_hash": "sha256:" + "b" * 64,
            },
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["validation"] == {"status": "VALID", "gaps": []}
    return cast(dict[str, Any], patched.json())


@pytest.mark.asyncio
async def test_seller_search_is_role_scoped_and_public_safe(
    api_client: httpx.AsyncClient,
) -> None:
    first_product = await _register_product(api_client, "search-one")
    second_product = await _register_product(api_client, "search-two")
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

    result = await api_client.get("/v1/seller/products/search?q=Test", headers=EDITOR)
    assert result.status_code == 200, result.text
    payload = result.json()
    assert {row["id"] for row in payload["results"]} == {
        first_product,
        second_product,
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

    other_tenant = await api_client.get(
        "/v1/seller/products/search?q=Test",
        headers={**EDITOR, "X-Organization-Id": "org_other"},
    )
    assert other_tenant.status_code == 200
    assert other_tenant.json() == {"results": []}


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_seller_review_publish_suspend_and_exports_are_exact_and_separated(
    api_client: httpx.AsyncClient,
    seller_product: dict[str, str],
) -> None:
    draft_id = seller_product["draft_id"]
    draft_path = f"/v1/seller/pack-drafts/{draft_id}"
    draft = await _prepare_reviewable_draft(api_client, draft_id)
    revision_hash = draft["revision_hash"]

    submitted = await api_client.post(
        draft_path + "/submit-review",
        headers={**EDITOR, **_idem("seller-submit-review-0001")},
        json={"revision_hash": revision_hash},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["state"] == "IN_REVIEW"

    same_actor_reviewer = await api_client.post(
        draft_path + "/review-decisions",
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
        draft_path + "/review-decisions",
        headers=review_headers,
        json=review_body,
    )
    assert approved.status_code == 201, approved.text
    assert approved.json()["decision"] == "APPROVE"
    replayed_approval = await api_client.post(
        draft_path + "/review-decisions",
        headers=review_headers,
        json=review_body,
    )
    assert replayed_approval.json() == approved.json()

    publish_headers = {**REVIEWER, **_idem("seller-publish-0001")}
    published = await api_client.post(
        draft_path + "/publish",
        headers=publish_headers,
        json={"revision_hash": revision_hash},
    )
    assert published.status_code == 201, published.text
    assert published.json()["state"] == "PUBLISHED"
    assert published.json()["publisher_authority"] == "SELLER_SEALED"
    assert published.json()["proof_adapter"]["artifact_digest"] == "sha256:" + "a" * 64
    pack_id = published.json()["id"]
    replayed_publish = await api_client.post(
        draft_path + "/publish",
        headers=publish_headers,
        json={"revision_hash": revision_hash},
    )
    assert replayed_publish.json() == published.json()

    frozen = await api_client.patch(
        draft_path,
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
    seller_product: dict[str, str],
) -> None:
    draft_id = seller_product["draft_id"]
    draft_path = f"/v1/seller/pack-drafts/{draft_id}"
    forbidden = await api_client.patch(
        draft_path,
        headers={**EDITOR, **_idem("seller-private-field-0001")},
        json={
            "base_revision": 1,
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
        draft_path + "/submit-review",
        headers={**EDITOR, **_idem("seller-wrong-hash-0001")},
        json={"revision_hash": "sha256:" + "0" * 64},
    )
    assert wrong_hash.status_code == 409
    assert wrong_hash.json()["error"]["code"] == "SELLER_REVISION_HASH_MISMATCH"


@pytest.mark.asyncio
async def test_activity_metric_is_deduplicated_and_non_causal(
    api_client: httpx.AsyncClient,
    seller_product: dict[str, str],
) -> None:
    response = await api_client.get(
        f"/v1/seller/products/{seller_product['product_id']}/activity-metrics", headers=EDITOR
    )
    assert response.status_code == 200, response.text
    metrics = response.json()
    assert metrics["answer_rendered_count"] == 0
    assert metrics["seller_handoff_requested_count"] == 0
    assert metrics["observed_self_service_count"] == 0
    assert metrics["measurement_label"] == "OBSERVATIONAL_NOT_CAUSAL"
    assert "deflection" not in response.text.casefold()
