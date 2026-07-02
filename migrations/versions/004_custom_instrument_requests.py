"""custom_instrument_requests

Revision ID: 004
Revises: 003
Create Date: 2026-06-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "custom_instrument_requests",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("plan_id", sa.Text(), nullable=True),
        sa.Column("market", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("strategies_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("years", sa.BigInteger(), nullable=False),
        sa.Column("enable_paper", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("backtest_job_id", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("request_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("years BETWEEN 1 AND 5", name="ck_custom_instrument_requests_years"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_custom_requests_user_created", "custom_instrument_requests", ["user_id", "created_at"])
    op.create_index("idx_custom_requests_status_created", "custom_instrument_requests", ["status", "created_at"])
    op.create_index("idx_custom_requests_symbol", "custom_instrument_requests", ["market", "symbol"])
    op.create_index("idx_custom_requests_backtest_job", "custom_instrument_requests", ["backtest_job_id"])


def downgrade() -> None:
    op.drop_index("idx_custom_requests_backtest_job", table_name="custom_instrument_requests")
    op.drop_index("idx_custom_requests_symbol", table_name="custom_instrument_requests")
    op.drop_index("idx_custom_requests_status_created", table_name="custom_instrument_requests")
    op.drop_index("idx_custom_requests_user_created", table_name="custom_instrument_requests")
    op.drop_table("custom_instrument_requests")
