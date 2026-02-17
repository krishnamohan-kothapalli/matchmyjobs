# engine/scorer.py
# ═══════════════════════════════════════════════════════════════════════════════
# Hybrid Scoring Engine — v3.0 Logic + v5.0 Output Format
#
# Restores the original v3.0 scoring approach:
#   - Uses diagnostics.py checks (contact, headings, dates, education,
#     placement, title alignment, keyword stuffing)
#   - Uses spaCy semantic similarity as a scoring component
#   - Uses density chart (keyword frequency visualisation)
#   - Applies penalties (missing title, bad education, stuffing, skill gaps)
#
# Output format matches v5.0 so the current frontend works unchanged.
# ═══════════════════════════════════════════════════════════════════════════════

from .skills      import (extract_soft_skills, keyword_frequency,
                           detect_keyword_stuffing, spacy_extract_skills)
from .seniority   import build_seniority_audit, detect_resume_level
from .diagnostics import (check_contact, check_section_headings, check_dates,
                           check_education, check_quantified_impact,
                           check_keyword_placement, check_title_alignment,
                           check_keyword_stuffing)
from .density     import calculate_density
from .ai_parser   import extract_all, generate_suggestions
from .ats_suggestions import generate_fallback_suggestions
import logging

logger = logging.getLogger(__name__)

# ── Score weights — sum to 100 ────────────────────────────────────────────────
W_KEYWORD_OVERLAP   = 30   # keyword_overlap
W_SEMANTIC          = 10   # blended into keyword_placement
W_PLACEMENT         = 10   # keyword_placement (combined with semantic = 20 max)
W_EXPERIENCE        = 10   # experience
W_EDUCATION         = 10   # education
W_STRUCTURE         = 3    # structure (section headings)
W_FORMATTING        = 2    # formatting (date consistency)
W_IMPACT            = 5    # impact
W_CONTACT           = 5    # contact
W_SENIORITY         = 5    # seniority


def _pct(part: int, total: int) -> float:
    return (part / total * 100) if total else 0


