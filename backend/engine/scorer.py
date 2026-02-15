# engine/scorer.py
# ─────────────────────────────────────────────────────────────────────────────
# Central scoring orchestrator.
#
# ENHANCEMENTS v3.0:
#   - Prioritize Claude title extraction over regex
#   - Better error context
#   - Improved experience mismatch detection
#
# Flow:
#   1. Claude extracts + matches skills from both JD and resume simultaneously
#   2. Deterministic checks run using extracted data (contact, structure, etc.)
#   3. Score assembled from 7 weighted dimensions
#   4. Claude generates improvement suggestions from findings
# ─────────────────────────────────────────────────────────────────────────────

from .skills      import (extract_soft_skills, keyword_frequency,
                           detect_keyword_stuffing, spacy_extract_skills)
from .seniority   import build_seniority_audit, detect_resume_level
from .diagnostics import (check_contact, check_section_headings, check_dates,
                           check_education, check_quantified_impact,
                           check_keyword_placement, check_title_alignment,
                           check_keyword_stuffing)
from .density     import calculate_density
from .ai_parser   import extract_all, generate_suggestions

# ── Score weights (sum = 100) ─────────────────────────────────────────────────
W_KEYWORD_OVERLAP   = 35
W_SEMANTIC          = 20
W_PLACEMENT         = 15
W_STRUCTURE         = 10
W_SENIORITY         = 10
W_IMPACT            = 5
W_CONTACT           = 5

# ── Penalties ─────────────────────────────────────────────────────────────────
P_MISSING_TITLE     = 8
P_MISSING_EDU       = 5
P_KEYWORD_STUFFING  = 5
P_PER_MISSING_SKILL = 1
P_MAX_SKILL_PENALTY = 15


def _pct(part: int, total: int) -> float:
    return (part / total * 100) if total else 0


