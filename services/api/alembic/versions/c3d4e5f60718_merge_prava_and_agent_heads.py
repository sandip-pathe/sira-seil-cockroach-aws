"""merge Prava OAuth and agent mission migration heads

Revision ID: c3d4e5f60718
Revises: a1d4e7f9b203, b1c2d3e4f506
Create Date: 2026-08-06 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "c3d4e5f60718"
down_revision: tuple[str, str] = ("a1d4e7f9b203", "b1c2d3e4f506")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the two independently created migration branches."""


def downgrade() -> None:
    """Split back to the two parent migration heads."""
