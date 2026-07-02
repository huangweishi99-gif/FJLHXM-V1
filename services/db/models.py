from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (UniqueConstraint("market", "symbol", name="uq_instruments_market_symbol"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    market: Mapped[str] = mapped_column(Text, nullable=False)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    exchange: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str | None] = mapped_column(Text)
    multiplier: Mapped[float | None] = mapped_column(Numeric)
    tick_size: Mapped[float | None] = mapped_column(Numeric)
    margin_rate: Mapped[float | None] = mapped_column(Numeric)
    is_whitelisted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    metadata_json: Mapped[str | None] = mapped_column("metadata", Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")


class Bar(Base):
    __tablename__ = "bars"

    instrument_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timeframe: Mapped[str] = mapped_column(Text, primary_key=True)
    dt: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[float] = mapped_column(Numeric, nullable=False)
    high: Mapped[float] = mapped_column(Numeric, nullable=False)
    low: Mapped[float] = mapped_column(Numeric, nullable=False)
    close: Mapped[float] = mapped_column(Numeric, nullable=False)
    volume: Mapped[float | None] = mapped_column(Numeric)
    source: Mapped[str | None] = mapped_column(Text)


class TradeContextSnapshot(Base):
    __tablename__ = "trade_context_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trade_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    setup_key: Mapped[str | None] = mapped_column(Text)
    strategy_id: Mapped[str] = mapped_column(Text, nullable=False)
    market: Mapped[str] = mapped_column(Text, nullable=False)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    timeframe: Mapped[str] = mapped_column(Text, nullable=False)
    entry_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    side: Mapped[int | None] = mapped_column(BigInteger)
    entry_price: Mapped[float | None] = mapped_column(Numeric)
    initial_stop: Mapped[float | None] = mapped_column(Numeric)
    exit_reason: Mapped[str | None] = mapped_column(Text)
    net_pnl: Mapped[float | None] = mapped_column(Numeric)
    r_multiple: Mapped[float | None] = mapped_column(Numeric)
    holding_bars: Mapped[int | None] = mapped_column(BigInteger)
    engine_version: Mapped[str | None] = mapped_column(Text)
    context_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")


class ContextBucketStat(Base):
    __tablename__ = "context_bucket_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    strategy_id: Mapped[str] = mapped_column(Text, nullable=False)
    market: Mapped[str] = mapped_column(Text, nullable=False)
    bucket_key: Mapped[str] = mapped_column(Text, nullable=False)
    count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    wins: Mapped[int] = mapped_column(BigInteger, nullable=False)
    win_rate: Mapped[float | None] = mapped_column(Numeric)
    win_rate_smoothed: Mapped[float | None] = mapped_column(Numeric)
    avg_r: Mapped[float | None] = mapped_column(Numeric)
    avg_r_smoothed: Mapped[float | None] = mapped_column(Numeric)
    sample_confidence: Mapped[float | None] = mapped_column(Numeric)
    signal_score: Mapped[float | None] = mapped_column(Numeric)
    signal_tier: Mapped[str | None] = mapped_column(Text)
    engine_version: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")


class BacktestJob(Base):
    __tablename__ = "backtest_jobs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str | None] = mapped_column(Text)
    market: Mapped[str] = mapped_column(Text, nullable=False)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    strategy_id: Mapped[str] = mapped_column(Text, nullable=False)
    years: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    cache_key: Mapped[str] = mapped_column(Text, nullable=False)
    params_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CustomInstrumentRequest(Base):
    __tablename__ = "custom_instrument_requests"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str | None] = mapped_column(Text)
    plan_id: Mapped[str | None] = mapped_column(Text)
    market: Mapped[str] = mapped_column(Text, nullable=False)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    strategies_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    years: Mapped[int] = mapped_column(BigInteger, nullable=False)
    enable_paper: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    backtest_job_id: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    request_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaperWatchlist(Base):
    __tablename__ = "paper_watchlist"
    __table_args__ = (UniqueConstraint("request_id", name="uq_paper_watchlist_request_id"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    request_id: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    plan_id: Mapped[str | None] = mapped_column(Text)
    market: Mapped[str] = mapped_column(Text, nullable=False)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    strategies_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    params_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")


class AuthUser(Base):
    __tablename__ = "auth_users"
    __table_args__ = (UniqueConstraint("account", name="uq_auth_users_account"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    account: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    plan_id: Mapped[str] = mapped_column(Text, nullable=False, server_default="free")
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")


class SubscriptionOrder(Base):
    __tablename__ = "subscription_orders"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    plan_id: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    external_ref: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaperAccount(Base):
    __tablename__ = "paper_accounts"
    __table_args__ = (UniqueConstraint("user_id", name="uq_paper_accounts_user_id"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    market_group: Mapped[str] = mapped_column(Text, nullable=False, server_default="scoped_shared_v1_1")
    initial_cash: Mapped[float] = mapped_column(Numeric, nullable=False)
    cash: Mapped[float] = mapped_column(Numeric, nullable=False)
    equity: Mapped[float] = mapped_column(Numeric, nullable=False)
    storage_mode: Mapped[str] = mapped_column(Text, nullable=False, server_default="pg")
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")


class PaperAccountLedger(Base):
    __tablename__ = "paper_account_ledger"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    account_id: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    symbol: Mapped[str | None] = mapped_column(Text)
    market: Mapped[str | None] = mapped_column(Text)
    strategy_id: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[float | None] = mapped_column(Numeric)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")


class PaperUserOpenPosition(Base):
    __tablename__ = "paper_user_open_positions"
    __table_args__ = (UniqueConstraint("user_id", "position_key", name="uq_paper_user_open_positions_key"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    market: Mapped[str] = mapped_column(Text, nullable=False, server_default="CRYPTO")
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    position_key: Mapped[str] = mapped_column(Text, nullable=False)
    strategy_id: Mapped[str | None] = mapped_column(Text)
    side: Mapped[str | None] = mapped_column(Text)
    entry_price: Mapped[float | None] = mapped_column(Numeric)
    current_stop: Mapped[float | None] = mapped_column(Numeric)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")


class PaperUserPendingOrder(Base):
    __tablename__ = "paper_user_pending_orders"
    __table_args__ = (UniqueConstraint("user_id", "order_id", name="uq_paper_user_pending_orders_order"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    market: Mapped[str] = mapped_column(Text, nullable=False, server_default="CRYPTO")
    order_id: Mapped[str] = mapped_column(Text, nullable=False)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    strategy_id: Mapped[str | None] = mapped_column(Text)
    side: Mapped[str | None] = mapped_column(Text)
    trigger_price: Mapped[float | None] = mapped_column(Numeric)
    stop_price: Mapped[float | None] = mapped_column(Numeric)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="ACTIVE")
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
