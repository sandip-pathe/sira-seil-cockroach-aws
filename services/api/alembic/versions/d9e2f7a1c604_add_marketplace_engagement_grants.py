"""add explicit cross-organization engagement grants

Revision ID: d9e2f7a1c604
Revises: a4c8e1f7b205
Create Date: 2026-08-02 16:30:00
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "d9e2f7a1c604"
down_revision: str | None = "a4c8e1f7b205"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BRIEF_KEYS = frozenset(
    {
        "schema_version",
        "requirement_brief_id",
        "version",
        "purchase_brief_id",
        "purchase_brief_version",
        "request_id",
        "visibility",
        "category_id",
        "intent",
        "desired_outcome",
        "team",
        "data_profile",
        "hard_requirements",
        "preferences",
        "allowed_stack_context",
        "seller_questions",
        "expires_at",
        "content_hash",
    }
)


def _hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _backfill() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT e.id, e.organization_id, e.expected_buyer_actor_id,
                   e.expected_seller_actor_id, e.requirement_brief_hash, rb.payload
            FROM engagements AS e
            JOIN requirement_brief_versions AS rb
              ON rb.organization_id = e.organization_id
             AND rb.id = e.requirement_brief_id
             AND rb.version = e.requirement_brief_version
             AND rb.content_hash = e.requirement_brief_hash
            """
        )
    ).mappings()
    for row in rows:
        actor_id = str(row["expected_seller_actor_id"])
        seller_org = "org_seller_" + hashlib.sha256(actor_id.encode()).hexdigest()[:16]
        exists = connection.execute(
            sa.text("SELECT 1 FROM organizations WHERE id = :id"), {"id": seller_org}
        ).scalar_one_or_none()
        if exists is None:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO organizations (id, name, version, created_at, updated_at)
                    VALUES (:id, :name, 1, :now, :now)
                    """
                ),
                {
                    "id": seller_org,
                    "name": "Migrated seller organization",
                    "now": datetime.now(UTC),
                },
            )
        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        safe_brief = {key: value for key, value in dict(payload).items() if key in _BRIEF_KEYS}
        grant_scope = "SANITIZED_BRIEF_AND_CONTACT_CONSENT"
        grant_hash = _hash(
            {
                "engagement_id": row["id"],
                "buyer_organization_id": row["organization_id"],
                "seller_organization_id": seller_org,
                "buyer_actor_id": row["expected_buyer_actor_id"],
                "seller_actor_id": actor_id,
                "requirement_brief_hash": row["requirement_brief_hash"],
                "grant_scope": grant_scope,
            }
        )
        connection.execute(
            sa.text(
                """
                UPDATE engagements
                   SET seller_organization_id = :seller_organization_id,
                       grant_scope = :grant_scope,
                       grant_status = 'ACTIVE',
                       grant_hash = :grant_hash,
                       seller_visible_requirement_brief = :seller_visible_requirement_brief,
                       granted_at = :granted_at
                 WHERE id = :id
                """
            ).bindparams(
                sa.bindparam(
                    "seller_visible_requirement_brief",
                    type_=sa.JSON(),
                )
            ),
            {
                "seller_organization_id": seller_org,
                "grant_scope": grant_scope,
                "grant_hash": grant_hash,
                "seller_visible_requirement_brief": safe_brief,
                "granted_at": datetime.now(UTC),
                "id": row["id"],
            },
        )


def _install_postgres_policies() -> None:
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return
    current_org = "NULLIF(current_setting('app.organization_id', true), '')"
    buyer = f"organization_id = {current_org}"
    seller = f"seller_organization_id = {current_org} AND grant_status = 'ACTIVE'"
    op.execute(sa.text("DROP POLICY IF EXISTS tenant_access ON engagements"))
    op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON engagements"))
    for name in (
        "engagement_party_select",
        "engagement_owner_insert",
        "engagement_party_update",
        "engagement_owner_delete",
    ):
        op.execute(sa.text(f"DROP POLICY IF EXISTS {name} ON engagements"))
    op.execute(
        sa.text(
            "CREATE POLICY engagement_party_select ON engagements FOR SELECT TO PUBLIC "
            f"USING ({buyer} OR ({seller}))"
        )
    )
    op.execute(
        sa.text(
            "CREATE POLICY engagement_owner_insert ON engagements FOR INSERT TO PUBLIC "
            f"WITH CHECK ({buyer})"
        )
    )
    op.execute(
        sa.text(
            "CREATE POLICY engagement_party_update ON engagements FOR UPDATE TO PUBLIC "
            f"USING ({buyer} OR ({seller})) WITH CHECK ({buyer} OR ({seller}))"
        )
    )
    op.execute(
        sa.text(
            "CREATE POLICY engagement_owner_delete ON engagements FOR DELETE TO PUBLIC "
            f"USING ({buyer})"
        )
    )


def upgrade() -> None:
    with op.batch_alter_table("engagements") as batch:
        batch.add_column(sa.Column("seller_organization_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("grant_scope", sa.String(80), nullable=True))
        batch.add_column(sa.Column("grant_status", sa.String(24), nullable=True))
        batch.add_column(sa.Column("grant_hash", sa.String(80), nullable=True))
        batch.add_column(sa.Column("seller_visible_requirement_brief", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True))
    _backfill()
    with op.batch_alter_table("engagements") as batch:
        for column in (
            "seller_organization_id",
            "grant_scope",
            "grant_status",
            "grant_hash",
            "seller_visible_requirement_brief",
            "granted_at",
        ):
            batch.alter_column(column, nullable=False)
        batch.create_foreign_key(
            "fk_engagement_seller_organization",
            "organizations",
            ["seller_organization_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_check_constraint(
            "ck_engagement_distinct_organizations",
            "organization_id <> seller_organization_id",
        )
        batch.create_check_constraint(
            "ck_engagement_grant_scope",
            "grant_scope = 'SANITIZED_BRIEF_AND_CONTACT_CONSENT'",
        )
        batch.create_check_constraint(
            "ck_engagement_grant_status",
            "grant_status IN ('ACTIVE','REVOKED','EXPIRED')",
        )
        batch.create_unique_constraint(
            "uq_engagement_grant_hash", ["organization_id", "grant_hash"]
        )
        batch.create_index("ix_engagements_seller_organization_id", ["seller_organization_id"])
    _install_postgres_policies()


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        current_org = "NULLIF(current_setting('app.organization_id', true), '')"
        for name in (
            "engagement_party_select",
            "engagement_owner_insert",
            "engagement_party_update",
            "engagement_owner_delete",
        ):
            op.execute(sa.text(f"DROP POLICY IF EXISTS {name} ON engagements"))
        op.execute(
            sa.text(
                "CREATE POLICY tenant_access ON engagements AS PERMISSIVE FOR ALL TO PUBLIC "
                f"USING (organization_id = {current_org}) "
                f"WITH CHECK (organization_id = {current_org})"
            )
        )
        op.execute(
            sa.text(
                "CREATE POLICY tenant_isolation ON engagements AS RESTRICTIVE FOR ALL TO PUBLIC "
                f"USING (organization_id = {current_org}) "
                f"WITH CHECK (organization_id = {current_org})"
            )
        )
    with op.batch_alter_table("engagements") as batch:
        batch.drop_index("ix_engagements_seller_organization_id")
        batch.drop_constraint("uq_engagement_grant_hash", type_="unique")
        batch.drop_constraint("ck_engagement_grant_status", type_="check")
        batch.drop_constraint("ck_engagement_grant_scope", type_="check")
        batch.drop_constraint("ck_engagement_distinct_organizations", type_="check")
        batch.drop_constraint("fk_engagement_seller_organization", type_="foreignkey")
        batch.drop_column("granted_at")
        batch.drop_column("seller_visible_requirement_brief")
        batch.drop_column("grant_hash")
        batch.drop_column("grant_status")
        batch.drop_column("grant_scope")
        batch.drop_column("seller_organization_id")
