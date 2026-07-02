"""backtest_jobs

Revision ID: 003
Revises: 002
Create Date: 2026-06-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtest_jobs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("market", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("strategy_id", sa.Text(), nullable=False),
        sa.Column("years", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("cache_key", sa.Text(), nullable=False),
        sa.Column("params_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("years BETWEEN 1 AND 5", name="ck_backtest_jobs_years"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_backtest_jobs_status_created", "backtest_jobs", ["status", "created_at"])
    op.create_index("idx_backtest_jobs_cache_key", "backtest_jobs", ["cache_key"])
    op.create_index("idx_backtest_jobs_symbol", "backtest_jobs", ["market", "symbol"])


def downgrade() -> None:
    op.drop_index("idx_backtest_jobs_symbol", table_name="backtest_jobs")
    op.drop_index("idx_backtest_jobs_cache_key", table_name="backtest_jobs")
    op.drop_index("idx_backtest_jobs_status_created", table_name="backtest_jobs")
    op.drop_table("backtest_jobs")
