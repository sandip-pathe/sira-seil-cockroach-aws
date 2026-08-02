from __future__ import annotations

from datetime import UTC, datetime

from sira_api.graph_ledger import DecisionLedgerMetadata, build_decision_ledger
from sira_api.graph_persistence import (
    EvaluationPersistenceMetadata,
    build_evaluation_graph_write,
    ensure_evaluation_pipeline_version,
)

from decision_engine import evaluate_decision_graph, load_demo_decision_graph_input
from domain import content_hash
from persistence.database import Database, DatabaseSettings
from persistence.models import (
    Base,
    DecisionRecord,
    Organization,
    PurchaseBriefVersion,
    PurchaseRequest,
)
from persistence.repositories import WorkflowRepository

NOW = datetime(2026, 8, 2, 6, 0, tzinfo=UTC)


async def test_repository_accepts_the_complete_adapter_aggregate() -> None:
    decision_input = load_demo_decision_graph_input()
    decision = evaluate_decision_graph(decision_input, generated_at=NOW)
    ledger = build_decision_ledger(
        decision,
        decision_input,
        DecisionLedgerMetadata(
            decision_id="dec_graph_adapter",
            decision_version=1,
            supersedes_decision_id=None,
            request_id="req_graph_adapter",
            purchase_brief_id="pb_graph_adapter",
            purchase_brief_version=1,
            requirement_brief_id="rb_graph_adapter",
            requirement_brief_version=1,
            company_profile_version=1,
            stack_snapshot=1,
            policy_version=1,
            created_at=NOW,
        ),
    )
    metadata = EvaluationPersistenceMetadata(
        organization_id="org_graph_adapter",
        purchase_request_id="req_graph_adapter",
        purchase_brief_id="pb_graph_adapter",
        decision_id="dec_graph_adapter",
        candidate_set_version="candidate_set_demo_v1",
        quote_set_version="quote_set_demo_v1",
        risk_rule_set_version="risk_rules_demo_v1",
        valuation_currency="USD",
    )
    graph = build_evaluation_graph_write(decision, decision_input, ledger, metadata)

    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    try:
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with database.transaction(metadata.organization_id) as session:
            session.add(Organization(id=metadata.organization_id, name="Graph Adapter Tenant"))
            session.add(
                PurchaseRequest(
                    id=metadata.purchase_request_id,
                    organization_id=metadata.organization_id,
                    intent="Persist the deterministic graph",
                    status="EVALUATING",
                    visibility="PRIVATE",
                    version=1,
                    payload={"request": "graph adapter"},
                    request_hash=content_hash({"request": "graph adapter"}),
                )
            )
            session.add(
                PurchaseBriefVersion(
                    id=metadata.purchase_brief_id,
                    organization_id=metadata.organization_id,
                    purchase_request_id=metadata.purchase_request_id,
                    version=1,
                    status="ACCEPTED",
                    payload={"brief": "graph adapter"},
                    content_hash=content_hash({"brief": "graph adapter"}),
                    supersedes_id=None,
                )
            )
            session.add(
                DecisionRecord(
                    id=metadata.decision_id,
                    organization_id=metadata.organization_id,
                    purchase_request_id=metadata.purchase_request_id,
                    purchase_brief_id=metadata.purchase_brief_id,
                    version=1,
                    supersedes_id=None,
                    decision_hash=ledger["decision_hash"],
                    selected_solution_plan_id=decision.base.selected_plan_id,
                    payload=ledger,
                )
            )
            await session.flush()

            repository = WorkflowRepository(session, metadata.organization_id)
            first_pipeline = await ensure_evaluation_pipeline_version(
                repository, decision_input, metadata
            )
            second_pipeline = await ensure_evaluation_pipeline_version(
                repository, decision_input, metadata
            )
            assert first_pipeline.id == second_pipeline.id

            await repository.add_evaluation_graph(graph)
            snapshot = await repository.get_evaluation_graph(graph.evaluation_run.id)
            assert snapshot.evaluation_run.evaluation_payload_hash == (
                decision.base.evaluation_payload_hash
            )
            assert len(snapshot.solution_plans) == len(decision.base.plans)
            assert len(snapshot.candidate_set_members) == len(graph.candidate_set_members)
            assert len(snapshot.decision_gate_results) == len(graph.decision_gate_results)
            assert len(snapshot.score_bounds) == 7 * len(decision.base.plans)
            assert len(snapshot.robustness_frontiers) == 3 * len(decision.base.plans)
    finally:
        await database.close()
