from decision_engine.snowflake_v1 import evaluate_snowflake_decision


def _source() -> dict[str, object]:
    return {
        "company_id": "comp_consultco",
        "context_version": 1,
        "facts": [
            {"fact_id": "seats", "fact_key": "REQUIRED_SEATS", "typed_value": 10},
            {"fact_id": "budget", "fact_key": "MAX_UNIT_PRICE", "typed_value": 100},
            {"fact_id": "crm", "fact_key": "CRM_SYNC_REQUIRED", "typed_value": True},
            {"fact_id": "stack", "fact_key": "CURRENT_CRM", "typed_value": "HubSpot"},
        ],
        "products": [
            {"product_id": "meetai", "name": "MeetAI"},
            {"product_id": "notesync", "name": "NoteSync"},
        ],
        "offers": [
            {
                "offer_id": "meetai-base",
                "product_id": "meetai",
                "unit_price": 80,
                "min_seats": 1,
                "max_seats": 100,
            },
            {
                "offer_id": "meetai-crm",
                "product_id": "meetai",
                "unit_price": 120,
                "min_seats": 1,
                "max_seats": 100,
            },
            {
                "offer_id": "notesync-team",
                "product_id": "notesync",
                "unit_price": 95,
                "min_seats": 1,
                "max_seats": 100,
            },
        ],
        "claims": [
            {
                "claim_id": "meetai-hubspot-price",
                "product_id": "meetai",
                "claim_key": "HUBSPOT_MIN_TIER_PRICE",
                "typed_value": 120,
            },
            {
                "claim_id": "notesync-hubspot",
                "product_id": "notesync",
                "claim_key": "HUBSPOT_INCLUDED_IN_BASE",
                "typed_value": True,
            },
        ],
    }


def test_private_company_fact_materially_changes_the_winner() -> None:
    result = evaluate_snowflake_decision(_source())

    assert result["selected_product_id"] == "notesync"
    assert result["counterfactual"] == {
        "outcome": "WINNER_CHANGED",
        "removed_fact_keys": ["CRM_SYNC_REQUIRED", "CURRENT_CRM"],
        "before_selected_product_id": "notesync",
        "after_selected_product_id": "meetai",
    }
    assert result["input_hash"].startswith("sha256:")
    assert result["decision_hash"].startswith("sha256:")
