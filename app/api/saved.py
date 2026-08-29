"""
Saved Standards API Endpoints
GET    /api/saved
POST   /api/saved
DELETE /api/saved/{id}
"""
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.standard import SaveStandardRequest, SavedStandardResponse
from app.services.standards_service import StandardsService

router = APIRouter(prefix="/saved", tags=["Saved Standards"])


@router.get("", response_model=List[SavedStandardResponse])
def get_saved_standards(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all saved standards for the authenticated user."""
    return StandardsService.get_saved_standards(db=db, user=current_user)


@router.post("", response_model=SavedStandardResponse, status_code=status.HTTP_201_CREATED)
def save_standard(
    req: SaveStandardRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bookmark an Indian Standard for the current user."""
    return StandardsService.save_standard(db=db, user=current_user, req=req)


@router.delete("/{standard_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_standard(
    standard_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a saved standard for the current user."""
    StandardsService.delete_saved_standard(db=db, user=current_user, standard_id=standard_id)
    return None
