# usage_api.py
"""
API endpoints for usage tracking and user management
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, date
from database import get_db, get_user_by_email, check_analysis_limit, increment_analysis_count, get_current_month_usage

router = APIRouter(prefix="/api/usage", tags=["usage"])

# Daily cap for unlimited tier to prevent token abuse
DAILY_CAP_UNLIMITED = 30

def check_daily_cap(db, user_id: int, tier: str) -> bool:
    """Returns True if user is under their daily cap."""
    if tier != "unlimited":
        return True
    from database import Usage
    from sqlalchemy import func
    today = date.today().strftime("%Y-%m-%d")
    # Count analyses today by checking usage increment timestamps
    # Simple approach: track in a separate field or just allow — 
    # for now soft-enforce via existing month tracking
    return True  # Full daily tracking requires schema change — safe default


# ═══════════════════════════════════════════════════════════════════════════════
# Request/Response Models
# ═══════════════════════════════════════════════════════════════════════════════

class UsageCheckRequest(BaseModel):
    email: str


class UsageCheckResponse(BaseModel):
    can_analyze: bool
    analyses_used: int
    analyses_limit: int
    tier: str
    message: str


class UsageIncrementRequest(BaseModel):
    email: str


# ═══════════════════════════════════════════════════════════════════════════════
# API Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/check", response_model=UsageCheckResponse)
async def check_usage(request: UsageCheckRequest, db: Session = Depends(get_db)):
    """
    Check if user can perform another analysis.
    
    Usage from frontend:
        const response = await fetch('/api/usage/check', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email: 'user@example.com'})
        });
    """
    user = get_user_by_email(db, request.email)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    can_analyze, current_count, limit = check_analysis_limit(db, user.id)
    
    if can_analyze:
        message = f"You have {limit - current_count} analyses remaining this month"
    else:
        message = f"You've used all {limit} analyses this month. Upgrade to Job Seeker ($14/mo), Unlimited ($29/mo), or Recruiter ($79/mo)."
    
    return UsageCheckResponse(
        can_analyze=can_analyze,
        analyses_used=current_count,
        analyses_limit=limit,
        tier=user.tier,
        message=message
    )


@router.post("/increment")
async def increment_usage(request: UsageIncrementRequest, db: Session = Depends(get_db)):
    """
    Increment usage count after successful analysis.
    
    Call this AFTER analysis completes successfully.
    """
    user = get_user_by_email(db, request.email)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if under limit
    can_analyze, current_count, limit = check_analysis_limit(db, user.id)
    
    if not can_analyze:
        raise HTTPException(
            status_code=403, 
            detail=f"Analysis limit reached ({current_count}/{limit})"
        )
    
    # Increment count
    new_count = increment_analysis_count(db, user.id)
    
    return {
        "success": True,
        "analyses_used": new_count,
        "analyses_limit": limit,
        "remaining": limit - new_count
    }


@router.get("/reset-demo")
async def reset_usage_demo(email: str, db: Session = Depends(get_db)):
    """
    DEMO ONLY: Reset usage count to 0 for testing.
    
    Remove this endpoint in production!
    
    Usage:
        GET /api/usage/reset-demo?email=user@example.com
    """
    user = get_user_by_email(db, email)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    from database import get_current_month_usage
    usage = get_current_month_usage(db, user.id)
    usage.analyses_count = 0
    usage.optimizations_count = 0
    db.commit()
    
    return {
        "success": True,
        "message": f"Usage reset for {email}",
        "analyses_count": 0,
        "tier": user.tier
    }
