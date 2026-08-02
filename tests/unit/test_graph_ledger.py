from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema.validators import validator_for
from referencing import Registry, Resource
from sira_api.graph_ledger import DecisionLedgerMetadata, build_decision_ledger

from decision_engine import evaluate_decision_graph, load_demo_decision_graph_input
from domain.hashing import content_hash

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "fixtures" / "demo"
SCHEMAS = ROOT / "contracts" / "jsonschema"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _ledger() -> dict[str, Any]:
    graph_input = load_demo_decision_graph_input(DEMO)
    decision = evaluate_decision_graph(
        graph_input,
        evaluation_id="eval_consultco_v1",
        generated_at=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
    )
    names = {
        path.stem: _load(path)["identity"]["product_name"]
        for path in sorted((DEMO / "packs").glob("*.json"))
    }
    return build_decision_ledger(
        decision,
        graph_input,
        DecisionLedgerMetadata(
            decision_id="dec_consultco_v1",
            decision_version=1,
            supersedes_decision_id=None,
            request_id="req_demo",
            purchase_brief_id="pb_consultco_v1",
            purchase_brief_version=1,
            requirement_brief_id="rb_consultco_v1",
            requirement_brief_version=1,
            company_profile_version=1,
            stack_snapshot=1,
            policy_version=1,
            created_at=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
            selected_stack_patch_id="patch_consultco_fixture_d",
        ),
        component_names=names,
    )


def test_graph_ledger_validates_against_frozen_contract() -> None:
    schemas = {path.name: _load(path) for path in SCHEMAS.glob("*.json")}
    registry = Registry().with_resources(
        [(schema["$id"], Resource.from_contents(schema)) for schema in schemas.values()]
    )
    schema = schemas["decision-ledger.schema.json"]
    validator_for(schema)(schema, registry=registry).validate(_ledger())


def test_graph_ledger_contains_all_actions_and_demo_outcomes() -> None:
    ledger = _ledger()
    actions = {item["action_type"] for item in ledger["solution_plans"]}
    statuses = {item["status"] for item in ledger["component_results"]}
    ranked = ledger["evaluation"]["ranked_solution_plan_ids"]
    plan_by_id = {item["solution_plan_id"]: item for item in ledger["solution_plans"]}

    assert actions == {
        "REUSE_EXISTING",
        "CONFIGURE_EXISTING",
        "NO_ACTION",
        "RENEW",
        "RESIZE",
        "REPLACE",
        "CANCEL",
    }
    assert {"SIRA_INELIGIBLE", "SEIL_PASS", "ELIGIBLE"} <= statuses
    assert plan_by_id[ranked[0]]["components"][0]["component_id"] == "product_fixture_d"
    assert plan_by_id[ranked[1]]["action_type"] == "RENEW"
    assert len(ledger["solution_plans"]) == 10
    assert (
        ledger["counterfactuals"][0]["generic_selected_plan_id"]
        != ledger["selected_solution_plan_id"]
    )


def test_graph_ledger_hash_excludes_only_its_own_hash() -> None:
    ledger = _ledger()
    assert ledger["decision_hash"] == content_hash(
        {key: value for key, value in ledger.items() if key != "decision_hash"}
    )


def test_graph_reason_codes_are_contract_safe() -> None:
    ledger = _ledger()
    reason_codes = {
        reason["reason_code"]
        for plan in ledger["solution_plans"]
        for gate in plan["gate_results"]
        for reason in gate["reasons"]
    }
    assert reason_codes
    assert all(re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", code) for code in reason_codes)
