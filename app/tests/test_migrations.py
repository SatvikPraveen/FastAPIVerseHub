# File: app/tests/test_migrations.py
"""Guard rails for the Alembic migration chain.

* ``upgrade head`` must succeed from an empty database.
* After upgrading, the schema must match ``Base.metadata`` exactly, so a
  model change without a migration fails CI instead of production.
* ``downgrade base`` must undo everything (migrations are reversible).
"""

from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect

import app.models  # noqa: F401 - register every table on Base.metadata
from alembic import command
from app.models.base import Base

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def alembic_config(tmp_path: Path) -> tuple[Config, str]:
    db_file = tmp_path / "migrations.db"
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_file}")
    # post-write hooks are irrelevant here and require ruff on PATH
    cfg.set_section_option("post_write_hooks", "hooks", "")
    return cfg, f"sqlite:///{db_file}"


@pytest.mark.timeout(120)
def test_upgrade_head_matches_models(alembic_config: tuple[Config, str]) -> None:
    cfg, sync_url = alembic_config
    command.upgrade(cfg, "head")

    engine = create_engine(sync_url)
    with engine.connect() as conn:
        tables = set(inspect(conn).get_table_names())
        assert "alembic_version" in tables
        assert set(Base.metadata.tables) <= tables

        ctx = MigrationContext.configure(conn, opts={"compare_type": True, "render_as_batch": True})
        diffs = compare_metadata(ctx, Base.metadata)
    engine.dispose()

    assert diffs == [], f"models and migrations have drifted: {diffs}"


@pytest.mark.timeout(120)
def test_downgrade_base_is_clean(alembic_config: tuple[Config, str]) -> None:
    cfg, sync_url = alembic_config
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    engine = create_engine(sync_url)
    with engine.connect() as conn:
        remaining = set(inspect(conn).get_table_names()) - {"alembic_version"}
    engine.dispose()

    assert remaining == set(), f"downgrade left tables behind: {remaining}"
