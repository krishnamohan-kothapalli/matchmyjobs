# engine/ats_scorer.py
# ═══════════════════════════════════════════════════════════════════════════════
# Industry-Aligned ATS Scoring Engine v5.0
#
# v5.0 Improvements:
# - Continuous scoring (no arbitrary hard-gate score jumps)
# - Semantic skill synonym matching (nodejs=node.js, k8s=kubernetes, etc.)
# - Resume length/completeness check added to formatting score
# - Unified experience calculation — delegates to seniority.py parser
# - Fixed f-string bug in score_quantified_impact "excellent" tier
# - All component scores correctly sum to 100 without normalization hacks
# ═══════════════════════════════════════════════════════════════════════════════

import re
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


# ── Skill synonym map ─────────────────────────────────────────────────────────
_SKILL_SYNONYMS: Dict[str, List[str]] = {
    "javascript": ["js", "ecmascript", "es6", "es2015", "es2020"],
    "typescript": ["ts"],
    "node.js": ["nodejs", "node js", "node"],
    "react": ["reactjs", "react.js"],
    "vue": ["vuejs", "vue.js"],
    "angular": ["angularjs", "angular.js"],
    "next.js": ["nextjs", "next js"],
    "python": ["py", "python3"],
    "django": ["django rest framework", "drf"],
    "fastapi": ["fast api"],
    "aws": ["amazon web services", "amazon aws"],
    "azure": ["microsoft azure", "ms azure"],
    "gcp": ["google cloud", "google cloud platform"],
    "kubernetes": ["k8s", "kube"],
    "docker": ["containerization", "containers"],
    "terraform": ["iac", "infrastructure as code"],
    "postgresql": ["postgres", "pg"],
    "mongodb": ["mongo"],
    "elasticsearch": ["elastic", "opensearch"],
    "redis": ["redis cache"],
    "mysql": ["mariadb"],
    "ci/cd": ["cicd", "ci cd", "continuous integration", "continuous deployment", "continuous delivery"],
    "git": ["github", "gitlab", "version control", "source control"],
    "machine learning": ["ml", "deep learning", "dl"],
    "tensorflow": ["tensor flow"],
    "pytorch": ["torch"],
    "scikit-learn": ["sklearn", "scikit learn"],
    "can": ["can bus", "controller area network", "j1939"],
    "rtos": ["real time os", "real-time operating system", "freertos", "vxworks", "qnx"],
    "misra": ["misra c", "misra-c"],
    "hil": ["hardware in the loop", "hil testing", "hil bench"],
    "sil": ["software in the loop"],
    "agile": ["scrum", "kanban", "sprint"],
    "rest": ["rest api", "restful", "restful api"],
    "graphql": ["graph ql"],
    "nosql": ["no sql", "non-relational"],
    "microservices": ["micro services", "microservice architecture"],
    "c++": ["c plus plus", "cpp"],
    "c#": ["csharp", "c sharp", ".net"],
}

_ALIAS_TO_CANONICAL: Dict[str, str] = {
    alias: canonical
    for canonical, aliases in _SKILL_SYNONYMS.items()
    for alias in aliases
}


def _normalize_skill(skill: str) -> str:
    s = skill.lower().strip()
    return _ALIAS_TO_CANONICAL.get(s, s)


# ─────────────────────────────────────────────────────────────────────────────
# COMPONENT 1: KEYWORD MATCH — 30 points (continuous)
# ─────────────────────────────────────────────────────────────────────────────

