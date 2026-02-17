# engine/diagnostics.py
# Full file with title extraction fix and keyword placement fix

import re

# ── Regex patterns ─────────────────────────────────────────────────────────
_EMAIL_RE    = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
_PHONE_RE    = re.compile(r"\(?\d{3}\)?[\s\.-]?\d{3}[\s\.-]?\d{4}")
_LOCATION_RE = re.compile(r"[A-Z][a-zA-Z\s]{2,20},\s?(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b")
_LINKEDIN_RE = re.compile(r"(?:linkedin\.com/in/|(?<!\w)in/)[\w\-]{3,}", re.IGNORECASE)

_DATE_RE = re.compile(
    r"(\d{1,2}/\d{2,4}|\b(?:19|20)\d{2}\b"  # BUG 3 FIX: require 19xx/20xx to avoid phone digits
    r"|(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4})",
    re.IGNORECASE,
)

_METRIC_RE = re.compile(
    r"(\d+\s*%|\$\s*\d+|\d+\s*x\b|\d+\s*times|\d+\s*million"
    r"|\d+\s*billion|\d+\s*users|\d+\s*clients|\d+\s*team"
    r"|\d+\s*engineers|\d+\s*people|\d+\s*reports)",
    re.IGNORECASE,
)

_STANDARD_HEADINGS = {
    "summary":     ["summary", "professional summary", "profile", "objective",
                    "professional profile", "career objective"],
    "experience":  ["experience", "work experience", "professional experience",
                    "employment history", "work history", "career history"],
    "education":   ["education", "academic background", "academic history",
                    "qualifications", "degrees"],
    "skills":      ["skills", "technical skills", "core competencies",
                    "key skills", "areas of expertise", "competencies"],
}

_NONSTANDARD_HEADINGS = [
    "career highlights", "what i bring", "why hire me",
    "my journey", "career story", "professional journey",
    "achievements overview", "value proposition",
]

_DEGREE_KEYWORDS = [
    "bachelor", "b.s.", "b.a.", "bs ", "ba ", "master", "m.s.", "m.a.",
    "mba", "phd", "ph.d", "doctorate", "associate degree", "a.s.", "a.a.",
    "degree", "university", "college", "graduated",
]

_EDU_REQUIRED_RE = re.compile(
    r"(required?|must\s+have|minimum).{0,40}(bachelor|master|degree|phd|mba)",
    re.IGNORECASE,
)
_EDU_PREFERRED_RE = re.compile(
    r"(preferred?|nice\s+to\s+have|desired?).{0,40}(bachelor|master|degree|phd|mba)",
    re.IGNORECASE,
)


def check_contact(resume_text: str) -> dict:
    has_email    = bool(_EMAIL_RE.search(resume_text))
    has_phone    = bool(_PHONE_RE.search(resume_text))

    # BUG 1 FIX: original _LOCATION_RE matched tool names like "Postman, JM"
    # New approach: require a real US state abbreviation, or detect known city names
    # in the resume header (first 5 lines).
    _US_STATES = (
        "AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|"
        "MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC"
    )
    import re as _re
    _state_loc_re = _re.compile(rf'[A-Z][a-zA-Z\s]{{2,20}},\s?({_US_STATES})\b', _re.MULTILINE)
    _city_re = _re.compile(
        r'\b(?:New York|Los Angeles|San Francisco|Chicago|Houston|Seattle|Austin|Boston|' +
        r'Jersey City|New Jersey|Brooklyn|Manhattan|Charlotte|Atlanta|Dallas|Miami|Phoenix|' +
        r'Denver|Portland|Philadelphia|Minneapolis|Nashville|San Diego|Washington)\b',
        _re.IGNORECASE
    )
    header = '\n'.join(resume_text.split('\n')[:5])
    has_location = bool(_state_loc_re.search(resume_text)) or bool(_city_re.search(header))

    # BUG 2 FIX: support LinkedIn shorthand "in/username" without full domain
    has_linkedin = bool(_re.search(
        r'(?:linkedin\.com/in/|(?<!\w)in/)[\w\-]{3,}',
        resume_text, _re.IGNORECASE
    ))

    return {
        "location": {
            "status": "hit" if has_location else "miss",
            "msg": (
                "Geo-Searchability Verified: Location found. Workday and iCIMS "
                "prioritise regional candidates — this prevents your profile from "
                "being filtered out in location-based queries."
                if has_location else
                "Searchability Risk: No City/State detected. Workday, iCIMS, and "
                "Taleo all run location filters during initial screening — missing "
                "location can result in automatic exclusion from regional searches."
            ),
        },
        "contact_channels": {
            "status": "hit" if (has_email and has_phone) else "miss",
            "msg": (
                "Contact Complete: Email and phone detected. ATS systems like "
                "Greenhouse and Lever use these to auto-populate candidate profiles."
                if (has_email and has_phone) else
                "Incomplete Contact: Missing email or phone. ATS systems like "
                "Greenhouse and Lever require both for candidate profile creation."
            ),
        },
        "linkedin": {
            "status": "hit" if has_linkedin else "miss",
            "msg": (
                "LinkedIn Profile Detected: SmartRecruiters and Lever cross-reference "
                "LinkedIn profiles for candidate validation and enrichment."
                if has_linkedin else
                "LinkedIn Missing: SmartRecruiters and Lever recruiters routinely "
                "cross-check LinkedIn. Add your LinkedIn URL to enable profile "
                "enrichment and increase credibility."
            ),
        },
    }


