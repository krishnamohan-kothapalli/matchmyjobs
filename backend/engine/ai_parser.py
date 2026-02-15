# engine/ai_parser.py
# ─────────────────────────────────────────────────────────────────────────────
# All Claude API calls in one place.
#
# ENHANCEMENTS v3.0:
#   - Smart truncation (preserves beginning + end instead of hard cutoff)
#   - Configurable model via environment variable
#   - Better error context
#
# Three responsibilities:
#   1. extract_all()        — single API call extracts skills from BOTH
#                             JD and resume simultaneously, compares them,
#                             and parses JD metadata. Replaces ESCO database.
#   2. generate_suggestions() — actionable resume fixes from findings
#
# Why one call for extraction:
#   Claude can compare both documents in context and reason about
#   semantic equivalence (e.g. "HIL bench setup" == "hardware in the loop")
#   which two separate calls cannot do.
# ─────────────────────────────────────────────────────────────────────────────

import os
import json
import re
import logging
from anthropic import Anthropic

logger = logging.getLogger(__name__)

_client = None

# ENHANCED: Configurable model via environment variable
# Default: Haiku for cost efficiency
# Production: Set CLAUDE_MODEL=claude-sonnet-4-5-20250929 for better accuracy
_MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set. Add it to your .env file.")
        _client = Anthropic(api_key=api_key)
    return _client


