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
    """Create SQLAlchemy engine configured for Neon PostgreSQL."""
    if not settings.is_db_configured:
        raise RuntimeError(
            "DATABASE_URL is not configured. "
            "Set it in backend/.env before starting the server."
        )

    # Neon requires SSL. The connection string already includes sslmode=require.
    # connect_args forces SSL for psycopg2.
    engine = create_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,         # Verify connection health before use
        pool_recycle=300,           # Recycle connections every 5 minutes
        connect_args={
            "sslmode": "require",
            "connect_timeout": 30,
        },
        echo=settings.debug,        # Log SQL in dev mode
    )
    return engine


engine = get_engine()
