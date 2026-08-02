"""allow multiple policy bundles per pipeline version

Revision ID: f1b8d6a42003
Revises: ec4ca586ccc9
Create Date: 2026-08-02 06:45:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f1b8d6a42003"
down_revision: str | None = "ec4ca586ccc9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_evaluation_pipeline_version",
        "evaluation_pipeline_versions",
        type_="unique",
    )
    op.create_index(
        "ix_evaluation_pipeline_version_lookup",
        "evaluation_pipeline_versions",
        ["organization_id", "pipeline_version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_evaluation_pipeline_version_lookup",
        table_name="evaluation_pipeline_versions",
    )
    op.create_unique_constraint(
        "uq_evaluation_pipeline_version",
        "evaluation_pipeline_versions",
        ["organization_id", "pipeline_version"],
    )
