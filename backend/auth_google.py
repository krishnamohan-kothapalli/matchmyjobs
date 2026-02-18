import os
import httpx
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from database import get_db, get_user_by_email, create_user, get_current_month_usage

router = APIRouter(prefix="/auth/google", tags=["google-auth"])

GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = "https://matchmyjobs.onrender.com/auth/google/callback"

TIER_LIMITS = {
    "free":       5,
    "job_seeker": 120,
    "unlimited":  500,
    "recruiter":  1000,
}

@router.get('/login')
async def google_login():
    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"redirect_uri={GOOGLE_REDIRECT_URI}&"
        f"response_type=code&"
        f"scope=openid email profile&"
        f"access_type=offline"
    )
    return RedirectResponse(google_auth_url)

@router.get('/callback')
async def google_callback(code: str, db: Session = Depends(get_db)):
    try:
        async with httpx.AsyncClient() as client:
            # Exchange code for token
            token_response = await client.post(
                'https://oauth2.googleapis.com/token',
                data={
                    'code': code,
                    'client_id': GOOGLE_CLIENT_ID,
                    'client_secret': GOOGLE_CLIENT_SECRET,
                    'redirect_uri': GOOGLE_REDIRECT_URI,
                    'grant_type': 'authorization_code'
                }
            )
            token_data = token_response.json()

            if 'error' in token_data:
                raise HTTPException(status_code=400, detail=token_data['error'])

            # Get user info from Google
            access_token = token_data['access_token']
            user_response = await client.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {access_token}'}
            )
            user_info = user_response.json()

        email = user_info.get('email', '').lower().strip()
        name  = user_info.get('name', email.split('@')[0])

        if not email:
            raise ValueError("No email returned from Google")

        # ── Find or create user in database ──────────────────────────────────
        user = get_user_by_email(db, email)

        if not user:
            # New user — create with free tier
            # Google users don't have a password, use a placeholder hash
            import hashlib, secrets
            placeholder_hash = hashlib.sha256(
                f"google_oauth_{secrets.token_hex(16)}".encode()
            ).hexdigest()
            user = create_user(
                db,
                email=email,
                full_name=name,
                password_hash=placeholder_hash,
                tier="free"
            )

        # ── Get current usage ─────────────────────────────────────────────────
        usage = get_current_month_usage(db, user.id)
        limit = TIER_LIMITS.get(user.tier, 5)

        # ── Build session token (simple, not JWT — keep consistent with email auth) ──
        token = f"google_{user_info.get('id')}_{user.id}"

        return RedirectResponse(
            f"https://matchmyjobs.com/auth.html"
            f"?token={token}"
            f"&email={email}"
            f"&name={name}"
            f"&tier={user.tier}"
            f"&analyses_used={usage.analyses_count}"
            f"&analyses_limit={limit}"
        )

    except Exception as e:
        return RedirectResponse(f"https://matchmyjobs.com/auth.html?error={str(e)}")
