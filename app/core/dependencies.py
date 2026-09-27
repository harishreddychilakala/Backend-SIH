import time
from typing import Dict, Tuple
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import decode_access_token
from app.models.user import User

# Bearer token extractor
bearer_scheme = HTTPBearer(auto_error=True)

# In-memory user cache to accelerate concurrent API requests after login: {user_id: (user_obj, timestamp)}
_USER_CACHE: Dict[str, Tuple[User, float]] = {}
_USER_CACHE_TTL_SECONDS = 60.0


def cache_authenticated_user(user: User):
    """Pre-warm or update user in-memory cache."""
    if user and user.id:
        _USER_CACHE[str(user.id)] = (user, time.time())


def invalidate_user_cache(user_id: str):
    """Remove user from cache on profile modification or logout."""
    _USER_CACHE.pop(str(user_id), None)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency that extracts the authenticated user from the JWT Bearer token.
    Uses in-memory cache to eliminate repetitive DB queries for concurrent requests.
    
    Usage:
        @router.get("/protected")
        def protected(current_user: User = Depends(get_current_user)):
            ...
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

    # Check cache first
    now = time.time()
    cached = _USER_CACHE.get(str(user_id))
    if cached:
        cached_user, ts = cached
        if now - ts < _USER_CACHE_TTL_SECONDS:
            try:
                # Merge into current session without issuing a SELECT query
                return db.merge(cached_user, load=False)
            except Exception:
                # Fallback to standard DB query if merge fails
                pass

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    cache_authenticated_user(user)
    return user
