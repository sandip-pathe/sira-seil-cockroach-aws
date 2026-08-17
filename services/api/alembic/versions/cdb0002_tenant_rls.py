"""Enforce tenant isolation for the CockroachDB runtime role.

Revision ID: cdb0002
Revises: cdb0001
Create Date: 2026-08-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "cdb0002"
down_revision: str | None = "cdb0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "action_runs",
    "agent_capability_grants",
    "agent_effects",
    "agent_experiments",
    "agent_mission_artifacts",
    "agent_mission_checkpoints",
    "agent_mission_events",
    "agent_mission_tasks",
    "agent_missions",
    "approval_events",
    "approval_requests",
    "browser_return_bindings",
    "calibration_runs",
    "candidate_feedback",
    "candidate_set_members",
    "counterfactual_records",
    "decision_gate_results",
    "decision_records",
    "decision_simulations",
    "decision_source_snapshots",
    "discovery_runs",
    "engagements",
    "entitlements",
    "evaluation_pipeline_versions",
    "evaluation_runs",
    "evaluation_solution_plans",
    "evidence_assessments",
    "idempotency_records",
    "identity_merges",
    "merchant_orders",
    "outbox_events",
    "outcome_checkpoints",
    "payment_attempts",
    "payment_sessions",
    "purchase_brief_versions",
    "purchase_intents",
    "purchase_requests",
    "purchase_reversals",
    "receipts",
    "requirement_brief_versions",
    "result_artifacts",
    "robustness_frontiers",
    "score_bounds",
    "score_components",
    "seller_activity_events",
    "seller_evidence_attachments",
    "seller_pack_draft_revisions",
    "seller_pack_drafts",
    "seller_pack_export_artifacts",
    "seller_pack_suspensions",
    "seller_pack_versions",
    "seller_product_claims",
    "seller_products",
    "seller_review_decisions",
    "seller_review_submissions",
    "solution_plan_components",
    "stack_patches",
    "stack_snapshots",
    "transaction_transitions",
    "workflow_runs",
)

_TENANT_EXPRESSION = (
    "organization_id = split_part(current_setting('application_name', true), '.', 2)"
)


def upgrade() -> None:
    op.execute("CREATE ROLE IF NOT EXISTS sira_runtime")
    op.execute("GRANT USAGE ON SCHEMA public TO sira_runtime")
    # Tenant rows reference organizations, and readiness verifies the migration head.
    op.execute("GRANT SELECT ON TABLE organizations, alembic_version TO sira_runtime")
    op.execute("ALTER TABLE organizations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organizations FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY organization_isolation ON organizations FOR SELECT TO sira_runtime "
        "USING (id = split_part(current_setting('application_name', true), '.', 2))"
    )
    for table in TENANT_TABLES:
        op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "{table}" TO sira_runtime')
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(
            f'CREATE POLICY tenant_isolation ON "{table}" '
            f"FOR ALL TO sira_runtime USING ({_TENANT_EXPRESSION}) "
            f"WITH CHECK ({_TENANT_EXPRESSION})"
        )


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON TABLE "{table}" FROM sira_runtime')
    op.execute("DROP POLICY IF EXISTS organization_isolation ON organizations")
    op.execute("ALTER TABLE organizations DISABLE ROW LEVEL SECURITY")
    op.execute("REVOKE SELECT ON TABLE organizations, alembic_version FROM sira_runtime")
    op.execute("REVOKE USAGE ON SCHEMA public FROM sira_runtime")
    op.execute("DROP ROLE IF EXISTS sira_runtime")
