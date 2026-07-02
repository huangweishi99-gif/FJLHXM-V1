"""trade_context_snapshots + context_bucket_stats

Revision ID: 002
Revises: 001
Create Date: 2026-06-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trade_context_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("trade_id", sa.Text(), nullable=False),
        sa.Column("setup_key", sa.Text(), nullable=True),
        sa.Column("strategy_id", sa.Text(), nullable=False),
        sa.Column("market", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("timeframe", sa.Text(), nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("side", sa.SmallInteger(), nullable=True),
        sa.Column("entry_price", sa.Numeric(), nullable=True),
        sa.Column("initial_stop", sa.Numeric(), nullable=True),
        sa.Column("exit_reason", sa.Text(), nullable=True),
        sa.Column("net_pnl", sa.Numeric(), nullable=True),
        sa.Column("r_multiple", sa.Numeric(), nullable=True),
        sa.Column("holding_bars", sa.Integer(), nullable=True),
        sa.Column("engine_version", sa.Text(), nullable=True),
        sa.Column("context_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trade_id", name="uq_trade_context_snapshots_trade_id"),
    )
    op.create_index("idx_tcs_strategy_market", "trade_context_snapshots", ["strategy_id", "market"])
    op.create_index("idx_tcs_symbol", "trade_context_snapshots", ["symbol"])

    op.create_table(
        "context_bucket_stats",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("strategy_id", sa.Text(), nullable=False),
        sa.Column("market", sa.Text(), nullable=False),
        sa.Column("bucket_key", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("wins", sa.Integer(), nullable=False),
        sa.Column("win_rate", sa.Numeric(), nullable=True),
        sa.Column("win_rate_smoothed", sa.Numeric(), nullable=True),
        sa.Column("avg_r", sa.Numeric(), nullable=True),
        sa.Column("avg_r_smoothed", sa.Numeric(), nullable=True),
        sa.Column("sample_confidence", sa.Numeric(), nullable=True),
        sa.Column("signal_score", sa.Numeric(), nullable=True),
        sa.Column("signal_tier", sa.Text(), nullable=True),
        sa.Column("engine_version", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "strategy_id",
            "market",
            "bucket_key",
            "engine_version",
            name="uq_context_bucket_stats_key",
        ),
    )
    op.create_index("idx_cbs_strategy_market", "context_bucket_stats", ["strategy_id", "market"])


def downgrade() -> None:
    op.drop_index("idx_cbs_strategy_market", table_name="context_bucket_stats")
    op.drop_table("context_bucket_stats")
    op.drop_index("idx_tcs_symbol", table_name="trade_context_snapshots")
    op.drop_index("idx_tcs_strategy_market", table_name="trade_context_snapshots")
    op.drop_table("trade_context_snapshots")
