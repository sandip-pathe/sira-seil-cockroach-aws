from __future__ import annotations

from hashlib import sha256

import pytest

from integrations.aws_services import LocalContentAddressedEvidenceStore


async def test_local_evidence_store_is_content_addressed_idempotent_and_versioned(tmp_path) -> None:
    store = LocalContentAddressedEvidenceStore(tmp_path)
    body = b"published seller evidence"

    first = await store.put(
        organization_id="org-seller",
        body=body,
        content_type="text/plain",
    )
    second = await store.put(
        organization_id="org-seller",
        body=body,
        content_type="text/plain",
    )

    digest = sha256(body).hexdigest()
    assert first == second
    assert first.sha256 == f"sha256:{digest}"
    assert first.version_id == f"sha256-{digest}"
    assert (tmp_path / first.key).read_bytes() == body


async def test_local_evidence_store_rejects_invalid_tenant_and_empty_input(tmp_path) -> None:
    store = LocalContentAddressedEvidenceStore(tmp_path)
    with pytest.raises(ValueError, match="organization_id"):
        await store.put(organization_id="../escape", body=b"x", content_type="text/plain")
    with pytest.raises(ValueError, match="must not be empty"):
        await store.put(organization_id="org-seller", body=b"", content_type="text/plain")
