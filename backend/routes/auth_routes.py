"""
VOICEGUARD AI — Authentication Routes
Endpoints for user registration, login, logout, profile, and session management.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

logger = logging.getLogger("voiceguard.auth")

from backend.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_current_user,
    hash_password,
    log_security_event,
    verify_password,
)
from backend.database import get_db
from backend.models import User
from backend.schemas import (
    PasswordUpdate,
    ProfileUpdate,
    TokenResponse,
    UserLogin,
    UserResponse,
    UserSignup,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    user_data: UserSignup,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    """Register a new user account with validated email and password."""
    if not user_data.termsAccepted:
        logger.warning(f"Registration rejected for '{user_data.email}': terms not accepted")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Terms and Privacy Notice acceptance is required.",
        )

    normalized_email = user_data.email.strip().lower()

    existing = db.query(User).filter(User.email == normalized_email).first()
    if existing:
        logger.warning(f"Registration rejected: duplicate email '{normalized_email}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    hashed_pw = hash_password(user_data.password)

    new_user = User(
        full_name=user_data.fullName.strip(),
        email=normalized_email,
        hashed_password=hashed_pw,
        is_active=True,
    )
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except Exception as exc:
        db.rollback()
        logger.error(f"Database error during registration for '{normalized_email}': {exc}")
        msg = str(exc)
        if "UNIQUE" in msg or "already exists" in msg.lower() or "users.email" in msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email address already exists.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create the user account due to a database error.",
        ) from exc

    # Issue JWT token
    token_ttl = timedelta(days=30) if user_data.remember else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token({"sub": new_user.id, "email": new_user.email}, expires_delta=token_ttl)

    # Set HttpOnly cookie for browser compatibility
    response.set_cookie(
        key="vg_session",
        value=token,
        max_age=int(token_ttl.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )

    log_security_event(db, new_user.id, "auth.signup", f"User registered: {new_user.email}", request)
    logger.info(f"User registration successful: '{new_user.email}' (ID: {new_user.id})")

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    """Authenticate with email/username and password and return a JWT access token."""
    normalized_email = (credentials.email or credentials.username or "").strip().lower()

    user = db.query(User).filter(User.email == normalized_email).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        log_security_event(
            db, None, "auth.login_failed", f"Failed login attempt for: {normalized_email}", request
        )
        logger.warning(f"Login failed: invalid credentials for '{normalized_email}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.warning(f"Login rejected: inactive account for '{normalized_email}'")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is currently inactive. Contact your security administrator.",
        )

    token_ttl = timedelta(days=30) if credentials.remember else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token({"sub": user.id, "email": user.email}, expires_delta=token_ttl)

    # Set cookie for browser
    response.set_cookie(
        key="vg_session",
        value=token,
        max_age=int(token_ttl.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )

    log_security_event(db, user.id, "auth.login", f"User logged in: {user.email}", request)
    logger.info(f"User login successful: '{user.email}' (ID: {user.id})")

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me")
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """Retrieve profile data for the authenticated user."""
    return {"user": UserResponse.model_validate(current_user)}


@router.get("/status")
async def auth_status(request: Request, db: Session = Depends(get_db)) -> Dict[str, bool]:
    """Lightweight check to determine whether the request holds a valid session."""
    token = request.cookies.get("vg_session") or request.cookies.get("access_token")
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()

    if not token:
        return {"authenticated": False}

    from backend.auth import decode_access_token
    payload = decode_access_token(token)
    if not payload:
        return {"authenticated": False}

    user = db.query(User).filter(User.id == payload.get("sub")).first()
    return {"authenticated": bool(user and user.is_active)}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Refreshes an active authentication session and issues a new JWT access token.
    Extends the session lifespan without re-prompting credentials.
    """
    token_ttl = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token({"sub": current_user.id, "email": current_user.email}, expires_delta=token_ttl)

    response.set_cookie(
        key="vg_session",
        value=token,
        max_age=int(token_ttl.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )

    log_security_event(db, current_user.id, "auth.refresh", f"Token refreshed: {current_user.email}", request)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(current_user),
    )


@router.post("/logout")
async def logout(response: Response, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Terminate the current authentication session and clear cookies."""
    response.delete_cookie(key="vg_session", path="/")
    response.delete_cookie(key="access_token", path="/")
    log_security_event(db, current_user.id, "auth.logout", f"User logged out: {current_user.email}")
    return {"ok": True, "message": "Successfully logged out."}


@router.patch("/profile", response_model=Dict[str, Any])
async def update_profile(
    body: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update profile full name."""
    current_user.full_name = body.fullName.strip()
    db.commit()
    db.refresh(current_user)
    return {"user": UserResponse.model_validate(current_user)}


@router.patch("/password")
async def update_password(
    body: PasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update user password with current password verification."""
    if not verify_password(body.currentPassword, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    if body.newPassword == body.currentPassword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from your current password.",
        )

    current_user.hashed_password = hash_password(body.newPassword)
    db.commit()
    log_security_event(db, current_user.id, "auth.password_update", "Password updated successfully.")
    return {"ok": True, "message": "Password updated successfully."}
