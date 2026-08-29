"""
Users API Endpoints
GET   /api/users/me
PATCH /api/users/me
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserUpdate, UserProfileResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserProfileResponse)
def get_user_profile(current_user: User = Depends(get_current_user)):
    """Get current user's profile details."""
    return current_user


@router.patch("/me", response_model=UserProfileResponse)
def update_user_profile(
    req: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update profile information for the authenticated user."""
    updated = AuthService.update_user_profile(db, current_user, req)
    return updated