def run_analysis(resume_text: str, jd_text: str, nlp) -> dict:
    """
    Hybrid analysis: v3.0 scoring logic with v5.0 output format.

    Flow:
      1. Claude AI extraction (skills from both JD and resume)
      2. spaCy for semantic similarity + fallback extraction
      3. Deterministic structural checks via diagnostics.py
      4. Weighted scoring + penalties -> final_score
      5. AI improvement suggestions
      6. Density chart
      7. Response shaped to v5.0 keys for frontend compatibility
    """
    try:
        # ── Step 1: AI extraction ─────────────────────────────────────────────
        logger.info("Starting AI extraction...")
        extraction = extract_all(jd_text, resume_text)

        hits          = extraction.get("matched_skills", [])
        missing       = extraction.get("missing_skills", [])
        all_jd_skills = set(extraction.get("jd_required_skills", []))

        # ── Step 2: spaCy docs + fallback if AI returned nothing ─────────────
        res_doc = nlp(resume_text)
        jd_doc  = nlp(jd_text)

        if not hits and not missing:
            logger.warning("AI extraction returned no data — falling back to spaCy")
            res_skills    = spacy_extract_skills(res_doc)
            jd_skills     = spacy_extract_skills(jd_doc)
            hits          = sorted(jd_skills & res_skills)
            missing       = sorted(jd_skills - res_skills)
            all_jd_skills = jd_skills

        soft_skills = extract_soft_skills(resume_text)
        stuffed     = detect_keyword_stuffing(resume_text, hits, threshold=5)

        logger.info(
            "Extraction: %d matched, %d missing, %d soft skills",
            len(hits), len(missing), len(soft_skills)
        )

        # ── Step 3: Deterministic structural checks ───────────────────────────
        contact        = check_contact(resume_text)
        headings       = check_section_headings(resume_text)
        dates          = check_dates(resume_text)
        education      = check_education(resume_text, jd_text)
        impact         = check_quantified_impact(resume_text)
        placement      = check_keyword_placement(resume_text, set(hits))
        stuffing_check = check_keyword_stuffing(stuffed)

        # Title: prefer Claude's extraction, fall back to regex
        ai_title = extraction.get("job_title", "").strip()
        if ai_title and len(ai_title) > 3:
            title_words = [w for w in ai_title.split() if len(w) > 2]
            title_found = any(w.lower() in resume_text.lower() for w in title_words)
            title_info = {
                "clean_title": ai_title,
                "status": "hit" if title_found else "miss",
                "msg": (
                    f"Title Aligned: Your resume reflects the target role '{ai_title}'. "
                    "Greenhouse and Lever rank candidates higher when the profile title "
                    "matches the JD title exactly."
                    if title_found else
                    f"Title Gap: The role title '{ai_title}' isn't explicitly reflected "
                    "in your resume. Add it to your summary or headline — Greenhouse "
                    "and Lever use title matching as a primary relevance signal."
                )
            }
        else:
            title_info = check_title_alignment(resume_text, jd_text)

        seniority = build_seniority_audit(resume_text, jd_text)

        # ── Step 4: Component scores ──────────────────────────────────────────
        total_jd = max(len(all_jd_skills), len(hits) + len(missing), 1)

        keyword_score   = (_pct(len(hits), total_jd) / 100) * W_KEYWORD_OVERLAP
        semantic_score  = res_doc.similarity(jd_doc) * W_SEMANTIC   # 0–10

        placement_score = W_PLACEMENT if placement["status"] == "hit" else (
            W_PLACEMENT * 0.4 if placement.get("summary_hits", 0) > 0 else 0
        )
        structure_score  = W_STRUCTURE if headings["status"] == "hit" else 0
        formatting_score = W_FORMATTING if dates["status"] == "hit" else (
            W_FORMATTING * 0.5 if headings["status"] == "hit" else 0
        )
        seniority_score = W_SENIORITY if seniority["status"] == "hit" else W_SENIORITY * 0.3
        impact_score    = W_IMPACT if impact["status"] == "hit" else (
            W_IMPACT * 0.4 if impact.get("count", 0) >= 1 else 0
        )
        education_score = W_EDUCATION if education["status"] == "hit" else 0
        contact_hits    = sum(1 for c in contact.values() if c["status"] == "hit")
        contact_score   = (contact_hits / len(contact)) * W_CONTACT

        # Experience score
        exp_data        = seniority.get("experience_audit", {})
        required_years  = extraction.get("required_years", 0)
        resume_years    = exp_data.get("total_years", 0)
        if required_years == 0:
            exp_score = W_EXPERIENCE
        else:
            gap = max(0, required_years - resume_years)
            if gap == 0:   exp_score = W_EXPERIENCE
            elif gap == 1: exp_score = W_EXPERIENCE * 0.75
            elif gap == 2: exp_score = W_EXPERIENCE * 0.45
            elif gap == 3: exp_score = W_EXPERIENCE * 0.20
            else:          exp_score = 0.0

        final_score = max(0.0, min(100.0, round(
            keyword_score + semantic_score + placement_score +
            structure_score + formatting_score + seniority_score + impact_score +
            education_score + contact_score + exp_score,
            1
        )))

        # ── Step 6: Tier + outlook ────────────────────────────────────────────
        if final_score >= 85:
            tier    = "excellent"
            outlook = "Top-tier candidate. Exceeds ATS thresholds across all major systems."
        elif final_score >= 70:
            tier    = "good"
            outlook = "Strong candidate. Should pass most ATS filters with minor optimisation."
        elif final_score >= 55:
            tier    = "fair"
            outlook = "Qualified candidate. Gaps present but passable with targeted improvements."
        elif final_score >= 40:
            tier    = "borderline"
            outlook = "Borderline candidate. Risk of auto-rejection in strict ATS systems."
        else:
            tier    = "poor"
            outlook = "High rejection risk. Critical gaps detected. Immediate optimisation required."

        logger.info("Score: %s/100 (%s)", final_score, tier)

        # ── Step 7: Weak areas for AI suggestions ─────────────────────────────
        weak_areas = []
        if placement["status"]      == "miss": weak_areas.append("keyword placement in experience bullets")
        if impact["status"]         == "miss": weak_areas.append("quantified achievements and metrics")
        if seniority["status"]      == "miss": weak_areas.append("seniority language and ownership verbs")
        if headings["status"]       == "miss": weak_areas.append("section structure and headings")
        if stuffing_check["status"] == "miss": weak_areas.append("keyword over-use")
        if len(missing) > 3:                   weak_areas.append(f"{len(missing)} missing required skills")

        # ── Step 8: AI suggestions ────────────────────────────────────────────
        suggestions = generate_suggestions(
            resume_text=resume_text,
            jd_text=jd_text,
            extraction=extraction,
            score=final_score,
            weak_areas=weak_areas,
        )
        if not suggestions:
            suggestions = generate_fallback_suggestions(final_score)

        logger.info("Generated %d suggestions", len(suggestions))

        # ── Step 9: Density chart ─────────────────────────────────────────────
        density = calculate_density(resume_text, jd_text)

        # ── Step 10: Audit sections ───────────────────────────────────────────
        skill_coverage = _pct(len(hits), total_jd)

        audit = {
            "Contact & Searchability": [
                contact["location"],
                contact["contact_channels"],
                contact["linkedin"],
            ],
            "Document Structure": [
                headings,
                dates,
            ],
            "Alignment & Seniority": [
                {"status": title_info["status"], "msg": title_info["msg"]},
                seniority,
            ],
            "Keyword Intelligence": [
                placement,
                stuffing_check,
                {
                    "status": "hit" if skill_coverage >= 50 else "miss",
                    "msg": (
                        f"Strong Skill Coverage: {len(hits)} of {total_jd} required skills "
                        f"matched ({round(skill_coverage)}%) — solid functional overlap."
                        if skill_coverage >= 50 else
                        f"Skill Gap: {len(hits)} of {total_jd} required skills matched "
                        f"({round(skill_coverage)}%). Add these missing skills: "
                        f"{', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}."
                    ),
                },
            ],
            "Experience & Qualifications": [
                impact,
                education,
            ],
        }

        # Experience timeline section
        if exp_data.get("has_mismatch"):
            audit["Experience Timeline"] = [{
                "status": "miss",
                "msg": exp_data["mismatch_msg"]
            }]
        elif exp_data.get("years_from_dates", 0) > 0:
            years_dates = exp_data["years_from_dates"]
            audit["Experience Timeline"] = [{
                "status": "hit",
                "msg": (
                    f"Timeline Verified: Date ranges calculate to {years_dates} years "
                    "of experience. ATS systems use chronological dates to validate "
                    "claimed experience levels."
                )
            }]

        # ── Step 11: Score breakdown (v5.0 key names for frontend) ────────────
        score_breakdown = {
            "keyword_overlap":   round(keyword_score, 1),
            "keyword_placement": round(min(placement_score + semantic_score, 20), 1),
            "experience":        round(exp_score, 1),
            "education":         round(education_score, 1),
            "formatting":        round(formatting_score, 1),
            "contact":           round(contact_score, 1),
            "structure":         round(structure_score, 1),
            "impact":            round(impact_score, 1),
            "seniority":         round(seniority_score, 1),
        }

        # ── Step 12: ATS-specific scores (v5.0 compat) ───────────────────────
        match_rate = round(skill_coverage)
        ats_specific_scores = {
            "workday_score":   _estimate_workday(keyword_score, exp_score, education_score),
            "greenhouse_rank": _estimate_greenhouse(keyword_score, placement_score, semantic_score),
            "taleo_match":     (
                f"{match_rate}% match — " + (
                    "Excellent fit" if match_rate >= 80 else
                    "Good fit"      if match_rate >= 60 else
                    "Moderate fit"  if match_rate >= 40 else
                    "Poor fit"
                )
            ),
            "icims_score":     _estimate_icims(education_score, structure_score, contact_score),
        }

        return {
            "score":               final_score,
            "tier":                tier,
            "outlook":             outlook,
            "seniority_match":     detect_resume_level(resume_text),
            "recent_hits":         sorted(hits),
            "missing":             sorted(missing),
            "soft_skills":         sorted(soft_skills),
            "density":             density,
            "audit":               audit,
            "score_breakdown":     score_breakdown,
            "ats_specific_scores": ats_specific_scores,
            "suggestions":         suggestions,
            "jd_parsed":           extraction,
        }

    except Exception as e:
        logger.error("Analysis failed: %s", e, exc_info=True)
        return _generate_fallback_response()