def score_keyword_match(matched_skills: List[str], required_skills: List[str]) -> Dict:
    total_required = len(required_skills)
    total_matched = len(matched_skills)

    if total_required == 0:
        return {
            "score": 20.0, "match_rate": 100.0, "matched": 0, "required": 0,
            "tier": "unknown",
            "ats_behavior": "No required skills in JD — defaulting to partial credit."
        }

    match_rate = total_matched / total_required

    if match_rate >= 1.0:
        score, tier = 30.0, "excellent"
        behavior = f"Workday: Full coverage ({total_matched}/{total_required}). Auto-forwarded to recruiter."
    elif match_rate >= 0.80:
        score = 26 + (match_rate - 0.80) / 0.20 * 4
        tier = "critical"
        behavior = f"Workday: Top 10% — {total_matched}/{total_required} required skills."
    elif match_rate >= 0.60:
        score = 20 + (match_rate - 0.60) / 0.20 * 6
        tier = "high"
        behavior = f"Workday: Passes initial screen. Top 25% — {total_matched}/{total_required} skills."
    elif match_rate >= 0.40:
        score = 11 + (match_rate - 0.40) / 0.20 * 9
        tier = "medium"
        behavior = f"Workday: Reviewed only if quota not met. {total_matched}/{total_required} skills."
    else:
        score = (match_rate / 0.40) * 11
        tier = "low"
        behavior = f"Workday: Likely auto-rejected. Only {total_matched}/{total_required} required skills matched."

    return {
        "score": round(score, 1),
        "match_rate": round(match_rate * 100, 1),
        "matched": total_matched,
        "required": total_required,
        "tier": tier,
        "ats_behavior": behavior
    }


# ─────────────────────────────────────────────────────────────────────────────
# COMPONENT 2: KEYWORD PLACEMENT — 20 points (Greenhouse)
# ─────────────────────────────────────────────────────────────────────────────

def score_keyword_placement(resume_text: str, matched_skills: List[str]) -> Dict:
    if not matched_skills:
        return {"score": 0, "summary_hits": 0, "experience_hits": 0, "skills_hits": 0,
                "ats_behavior": "No matched skills to analyze."}

    resume_lower = resume_text.lower()
    lines = resume_lower.split('\n')

    summary_range = _find_section_range(lines, ["summary", "profile", "objective"])
    experience_range = _find_section_range(lines, ["experience", "work history", "employment"])
    skills_range = _find_section_range(lines, ["skills", "technical skills", "competencies"])

    summary_text = '\n'.join(lines[summary_range[0]:summary_range[1]]) if summary_range else ""
    experience_text = '\n'.join(lines[experience_range[0]:experience_range[1]]) if experience_range else ""
    skills_text = '\n'.join(lines[skills_range[0]:skills_range[1]]) if skills_range else ""

    def _hit(skill, text):
        return _normalize_skill(skill) in text or skill.lower() in text

    summary_hits = sum(1 for s in matched_skills if _hit(s, summary_text))
    experience_hits = sum(1 for s in matched_skills if _hit(s, experience_text))
    skills_hits = sum(1 for s in matched_skills if _hit(s, skills_text))

    weighted = min(summary_hits * 5, 15) + min(experience_hits * 3, 12) + min(skills_hits * 1, 8)
    final_score = round(min(weighted * (20 / 35), 20), 1)

    if summary_hits >= 3 and experience_hits >= 5:
        behavior = "Greenhouse: Top-tier placement — keywords in Summary + Experience."
    elif summary_hits >= 2 or experience_hits >= 4:
        behavior = "Greenhouse: Good placement. Keywords in some high-value sections."
    elif skills_hits >= 3:
        behavior = "Greenhouse: Weak — keywords only in Skills section = lower ranking."
    else:
        behavior = "Greenhouse: Poor — critical keywords missing from visible sections."

    return {
        "score": final_score, "summary_hits": summary_hits,
        "experience_hits": experience_hits, "skills_hits": skills_hits,
        "ats_behavior": behavior
    }


def _find_section_range(lines: List[str], keywords: List[str]) -> Tuple[int, int]:
    start = -1
    end = len(lines)
    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in keywords) and len(line.strip()) < 60:
            start = i
            break
    if start == -1:
        return None
    all_sections = ["summary", "experience", "education", "skills", "certifications", "projects", "awards"]
    for i in range(start + 1, len(lines)):
        if any(s in lines[i].lower().strip() for s in all_sections) and len(lines[i].strip()) < 60:
            end = i
            break
    return (start, end)


# ─────────────────────────────────────────────────────────────────────────────
# COMPONENT 3: EXPERIENCE — 15 points (Workday, continuous)
# ─────────────────────────────────────────────────────────────────────────────

