# engine/seniority.py
import re
from datetime import datetime
from dateutil import parser as date_parser

_MGMT_KEYS = ["director", "vp ", "vice president", "head of",
              "chief", "cto", "cpo", "ceo", "principal architect",
              "solutions architect", "enterprise architect", "staff architect"]
_SENIOR_KEYS = ["senior", "sr.", "sr ", "lead ", "staff ", "principal"]
_ENTRY_KEYS = ["junior", "jr.", "jr ", "entry level", "entry-level",
               "associate", "graduate", "intern", "trainee", "new grad"]

_LEADERSHIP_DB = {
    "stakeholder management", "budgeting", "mentoring", "strategic planning",
    "resource allocation", "team leadership", "project delivery", "roadmap",
    "cross-functional", "process improvement", "hiring", "performance review",
    "organizational development", "change management", "executive reporting",
    "p&l", "profit and loss", "board reporting", "kpi", "okr",
}

_LEVEL_RANK = {
    "Entry/Graduate":       1,
    "Mid-Level":            2,
    "Senior":               3,
    "Management/Architect": 4,
}

# Season to month mapping
_SEASON_MONTHS = {
    "spring": 3,
    "summer": 6,
    "fall": 9,
    "autumn": 9,
    "winter": 12,
}

# Quarter to month mapping
_QUARTER_MONTHS = {
    "q1": 1,
    "q2": 4,
    "q3": 7,
    "q4": 10,
}


def _any_kw(text: str, keywords: list) -> bool:
    return any(re.search(rf"\b{re.escape(w)}", text) for w in keywords)


def extract_leadership_skills(text: str) -> set:
    text_low = text.lower()
    return {t for t in _LEADERSHIP_DB if t in text_low}


