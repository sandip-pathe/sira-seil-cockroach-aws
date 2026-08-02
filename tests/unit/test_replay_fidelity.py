from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

import pytest
from sira_api.errors import ApiProblem
from sira_api.fixtures import DemoFixtureBundle
from sira_api.graph_persistence import (
    EvaluationPersistenceMetadata,
    build_evaluation_graph_write,
)
from sira_api.service import WorkflowService

from domain import content_hash


def _frozen_run() -> tuple[WorkflowService, Any, dict[str, Any]]:
    service = WorkflowService(
        database=cast(Any, None),
        fixtures=DemoFixtureBundle.load(),
    )
    graph_input, graph_decision, ledger, _patch, commercial_terms = service._demo_graph_artifacts(
        organization_id="org_consultco",
        request_id="req_replay_demo",
        decision_id="dec_replay_demo",
        decision_version=1,
        supersedes_decision_id=None,
        purchase_brief_id="pb_replay_demo",
        purchase_brief_version=1,
        requirement_brief_id="rb_replay_demo",
        requirement_brief_version=1,
        stack_patch_id="patch_replay_demo",
    )
    graph = build_evaluation_graph_write(
        graph_decision,
        graph_input,
        ledger,
        EvaluationPersistenceMetadata(
            organization_id="org_consultco",
            purchase_request_id="req_replay_demo",
            purchase_brief_id="pb_replay_demo",
            decision_id="dec_replay_demo",
            candidate_set_version="demo_candidate_set_v1",
            quote_set_version="demo_quote_set_v1",
            risk_rule_set_version="demo_risk_rules_v1",
            valuation_currency="USD",
        ),
        commercial_terms_by_plan_id=commercial_terms,
    )
    return service, graph.evaluation_run, ledger


def test_replay_accepts_only_the_hash_identical_frozen_source() -> None:
    service, run, ledger = _frozen_run()

    _input, replay = service._verified_demo_replay_source(run, ledger)

    assert replay.base.evaluation_payload_hash == run.evaluation_payload_hash


def test_replay_refuses_an_internally_rehashed_substitute_input() -> None:
    service, run, ledger = _frozen_run()
    substituted = deepcopy(run.input_payload)
    substituted["frozen_input_hashes"][0][1] = "sha256:" + "0" * 64
    run.input_payload = substituted
    run.input_payload_hash = content_hash(substituted)

    with pytest.raises(ApiProblem) as caught:
        service._verified_demo_replay_source(run, ledger)

    assert caught.value.code == "REPLAY_INPUT_UNAVAILABLE"
    assert "frozen_input_hashes" in caught.value.details["mismatches"]
