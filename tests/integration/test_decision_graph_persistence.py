from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from domain import content_hash
from persistence.database import Database, DatabaseSettings
from persistence.models import (
    ActionRun,
    Base,
    CandidateSetMember,
    CounterfactualRecordModel,
    DecisionGateResult,
    DecisionRecord,
    DiscoveryRun,
    Engagement,
    EvaluationPipelineVersion,
    EvaluationRun,
    EvaluationSolutionPlan,
    EvidenceAssessmentRecord,
    IdentityMerge,
    Organization,
    PurchaseBriefVersion,
    PurchaseRequest,
    ResultArtifact,
    RobustnessFrontier,
    ScoreBound,
    ScoreComponentRecord,
    SolutionPlanComponent,
)
from persistence.repositories import (
    EvaluationGraphWrite,
    PersistenceConflict,
    RecordNotFound,
    WorkflowRepository,
)

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 2, 6, 0, tzinfo=UTC)
GRAPH_TABLES = {
    "evaluation_pipeline_versions",
    "evaluation_runs",
    "discovery_runs",
    "candidate_set_members",
    "identity_merges",
    "evaluation_solution_plans",
    "decision_gate_results",
    "evidence_assessments",
    "solution_plan_components",
    "score_components",
    "score_bounds",
    "robustness_frontiers",
    "counterfactual_records",
    "action_runs",
    "result_artifacts",
}


def _sha(payload: object) -> str:
    return content_hash(payload)


def _pipeline(organization_id: str = "org_a") -> EvaluationPipelineVersion:
    payload = {
        "pipeline_version": "pipeline_v1",
        "engine_version": "engine_v1",
        "taxonomy_version": "taxonomy_v1",
        "normalization_version": "normalization_v1",
        "policy_version": "policy_v1",
        "risk_rule_set_version": "risk_v1",
    }
    return EvaluationPipelineVersion(
        id=f"pipe_{organization_id}",
        organization_id=organization_id,
        pipeline_version="pipeline_v1",
        engine_version="engine_v1",
        taxonomy_version="taxonomy_v1",
        normalization_version="normalization_v1",
        policy_version="policy_v1",
        risk_rule_set_version="risk_v1",
        content_hash=_sha(payload),
        payload=payload,
    )


