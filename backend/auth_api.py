# auth_api.py
"""
Email/Password Authentication API for MatchMyJobs
"""

import os
import secrets
import hashlib
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db, get_user_by_email, get_current_month_usage, check_analysis_limit

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ─── Helpers ──────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = os.getenv("PASSWORD_SALT", "matchmyjobs_salt_2025")
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def generate_token(email: str) -> str:
    return f"mmj_{secrets.token_hex(32)}"

def get_tier_limit(tier: str) -> int:
    return {"free": 2, "analysis_pro": 50, "optimize": 50}.get(tier, 2)


# ─── Models ───────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    name: str
    email: str
    password: str

class SigninRequest(BaseModel):
    email: str
    password: str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/signup")
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    if len(request.name.strip()) < 2:
        raise HTTPException(400, "Name must be at least 2 characters.")
    if len(request.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")
    if "@" not in request.email or "." not in request.email:
        raise HTTPException(400, "Please enter a valid email address.")

    existing = get_user_by_email(db, request.email.lower())
    if existing:
        raise HTTPException(409, "An account with this email already exists. Please sign in.")

    from database import User
    user = User(
        email=request.email.lower().strip(),
        full_name=request.name.strip(),
        password_hash=hash_password(request.password),
        tier="free"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    get_current_month_usage(db, user.id)

    return {
        "token": generate_token(user.email),
        "email": user.email,
        "name": user.full_name,
        "tier": user.tier,
        "analysesUsed": 0,
        "analysesLimit": 2,
        "message": f"Welcome {user.full_name}! You have 2 free analyses this month."
    }


@router.post("/signin")
async def signin(request: SigninRequest, db: Session = Depends(get_db)):
    user = get_user_by_email(db, request.email.lower())
    if not user:
        raise HTTPException(401, "No account found with this email. Please sign up.")
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(401, "Incorrect password. Please try again.")

    can_analyze, current_count, limit = check_analysis_limit(db, user.id)

    return {
        "token": generate_token(user.email),
        "email": user.email,
        "name": user.full_name,
        "tier": user.tier,
        "analysesUsed": current_count,
        "analysesLimit": limit,
        "message": f"Welcome back, {user.full_name}!"
    }


@router.get("/me")
async def get_me(email: str, db: Session = Depends(get_db)):
    """Get user profile + full usage data for dashboard."""
    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(404, "User not found.")

    can_analyze, current_count, limit = check_analysis_limit(db, user.id)

    from database import Usage
    all_usage = db.query(Usage).filter(
        Usage.user_id == user.id
    ).order_by(Usage.month_year.desc()).all()

    return {
        "email": user.email,
        "name": user.full_name,
        "tier": user.tier,
        "member_since": user.created_at.strftime("%B %Y"),
        "current_month": {
            "analyses_used": current_count,
            "analyses_limit": limit,
            "remaining": max(0, limit - current_count),
            "can_analyze": can_analyze,
            "month": datetime.now().strftime("%B %Y")
        },
        "usage_history": [
            {
                "month": u.month_year,
                "analyses": u.analyses_count,
                "optimizations": u.optimizations_count
            }
            for u in all_usage
        ],
        "stats": {
            "total_analyses": sum(u.analyses_count for u in all_usage),
            "months_active": len(all_usage),
        }
    }