def check_section_headings(resume_text: str) -> dict:
    res_low = resume_text.lower()
    
    has_std = {}
    for category, variants in _STANDARD_HEADINGS.items():
        has_std[category] = any(h in res_low for h in variants)
    
    has_nonstandard = any(h in res_low for h in _NONSTANDARD_HEADINGS)
    all_std = all(has_std.values())

    if all_std and not has_nonstandard:
        return {
            "status": "hit",
            "msg": (
                "Standard Structure: All major sections use ATS-recognised headings. "
                "Workday and Taleo can parse your resume without errors."
            ),
        }
    if not all_std:
        missing = [k for k, v in has_std.items() if not v]
        return {
            "status": "miss",
            "msg": (
                f"Missing Standard Headings: {', '.join(missing).title()} section(s) "
                "not found. Workday and Taleo require standard headings like "
                "'Experience', 'Education', 'Skills', 'Summary' to parse your resume "
                "correctly."
            ),
        }
    if has_nonstandard:
        return {
            "status": "miss",
            "msg": (
                "Non-Standard Headings Detected: Creative headings like 'Career Highlights' "
                "or 'My Journey' confuse Workday and Taleo parsers. Use standard ATS-compliant "
                "section names instead."
            ),
        }
    return {"status": "hit", "msg": "Structure validated."}


def check_dates(resume_text: str) -> dict:
    dates_found = _DATE_RE.findall(resume_text)
    count = len(dates_found)
    good = count >= 2

    return {
        "status": "hit" if good else "miss",
        "msg": (
            "Timeline Parsed: Chronological dates detected. Workday and Taleo use "
            "dates to auto-calculate total years of experience — accurate dates "
            "prevent mis-scoring of your seniority level."
            if good else
            "Date Format Issue: Insufficient or inconsistent dates. Workday and Taleo "
            "require chronological dates (e.g. 'Jan 2020 – Dec 2022') to parse your "
            "work history correctly."
        ),
    }


def check_education(resume_text: str, jd_text: str) -> dict:
    res_low = resume_text.lower()
    jd_low = jd_text.lower()

    has_edu = any(kw in res_low for kw in _DEGREE_KEYWORDS)
    edu_required = bool(_EDU_REQUIRED_RE.search(jd_low))
    edu_preferred = bool(_EDU_PREFERRED_RE.search(jd_low))

    if edu_required and not has_edu:
        return {
            "status": "miss",
            "msg": (
                "Education Hard Gate Risk: This role requires a degree, but none was "
                "detected in your resume. Taleo and Workday auto-reject candidates "
                "without required credentials — ensure your degree is clearly listed."
            ),
        }
    if edu_required and has_edu:
        return {
            "status": "hit",
            "msg": (
                "Education Hard Gate Cleared: Degree detected and the role requires "
                "one. This passes the binary education filter in Taleo and Workday."
            ),
        }
    if edu_preferred and has_edu:
        return {
            "status": "hit",
            "msg": (
                "Education Bonus: Degree detected and preferred by the JD. This adds "
                "positive weight in SmartRecruiters and iCIMS scoring."
            ),
        }
    if not has_edu:
        return {
            "status": "miss",
            "msg": (
                "Education Section Missing:No degree or education credentials detected. "
                "Even for senior roles, many ATS systems use education as a secondary "
                "verification filter — add your education section."
            ),
        }
    return {
        "status": "hit",
        "msg": (
            "Education Verified: Education credentials found. Satisfies basic "
            "HR compliance checks across all major ATS platforms."
        ),
    }


