"""
BIS SmartAI — Database Session
SQLAlchemy session factory and FastAPI get_db() dependency.
"""
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.db.database import engine

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session per request.
    Automatically closes the session on request completion.
    
    Usage:
        def endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
