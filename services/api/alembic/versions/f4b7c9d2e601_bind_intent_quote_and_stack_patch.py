"""bind purchase intents to exact quote and Stackfile patch versions

Revision ID: f4b7c9d2e601
Revises: c2d4e6f8a101
Create Date: 2026-08-02 08:00:00
"""

from collections.abc import Mapping, Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "f4b7c9d2e601"
down_revision: str | None = "c2d4e6f8a101"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError("existing immutable payload is not a JSON object")
    return value


def upgrade() -> None:
    with op.batch_alter_table("purchase_intents") as batch:
        batch.add_column(sa.Column("quote_version", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("stack_patch_id", sa.String(64), nullable=True))

    bind = op.get_bind()
    purchase_intents = sa.table(
        "purchase_intents",
        sa.column("id", sa.String(64)),
        sa.column("organization_id", sa.String(64)),
        sa.column("decision_id", sa.String(64)),
        sa.column("solution_plan_id", sa.String(64)),
        sa.column("payload", sa.JSON()),
        sa.column("quote_version", sa.Integer()),
        sa.column("stack_patch_id", sa.String(64)),
    )
    decision_records = sa.table(
        "decision_records",
        sa.column("id", sa.String(64)),
        sa.column("organization_id", sa.String(64)),
        sa.column("payload", sa.JSON()),
    )
    stack_patches = sa.table(
        "stack_patches",
        sa.column("id", sa.String(64)),
        sa.column("organization_id", sa.String(64)),
    )

    rows = bind.execute(
        sa.select(
            purchase_intents.c.id,
            purchase_intents.c.organization_id,
            purchase_intents.c.decision_id,
            purchase_intents.c.solution_plan_id,
            purchase_intents.c.payload,
        )
    ).mappings()
    for row in rows:
        intent_payload = _mapping(row["payload"])
        quote_version = intent_payload.get("quote_version")
        if isinstance(quote_version, bool) or not isinstance(quote_version, int):
            raise RuntimeError("existing Purchase Intent has no exact quote_version")

        decision_payload = bind.execute(
            sa.select(decision_records.c.payload).where(
                decision_records.c.id == row["decision_id"],
                decision_records.c.organization_id == row["organization_id"],
            )
        ).scalar_one()
        ledger = _mapping(_mapping(decision_payload).get("ledger"))
        solution_plans = ledger.get("solution_plans")
        if not isinstance(solution_plans, list):
            raise RuntimeError("existing Decision Record has no Solution Plans")
        selected_plan = next(
            (
                _mapping(plan)
                for plan in solution_plans
                if isinstance(plan, Mapping)
                and plan.get("solution_plan_id") == row["solution_plan_id"]
            ),
            None,
        )
        if selected_plan is None:
            raise RuntimeError("existing Purchase Intent has no selected Solution Plan")
        stack_patch_id = selected_plan.get("stack_patch_id")
        if not isinstance(stack_patch_id, str) or not stack_patch_id:
            raise RuntimeError("existing selected Solution Plan has no Stackfile patch")
        linked_patch = bind.execute(
            sa.select(stack_patches.c.id).where(
                stack_patches.c.id == stack_patch_id,
                stack_patches.c.organization_id == row["organization_id"],
            )
        ).scalar_one_or_none()
        if linked_patch is None:
            raise RuntimeError("existing selected Solution Plan references an unavailable patch")
        bind.execute(
            sa.update(purchase_intents)
            .where(purchase_intents.c.id == row["id"])
            .values(quote_version=quote_version, stack_patch_id=stack_patch_id)
        )

    with op.batch_alter_table("purchase_intents") as batch:
        batch.drop_constraint("uq_purchase_intent_business_lock", type_="unique")
        batch.alter_column("quote_version", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("stack_patch_id", existing_type=sa.String(64), nullable=False)
        batch.create_check_constraint(
            "ck_purchase_intent_quote_version_positive", "quote_version >= 1"
        )
        batch.create_foreign_key(
            "fk_purchase_intents_stack_patch_id_stack_patches",
            "stack_patches",
            ["stack_patch_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_unique_constraint(
            "uq_purchase_intent_business_lock",
            [
                "organization_id",
                "decision_id",
                "solution_plan_id",
                "quote_id",
                "quote_version",
            ],
        )


def downgrade() -> None:
    with op.batch_alter_table("purchase_intents") as batch:
        batch.drop_constraint("uq_purchase_intent_business_lock", type_="unique")
        batch.drop_constraint(
            "fk_purchase_intents_stack_patch_id_stack_patches", type_="foreignkey"
        )
        batch.drop_constraint("ck_purchase_intent_quote_version_positive", type_="check")
        batch.drop_column("stack_patch_id")
        batch.drop_column("quote_version")
        batch.create_unique_constraint(
            "uq_purchase_intent_business_lock",
            ["organization_id", "decision_id", "solution_plan_id", "quote_id"],
        )
