"""instruments + bars (Timescale hypertable)

Revision ID: 001
Revises:
Create Date: 2026-05-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def _timescale_available() -> bool:
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb'")
    ).fetchone()
    return row is not None


def upgrade() -> None:
    use_timescale = _timescale_available()
    if use_timescale:
        op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    op.create_table(
        "instruments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("market", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("exchange", sa.Text(), nullable=True),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.Column("multiplier", sa.Numeric(), nullable=True),
        sa.Column("tick_size", sa.Numeric(), nullable=True),
        sa.Column("margin_rate", sa.Numeric(), nullable=True),
        sa.Column("is_whitelisted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("metadata", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market", "symbol", name="uq_instruments_market_symbol"),
    )

    op.create_table(
        "bars",
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("timeframe", sa.Text(), nullable=False),
        sa.Column("dt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(), nullable=False),
        sa.Column("high", sa.Numeric(), nullable=False),
        sa.Column("low", sa.Numeric(), nullable=False),
        sa.Column("close", sa.Numeric(), nullable=False),
        sa.Column("volume", sa.Numeric(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("instrument_id", "timeframe", "dt"),
    )

    op.create_index("idx_bars_instrument_timeframe_dt", "bars", ["instrument_id", "timeframe", "dt"])
    if use_timescale:
        op.execute(
            "SELECT create_hypertable('bars', 'dt', if_not_exists => TRUE, migrate_data => TRUE)"
        )


def downgrade() -> None:
    op.drop_index("idx_bars_instrument_timeframe_dt", table_name="bars")
    op.drop_table("bars")
    op.drop_table("instruments")