def _graph(
    *,
    suffix: str,
    run_kind: str,
    selected_plan_id: str,
    with_details: bool,
    organization_id: str = "org_a",
) -> EvaluationGraphWrite:
    input_payload = {"frozen_input": suffix}
    evaluation_payload = {"ordered_evaluation": suffix, "selected": selected_plan_id}
    evaluation = EvaluationRun(
        id=f"eval_{suffix}",
        organization_id=organization_id,
        purchase_request_id="req_a",
        purchase_brief_id="pb_a",
        decision_id="dec_a",
        evaluation_pipeline_version_id=f"pipe_{organization_id}",
        run_kind=run_kind,
        evaluated_at=NOW,
        request_version="request_v1",
        company_profile_version="company_v1",
        stackfile_version="stack_v1",
        registry_version="registry_v1",
        candidate_set_version="candidate_set_v1",
        pack_set_version="pack_set_v1",
        offer_set_version="offer_set_v1",
        quote_set_version="quote_set_v1",
        taxonomy_version="taxonomy_v1",
        normalization_version="normalization_v1",
        policy_version="policy_v1",
        fx_version="fx_v1",
        pipeline_version="pipeline_v1",
        engine_version="engine_v1",
        input_payload_hash=_sha(input_payload),
        input_payload=input_payload,
        evaluation_payload_hash=_sha(evaluation_payload),
        evaluation_payload=evaluation_payload,
        selected_solution_plan_id=selected_plan_id,
        rank_stability="STABLE",
    )
    discovery = DiscoveryRun(
        id=f"discovery_{suffix}",
        organization_id=organization_id,
        evaluation_run_id=evaluation.id,
        candidate_set_hash=_sha({"candidate_set": suffix}),
        output_hash=_sha({"discovery": suffix}),
        raw_record_count=2 if with_details else 0,
        canonical_product_count=1 if with_details else 0,
        duplicate_count=1 if with_details else 0,
        generated_solution_plan_count=1,
        excluded_count=0,
        payload={"discovery": suffix},
    )
    plan_record_id = f"plan_record_{suffix}"
    plan = EvaluationSolutionPlan(
        id=plan_record_id,
        organization_id=organization_id,
        evaluation_run_id=evaluation.id,
        solution_plan_id=selected_plan_id,
        action="BUY",
        component_hash=_sha({"components": suffix}),
        plan_hash=_sha({"solution_plan": suffix}),
        construction_lifecycle="CANDIDATE",
        lifecycle="EXECUTABLE",
        candidate_status="SEIL_PASS",
        primary_reason_code=None,
        rank_position=1,
        selected=True,
        ordering_frontier_member=True,
        resolution_frontier_member=False,
        quote_required=False,
        quote_policy_reason="NONE",
        permitted_resolution=None,
        autonomous_execution_allowed=True,
        stable_action_ids=[f"action_{suffix}"],
        payload={"solution_plan": suffix},
    )
    if not with_details:
        return EvaluationGraphWrite(
            evaluation_run=evaluation,
            discovery_run=discovery,
            solution_plans=(plan,),
        )

    member = CandidateSetMember(
        id=f"member_{suffix}",
        organization_id=organization_id,
        discovery_run_id=discovery.id,
        canonical_identity_id="product_fixture_d:business:us",
        source_record_id="pack_record_d_v1",
        member_kind="PACK",
        disposition="INCLUDED",
        ordinal=0,
        pack_id="pack_d",
        pack_version=1,
        offer_id="offer_d",
        offer_version=1,
        current_action_id=None,
        member_hash=_sha({"member": suffix}),
        payload={"member": suffix},
    )
    merge = IdentityMerge(
        id=f"merge_{suffix}",
        organization_id=organization_id,
        discovery_run_id=discovery.id,
        canonical_identity_id=member.canonical_identity_id,
        merged_record_id="pack_record_d_alias",
        reason_codes=["NORMALIZED_ALIAS"],
        merge_hash=_sha({"merge": suffix}),
    )
    component = SolutionPlanComponent(
        id=f"component_{suffix}",
        organization_id=organization_id,
        evaluation_run_id=evaluation.id,
        solution_plan_record_id=plan.id,
        component_id="component_product_d",
        ordinal=0,
        source_type="PACK",
        action="BUY",
        source_record_id=member.source_record_id,
        component_hash=_sha({"component": suffix}),
        payload={"component": suffix},
    )
    gate = DecisionGateResult(
        id=f"gate_{suffix}",
        organization_id=organization_id,
        evaluation_run_id=evaluation.id,
        solution_plan_record_id=plan.id,
        gate_id="gate_data_residency",
        truth="TRUE",
        derived_status="SEIL_PASS",
        is_primary=True,
        reason_codes=["RESIDENCY_SUPPORTED"],
        evaluated_predicates=["data_residency == US"],
        source_fact_ids=["fact_residency"],
        permitted_resolution=None,
        overridable=False,
        result_hash=_sha({"gate": suffix}),
    )
    evidence = EvidenceAssessmentRecord(
        id=f"evidence_{suffix}",
        organization_id=organization_id,
        evaluation_run_id=evaluation.id,
        evidence_id="evidence_residency",
        source_record_id=member.source_record_id,
        field="data_residency",
        supported_criterion_ids=["criterion_residency"],
        source_allowed=True,
        method_allowed=True,
        scope_match=True,
        reconstructable=True,
        freshness_current=True,
        disputed=False,
        revoked=False,
        state="ACCEPTABLE",
        age_lower_numerator=1,
        age_lower_denominator=10,
        age_upper_numerator=1,
        age_upper_denominator=5,
        reason_codes=[],
        assessment_hash=_sha({"evidence": suffix}),
    )
    score_component = ScoreComponentRecord(
        id=f"score_component_{suffix}",
        organization_id=organization_id,
        evaluation_run_id=evaluation.id,
        solution_plan_record_id=plan.id,
        criterion_id="criterion_residency",
        weight=5,
        coverage_weight=5,
        conservative_satisfaction_numerator=1,
        conservative_satisfaction_denominator=1,
        optimistic_satisfaction_numerator=1,
        optimistic_satisfaction_denominator=1,
        contribution_conservative_numerator=5,
        contribution_conservative_denominator=1,
        contribution_optimistic_numerator=5,
        contribution_optimistic_denominator=1,
        evidence_ids=[evidence.evidence_id],
        evidence_state="ACCEPTABLE",
        prior_label=None,
        input_hash=_sha({"score_input": suffix}),
        component_hash=_sha({"score_component": suffix}),
    )
    bound = ScoreBound(
        id=f"bound_{suffix}",
        organization_id=organization_id,
        evaluation_run_id=evaluation.id,
        solution_plan_record_id=plan.id,
        dimension="PREFERENCE",
        bound_status="AVAILABLE",
        value_kind="RATIO",
        lower_numerator=4,
        lower_denominator=5,
        base_numerator=9,
        base_denominator=10,
        upper_numerator=1,
        upper_denominator=1,
        currency=None,
        unavailable_reason=None,
        calculation_payload={"operator": "WEIGHTED_MEAN"},
        bound_hash=_sha({"bound": suffix}),
    )
    frontier = RobustnessFrontier(
        id=f"frontier_{suffix}",
        organization_id=organization_id,
        evaluation_run_id=evaluation.id,
        solution_plan_record_id=plan.id,
        frontier_kind="ORDERING",
        decision_rank_stability="STABLE",
        member=True,
        can_beat_selected=False,
        permitted_resolution=None,
        frontier_payload={"frontier": suffix},
        frontier_hash=_sha({"frontier": suffix}),
    )
    return EvaluationGraphWrite(
        evaluation_run=evaluation,
        discovery_run=discovery,
        solution_plans=(plan,),
        candidate_set_members=(member,),
        identity_merges=(merge,),
        decision_gate_results=(gate,),
        evidence_assessments=(evidence,),
        solution_plan_components=(component,),
        score_components=(score_component,),
        score_bounds=(bound,),
        robustness_frontiers=(frontier,),
    )