def check_quantified_impact(resume_text: str) -> dict:
    metrics_found = _METRIC_RE.findall(resume_text)
    count = len(metrics_found)
    good = count >= 3

    return {
        "status": "hit" if good else "miss",
        "msg": (
            f"Impact Signals Detected: {count} quantified achievements found "
            "(%, $, or numeric results). SmartRecruiters and Workday AI scoring "
            "weighs measurable outcomes heavily — this significantly boosts your rank."
            if good else
            f"Weak Impact Signals: Only {count} measurable result(s) found. "
            "Add metrics to your bullet points (e.g. 'Reduced load time by 40%', "
            "'Managed $2M budget') — Workday and SmartRecruiters AI scoring ranks "
            "quantified resumes 2–3 positions higher."
        ),
        "count": count,
    }


# Replace the check_keyword_placement function in diagnostics.py with this:

def check_keyword_placement(resume_text: str, jd_skills: set) -> dict:
    res_low = resume_text.lower()
    lines = res_low.split('\n')
    
    # Find summary section
    summary_start = -1
    summary_end = -1
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if any(h in line_stripped for h in ["professional summary", "summary", "profile", "objective"]):
            summary_start = i
            # Find where summary ends (next major section)
            for j in range(i + 1, min(i + 30, len(lines))):  # Look ahead max 30 lines
                next_line = lines[j].strip()
                if any(h in next_line for h in [
                    "experience", "work history", "employment", 
                    "education", "skills", "competencies", "certifications"
                ]) and len(next_line) < 50:  # Section headers are typically short
                    summary_end = j
                    break
            if summary_end == -1:
                summary_end = min(i + 15, len(lines))  # Default: 15 lines after header
            break
    
    # Find experience section
    exp_start = -1
    exp_end = len(lines)
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if any(h in line_stripped for h in ["professional experience", "work experience", "experience", "employment history"]):
            exp_start = i
            # Find where experience ends
            for j in range(i + 1, len(lines)):
                next_line = lines[j].strip()
                if any(h in next_line for h in [
                    "education", "certifications", "awards", "publications"
                ]) and len(next_line) < 50:
                    exp_end = j
                    break
            break
    
    # Extract text from sections
    summary_text = ""
    if summary_start != -1 and summary_end != -1:
        summary_text = '\n'.join(lines[summary_start:summary_end])
    
    exp_text = ""
    if exp_start != -1:
        exp_text = '\n'.join(lines[exp_start:exp_end])
    
    # Count skills in each section
    skills_in_summary = sum(1 for skill in jd_skills if skill.lower() in summary_text)
    skills_in_exp = sum(1 for skill in jd_skills if skill.lower() in exp_text)
    
    # Good placement = at least 3 skills in summary OR at least 5 in experience
    placement_ok = skills_in_summary >= 3 or skills_in_exp >= 5
    
    return {
        "status": "hit" if placement_ok else "miss",
        "msg": (
            f"Keyword Placement Strong: {skills_in_summary} key skill(s) in your "
            f"summary and {skills_in_exp} in your experience section. ATS systems "
            "weight keywords in Summary and Experience 2-3x higher than Skills lists."
            if placement_ok else
            "Keyword Placement Weak: Critical JD keywords appear only in your Skills "
            "section or not at all. Move key skills into your Summary and Experience "
            "bullet points — this is the single highest-impact score improvement."
        ),
        "summary_hits": skills_in_summary,
        "exp_hits": skills_in_exp,
    }