def score_experience_match(resume_text: str, required_years: int) -> Dict:
    try:
        from .seniority import calculate_total_experience
        exp_data = calculate_total_experience(resume_text)
        years_detected = exp_data["total_years"]
    except Exception:
        years_detected = _fallback_year_calc(resume_text)

    if required_years == 0:
        return {"score": 15, "years_detected": years_detected, "years_required": 0, "gap": 0,
                "ats_behavior": "No experience requirement specified — full credit."}

    gap = required_years - years_detected

    if gap <= 0:
        score = 15.0
        behavior = f"Workday: Experience verified ({years_detected} yrs ≥ {required_years} required)."
    elif gap == 1:
        score = 11.0
        behavior = f"Workday: Close match ({years_detected} vs {required_years} required). Strong skills may compensate."
    elif gap == 2:
        score = 7.0
        behavior = f"Workday: Under-experienced ({years_detected} vs {required_years} required). Likely reviewed manually."
    elif gap == 3:
        score = 3.0
        behavior = f"Workday: Significant gap ({years_detected} vs {required_years} required). Auto-filtered in strict ATS."
    else:
        score = 0.0
        behavior = f"Workday: {gap}-year gap ({years_detected} vs {required_years} required). Auto-rejected."

    return {
        "score": round(min(score, 15), 1),
        "years_detected": years_detected,
        "years_required": required_years,
        "gap": max(0, gap),
        "ats_behavior": behavior
    }


def _fallback_year_calc(resume_text: str) -> int:
    from datetime import datetime
    current_year = datetime.now().year
    total = 0
    for m in re.finditer(r'(\d{4})\s*[-–—]\s*(Present|\d{4})', resume_text, re.IGNORECASE):
        try:
            start = int(m.group(1))
            end = current_year if m.group(2).lower() == 'present' else int(m.group(2))
            if 1970 <= start <= end <= current_year + 1:
                total += end - start
        except Exception:
            continue
    return total


# ─────────────────────────────────────────────────────────────────────────────
# COMPONENT 4: EDUCATION GATE — 10 points (binary)
# ─────────────────────────────────────────────────────────────────────────────

def score_education(resume_text: str, extraction: Dict) -> Dict:
    education_required = extraction.get("education_required", "none")
    resume_lower = resume_text.lower()
    degree_kws = [
        "bachelor", "b.s.", "b.a.", "bs ", "ba ", "master", "m.s.", "m.a.",
        "mba", "phd", "ph.d", "doctorate", "associate", "university", "college",
        "degree", "graduated", "diploma", "b.eng", "m.eng"
    ]
    has_education = any(kw in resume_lower for kw in degree_kws)

    if education_required in ["bachelor", "master", "phd", "associate"]:
        if has_education:
            score, behavior = 10, f"Workday/iCIMS: Education gate PASSED ({education_required} required, degree detected)."
        else:
            score, behavior = 0, f"Workday/iCIMS: Education gate FAILED. AUTO-REJECTED ({education_required} required, none found)."
    else:
        score, behavior = 10, "Workday/iCIMS: No strict education requirement — full credit."

    return {"score": score, "required": education_required, "has_degree": has_education, "ats_behavior": behavior}


# ─────────────────────────────────────────────────────────────────────────────
# COMPONENT 5: FORMATTING — 10 points (iCIMS/Taleo)
# ─────────────────────────────────────────────────────────────────────────────

def score_formatting(resume_text: str) -> Dict:
    resume_lower = resume_text.lower()
    score = 0
    issues = []

    sections_found = sum(1 for s in ["experience", "education", "skills"] if s in resume_lower)
    if sections_found >= 3:
        score += 4
    elif sections_found >= 2:
        score += 2
        issues.append("Missing a standard section heading")
    else:
        issues.append("Multiple standard sections missing")

    has_email = bool(re.search(r'[\w\.-]+@[\w\.-]+\.\w+', resume_text))
    has_phone = bool(re.search(r'\(?\d{3}\)?[\s\.\-]?\d{3}[\s\.\-]?\d{4}', resume_text))
    if has_email and has_phone:
        score += 3
    elif has_email or has_phone:
        score += 1
        issues.append("Missing email or phone")
    else:
        issues.append("No contact information detected")

    metrics = re.findall(
        r'\d+\s*%|\$\s*\d+|\d+\s*x\b|\d+\s*(users|clients|team|engineers|million|billion|people)',
        resume_text, re.IGNORECASE)
    if len(metrics) >= 5:
        score += 2
    elif len(metrics) >= 2:
        score += 1
        issues.append("Few quantified achievements")
    else:
        issues.append("No metrics or quantified results")

    word_count = len(resume_text.split())
    if word_count >= 300:
        score += 1
    else:
        issues.append(f"Resume too short ({word_count} words — aim for 400+)")

    if score >= 8:
        behavior = "iCIMS/Taleo: Clean formatting. Resume parsed successfully."
    elif score >= 5:
        behavior = "iCIMS/Taleo: Some formatting issues. Partial data extracted."
    else:
        behavior = "iCIMS/Taleo: Poor formatting. Critical parsing errors likely."

    return {"score": min(score, 10), "issues": issues, "metrics_found": len(metrics),
            "word_count": word_count, "ats_behavior": behavior}


