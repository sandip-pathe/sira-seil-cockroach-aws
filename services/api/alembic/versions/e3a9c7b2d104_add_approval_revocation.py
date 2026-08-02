"""add approval revocation

Revision ID: e3a9c7b2d104
Revises: f1b8d6a42003
Create Date: 2026-08-02 18:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e3a9c7b2d104"
down_revision: str | None = "f1b8d6a42003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_purchase_intent_approval_status", "purchase_intents", type_="check")
    op.create_check_constraint(
        "ck_purchase_intent_approval_status",
        "purchase_intents",
        "approval_status IN ("
        "'NOT_REQUESTED','PENDING','APPROVED','REJECTED','REVOKED','EXPIRED','SUPERSEDED')",
    )
    op.create_check_constraint(
        "ck_approval_request_status",
        "approval_requests",
        "status IN ('PENDING','APPROVED','REJECTED','REVOKED','EXPIRED','SUPERSEDED')",
    )
    op.drop_constraint("ck_approval_event_action", "approval_events", type_="check")
    op.create_check_constraint(
        "ck_approval_event_action",
        "approval_events",
        "action IN ('APPROVE','REJECT','REVOKE','DELEGATE')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_approval_event_action", "approval_events", type_="check")
    op.create_check_constraint(
        "ck_approval_event_action",
        "approval_events",
        "action IN ('APPROVE','REJECT','DELEGATE')",
    )
    op.drop_constraint("ck_approval_request_status", "approval_requests", type_="check")
    op.drop_constraint("ck_purchase_intent_approval_status", "purchase_intents", type_="check")
    op.create_check_constraint(
        "ck_purchase_intent_approval_status",
        "purchase_intents",
        "approval_status IN ("
        "'NOT_REQUESTED','PENDING','APPROVED','REJECTED','EXPIRED','SUPERSEDED')",
    )
