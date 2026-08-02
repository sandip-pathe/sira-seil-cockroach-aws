from copy import deepcopy
from datetime import UTC, datetime

from sira_api.decision_projection import build_demo_decision_projection
from sira_api.fixtures import DemoFixtureBundle
from sira_api.schemas import DecisionLedgerView, DecisionView, StackPatchView


def test_accepted_weight_version_builds_a_fresh_decision_and_patch() -> None:
    fixtures = DemoFixtureBundle.load()
    purchase_brief = deepcopy(fixtures.purchase_brief)
    purchase_brief.update(
        {
            "purchase_brief_id": "pb_consultco_v2",
            "version": 2,
            "supersedes_version": 1,
        }
    )
    crm_preference = next(
        item
        for item in purchase_brief["preferences"]
        if item["criterion_id"] == "pref_native_crm_sync"
    )
    crm_preference["weight"] = 2
    requirement_brief = deepcopy(fixtures.requirement_brief)
    requirement_brief.update(
        {
            "requirement_brief_id": "rb_consultco_v2",
            "purchase_brief_id": "pb_consultco_v2",
            "purchase_brief_version": 2,
            "version": 2,
        }
    )

    projected = build_demo_decision_projection(
        fixtures=fixtures,
        purchase_brief=purchase_brief,
        requirement_brief=requirement_brief,
        request_id="req_demo",
        decision_id="dec_consultco_v2",
        created_at=datetime(2026, 8, 2, 2, 0, tzinfo=UTC),
    )

    DecisionLedgerView.model_validate(projected.ledger)
    DecisionView.model_validate(projected.decision_view)
    StackPatchView.model_validate(projected.stack_patch)
    assert projected.ledger["decision_hash"] != fixtures.decision_ledger()["decision_hash"]
    assert projected.ledger["purchase_brief_version"] == 2
    assert projected.ledger["selected_solution_plan_id"] == "sol_buy_fixture_d"
    assert projected.decision_view["selected_solution_plan"]["preference_score"] == 80
    assert projected.stack_patch["patch_id"] == "patch_dec_consultco_v2"
    assert projected.stack_patch["decision_id"] == "dec_consultco_v2"