async def _database() -> Database:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.sessions() as session, session.begin():
        session.add(Organization(id="org_a", name="Tenant A"))
        session.add(Organization(id="org_b", name="Tenant B"))
        session.add(
            PurchaseRequest(
                id="req_a",
                organization_id="org_a",
                intent="Choose a supported action",
                status="EVALUATING",
                visibility="PRIVATE",
                version=1,
                payload={"request": "a"},
                request_hash=_sha({"request": "a"}),
            )
        )
        session.add(
            PurchaseBriefVersion(
                id="pb_a",
                organization_id="org_a",
                purchase_request_id="req_a",
                version=1,
                status="ACCEPTED",
                payload={"brief": "a"},
                content_hash=_sha({"brief": "a"}),
                supersedes_id=None,
            )
        )
        session.add(
            DecisionRecord(
                id="dec_a",
                organization_id="org_a",
                purchase_request_id="req_a",
                purchase_brief_id="pb_a",
                version=1,
                supersedes_id=None,
                decision_hash=_sha({"decision": "a"}),
                selected_solution_plan_id="sol_base",
                payload={"decision": "a"},
            )
        )
    return database


def test_graph_models_and_engagement_binding_are_typed_and_tenant_owned() -> None:
    assert GRAPH_TABLES <= set(Base.metadata.tables)
    for table_name in GRAPH_TABLES:
        assert Base.metadata.tables[table_name].c.organization_id.nullable is False

    engagement = Base.metadata.tables[Engagement.__tablename__]
    assert engagement.c.requirement_brief_id.nullable is False
    assert engagement.c.requirement_brief_version.nullable is False
    assert engagement.c.requirement_brief_hash.nullable is False
    engagement_constraints = {constraint.name for constraint in engagement.constraints}
    assert "ck_engagement_requirement_brief_version_positive" in engagement_constraints
    assert "fk_engagement_exact_requirement_brief" in engagement_constraints

    prohibited = {"credential", "token", "cvv", "card_number", "prava_secret"}
    graph_columns = {
        column.name.lower()
        for table_name in GRAPH_TABLES
        for column in Base.metadata.tables[table_name].columns
    }
    assert prohibited.isdisjoint(graph_columns)


