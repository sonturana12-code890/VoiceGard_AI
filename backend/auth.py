"""
VOICEGUARD AI — Authentication & Security Utilities
JWT token management, password hashing (bcrypt), and current user dependency.
"""

from __future__ import annotations

import os
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

try:
    from backend.database import get_db
    from backend.models import SecurityEvent, User
except ImportError:
    from database import get_db
    from models import SecurityEvent, User

# Secret key & JWT configuration
configured_secret_key = os.environ.get("SECRET_KEY")
if not configured_secret_key:
    environment = os.environ.get("APP_ENV", os.environ.get("ENVIRONMENT", "development"))
    if environment.lower() in {"prod", "production"}:
        raise RuntimeError("SECRET_KEY must be configured in production.")
    configured_secret_key = "voiceguard-ai-dev-secret-key-32bytes-stable-jwt-token"

SECRET_KEY = configured_secret_key
ALGORITHM = os.environ.get("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))

security_bearer = HTTPBearer(auto_error=False)


# ============================================================================
# PASSWORD HASHING (BCRYPT)
# ============================================================================

def hash_password(password: str) -> str:
    """Hashes a password without bcrypt's 72-byte input limit."""
    salt = bcrypt.gensalt(rounds=12)
    password_digest = hashlib.sha256(password.encode("utf-8")).digest()
    hashed = bcrypt.hashpw(password_digest, salt)
    return f"bcrypt-sha256${hashed.decode('utf-8')}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a stored bcrypt hash."""
    try:
        if hashed_password.startswith("bcrypt-sha256$"):
            password_bytes = hashlib.sha256(plain_password.encode("utf-8")).digest()
            stored_hash = hashed_password.removeprefix("bcrypt-sha256$")
        else:
            # Preserve hashes created by older releases that passed raw bytes to bcrypt.
            password_bytes = plain_password.encode("utf-8")[:72]
            stored_hash = hashed_password
        return bcrypt.checkpw(
            password_bytes, stored_hash.encode("utf-8")
        )
    except Exception:
        return False


# ============================================================================
# JWT TOKEN HANDLING
# ============================================================================

def create_access_token(
    data: dict, expires_delta: Optional[timedelta] = None
) -> str:
    """Generates an encoded JSON Web Token (JWT) with expiration."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decodes and validates a JWT token; returns payload or None."""
    if not token or not isinstance(token, str):
        return None
    try:
        clean_token = token.strip()
        if clean_token.lower().startswith("bearer "):
            clean_token = clean_token[7:].strip()
        payload = jwt.decode(clean_token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except (jwt.PyJWTError, ValueError):
        return None


# ============================================================================
# FASTAPI DEPENDENCY: GET CURRENT USER
# ============================================================================

async def get_current_user(
    request: Request,
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    Extracts and authenticates the user from:
    1. HTTP Authorization Bearer token header (FastAPI security scheme)
    2. Direct Authorization header fallback
    3. 'vg_session', 'access_token', or 'vg_token' cookies (browser support)
    """
    token: Optional[str] = None

    # 1. Check Bearer credentials from scheme
    if bearer and bearer.credentials:
        token = bearer.credentials.strip()

    # 2. Check Raw Authorization header fallback
    if not token:
        raw_auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if raw_auth:
            parts = raw_auth.strip().split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1].strip()
            elif len(parts) == 1:
                token = parts[0].strip()

    # 3. Check Cookie fallback
    if not token:
        token = (
            request.cookies.get("vg_session")
            or request.cookies.get("access_token")
            or request.cookies.get("vg_token")
        )

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in to access this resource.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Strip any redundant 'Bearer ' prefix
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired or token is invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    return user


def log_security_event(
    db: Session,
    user_id: Optional[str],
    event_type: str,
    description: str,
    request: Optional[Request] = None,
) -> SecurityEvent:
    """Helper to log audit and security events in the database."""
    ip_address = None
    if request:
        ip_address = request.client.host if request.client else None

    event = SecurityEvent(
        user_id=user_id,
        event_type=event_type,
        event_description=description,
        ip_address=ip_address,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

