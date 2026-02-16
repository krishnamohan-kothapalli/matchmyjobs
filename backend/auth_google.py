import os
import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/auth/google", tags=["google-auth"])

GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = "https://matchmyjobs.onrender.com/auth/google/callback"

@router.get('/login')
async def google_login():
    # Redirect to Google OAuth
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
async def google_callback(code: str):
    try:
        # Exchange code for token
        async with httpx.AsyncClient() as client:
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
            
            # Get user info
            access_token = token_data['access_token']
            user_response = await client.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {access_token}'}
            )
            user_info = user_response.json()
        
        # TODO: Store user in database here
        
        # For now, redirect back to frontend with user info
        email = user_info.get('email')
        name = user_info.get('name')
        
        # Create a simple token (in production, use JWT)
        token = f"google_{user_info.get('id')}"
        
        # Redirect to frontend with data
        return RedirectResponse(
            f"https://matchmyjobs.com/auth.html?token={token}&email={email}&name={name}"
        )
        
    except Exception as e:
        return RedirectResponse(f"https://matchmyjobs.com/auth.html?error={str(e)}")