def check_title_alignment(resume_text: str, jd_text: str) -> dict:
    """Extract actual job title from JD robustly."""
    _LABEL_ONLY_RE = re.compile(
        r"^(job\s*description|job\s*title|role|position|title|duties"
        r"|about\s*the\s*role|about\s*us|overview|description|"
        r"duties\s*&\s*responsibilities|responsibilities)\s*:?\s*$",
        re.IGNORECASE,
    )
    _TITLE_SIGNALS = [
        "engineer", "developer", "manager", "analyst", "designer", "architect",
        "director", "lead", "specialist", "consultant", "coordinator", "officer",
        "associate", "scientist", "administrator", "executive", "head", "vp",
        "product", "software", "data", "senior", "junior", "staff", "principal",
    ]

    clean_title = ""
    jd_lines = [l.strip() for l in jd_text.split("\n") if l.strip()]

    # Pass 1: find first line that looks like a real job title
    for line in jd_lines[:8]:
        if _LABEL_ONLY_RE.match(line):
            continue
        stripped = re.sub(
            r"^(job\s*title|role|position|title)\s*:\s*", "", line, flags=re.IGNORECASE
        ).strip()
        if len(stripped.split()) <= 8:
            if any(signal in stripped.lower() for signal in _TITLE_SIGNALS):
                clean_title = stripped
                break

    # Pass 2: scan JD body for "of an embedded software engineer" pattern
    if not clean_title:
        _BODY_TITLE_RE = re.compile(
            r"(?:of an?|for an?|as an?|hiring an?|seeking an?)\s+"
            r"([A-Z][a-zA-Z\s/]+(?:engineer|developer|manager|analyst|"
            r"architect|designer|specialist|lead|director|scientist|consultant))",
            re.IGNORECASE,
        )
        m = _BODY_TITLE_RE.search(jd_text)
        if m:
            clean_title = m.group(1).strip()

    # Pass 3: standalone title pattern anywhere in first 500 chars
    if not clean_title:
        _STANDALONE_RE = re.compile(
            r"\b((?:senior|junior|lead|staff|principal|qa|embedded|software|"
            r"systems?|hardware|firmware|automation)\s+){0,3}"
            r"(?:engineer|developer|manager|analyst|architect|designer|scientist)\b",
            re.IGNORECASE,
        )
        m = _STANDALONE_RE.search(jd_text[:500])
        if m:
            clean_title = m.group(0).strip()

    if not clean_title:
        clean_title = "Target Role"

    jd_core = re.sub(r"[^a-zA-Z0-9\s]", "", clean_title).lower().strip()
    res_core = re.sub(r"[^a-zA-Z0-9\s]", "", resume_text.lower())
    jd_words = {w for w in jd_core.split() if len(w) > 2}
    res_words = set(res_core.split())
    overlap = jd_words & res_words
    title_match = len(overlap) >= max(1, len(jd_words) - 1) if jd_words else False

    return {
        "clean_title": clean_title,
        "status": "hit" if title_match else "miss",
        "msg": (
            f"Title Aligned: Your resume reflects the target role '{clean_title}'. "
            "Greenhouse and Lever rank candidates higher when the profile title "
            "matches the JD title exactly."
            if title_match else
            f"Title Gap: The role title '{clean_title}' isn't explicitly reflected "
            "in your resume. Add it to your summary or headline — Greenhouse and "
            "Lever use title matching as a primary relevance signal."
        ),
    }


def check_keyword_stuffing(stuffed_skills: list) -> dict:
    if stuffed_skills:
        return {
            "status": "miss",
            "msg": (
                f"Over-Optimisation Detected: '{stuffed_skills[0]}' and "
                f"{len(stuffed_skills) - 1} other skill(s) appear suspiciously often. "
                "Modern ATS platforms (SmartRecruiters, Workday) use NLP to detect "
                "keyword stuffing and penalise or flag affected resumes."
            ),
        }
    return {
        "status": "hit",
        "msg": (
            "Natural Keyword Density: No keyword stuffing detected. Your resume "
            "reads naturally, which passes NLP-based authenticity checks in "
            "SmartRecruiters and Workday AI scoring."
        ),
    }


def _find_next_section(text: str, start_pos: int) -> int:
    all_headings = [
        h for variants in _STANDARD_HEADINGS.values()
        for h in variants
    ]
    next_pos = len(text)
    for heading in all_headings:
        pos = text.find(heading, start_pos + 5)
        if pos != -1 and pos < next_pos:
            next_pos = pos
    return next_pos