def test_graph_migration_forces_rls_for_every_new_tenant_table() -> None:
    migration = (
        ROOT
        / "services"
        / "api"
        / "alembic"
        / "versions"
        / "23a8fff461fe_add_decision_graph_records.py"
    ).read_text(encoding="utf-8")
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "CREATE POLICY tenant_isolation" in migration
    for table_name in GRAPH_TABLES:
        assert f'"{table_name}"' in migration


@pytest.mark.asyncio
async def test_repository_atomically_round_trips_complete_evaluation_graph() -> None:
    database = await _database()
    try:
        graph = _graph(
            suffix="base", run_kind="BASE", selected_plan_id="sol_base", with_details=True
        )
        async with database.transaction("org_a") as session:
            repository = WorkflowRepository(session, "org_a")
            await repository.add_evaluation_pipeline_version(_pipeline())
            await repository.add_evaluation_graph(graph)

        async with database.transaction("org_a") as session:
            snapshot = await WorkflowRepository(session, "org_a").get_evaluation_graph("eval_base")
            assert snapshot.evaluation_run.evaluation_payload_hash == _sha(
                {"ordered_evaluation": "base", "selected": "sol_base"}
            )
            assert [plan.solution_plan_id for plan in snapshot.solution_plans] == ["sol_base"]
            assert [member.source_record_id for member in snapshot.candidate_set_members] == [
                "pack_record_d_v1"
            ]
            assert len(snapshot.identity_merges) == 1
            assert len(snapshot.decision_gate_results) == 1
            assert len(snapshot.evidence_assessments) == 1
            assert len(snapshot.solution_plan_components) == 1
            assert len(snapshot.score_components) == 1
            assert snapshot.score_bounds[0].lower_numerator == 4
            assert snapshot.score_bounds[0].lower_denominator == 5
            assert snapshot.robustness_frontiers[0].decision_rank_stability == "STABLE"
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_repository_rejects_reversed_exact_bounds_before_writing_graph() -> None:
    database = await _database()
    try:
        graph = _graph(
            suffix="base", run_kind="BASE", selected_plan_id="sol_base", with_details=True
        )
        graph.score_bounds[0].lower_numerator = 2
        graph.score_bounds[0].lower_denominator = 1
        graph.score_bounds[0].base_numerator = 1
        graph.score_bounds[0].base_denominator = 1
        graph.score_bounds[0].upper_numerator = 1
        graph.score_bounds[0].upper_denominator = 1
        async with database.transaction("org_a") as session:
            repository = WorkflowRepository(session, "org_a")
            await repository.add_evaluation_pipeline_version(_pipeline())
            with pytest.raises(PersistenceConflict, match="values are reversed"):
                await repository.add_evaluation_graph(graph)

        async with database.transaction("org_a") as session:
            with pytest.raises(RecordNotFound):
                await WorkflowRepository(session, "org_a").get_evaluation_graph("eval_base")
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_counterfactuals_bind_existing_evaluation_payload_hashes_only() -> None:
    database = await _database()
    try:
        graphs = (
            _graph(suffix="base", run_kind="BASE", selected_plan_id="sol_base", with_details=False),
            _graph(
                suffix="generic",
                run_kind="GENERIC",
                selected_plan_id="sol_generic",
                with_details=False,
            ),
            _graph(
                suffix="alternate",
                run_kind="COUNTERFACTUAL",
                selected_plan_id="sol_alternate",
                with_details=False,
            ),
        )
        async with database.transaction("org_a") as session:
            repository = WorkflowRepository(session, "org_a")
            await repository.add_evaluation_pipeline_version(_pipeline())
            for graph in graphs:
                await repository.add_evaluation_graph(graph)

        payload = {
            "outcome": "WINNER_CHANGED",
            "base_evaluation_payload_hash": graphs[0].evaluation_run.evaluation_payload_hash,
            "alternate_evaluation_payload_hash": graphs[2].evaluation_run.evaluation_payload_hash,
            "generic_evaluation_payload_hash": graphs[1].evaluation_run.evaluation_payload_hash,
            "removed_fact_ids": ["fact_private_1"],
        }
        record = CounterfactualRecordModel(
            id="counterfactual_a",
            organization_id="org_a",
            decision_id="dec_a",
            outcome="WINNER_CHANGED",
            removed_fact_ids=["fact_private_1"],
            alternative_fact_id_sets=[],
            tested_limit=3,
            base_evaluation_payload_hash=graphs[0].evaluation_run.evaluation_payload_hash,
            alternate_evaluation_payload_hash=graphs[2].evaluation_run.evaluation_payload_hash,
            generic_evaluation_payload_hash=graphs[1].evaluation_run.evaluation_payload_hash,
            base_selected_solution_plan_id="sol_base",
            alternate_selected_solution_plan_id="sol_alternate",
            generic_selected_solution_plan_id="sol_generic",
            changed_gate_ids=["gate_private_context"],
            record_hash=_sha(payload),
            payload=payload,
        )
        async with database.transaction("org_a") as session:
            repository = WorkflowRepository(session, "org_a")
            await repository.add_counterfactual_record(record)
            stored = await repository.get_counterfactual_record(record.record_hash)
            assert (
                stored.base_evaluation_payload_hash
                == graphs[0].evaluation_run.evaluation_payload_hash
            )
            assert (
                stored.alternate_evaluation_payload_hash
                == graphs[2].evaluation_run.evaluation_payload_hash
            )
            assert "evaluation_run_id" not in stored.payload

        bad_payload = {"outcome": "WINNER_CHANGED", "unknown": True}
        missing = CounterfactualRecordModel(
            id="counterfactual_missing",
            organization_id="org_b",
            decision_id=None,
            outcome="WINNER_CHANGED",
            removed_fact_ids=["fact_private_1"],
            alternative_fact_id_sets=[],
            tested_limit=3,
            base_evaluation_payload_hash=graphs[0].evaluation_run.evaluation_payload_hash,
            alternate_evaluation_payload_hash=graphs[2].evaluation_run.evaluation_payload_hash,
            generic_evaluation_payload_hash=graphs[1].evaluation_run.evaluation_payload_hash,
            base_selected_solution_plan_id="sol_base",
            alternate_selected_solution_plan_id="sol_alternate",
            generic_selected_solution_plan_id="sol_generic",
            changed_gate_ids=[],
            record_hash=_sha(bad_payload),
            payload=bad_payload,
        )
        async with database.transaction("org_b") as session:
            with pytest.raises(PersistenceConflict, match="unknown tenant evaluation"):
                await WorkflowRepository(session, "org_b").add_counterfactual_record(missing)
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_action_run_and_verified_result_artifact_are_action_neutral() -> None:
    database = await _database()
    try:
        graph = _graph(
            suffix="base", run_kind="BASE", selected_plan_id="sol_base", with_details=False
        )
        async with database.transaction("org_a") as session:
            repository = WorkflowRepository(session, "org_a")
            await repository.add_evaluation_pipeline_version(_pipeline())
            await repository.add_evaluation_graph(graph)
            session.add(
                DecisionRecord(
                    id="dec_selected",
                    organization_id="org_a",
                    purchase_request_id="req_a",
                    purchase_brief_id="pb_a",
                    version=2,
                    supersedes_id="dec_a",
                    decision_hash=_sha({"decision": "selected"}),
                    selected_solution_plan_id="sol_base",
                    payload={
                        "decision": "selected",
                        "evaluation_payload_hash": graph.evaluation_run.evaluation_payload_hash,
                    },
                )
            )

        run_payload = {"action": "BUY", "checkpoint": "approved"}
        action_run = ActionRun(
            id="action_run_a",
            organization_id="org_a",
            decision_id="dec_selected",
            solution_plan_record_id="plan_record_base",
            solution_plan_id="sol_base",
            purchase_intent_id=None,
            action="BUY",
            status="RUNNING",
            current_checkpoint="approved",
            last_successful_checkpoint="selected",
            owner_role="CARDHOLDER",
            blocking_task=None,
            recovery_action=None,
            retryable=False,
            safe_to_leave=True,
            started_at=NOW,
            completed_at=None,
            run_hash=_sha(run_payload),
            supersedes_id=None,
            payload=run_payload,
        )
        artifact_payload = {"artifact": "decision_record", "verified": True}
        artifact = ResultArtifact(
            id="artifact_a",
            organization_id="org_a",
            action_run_id=action_run.id,
            artifact_type="DECISION_RECORD",
            verification_state="VERIFIED",
            actor_id="actor_buyer",
            owner_role="REQUESTER",
            occurred_at=NOW,
            verified_at=NOW,
            safe_label="Decision recorded",
            href="/v1/result-artifacts/artifact_a",
            stack_patch_id=None,
            receipt_id=None,
            artifact_hash=_sha(artifact_payload),
            payload=artifact_payload,
        )
        async with database.transaction("org_a") as session:
            repository = WorkflowRepository(session, "org_a")
            await repository.add_action_run(action_run)
            await repository.add_result_artifact(artifact)

        async with database.transaction("org_a") as session:
            snapshot = await WorkflowRepository(session, "org_a").get_action_run_snapshot(
                action_run.id
            )
            assert snapshot.action_run.decision_id == "dec_selected"
            assert snapshot.action_run.purchase_intent_id is None
            assert snapshot.result_artifacts[0].verification_state == "VERIFIED"
            assert snapshot.result_artifacts[0].artifact_type == "DECISION_RECORD"
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_action_run_rejects_plan_from_non_direct_source_decision() -> None:
    database = await _database()
    try:
        graph = _graph(
            suffix="base", run_kind="BASE", selected_plan_id="sol_base", with_details=False
        )
        async with database.transaction("org_a") as session:
            repository = WorkflowRepository(session, "org_a")
            await repository.add_evaluation_pipeline_version(_pipeline())
            await repository.add_evaluation_graph(graph)
            session.add_all(
                (
                    DecisionRecord(
                        id="dec_selected",
                        organization_id="org_a",
                        purchase_request_id="req_a",
                        purchase_brief_id="pb_a",
                        version=2,
                        supersedes_id="dec_a",
                        decision_hash=_sha({"decision": "selected"}),
                        selected_solution_plan_id="sol_base",
                        payload={
                            "decision": "selected",
                            "evaluation_payload_hash": graph.evaluation_run.evaluation_payload_hash,
                        },
                    ),
                    DecisionRecord(
                        id="dec_grandchild",
                        organization_id="org_a",
                        purchase_request_id="req_a",
                        purchase_brief_id="pb_a",
                        version=3,
                        supersedes_id="dec_selected",
                        decision_hash=_sha({"decision": "grandchild"}),
                        selected_solution_plan_id="sol_base",
                        payload={
                            "decision": "grandchild",
                            "evaluation_payload_hash": graph.evaluation_run.evaluation_payload_hash,
                        },
                    ),
                )
            )

        payload = {"action": "BUY", "checkpoint": "queued"}
        async with database.transaction("org_a") as session:
            with pytest.raises(PersistenceConflict, match="does not belong"):
                await WorkflowRepository(session, "org_a").add_action_run(
                    ActionRun(
                        id="action_run_invalid",
                        organization_id="org_a",
                        decision_id="dec_grandchild",
                        solution_plan_record_id="plan_record_base",
                        solution_plan_id="sol_base",
                        purchase_intent_id=None,
                        action="BUY",
                        status="QUEUED",
                        current_checkpoint=None,
                        last_successful_checkpoint=None,
                        owner_role="DECISION_MAKER",
                        blocking_task=None,
                        recovery_action=None,
                        retryable=False,
                        safe_to_leave=True,
                        started_at=NOW,
                        completed_at=None,
                        run_hash=_sha(payload),
                        supersedes_id=None,
                        payload=payload,
                    )
                )
    finally:
        await database.close()
