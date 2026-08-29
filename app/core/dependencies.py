"""
BIS SmartAI — FastAPI Dependencies
Reusable dependency injection for authentication and database sessions.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import decode_access_token
from app.models.user import User

# Bearer token extractor
bearer_scheme = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency that extracts the authenticated user from the JWT Bearer token.
    
    Usage:
        @router.get("/protected")
        def protected(current_user: User = Depends(get_current_user)):
            ...
    
    Raises 401 if token is missing, invalid, or expired.
    Users must NEVER be able to access another user's data.
    Always filter queries using current_user.id.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    return user