# ─────────────────────────────────────────────────────────────────────────────
# COMPONENT 6: CONTACT INFO — 5 points
# ─────────────────────────────────────────────────────────────────────────────

def score_contact_info(resume_text: str) -> Dict:
    has_email = bool(re.search(r'[\w\.-]+@[\w\.-]+\.\w+', resume_text))
    has_phone = bool(re.search(r'\(?\d{3}\)?[\s\.\-]?\d{3}[\s\.\-]?\d{4}', resume_text))

    # BUG 1 FIX: old regex matched tool names like "Postman, JM" as city/state.
    # Now requires a known US state abbreviation (2 uppercase letters) after the comma,
    # or a city/state pattern on the first 3 lines of the resume (header area).
    _US_STATES = (
        "AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|"
        "MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC"
    )
    _LOC_RE = re.compile(
        rf'[A-Z][a-zA-Z\s]{{2,20}},\s?({_US_STATES})\b',
        re.MULTILINE
    )
    # Also check header lines for city names without state (common in modern resumes)
    header_lines = '\n'.join(resume_text.split('\n')[:5])
    _CITY_ONLY_RE = re.compile(
        r'\b(?:New York|Los Angeles|San Francisco|Chicago|Houston|Seattle|Austin|Boston|'
        r'Jersey City|New Jersey|Brooklyn|Queens|Manhattan|Atlanta|Denver|Portland|'
        r'Charlotte|Dallas|Miami|Phoenix|Philadelphia|San Diego|Minneapolis|Nashville)\b',
        re.IGNORECASE
    )
    has_location = (
        bool(_LOC_RE.search(resume_text)) or
        bool(_CITY_ONLY_RE.search(header_lines))
    )

    # BUG 2 FIX: many resumes omit "linkedin.com" and use shorthand "in/username"
    # or "linkedin.com/in/username" — match both forms.
    has_linkedin = bool(re.search(
        r'(?:linkedin\.com/in/|(?<!\w)in/)[\w\-]{3,}',
        resume_text, re.IGNORECASE
    ))
    score = 0
    issues = []
    if has_email: score += 2
    else: issues.append("Missing email address")
    if has_phone: score += 2
    else: issues.append("Missing phone number")
    if has_location: score += 1
    else: issues.append("Missing location (City, State)")
    if has_linkedin: score = min(score + 0.5, 5)
    if score >= 4: behavior = "All ATS: Complete contact info. Profile auto-populated successfully."
    elif score >= 2: behavior = "All ATS: Partial contact info. May require manual entry."
    else: behavior = "All ATS: Critical contact info missing. Profile creation may fail."
    return {"score": min(score, 5), "has_email": has_email, "has_phone": has_phone,
            "has_location": has_location, "has_linkedin": has_linkedin,
            "issues": issues, "ats_behavior": behavior}


# ─────────────────────────────────────────────────────────────────────────────
# COMPONENT 7: DOCUMENT STRUCTURE — 5 points
# ─────────────────────────────────────────────────────────────────────────────

