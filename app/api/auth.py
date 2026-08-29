"""
Authentication API Endpoints
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
POST /api/auth/forgot-password
GET  /api/auth/me
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest, LoginRequest, ForgotPasswordRequest,
    TokenResponse, UserResponse
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account."""
    user, token = AuthService.register_user(db, req)
    return {
        "user": user,
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user with email and password."""
    user, token = AuthService.authenticate_user(db, req)
    return {
        "user": user,
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    """Log out current user (client invalidates token)."""
    return {"message": "Successfully logged out."}


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest):
    """Initiate password reset (demo)."""
    return {"message": f"If an account exists for {req.email}, a password reset link has been sent."}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Get the currently authenticated user profile."""
    return current_user
