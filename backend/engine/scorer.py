# engine/scorer.py
# ═══════════════════════════════════════════════════════════════════════════════
# ATS-Aligned Scoring Orchestrator v5.0
#
# v5.0 Changes:
# - Score components now sum directly to 100 (no normalization hacks)
# - legacy_breakdown values reflect actual component scores
# - generate_suggestions() from ai_parser is now properly wired in
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

    Flow:
      1. AI extraction (Claude) — skills, metadata
      2. ATS scoring — Workday/Greenhouse/Taleo/iCIMS algorithms
      3. ATS-specific suggestions
    """
    try:
        # ── Step 1: AI Extraction ───────────────────────────────────────────
        logger.info("Starting AI extraction...")
        extraction = extract_all(jd_text, resume_text)

        if not extraction.get("matched_skills") and not extraction.get("missing_skills"):
            logger.warning("AI extraction returned no data, using fallback")
            return _generate_fallback_response()

        soft_skills = extract_soft_skills(resume_text)

        logger.info(
            "AI extraction complete: %d matched, %d missing, %d soft skills",
            len(extraction.get("matched_skills", [])),
            len(extraction.get("missing_skills", [])),
            len(soft_skills)
        )

        # ── Step 2: ATS Scoring ─────────────────────────────────────────────
        logger.info("Calculating ATS score...")
        ats_results = calculate_ats_score(resume_text, extraction)

        final_score = ats_results["final_score"]
        tier = ats_results["tier"]

        logger.info(f"ATS score: {final_score}/100 ({tier})")

        # ── Step 3: Suggestions ─────────────────────────────────────────────
        logger.info("Generating suggestions...")
        suggestions = generate_ats_suggestions(
            ats_score_breakdown=ats_results,
            extraction=extraction,
            final_score=final_score
        )

        if not suggestions:
            logger.warning("No suggestions generated, using fallback")
            suggestions = generate_fallback_suggestions(final_score)

        logger.info(f"Generated {len(suggestions)} suggestions")

        # ── Step 4: Build response ──────────────────────────────────────────
        breakdown = ats_results["breakdown"]

        # v5.0: scores are already in their final form — no normalization needed
        legacy_breakdown = {
            "keyword_overlap":   breakdown["keyword_match"]["score"],       # /30
            "keyword_placement": breakdown["keyword_placement"]["score"],   # /20
            "experience":        breakdown["experience"]["score"],          # /15
            "education":         breakdown["education"]["score"],           # /10
            "formatting":        breakdown["formatting"]["score"],          # /10
            "contact":           breakdown["contact_info"]["score"],        # /5
            "structure":         breakdown["document_structure"]["score"],  # /5
            "impact":            breakdown["quantified_impact"]["score"],   # /5
            "seniority":         breakdown["seniority_match"]["score"],     # /5
            "penalties":         0
        }

        audit = _build_audit_sections(breakdown, extraction)

        return {
            "score": final_score,
            "tier": tier,
            "outlook": ats_results["outlook"],

            "recent_hits": sorted(extraction.get("matched_skills", [])),
            "missing":     sorted(extraction.get("missing_skills", [])),
            "soft_skills": sorted(soft_skills),

            "score_breakdown": legacy_breakdown,
            "ats_specific_scores": ats_results["ats_specific_scores"],

            "ats_details": {
                "keyword_match":     breakdown["keyword_match"],
                "keyword_placement": breakdown["keyword_placement"],
                "experience_match":  breakdown["experience"],
                "education_gate":    breakdown["education"],
                "formatting_quality": breakdown["formatting"]
            },

            "suggestions": suggestions,
            "audit": audit,
            "jd_parsed": extraction,
            "seniority_match": extraction.get("seniority_level", "mid"),
        }

    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        return _generate_fallback_response()


def _build_audit_sections(breakdown: dict, extraction: dict) -> dict:
    """Build audit sections for frontend (legacy format)."""
    keyword_match = breakdown["keyword_match"]
    placement     = breakdown["keyword_placement"]
    experience    = breakdown["experience"]
    education     = breakdown["education"]
    formatting    = breakdown["formatting"]
    contact       = breakdown["contact_info"]
    structure     = breakdown["document_structure"]
    impact        = breakdown["quantified_impact"]
    seniority     = breakdown["seniority_match"]

    matched   = len(extraction.get("matched_skills", []))
    missing   = len(extraction.get("missing_skills", []))
    total_req = matched + missing
    match_rate = keyword_match.get("match_rate", 0)

    return {
        "Contact & Searchability": [
            {
                "status": "hit" if contact["has_email"] else "miss",
                "msg": "✓ Email detected. ATS can contact you." if contact["has_email"]
                       else "✕ Email missing. All ATS require email for candidate profile creation."
            },
            {
                "status": "hit" if contact["has_phone"] else "miss",
                "msg": "✓ Phone detected. Interview scheduling possible." if contact["has_phone"]
                       else "✕ Phone missing. ATS require phone for scheduling."
            },
            {
                "status": "hit" if contact["has_location"] else "miss",
                "msg": contact["ats_behavior"]
            }
        ],

        "Document Structure": [
            {
                "status": "hit" if structure["score"] >= 4 else "miss",
                "msg": structure["ats_behavior"]
            },
            {
                "status": "hit" if structure["has_dates"] else "miss",
                "msg": "✓ Chronological dates detected. Work history timeline clear." if structure["has_dates"]
                       else "✕ Dates missing. ATS calculate experience from date ranges."
            }
        ],

        "Keyword Intelligence": [
            {
                "status": "hit" if keyword_match["score"] >= 20 else "miss",
                "msg": keyword_match["ats_behavior"]
            },
            {
                "status": "hit" if placement["score"] >= 12 else "miss",
                "msg": placement["ats_behavior"]
            },
            {
                "status": "hit" if match_rate >= 60 else "miss",
                "msg": (
                    f"✓ Skill Coverage: {matched}/{total_req} required skills matched ({round(match_rate)}%). Strong ATS coverage."
                    if match_rate >= 60 else
                    f"⚠ Skill Gap: {matched}/{total_req} required skills matched ({round(match_rate)}%). "
                    f"Add {missing} missing skill{'s' if missing != 1 else ''} to reach 60%+ threshold."
                )
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
            },
            {
                "status": "hit" if seniority["match"] else "miss",
                "msg": seniority["ats_behavior"]
            }
        ],

        "Impact & Results": [
            {
                "status": "hit" if impact["score"] >= 3 else "miss",
                "msg": impact["ats_behavior"]
            },
            {
                "status": "hit" if impact["metrics_count"] >= 5 else "miss",
                "msg": (
                    f"✓ Strong metrics: {impact['metrics_count']} quantified achievements detected."
                    if impact["metrics_count"] >= 5 else
                    f"💡 {impact['metrics_count']} metric{'s' if impact['metrics_count'] != 1 else ''} found. "
                    f"Add {max(0, 5 - impact['metrics_count'])} more: '% improvement', 'team size', '$ saved', 'users impacted'."
                )
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
    return {
        "score": 0, "tier": "error",
        "outlook": "Unable to analyze resume. Please check inputs and try again.",
        "recent_hits": [], "missing": [], "soft_skills": [],
        "score_breakdown": {
            "keyword_overlap": 0, "keyword_placement": 0, "experience": 0,
            "education": 0, "formatting": 0, "contact": 0, "structure": 0,
            "impact": 0, "seniority": 0, "penalties": 0
        },
        "ats_specific_scores": {
            "workday_score": "N/A", "greenhouse_rank": "N/A",
            "taleo_match": "N/A", "icims_score": "N/A"
        },
        "suggestions": generate_fallback_suggestions(0),
        "audit": {}, "jd_parsed": {}, "seniority_match": "unknown"
    }
