"""paper_accounts + paper_account_ledger

Revision ID: 008
Revises: 007
Create Date: 2026-06-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_accounts",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("market_group", sa.Text(), nullable=False, server_default="scoped_shared_v1_1"),
        sa.Column("initial_cash", sa.Numeric(), nullable=False),
        sa.Column("cash", sa.Numeric(), nullable=False),
        sa.Column("equity", sa.Numeric(), nullable=False),
        sa.Column("storage_mode", sa.Text(), nullable=False, server_default="pg"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_paper_accounts_user_id"),
    )
    op.create_index("idx_paper_accounts_user_id", "paper_accounts", ["user_id"])

    op.create_table(
        "paper_account_ledger",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=True),
        sa.Column("market", sa.Text(), nullable=True),
        sa.Column("strategy_id", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_paper_account_ledger_user_created", "paper_account_ledger", ["user_id", "created_at"])
    op.create_index("idx_paper_account_ledger_account", "paper_account_ledger", ["account_id"])


def downgrade() -> None:
    op.drop_index("idx_paper_account_ledger_account", table_name="paper_account_ledger")
    op.drop_index("idx_paper_account_ledger_user_created", table_name="paper_account_ledger")
    op.drop_table("paper_account_ledger")
    op.drop_index("idx_paper_accounts_user_id", table_name="paper_accounts")
    op.drop_table("paper_accounts")
