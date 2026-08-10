from __future__ import annotations

from sira_api.workspace_schemas import CatalogProductView
from sira_api.workspace_service import WorkspaceService


# Regression: ISSUE-001 — DataHub fit fields were stripped from product cards
# Found by /qa on 2026-08-10
# Report: .gstack/qa-reports/qa-report-localhost-2026-08-10.md
def test_datahub_fit_survives_catalog_response_validation() -> None:
    decision = {
        "selected_adapter_id": "adapter-b",
        "seller_projections": [
            {
                "adapterId": "adapter-a",
                "sourcePackVersionId": "pack-a-v1",
                "projectionHash": "sha256:" + "a" * 64,
                "fixedPrice": {"currency": "USD", "amount": "0.02"},
            },
            {
                "adapterId": "adapter-b",
                "sourcePackVersionId": "pack-b-v1",
                "projectionHash": "sha256:" + "b" * 64,
                "fixedPrice": {"currency": "USD", "amount": "0.05"},
            },
        ],
    }

    products = [
        CatalogProductView.model_validate(product).model_dump()
        for product in WorkspaceService._datahub_products(decision)
    ]

    assert products[0]["fit"] == "Qualified"
    assert products[0]["why_company"].startswith("Passed the DataHub-derived")
    assert products[0]["requirement_coverage"] == "3 of 3 required gates passed"
    assert products[1]["fit"] == "Blocked"
    assert products[1]["requirement_coverage"] == "2 of 3 required gates passed"