def run_analysis(resume_text: str, jd_text: str, nlp) -> dict:
    """
    Full hybrid analysis. Returns structured result.
    
    ENHANCED: Better title extraction, improved error context
    """

    # ── Step 1: Claude extracts skills from both docs simultaneously ──────────
    extraction = extract_all(jd_text, resume_text)

    # Primary skill sets come from Claude
    hits    = extraction.get("matched_skills", [])
    missing = extraction.get("missing_skills", [])
    all_jd_skills = set(extraction.get("jd_required_skills", []))

    # Fallback: if Claude failed, use spaCy
    if not hits and not missing:
        res_doc   = nlp(resume_text)
        jd_doc    = nlp(jd_text)
        res_skills = spacy_extract_skills(res_doc)
        jd_skills  = spacy_extract_skills(jd_doc)
        hits       = sorted(jd_skills & res_skills)
        missing    = sorted(jd_skills - res_skills)
        all_jd_skills = jd_skills
    else:
        # Still need docs for semantic similarity
        res_doc = nlp(resume_text)
        jd_doc  = nlp(jd_text)

    soft_skills = extract_soft_skills(resume_text)
    stuffed     = detect_keyword_stuffing(resume_text, hits, threshold=5)

    # ── Step 2: Deterministic structural checks ───────────────────────────────
    contact        = check_contact(resume_text)
    headings       = check_section_headings(resume_text)
    dates          = check_dates(resume_text)
    education      = check_education(resume_text, jd_text)
    impact         = check_quantified_impact(resume_text)
    placement      = check_keyword_placement(resume_text, set(hits))
    
    # ENHANCED: ALWAYS use Claude's title extraction first — it handles any format
    # Only fall back to regex if Claude completely failed
    ai_title = extraction.get("job_title", "").strip()
    
    if ai_title and len(ai_title) > 3:  # Valid title from Claude
        # Check if title words appear in resume
        title_words = [word for word in ai_title.split() if len(word) > 2]
        title_found = any(word.lower() in resume_text.lower() for word in title_words)
        
        title_info = {
            "clean_title": ai_title,
            "status": "hit" if title_found else "miss",
            "msg": (
                f"Title Aligned: Your resume reflects the target role '{ai_title}'. "
                "Greenhouse and Lever rank candidates higher when the profile title matches the JD title exactly."
                if title_found
                else f"Title Gap: The role title '{ai_title}' isn't explicitly reflected in your resume. "
                     "Add it to your summary or headline — Greenhouse and Lever use title matching as a primary relevance signal."
            )
        }
    else:
        # Fallback to regex only if Claude extraction failed
        title_info = check_title_alignment(resume_text, jd_text)
    
    seniority      = build_seniority_audit(resume_text, jd_text)
    stuffing_check = check_keyword_stuffing(stuffed)

    # ── Step 3: Component scores ──────────────────────────────────────────────
    total_jd  = max(len(all_jd_skills), len(hits) + len(missing), 1)
    keyword_score   = (_pct(len(hits), total_jd) / 100) * W_KEYWORD_OVERLAP
    semantic_score  = res_doc.similarity(jd_doc) * W_SEMANTIC

    placement_score = W_PLACEMENT if placement["status"] == "hit" else (
        W_PLACEMENT * 0.4 if placement.get("summary_hits", 0) > 0 else 0
    )
    structure_hits  = sum(1 for c in [headings, dates] if c["status"] == "hit")
    structure_score = (structure_hits / 2) * W_STRUCTURE
    seniority_score = W_SENIORITY if seniority["status"] == "hit" else W_SENIORITY * 0.3
    impact_score    = W_IMPACT if impact["status"] == "hit" else (
        W_IMPACT * 0.4 if impact.get("count", 0) >= 1 else 0
    )
    contact_hits    = sum(1 for c in contact.values() if c["status"] == "hit")
    contact_score   = (contact_hits / len(contact)) * W_CONTACT

    raw_score = (keyword_score + semantic_score + placement_score +
                 structure_score + seniority_score + impact_score + contact_score)

    # ── Step 4: Penalties ─────────────────────────────────────────────────────
    penalty = 0
    if title_info["status"] == "miss":
        penalty += P_MISSING_TITLE
    if education["status"] == "miss" and "Hard Gate" in education.get("msg", ""):
        penalty += P_MISSING_EDU
    if stuffing_check["status"] == "miss":
        penalty += P_KEYWORD_STUFFING
    penalty += min(len(missing) * P_PER_MISSING_SKILL, P_MAX_SKILL_PENALTY)

    final_score = max(0.0, min(100.0, round(raw_score - penalty, 1)))

    # ── Step 5: Identify weak areas for suggestions ───────────────────────────
    weak_areas = []
    if placement["status"]      == "miss": weak_areas.append("keyword placement in experience bullets")
    if impact["status"]         == "miss": weak_areas.append("quantified achievements and metrics")
    if seniority["status"]      == "miss": weak_areas.append("seniority language and ownership verbs")
    if headings["status"]       == "miss": weak_areas.append("section structure and headings")
    if stuffing_check["status"] == "miss": weak_areas.append("keyword over-use")
    if len(missing) > 3:                   weak_areas.append(f"{len(missing)} missing required skills")

    # ── Step 6: AI suggestions ────────────────────────────────────────────────
    suggestions = generate_suggestions(
        resume_text=resume_text,
        extraction=extraction,
        score=final_score,
        weak_areas=weak_areas,
    )

    # ── Step 7: Density chart ─────────────────────────────────────────────────
    density = calculate_density(resume_text, jd_text)

    # ── Step 8: Audit sections ────────────────────────────────────────────────
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
    
    # ── Experience Timeline Audit ──────────────────────────────────────────────
    exp_data = seniority.get("experience_audit", {})
    
    if exp_data.get("has_mismatch"):
        # Show mismatch warning
        audit["Experience Timeline"] = [{
            "status": "miss",
            "msg": exp_data["mismatch_msg"]
        }]
    elif exp_data.get("years_from_dates", 0) > 0:
        # Show verification message
        years_dates = exp_data["years_from_dates"]
        audit["Experience Timeline"] = [{
            "status": "hit",
            "msg": (
                f"Timeline Verified: Date ranges calculate to {years_dates} years "
                f"of experience. ATS systems use chronological dates to validate "
                "claimed experience levels."
            )
        }]

    # ── Step 9: Score breakdown ────────────────────────────────────────────────
    score_breakdown = {
        "keyword_overlap":   round(keyword_score, 1),
        "semantic_match":    round(semantic_score, 1),
        "keyword_placement": round(placement_score, 1),
        "structure":         round(structure_score, 1),
        "seniority":         round(seniority_score, 1),
        "impact":            round(impact_score, 1),
        "contact":           round(contact_score, 1),
        "penalties":         -round(penalty, 1),
    }

    return {
        "score":           final_score,
        "seniority_match": detect_resume_level(resume_text),
        "recent_hits":     sorted(hits),
        "missing":         sorted(missing),
        "soft_skills":     sorted(soft_skills),
        "density":         density,
        "audit":           audit,
        "score_breakdown": score_breakdown,
        "suggestions":     suggestions,
        "jd_parsed":       extraction,
    }
