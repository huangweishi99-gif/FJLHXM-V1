"""paper_user_open_positions + paper_user_pending_orders

Revision ID: 009
Revises: 008
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_user_open_positions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("market", sa.Text(), nullable=False, server_default="CRYPTO"),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("position_key", sa.Text(), nullable=False),
        sa.Column("strategy_id", sa.Text(), nullable=True),
        sa.Column("side", sa.Text(), nullable=True),
        sa.Column("entry_price", sa.Numeric(), nullable=True),
        sa.Column("current_stop", sa.Numeric(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "position_key", name="uq_paper_user_open_positions_key"),
    )
    op.create_index("idx_paper_user_open_positions_user", "paper_user_open_positions", ["user_id"])

    op.create_table(
        "paper_user_pending_orders",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("market", sa.Text(), nullable=False, server_default="CRYPTO"),
        sa.Column("order_id", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("strategy_id", sa.Text(), nullable=True),
        sa.Column("side", sa.Text(), nullable=True),
        sa.Column("trigger_price", sa.Numeric(), nullable=True),
        sa.Column("stop_price", sa.Numeric(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="ACTIVE"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "order_id", name="uq_paper_user_pending_orders_order"),
    )
    op.create_index("idx_paper_user_pending_orders_user", "paper_user_pending_orders", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_paper_user_pending_orders_user", table_name="paper_user_pending_orders")
    op.drop_table("paper_user_pending_orders")
    op.drop_index("idx_paper_user_open_positions_user", table_name="paper_user_open_positions")
    op.drop_table("paper_user_open_positions")
