# engine/scorer.py
# ═══════════════════════════════════════════════════════════════════════════════
# ATS-Aligned Scoring Orchestrator
#
# MAJOR REDESIGN v4.0:
# - Removed arbitrary custom weights
# - Implemented industry-standard ATS algorithms from real systems:
#   * Workday (keyword + experience gates)
#   * Greenhouse (placement weighting + ranking)
#   * Taleo (simple keyword matching)
#   * iCIMS (formatting requirements)
#
# Flow:
#   1. AI extracts skills and metadata (Claude)
#   2. Industry-standard ATS scoring (ats_scorer.py)
#   3. ATS-aligned suggestions (ats_suggestions.py)
# ═══════════════════════════════════════════════════════════════════════════════

from .skills      import extract_soft_skills
from .ai_parser   import extract_all
from .ats_scorer  import calculate_ats_score
from .ats_suggestions import generate_ats_suggestions, generate_fallback_suggestions
import logging

logger = logging.getLogger(__name__)


def run_analysis(resume_text: str, jd_text: str, nlp) -> dict:
    """
    Full ATS-aligned analysis using industry-standard scoring.
    
    SIMPLIFIED FLOW:
    1. AI extraction (Claude) - get skills, metadata
    2. ATS scoring - apply real algorithms from Workday/Greenhouse/etc
    3. Generate ATS-specific suggestions
    
    Returns structured result with ATS compatibility breakdown.
    """
    
    try:
        # ═══════════════════════════════════════════════════════════════════════
        # STEP 1: AI Extraction (Claude)
        # ═══════════════════════════════════════════════════════════════════════
        
        logger.info("Starting AI extraction...")
        extraction = extract_all(jd_text, resume_text)
        
        # Validate extraction succeeded
        if not extraction.get("matched_skills") and not extraction.get("missing_skills"):
            logger.warning("AI extraction returned no data, returning fallback")
            return _generate_fallback_response()
        
        # Extract soft skills separately (not covered by ATS)
        soft_skills = extract_soft_skills(resume_text)
        
        logger.info(
            "AI extraction complete: %d matched, %d missing, %d soft skills",
            len(extraction.get("matched_skills", [])),
            len(extraction.get("missing_skills", [])),
            len(soft_skills)
        )
        
        # ═══════════════════════════════════════════════════════════════════════
        # STEP 2: Industry-Standard ATS Scoring
        # ═══════════════════════════════════════════════════════════════════════
        
        logger.info("Calculating ATS score...")
        ats_results = calculate_ats_score(resume_text, extraction)
        
        final_score = ats_results["final_score"]
        tier = ats_results["tier"]
        
        logger.info(f"ATS score calculated: {final_score}/100 ({tier})")
        
        # ═══════════════════════════════════════════════════════════════════════
        # STEP 3: Generate ATS-Aligned Suggestions
        # ═══════════════════════════════════════════════════════════════════════
        
        logger.info("Generating ATS-aligned suggestions...")
        suggestions = generate_ats_suggestions(
            ats_score_breakdown=ats_results,
            extraction=extraction,
            final_score=final_score
        )
        
        # If no suggestions generated, use fallback
        if not suggestions:
            logger.warning("No suggestions generated, using fallback")
            suggestions = generate_fallback_suggestions(final_score)
        
        logger.info(f"Generated {len(suggestions)} suggestions")
        
        # ═══════════════════════════════════════════════════════════════════════
        # STEP 4: Build Legacy-Compatible Response
        # (For frontend compatibility)
        # ═══════════════════════════════════════════════════════════════════════
        
        # Convert ATS breakdown to legacy score_breakdown format
        breakdown = ats_results["breakdown"]
        legacy_breakdown = {
            "keyword_overlap": breakdown["keyword_match"]["score"],
            "keyword_placement": breakdown["keyword_placement"]["score"],
            "experience": breakdown["experience"]["score"],
            "education": breakdown["education"]["score"],
            "formatting": breakdown["formatting"]["score"],
            "penalties": 0  # No longer using penalties
        }
        
        # Build audit sections for frontend (legacy format)
        audit = _build_audit_sections(breakdown, extraction)
        
        # Return comprehensive result
        return {
            "score": final_score,
            "tier": tier,
            "outlook": ats_results["outlook"],
            
            # Skills breakdown
            "recent_hits": sorted(extraction.get("matched_skills", [])),
            "missing": sorted(extraction.get("missing_skills", [])),
            "soft_skills": sorted(soft_skills),
            
            # Scoring details
            "score_breakdown": legacy_breakdown,
            "ats_specific_scores": ats_results["ats_specific_scores"],
            
            # Detailed ATS analysis
            "ats_details": {
                "keyword_match": breakdown["keyword_match"],
                "keyword_placement": breakdown["keyword_placement"],
                "experience_match": breakdown["experience"],
                "education_gate": breakdown["education"],
                "formatting_quality": breakdown["formatting"]
            },
            
            # Suggestions
            "suggestions": suggestions,
            
            # Legacy compatibility
            "audit": audit,
            "jd_parsed": extraction,
            "seniority_match": extraction.get("seniority_level", "mid"),
        }
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        return _generate_fallback_response()


def _build_audit_sections(breakdown: dict, extraction: dict) -> dict:
    """
    Build audit sections for frontend display (legacy format).
    Converts new ATS breakdown into old audit structure.
    """
    
    keyword_match = breakdown["keyword_match"]
    placement = breakdown["keyword_placement"]
    experience = breakdown["experience"]
    education = breakdown["education"]
    formatting = breakdown["formatting"]
    
    matched = len(extraction.get("matched_skills", []))
    required = len(extraction.get("jd_required_skills", []))
    match_rate = keyword_match.get("match_rate", 0)
    
    return {
        "Keyword Intelligence": [
            {
                "status": "hit" if keyword_match["score"] >= 30 else "miss",
                "msg": keyword_match["ats_behavior"]
            },
            {
                "status": "hit" if placement["score"] >= 15 else "miss",
                "msg": placement["ats_behavior"]
            },
            {
                "status": "hit" if match_rate >= 60 else "miss",
                "msg": f"Skill Coverage: {matched}/{required} required skills matched ({round(match_rate)}%). " + 
                       ("Strong coverage for ATS parsing." if match_rate >= 60 else 
                        f"Add missing skills to reach 60%+ threshold.")
            }
        ],
        
        "Experience & Qualifications": [
            {
                "status": "hit" if experience["score"] >= 10 else "miss",
                "msg": experience["ats_behavior"]
            },
            {
                "status": "hit" if education["score"] == 10 else "miss",
                "msg": education["ats_behavior"]
            }
        ],
        
        "Document Formatting": [
            {
                "status": "hit" if formatting["score"] >= 7 else "miss",
                "msg": formatting["ats_behavior"]
            }
        ]
    }


def _generate_fallback_response() -> dict:
    """
    Generate fallback response when AI extraction completely fails.
    """
    return {
        "score": 0,
        "tier": "error",
        "outlook": "Unable to analyze resume. Please check inputs and try again.",
        "recent_hits": [],
        "missing": [],
        "soft_skills": [],
        "score_breakdown": {
            "keyword_overlap": 0,
            "keyword_placement": 0,
            "experience": 0,
            "education": 0,
            "formatting": 0,
            "penalties": 0
        },
        "ats_specific_scores": {
            "workday_score": "N/A",
            "greenhouse_rank": "N/A",
            "taleo_match": "N/A",
            "icims_score": "N/A"
        },
        "suggestions": generate_fallback_suggestions(0),
        "audit": {},
        "jd_parsed": {},
        "seniority_match": "unknown"
    }
