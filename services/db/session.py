from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

DEFAULT_DATABASE_URL = "postgresql+psycopg://fengji:fengji_dev@localhost:5432/fengji"


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def get_engine(url: str | None = None) -> Engine:
    return create_engine(
        url or get_database_url(),
        pool_pre_ping=True,
        connect_args={"connect_timeout": int(os.getenv("DATABASE_CONNECT_TIMEOUT", "3"))},
    )
