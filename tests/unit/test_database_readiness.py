from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from persistence.database import EXPECTED_ALEMBIC_HEADS

ROOT = Path(__file__).resolve().parents[2]


def test_expected_database_heads_match_migration_scripts() -> None:
    config = Config(str(ROOT / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)

    assert frozenset(scripts.get_heads()) == EXPECTED_ALEMBIC_HEADS
