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

    connect_args = {"connect_timeout": 30}
    # Neon/Cloud DBs require SSL; add sslmode if not already in URL query parameters
    if "sslmode=" not in db_url:
        connect_args["sslmode"] = "require"

    engine = create_engine(
        db_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,         # Verify connection health before use
        pool_recycle=300,           # Recycle connections every 5 minutes
        connect_args=connect_args,
        echo=settings.debug,        # Log SQL in dev mode
    )
    return engine


engine = get_engine()