def _clean_json(raw: str) -> str:
    """Strip markdown fences and whitespace from Claude's response."""
    raw = raw.strip()
    raw = re.sub(r"^```json\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"^```\s*",     "", raw, flags=re.MULTILINE)
    raw = raw.strip()
    return raw


def _smart_truncate(text: str, max_chars: int = 4000) -> str:
    """
    ENHANCED: Smart truncation that preserves beginning and end of document.
    
    Better than hard cutoff which might miss recent experience or important details.
    
    Strategy:
    - Keep first 60% (summary + early experience) 
    - Keep last 20% (recent experience, most important for scoring)
    - Skip middle 20% (older experience, less relevant)
    
    Args:
        text: Full document text
        max_chars: Maximum characters to keep
        
    Returns:
        Truncated text with beginning and end preserved
    """
    if len(text) <= max_chars:
        return text
    
    # Calculate split points
    first_part_size = int(max_chars * 0.6)
    last_part_size = int(max_chars * 0.2)
    
    # Extract parts
    first_part = text[:first_part_size]
    last_part = text[-last_part_size:]
    
    # Combine with ellipsis marker
    return (
        first_part + 
        "\n\n...[middle section truncated for length]...\n\n" + 
        last_part
    )


# ─────────────────────────────────────────────────────────────────────────────
# PROMPT 1 — Unified extraction
# One call, full picture. Extracts skills from both docs + JD metadata.
# ─────────────────────────────────────────────────────────────────────────────

_EXTRACT_PROMPT = """You are an expert ATS analyst and technical recruiter with deep knowledge across ALL industries and domains — software, embedded systems, automotive, aerospace, finance, healthcare, marketing, and more.

Analyse the job description and resume below. Return ONLY valid JSON with no explanation, no markdown, no code blocks.

Return exactly this structure:
{{
  "job_title": "exact job title extracted from JD",
  "seniority_level": "entry|mid|senior|management",
  "required_years": 0,
  "education_required": "none|associate|bachelor|master|phd",
  "education_preferred": "none|associate|bachelor|master|phd",

  "jd_required_skills": ["skill1", "skill2"],
  "jd_preferred_skills": ["skill1", "skill2"],
  "jd_responsibilities": ["resp1", "resp2"],

  "resume_skills": ["skill1", "skill2"],

  "matched_skills": ["skills present in BOTH — use the JD's version of the name"],
  "missing_skills": ["skills required by JD but NOT found in resume — be precise"],
  "bonus_skills": ["skills in resume that are preferred/nice-to-have in JD"],
  "extra_skills": ["skills in resume not mentioned in JD — may still add value"]
}}

Skill extraction rules:
- Extract ALL skills: hard skills, tools, technologies, frameworks, protocols, methodologies, domain terms, certifications
- Be domain-aware: for embedded roles extract protocols (CAN, J1939, SPI, I2C), testing methods (HIL, SIL), OS (RTOS, Linux), standards (MISRA, AUTOSAR)
- For software roles: languages, frameworks, cloud, DevOps, databases, testing
- For data roles: ML frameworks, statistical methods, data tools, platforms
- Treat semantic equivalents as matches: "HIL bench setup/troubleshooting" == "HIL testing" == "hardware in the loop"
- Treat synonym variants as matches: "C++" == "C plus plus", "Microsoft Azure" == "Azure", "GIT" == "Git"
- Use lowercase for all skill names
- Return [] never null for any array

CRITICAL - Years of Experience Extraction:
For required_years, extract the MINIMUM from any range:
- "3-6 years" → required_years: 3 (NOT 6)
- "5-8 years" → required_years: 5 (NOT 8)
- "3+ years" → required_years: 3
- "minimum 5 years" → required_years: 5
- If no years mentioned → required_years: 0
The minimum is used for hard gate filtering in ATS systems.

JOB DESCRIPTION:
{jd_text}

RESUME:
{resume_text}"""


def extract_all(jd_text: str, resume_text: str) -> dict:
    """
    Single Claude call that extracts skills from both JD and resume,
    performs matching with semantic understanding, and returns structured data.
    
    ENHANCED: Uses smart truncation to preserve both beginning and end of documents.
    
    Falls back to empty structure on failure — engine continues with spaCy only.
    """
    try:
        client   = _get_client()
        
        # ENHANCED: Smart truncation instead of hard cutoff
        truncated_jd = _smart_truncate(jd_text, 4000)
        truncated_resume = _smart_truncate(resume_text, 4000)
        
        response = client.messages.create(
            model=_MODEL,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": _EXTRACT_PROMPT.format(
                    jd_text=truncated_jd,
                    resume_text=truncated_resume,
                )
            }]
        )
        raw    = _clean_json(response.content[0].text)
        parsed = json.loads(raw)
        
        logger.info(
            "AI extraction complete (model=%s): %d matched, %d missing",
            _MODEL,
            len(parsed.get("matched_skills", [])),
            len(parsed.get("missing_skills", [])),
        )
        return parsed

    except Exception as e:
        logger.warning("AI extraction failed (model=%s), using spaCy fallback: %s", _MODEL, e)
        # ENHANCED: Log more context for debugging
        logger.debug("JD length: %d, Resume length: %d", len(jd_text), len(resume_text))
        return _empty_extraction()


def _empty_extraction() -> dict:
    return {
        "job_title":           "",
        "seniority_level":     "mid",
        "required_years":      0,
        "education_required":  "none",
        "education_preferred": "none",
        "jd_required_skills":  [],
        "jd_preferred_skills": [],
        "jd_responsibilities": [],
        "resume_skills":       [],
        "matched_skills":      [],
        "missing_skills":      [],
        "bonus_skills":        [],
        "extra_skills":        [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# PROMPT 2 — Improvement suggestions
# ─────────────────────────────────────────────────────────────────────────────

_SUGGESTIONS_PROMPT = """You are an expert resume coach and ATS specialist.

A candidate scored {score}/100 for this role: {job_title}

MISSING REQUIRED SKILLS: {missing}
WEAK AREAS DETECTED: {weak_areas}
ALL REQUIRED SKILLS: {required_skills}

RESUME:
{resume_text}

Provide exactly 5 specific, actionable improvements prioritised by ATS impact.
Return ONLY valid JSON, no explanation:
{{
  "suggestions": [
    {{
      "area": "exact section name (e.g. Professional Summary, Skills Section, Experience Bullets)",
      "priority": "high|medium|low",
      "issue": "one sentence describing the specific gap or problem",
      "fix": "exact text the candidate can copy-paste — a rewritten bullet, sentence, or skill addition",
      "impact": "one sentence explaining the ATS score improvement"
    }}
  ]
}}

Rules:
- Prioritise missing required skills first — suggest exact wording to add them
- Fixes must be copy-paste ready, not vague advice like "add more details"
- At least 2 fixes should be specific Experience bullet rewrites with metrics
- At least 1 fix should address keyword placement in Summary
- Keep each fix under 60 words
- Be domain-specific — use exact terminology from the JD"""


def generate_suggestions(
    resume_text:    str,
    extraction:     dict,
    score:          float,
    weak_areas:     list,
) -> list:
    """
    Generate specific copy-paste resume fixes based on extraction findings.
    
    ENHANCED: Uses smart truncation for long resumes.
    
    Returns list of suggestion dicts. Empty list on failure.
    """
    try:
        client = _get_client()

        missing_str  = ", ".join(extraction.get("missing_skills", [])[:10]) or "none"
        req_str      = ", ".join(extraction.get("jd_required_skills", [])[:12]) or "none"
        title        = extraction.get("job_title", "target role")
        weak_str     = ", ".join(weak_areas) if weak_areas else "keyword placement, quantified impact"

        # ENHANCED: Smart truncation for long resumes
        truncated_resume = _smart_truncate(resume_text, 3500)

        response = client.messages.create(
            model=_MODEL,
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": _SUGGESTIONS_PROMPT.format(
                    score=score,
                    job_title=title,
                    missing=missing_str,
                    weak_areas=weak_str,
                    required_skills=req_str,
                    resume_text=truncated_resume,
                )
            }]
        )

        raw         = _clean_json(response.content[0].text)
        parsed      = json.loads(raw)
        suggestions = parsed.get("suggestions", [])
        
        logger.info("Generated %d suggestions (model=%s)", len(suggestions), _MODEL)
        return suggestions

    except Exception as e:
        logger.warning("AI suggestions failed (model=%s): %s", _MODEL, e)
        return []