# ── ATS estimate helpers ──────────────────────────────────────────────────────

def _estimate_workday(keyword_score: float, exp_score: float, edu_score: float) -> str:
    pct = round(min(((keyword_score + exp_score + edu_score) / 50) * 100, 100))
    if pct >= 80: return f"{pct}% — Highly Qualified (Top 15%)"
    if pct >= 60: return f"{pct}% — Qualified (Top 35%)"
    return f"{pct}% — Under-qualified (Bottom 50%)"


def _estimate_greenhouse(keyword_score: float, placement_score: float, semantic_score: float) -> str:
    pct = round(min(((keyword_score + placement_score + semantic_score) / 50) * 100, 100))
    if pct >= 80: return "Top 10% — Auto-advanced to recruiter"
    if pct >= 60: return "Top 25% — Strong candidate pool"
    if pct >= 40: return "Top 50% — Reviewed if quota not met"
    return "Bottom 50% — Likely not reviewed"


def _estimate_icims(edu_score: float, structure_score: float, contact_score: float) -> str:
    pct = round(min(((edu_score + structure_score + contact_score) / 20) * 100, 100))
    if pct >= 85: return f"{pct}% — Excellent parsability"
    if pct >= 60: return f"{pct}% — Good parsability"
    return f"{pct}% — Poor parsability (data loss likely)"


def _generate_fallback_response() -> dict:
    return {
        "score": 0, "tier": "error",
        "outlook": "Unable to analyse resume. Please check your inputs and try again.",
        "seniority_match": "unknown",
        "recent_hits": [], "missing": [], "soft_skills": [],
        "density": {"labels": [], "jd_counts": [], "res_counts": [], "explanation": ""},
        "audit": {},
        "score_breakdown": {
            "keyword_overlap": 0, "keyword_placement": 0, "experience": 0,
            "education": 0, "formatting": 0, "contact": 0, "structure": 0,
            "impact": 0, "seniority": 0
        },
        "ats_specific_scores": {
            "workday_score": "N/A", "greenhouse_rank": "N/A",
            "taleo_match": "N/A",   "icims_score": "N/A"
        },
        "suggestions": generate_fallback_suggestions(0),
        "jd_parsed": {},
    }
