"""
BIS SmartAI — Database Engine
SQLAlchemy engine and Base model configured for Neon PostgreSQL.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def get_engine():
    """Create SQLAlchemy engine configured for PostgreSQL."""
    if not settings.is_db_configured:
        raise RuntimeError(
            "DATABASE_URL is not configured. "
            "Set it in backend/.env before starting the server."
        )

    db_url = settings.database_url
    # Support postgres:// prefix used by some platforms (e.g. Render / Supabase)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    connect_args = {
        "connect_timeout": 15,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    }
    # Neon/Cloud DBs require SSL; add sslmode if not already in URL query parameters
    if "sslmode=" not in db_url:
        connect_args["sslmode"] = "require"

    engine = create_engine(
        db_url,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_pre_ping=True,         # Verify connection health before use
        pool_recycle=1800,          # Keep connections alive and reuse for 30 minutes
        connect_args=connect_args,
        echo=False,                 # Avoid verbose SQL I/O in production/dev
    )
    return engine


engine = get_engine()
