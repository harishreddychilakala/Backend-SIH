"""
BIS SmartAI — Auth Service
Handles user registration, authentication, and profile updates.
"""
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest
from app.schemas.user import UserUpdate
from app.core.security import hash_password, verify_password, create_access_token


class AuthService:
    @staticmethod
    def register_user(db: Session, req: RegisterRequest) -> Tuple[User, str]:
        """Register a new user, return user model and JWT token."""
        # Check if email already exists
        existing = db.query(User).filter(User.email == req.email.lower().strip()).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
            )

        user = User(
            name=req.name.strip(),
            email=req.email.lower().strip(),
            password_hash=hash_password(req.password),
            organization=req.organization.strip() if req.organization else None,
            industry=req.industry if req.industry != "Select industry" else None,
            role=req.role if req.role != "Select role" else None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_access_token(subject=user.id)
        return user, token

    @staticmethod
    def authenticate_user(db: Session, req: LoginRequest) -> Tuple[User, str]:
        """Authenticate user credentials, return user and JWT token."""
        email_clean = req.email.lower().strip()
        user = db.query(User).filter(User.email == email_clean).first()

        if not user or not verify_password(req.password, user.password_hash):
            # Never reveal whether only email or password was wrong
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = create_access_token(subject=user.id)
        return user, token

    @staticmethod
    def update_user_profile(db: Session, user: User, req: UserUpdate) -> User:
        """Update profile fields for the authenticated user."""
        if req.name is not None:
            user.name = req.name.strip()
        if req.organization is not None:
            user.organization = req.organization.strip()
        if req.industry is not None:
            user.industry = req.industry
        if req.role is not None:
            user.role = req.role

        db.commit()
        db.refresh(user)
        return user
