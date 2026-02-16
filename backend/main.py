from dotenv import load_dotenv
load_dotenv()  # must be first — loads .env before engine imports read ANTHROPIC_API_KEY

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging

from models import AnalysisRequest
from engine import nlp, run_analysis

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MatchMetric API", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,  # Add this
)

# ENHANCED: Configuration constants
MAX_TEXT_LENGTH = 50000  # Match frontend limit
MIN_RESUME_LENGTH = 100
MIN_JD_LENGTH = 50


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.options("/score")
async def options_score():
    return {}

@app.get("/")
async def health():
    return {"status": "online", "version": "3.0"}


@app.post("/score")
async def get_score(request: AnalysisRequest):
    # ENHANCED: Comprehensive input validation
    
    # Check for empty inputs
    if not request.resume_text.strip():
        raise HTTPException(status_code=400, detail="Resume text cannot be empty.")
    if not request.jd_text.strip():
        raise HTTPException(status_code=400, detail="Job description cannot be empty.")
    
    # Check minimum lengths
    if len(request.resume_text) < MIN_RESUME_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Resume must be at least {MIN_RESUME_LENGTH} characters. Current: {len(request.resume_text)}"
        )
    if len(request.jd_text) < MIN_JD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Job description must be at least {MIN_JD_LENGTH} characters. Current: {len(request.jd_text)}"
        )
    
    # ENHANCED: Check maximum lengths to prevent abuse
    if len(request.resume_text) > MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Resume exceeds maximum length of {MAX_TEXT_LENGTH} characters. Please shorten your resume."
        )
    if len(request.jd_text) > MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Job description exceeds maximum length of {MAX_TEXT_LENGTH} characters."
        )
    
    # ENHANCED: Check for actual content (not just whitespace)
    resume_words = len([w for w in request.resume_text.split() if w.strip()])
    jd_words = len([w for w in request.jd_text.split() if w.strip()])
    
    if resume_words < 20:
        raise HTTPException(
            status_code=400,
            detail="Resume must contain at least 20 words of actual content."
        )
    if jd_words < 10:
        raise HTTPException(
            status_code=400,
            detail="Job description must contain at least 10 words of actual content."
        )

    try:
        results = run_analysis(request.resume_text, request.jd_text, nlp)
        logger.info(
            "Analysis completed — score: %s, resume_len: %d, jd_len: %d",
            results["score"],
            len(request.resume_text),
            len(request.jd_text)
        )
        return results
    except Exception as exc:
        logger.error("Analysis failed: %s", exc, exc_info=True)  # ENHANCED: Log full traceback
        raise HTTPException(status_code=500, detail="Internal analysis engine error. Please try again.")