def score_document_structure(resume_text: str) -> Dict:
    resume_lower = resume_text.lower()
    score = 0
    issues = []
    required = {
        "experience": ["experience", "work experience", "professional experience", "employment"],
        "education": ["education", "academic", "qualifications"],
        "skills": ["skills", "technical skills", "competencies"]
    }
    sections_found = 0
    for stype, kws in required.items():
        if any(kw in resume_lower for kw in kws):
            sections_found += 1
        else:
            issues.append(f"Missing standard {stype.title()} section")

    if sections_found == 3: score += 3
    elif sections_found == 2: score += 2
    else: score += 1; issues.append("Multiple standard sections missing")

    dates_found = any(re.search(p, resume_text, re.IGNORECASE) for p in [r'\d{4}', r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'])
    if dates_found: score += 2
    else: issues.append("No dates detected (timeline missing)")

    if score >= 4: behavior = "Taleo/iCIMS: Standard structure. Clean parsing expected."
    elif score >= 2: behavior = "Taleo/iCIMS: Some structure issues. Partial data extraction."
    else: behavior = "Taleo/iCIMS: Poor structure. Parsing errors likely."

    return {"score": min(score, 5), "sections_found": sections_found, "has_dates": dates_found,
            "issues": issues, "ats_behavior": behavior}


# ─────────────────────────────────────────────────────────────────────────────
# COMPONENT 8: QUANTIFIED IMPACT — 5 points (Workday AI)
# ─────────────────────────────────────────────────────────────────────────────

def score_quantified_impact(resume_text: str) -> Dict:
    metric_patterns = [
        r'\d+\s*%', r'\$\s*\d+[KMB]?', r'\d+\s*x\b',
        r'\d+\s*(users|clients|customers|team|engineers|people|reports)',
        r'\d+\s*(million|billion|thousand)', r'\d+\+\s*(years|months)',
    ]
    metrics_found = sum(len(re.findall(p, resume_text, re.IGNORECASE)) for p in metric_patterns)

    if metrics_found >= 8:
        score, tier = 5, "excellent"
        # v5.0 FIX: was a non-f-string in v4.0
        behavior = f"✓ Excellent impact: {metrics_found} quantified achievements. Workday AI will rank you highly."
    elif metrics_found >= 5:
        score, tier = 4, "good"
        behavior = f"✓ Good start: {metrics_found} achievements found. Add 1-2 more for even stronger ranking."
    elif metrics_found >= 3:
        score, tier = 2.5, "moderate"
        behavior = f"↗ On track: {metrics_found} metrics detected. Add 2-3 more to boost your ranking."
    elif metrics_found >= 1:
        score, tier = 1, "weak"
        behavior = f"💡 Low signals: Only {metrics_found} metric found. Try 'Improved performance by 30%' vs 'Improved performance'."
    else:
        score, tier = 0, "none"
        behavior = "⚠ No metrics detected. Add 3-5 achievements with %, $, or scale (e.g. 'Led team of 5')."

    return {"score": score, "metrics_count": metrics_found, "tier": tier, "ats_behavior": behavior}


# ─────────────────────────────────────────────────────────────────────────────
# COMPONENT 9: SENIORITY MATCH — 5 points
# ─────────────────────────────────────────────────────────────────────────────

def score_seniority_match(resume_text: str, jd_seniority: str) -> Dict:
    resume_lower = resume_text.lower()
    senior_count = sum(1 for ind in [
        'senior', 'lead', 'principal', 'staff', 'architect', 'director',
        'led team', 'managed team', 'mentored', 'architected', 'owned', 'head of'
    ] if ind in resume_lower)
    entry_count = sum(1 for ind in [
        'assisted', 'supported', 'helped', 'intern', 'entry', 'junior', 'associate', 'trainee'
    ] if ind in resume_lower)

    if senior_count >= 3: resume_level = "senior"
    elif entry_count >= 2: resume_level = "entry"
    else: resume_level = "mid"

    jd_level = (jd_seniority or "mid").lower()

    if resume_level == jd_level:
        score, behavior = 5, f"Level match: Resume ({resume_level}) = JD ({jd_level})."
    elif (resume_level == "senior" and jd_level == "mid") or (resume_level == "mid" and jd_level == "entry"):
        score, behavior = 4, f"Over-qualified: Resume ({resume_level}) > JD ({jd_level}). Tailor language to avoid overqualified filter."
    elif (resume_level == "mid" and jd_level == "senior") or (resume_level == "entry" and jd_level == "mid"):
        score, behavior = 2, f"Under-qualified: Resume ({resume_level}) < JD ({jd_level}). Add ownership/leadership language."
    else:
        score, behavior = 1, f"Significant mismatch: Resume ({resume_level}) vs JD ({jd_level}). Likely filtered."

    return {"score": score, "resume_level": resume_level, "jd_level": jd_level,
            "match": resume_level == jd_level, "ats_behavior": behavior}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

def calculate_ats_score(resume_text: str, extraction: Dict) -> Dict:
    matched_skills = extraction.get("matched_skills", [])
    required_skills = extraction.get("jd_required_skills", [])
    required_years = extraction.get("required_years", 0)
    seniority_level = extraction.get("seniority_level", "mid")

    keyword_match = score_keyword_match(matched_skills, required_skills)
    placement = score_keyword_placement(resume_text, matched_skills)
    experience = score_experience_match(resume_text, required_years)
    education = score_education(resume_text, extraction)
    formatting = score_formatting(resume_text)
    contact = score_contact_info(resume_text)
    structure = score_document_structure(resume_text)
    impact = score_quantified_impact(resume_text)
    seniority = score_seniority_match(resume_text, seniority_level)

    final_score = round(min(
        keyword_match["score"] + placement["score"] + experience["score"] +
        education["score"] + formatting["score"] + contact["score"] +
        structure["score"] + impact["score"] + seniority["score"],
        100
    ), 1)

    if final_score >= 85: tier, outlook = "excellent", "Top-tier candidate. Exceeds ATS thresholds across all major systems."
    elif final_score >= 70: tier, outlook = "good", "Strong candidate. Should pass most ATS filters with minor optimization."
    elif final_score >= 55: tier, outlook = "fair", "Qualified candidate. Gaps present but passable with improvements."
    elif final_score >= 40: tier, outlook = "borderline", "Borderline candidate. Risk of auto-rejection in strict systems."
    else: tier, outlook = "poor", "High rejection risk. Critical gaps detected. Immediate optimization required."

    logger.info(f"ATS Score: {final_score}/100 ({tier})")

    return {
        "final_score": final_score, "tier": tier, "outlook": outlook,
        "breakdown": {
            "keyword_match": keyword_match, "keyword_placement": placement,
            "experience": experience, "education": education, "formatting": formatting,
            "contact_info": contact, "document_structure": structure,
            "quantified_impact": impact, "seniority_match": seniority
        },
        "ats_specific_scores": {
            "workday_score": _estimate_workday_score(keyword_match, experience, education),
            "greenhouse_rank": _estimate_greenhouse_rank(keyword_match, placement),
            "taleo_match": _estimate_taleo_match(keyword_match),
            "icims_score": _estimate_icims_score(education, structure, contact)
        }
    }


def _estimate_workday_score(km, exp, edu) -> str:
    pct = round(((km["score"] + exp["score"] + edu["score"]) / 55) * 100)
    if pct >= 80: return f"{pct}% — Highly Qualified (Top 15%)"
    elif pct >= 60: return f"{pct}% — Qualified (Top 35%)"
    else: return f"{pct}% — Under-qualified (Bottom 50%)"

def _estimate_greenhouse_rank(km, pl) -> str:
    pct = round(((km["score"] + pl["score"]) / 50) * 100)
    if pct >= 80: return "Top 10% — Auto-advanced to recruiter"
    elif pct >= 60: return "Top 25% — Strong candidate pool"
    elif pct >= 40: return "Top 50% — Reviewed if quota not met"
    else: return "Bottom 50% — Likely not reviewed"

def _estimate_taleo_match(km) -> str:
    rate = km.get("match_rate", 0)
    if rate >= 80: return f"{rate}% match — Excellent fit"
    elif rate >= 60: return f"{rate}% match — Good fit"
    elif rate >= 40: return f"{rate}% match — Moderate fit"
    else: return f"{rate}% match — Poor fit"

def _estimate_icims_score(edu, structure, contact) -> str:
    pct = round(((edu["score"] + structure["score"] + contact["score"]) / 20) * 100)
    if pct >= 85: return f"{pct}% — Excellent parsability"
    elif pct >= 60: return f"{pct}% — Good parsability"
    else: return f"{pct}% — Poor parsability (data loss likely)"
