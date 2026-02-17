from dotenv import load_dotenv
load_dotenv()  # must be first — loads .env before engine imports read ANTHROPIC_API_KEY

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import logging
import os
from models import AnalysisRequest
from engine import nlp, run_analysis
from auth_google import router as google_auth_router
from usage_api import router as usage_router
from database import check_db_connection, get_db, get_user_by_email, check_analysis_limit, increment_analysis_count

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MatchMetric API", version="3.0")
app.include_router(google_auth_router)
app.include_router(usage_router)

# Check database connection on startup
@app.on_event("startup")
async def startup_event():
    if check_db_connection():
        logger.info("✅ Database connected successfully")
    else:
        logger.warning("⚠️  Database connection failed - check DATABASE_URL")

# CORS configuration
ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ENHANCED: Configuration constants
MAX_TEXT_LENGTH = 50000  # Match frontend limit
MIN_RESUME_LENGTH = 100
MIN_JD_LENGTH = 50


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.options("/{rest_of_path:path}")
async def preflight_handler(rest_of_path: str):
    return {}

@app.options("/score")
async def options_score():
    return {"ok": True}

@app.get("/")
async def health():
    return {"status": "online", "version": "3.0"}


@app.post("/score")
async def get_score(request: AnalysisRequest, db: Session = Depends(get_db)):
    
    # ── Input validation ────────────────────────────────────────────────────
    if not request.resume_text.strip():
        raise HTTPException(status_code=400, detail="Resume text cannot be empty.")
    if not request.jd_text.strip():
        raise HTTPException(status_code=400, detail="Job description cannot be empty.")
    
    if len(request.resume_text) < MIN_RESUME_LENGTH:
        raise HTTPException(status_code=400, detail=f"Resume must be at least {MIN_RESUME_LENGTH} characters.")
    if len(request.jd_text) < MIN_JD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Job description must be at least {MIN_JD_LENGTH} characters.")
    if len(request.resume_text) > MAX_TEXT_LENGTH:
        raise HTTPException(status_code=400, detail=f"Resume exceeds maximum length of {MAX_TEXT_LENGTH} characters.")
    if len(request.jd_text) > MAX_TEXT_LENGTH:
        raise HTTPException(status_code=400, detail=f"Job description exceeds maximum length of {MAX_TEXT_LENGTH} characters.")

    resume_words = len([w for w in request.resume_text.split() if w.strip()])
    jd_words = len([w for w in request.jd_text.split() if w.strip()])
    if resume_words < 20:
        raise HTTPException(status_code=400, detail="Resume must contain at least 20 words.")
    if jd_words < 10:
        raise HTTPException(status_code=400, detail="Job description must contain at least 10 words.")

    # ── Database: Check usage limit ─────────────────────────────────────────
    if request.email:
        user = get_user_by_email(db, request.email)
        if user:
            can_analyze, current_count, limit = check_analysis_limit(db, user.id)
            if not can_analyze:
                raise HTTPException(
                    status_code=403,
                    detail=f"Analysis limit reached ({current_count}/{limit} this month). Upgrade your plan to continue."
                )
            logger.info(f"Usage check passed for {request.email}: {current_count}/{limit}")
        else:
            logger.warning(f"Email {request.email} not found in database, allowing analysis")
    
    # ── Run analysis ────────────────────────────────────────────────────────
    try:
        results = run_analysis(request.resume_text, request.jd_text, nlp)
        logger.info(
            "Analysis completed — score: %s, user: %s",
            results["score"],
            request.email or "anonymous"
        )
        
        # ── Database: Increment usage count ─────────────────────────────────
        if request.email:
            user = get_user_by_email(db, request.email)
            if user:
                new_count = increment_analysis_count(db, user.id)
                logger.info(f"✅ Usage incremented for {request.email}: {new_count} this month")
                
                # Add usage info to response
                _, _, limit = check_analysis_limit(db, user.id)
                results["usage"] = {
                    "analyses_used": new_count,
                    "analyses_limit": limit,
                    "remaining": max(0, limit - new_count)
                }
        
        return results
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Analysis failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal analysis engine error. Please try again.")
