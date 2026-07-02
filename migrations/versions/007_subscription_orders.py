"""subscription_orders

Revision ID: 007
Revises: 006
Create Date: 2026-06-08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscription_orders",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("plan_id", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("external_ref", sa.Text(), nullable=True),
        sa.Column("metadata_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_subscription_orders_user_id", "subscription_orders", ["user_id"])
    op.create_index("idx_subscription_orders_created_at", "subscription_orders", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_subscription_orders_created_at", table_name="subscription_orders")
    op.drop_index("idx_subscription_orders_user_id", table_name="subscription_orders")
    op.drop_table("subscription_orders")