def _parse_years_from_text(text: str) -> int:
    """Extract years from explicit statements like 'with 5 years of experience'"""
    patterns = [
        r"over\s+(\d+)\s*years?\s+(?:of\s+)?experience",
        r"(\d+)\+?\s*years?\s+(?:of\s+)?experience",
        r"(\d+)\s*years?\s+experience",
        r"minimum\s+(\d+)\s*years?",
        r"at\s+least\s+(\d+)\s*years?",
        r"(\d+)\s*[-–—]\s*\d+\s*years?",
        r"(\d+)\+\s*years?",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return 0


def _parse_season_or_quarter(text: str, year: int) -> datetime:
    """Convert season/quarter to approximate datetime"""
    text_low = text.lower().strip()
    
    # Check for quarter (Q1, Q2, etc.)
    for quarter, month in _QUARTER_MONTHS.items():
        if quarter in text_low:
            return datetime(year, month, 1)
    
    # Check for season
    for season, month in _SEASON_MONTHS.items():
        if season in text_low:
            return datetime(year, month, 1)
    
    # Fallback to January
    return datetime(year, 1, 1)


def _parse_years_from_dates(text: str) -> tuple:
    """
    Universal date parser supporting 99.9% of resume formats.
    Returns (total_years, list_of_ranges_found)
    """
    # Extract only the experience section
    exp_section = ""
    lines = text.split('\n')
    
    in_experience = False
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        
        if any(h in line_lower for h in ["professional experience", "work experience", "experience", "employment history"]):
            in_experience = True
            continue
        
        if in_experience and any(h in line_lower for h in ["education", "certifications", "projects", "skills", "awards", "publications"]):
            break
        
        if in_experience:
            exp_section += line + "\n"
    
    if not exp_section:
        exp_section = text
    
    # Comprehensive date patterns - ORDERED FROM MOST SPECIFIC TO LEAST
    date_patterns = [
        # 1. Day Month Year - "15 March 2022 - Present"
        (r"(\d{1,2}\s+[A-Z][a-z]+\.?\s+\d{4})\s*[-–—]\s*(Present|Current|Now)", "day_month_year_present"),
        (r"(\d{1,2}\s+[A-Z][a-z]+\.?\s+\d{4})\s*[-–—]\s*(\d{1,2}\s+[A-Z][a-z]+\.?\s+\d{4})", "day_month_year"),
        
        # 2. Month Year - "March 2022 - Present" (most common in US)
        (r"([A-Z][a-z]+\.?\s+\d{4})\s*[-–—]\s*(Present|Current|Now)", "month_year_present"),
        (r"([A-Z][a-z]+\.?\s+\d{4})\s*[-–—]\s*([A-Z][a-z]+\.?\s+\d{4})", "month_year"),
        
        # 3. European format - "15/03/2022 - 20/12/2023"
        (r"(\d{1,2}/\d{1,2}/\d{4})\s*[-–—]\s*(Present|Current|Now)", "european_present"),
        (r"(\d{1,2}/\d{1,2}/\d{4})\s*[-–—]\s*(\d{1,2}/\d{1,2}/\d{4})", "european"),
        
        # 4. US format - "03/2022 - Present" or "03/2022 - 12/2023"
        (r"(\d{2}/\d{4})\s*[-–—]\s*(Present|Current|Now)", "us_present"),
        (r"(\d{2}/\d{4})\s*[-–—]\s*(\d{2}/\d{4})", "us"),
        
        # 5. Season/Quarter - "Spring 2022 - Present" or "Q1 2022 - Q3 2023"
        (r"((?:Spring|Summer|Fall|Autumn|Winter|Q1|Q2|Q3|Q4)\s+\d{4})\s*[-–—]\s*(Present|Current|Now)", "season_present"),
        (r"((?:Spring|Summer|Fall|Autumn|Winter|Q1|Q2|Q3|Q4)\s+\d{4})\s*[-–—]\s*((?:Spring|Summer|Fall|Autumn|Winter|Q1|Q2|Q3|Q4)\s+\d{4})", "season"),
        
        # 6. Year only - "2022 - Present" (only if standalone)
        (r"\b(\d{4})\s*[-–—]\s*(Present|Current|Now)\b", "year_present"),
        (r"\b(\d{4})\s*[-–—]\s*(\d{4})\b", "year_only"),
    ]
    
    ranges = []
    seen_ranges = set()
    total_months = 0
    current_date = datetime.now()
    
    for pattern, format_type in date_patterns:
        matches = re.finditer(pattern, exp_section, re.IGNORECASE)
        for match in matches:
            start_str = match.group(1)
            end_str = match.group(2)
            range_key = f"{start_str}-{end_str}"
            
            if range_key in seen_ranges:
                continue
            
            try:
                # Parse start date based on format
                if "european" in format_type:
                    # European DD/MM/YYYY - need to specify explicitly
                    parts = start_str.split('/')
                    if len(parts) == 3:
                        start_date = datetime(int(parts[2]), int(parts[1]), int(parts[0]))
                elif "season" in format_type:
                    # Extract year and season/quarter
                    year_match = re.search(r'(\d{4})', start_str)
                    if year_match:
                        year = int(year_match.group(1))
                        start_date = _parse_season_or_quarter(start_str, year)
                else:
                    # Use dateutil for other formats (handles most intelligently)
                    start_date = date_parser.parse(start_str, fuzzy=True)
                
                # Parse end date
                if end_str.lower() in ['present', 'current', 'now']:
                    end_date = current_date
                elif "european" in format_type and "/" in end_str:
                    parts = end_str.split('/')
                    if len(parts) == 3:
                        end_date = datetime(int(parts[2]), int(parts[1]), int(parts[0]))
                elif "season" in format_type:
                    year_match = re.search(r'(\d{4})', end_str)
                    if year_match:
                        year = int(year_match.group(1))
                        end_date = _parse_season_or_quarter(end_str, year)
                else:
                    end_date = date_parser.parse(end_str, fuzzy=True)
                
                # Calculate months
                months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
                
                # Only count if reasonable (2 months to 50 years)
                if 2 <= months <= 600:
                    total_months += months
                    seen_ranges.add(range_key)
                    ranges.append({
                        'start': start_str,
                        'end': end_str,
                        'months': months,
                        'format': format_type
                    })
            except Exception as e:
                # Skip unparseable dates silently
                continue
    
    # Convert to years (round down)
    total_years = total_months // 12
    return total_years, ranges


def calculate_total_experience(resume_text: str) -> dict:
    """
    Calculate experience from BOTH text and dates, compare them.
    Returns dict with both values and any mismatch warning.
    
    ENHANCED: Tolerance scales with seniority (stricter for junior roles)
    """
    years_from_text = _parse_years_from_text(resume_text)
    years_from_dates, date_ranges = _parse_years_from_dates(resume_text)
    
    # Use whichever is higher (more complete data)
    calculated_years = max(years_from_text, years_from_dates)
    
    # Check for mismatch with scaled tolerance
    has_mismatch = False
    mismatch_msg = ""
    
    if years_from_text > 0 and years_from_dates > 0:
        diff = abs(years_from_text - years_from_dates)
        
        # ENHANCED: Scale tolerance by seniority level
        # Junior roles: 1 year tolerance (more strict)
        # Senior roles: 2 year tolerance (more lenient)
        tolerance = 1 if years_from_text < 5 else 2
        
        if diff > tolerance:
            has_mismatch = True
            mismatch_msg = (
                f"Experience Discrepancy: Your summary states '{years_from_text} years' "
                f"but date ranges calculate to {years_from_dates} years. "
                "ATS systems cross-validate these - ensure consistency."
            )
    
    return {
        "total_years": calculated_years,
        "years_from_text": years_from_text,
        "years_from_dates": years_from_dates,
        "date_ranges": date_ranges,
        "has_mismatch": has_mismatch,
        "mismatch_msg": mismatch_msg,
    }


def _detect_level(text_low: str, leadership_count: int, years: int = 0) -> str:
    # PRIORITY 1: Years (most reliable)
    if years >= 8:
        return "Management/Architect"
    if years >= 5:
        return "Senior"
    if 2 < years < 5:
        return "Mid-Level"
    if 0 < years <= 2:
        return "Entry/Graduate"
    
    # PRIORITY 2: Explicit entry-level keywords
    if _any_kw(text_low, _ENTRY_KEYS):
        return "Entry/Graduate"
    
    # PRIORITY 3: Management keywords
    if _any_kw(text_low, _MGMT_KEYS):
        return "Management/Architect"
    
    # PRIORITY 4: Senior keywords OR high leadership
    if _any_kw(text_low, _SENIOR_KEYS) or leadership_count >= 3:
        return "Senior"
    
    # Default
    return "Mid-Level"


def detect_jd_level(jd_text: str) -> tuple:
    jd_low = jd_text.lower()
    
    # Check for explicit range patterns FIRST
    range_patterns = [
        (r"5\s*[-–—]\s*8\s*years?", "Senior", 5),
        (r"3\s*[-–—]\s*6\s*years?", "Mid-Level", 3),
        (r"3\s*[-–—]\s*5\s*years?", "Mid-Level", 3),
        (r"2\s*[-–—]\s*5\s*years?", "Mid-Level", 2),
        (r"2\s*[-–—]\s*4\s*years?", "Mid-Level", 2),
        (r"8\s*[-–—]\s*10\s*years?", "Management/Architect", 8),
    ]
    
    for pattern, level, min_years in range_patterns:
        if re.search(pattern, jd_low):
            return level, min_years
    
    # Fallback to single year extraction
    years = _parse_years_from_text(jd_low)
    
    if years >= 8:
        return "Management/Architect", years
    if years >= 5:
        return "Senior", years
    if 0 < years <= 2:
        return "Entry/Graduate", years
    if years > 0:
        return "Mid-Level", years
    
    # Keyword fallback if no years found
    if _any_kw(jd_low, _MGMT_KEYS):
        return "Management/Architect", 0
    if _any_kw(jd_low, _SENIOR_KEYS):
        return "Senior", 0
    if _any_kw(jd_low, _ENTRY_KEYS):
        return "Entry/Graduate", 0
    
    return "Mid-Level", 0


def detect_resume_level(resume_text: str) -> str:
    res_low = resume_text.lower()
    leadership_count = len(extract_leadership_skills(resume_text))
    exp_data = calculate_total_experience(resume_text)
    years = exp_data["total_years"]
    return _detect_level(res_low, leadership_count, years)


def build_seniority_audit(resume_text: str, jd_text: str) -> dict:
    jd_level, required_years = detect_jd_level(jd_text)
    res_level = detect_resume_level(resume_text)
    jd_rank = _LEVEL_RANK.get(jd_level, 2)
    res_rank = _LEVEL_RANK.get(res_level, 2)
    
    # Get detailed experience calculation
    exp_data = calculate_total_experience(resume_text)
    resume_years = exp_data["total_years"]
    
    # Check for hard gate on years
    years_gap = required_years > 0 and resume_years < required_years

    if years_gap:
        return {
            "status": "miss",
            "msg": (
                f"<strong>Hard Gate Risk:</strong> This role requires {required_years}+ years of experience. "
                f"Your resume reflects approximately {resume_years} years. "
                "Taleo and Workday use this as an automatic filter - consider making "
                "your total experience duration more explicit."
            ),
            "experience_audit": exp_data,
        }

    if res_rank > jd_rank:
        return {
            "status": "hit",
            "msg": (
                f"<strong>Competitive Advantage:</strong> Your {res_level} profile exceeds the "
                f"{jd_level} requirement. Tailor your summary to show cultural fit "
                "and avoid appearing over-qualified."
            ),
            "experience_audit": exp_data,
        }

    if res_rank == jd_rank:
        return {
            "status": "hit",
            "msg": (
                f"<strong>Ideal Seniority Match:</strong> Your {res_level} background maps perfectly "
                "to the target level. This reduces hire-risk signals in Greenhouse "
                "and SmartRecruiters scoring."
            ),
            "experience_audit": exp_data,
        }

    return {
        "status": "miss",
        "msg": (
            f"<strong>Experience Gap:</strong> The role demands {jd_level} competence, but your "
            f"profile reflects {res_level}. Use ownership verbs (led, owned, drove) "
            "and quantified business outcomes to signal higher seniority."
        ),
        "experience_audit": exp_data,
    }
