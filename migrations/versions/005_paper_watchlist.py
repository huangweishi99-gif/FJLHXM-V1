"""paper_watchlist

Revision ID: 005
Revises: 004
Create Date: 2026-06-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_watchlist",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("plan_id", sa.Text(), nullable=True),
        sa.Column("market", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("strategies_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("params_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_paper_watchlist_request_id"),
    )
    op.create_index("idx_paper_watchlist_user_status", "paper_watchlist", ["user_id", "status"])
    op.create_index("idx_paper_watchlist_symbol", "paper_watchlist", ["market", "symbol"])


def downgrade() -> None:
    op.drop_index("idx_paper_watchlist_symbol", table_name="paper_watchlist")
    op.drop_index("idx_paper_watchlist_user_status", table_name="paper_watchlist")
    op.drop_table("paper_watchlist")
