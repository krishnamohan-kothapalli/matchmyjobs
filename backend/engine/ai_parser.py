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
        logger.warning("AI extraction failed (model=%s), attempting semantic fallback: %s", _MODEL, e)
        logger.debug("JD length: %d, Resume length: %d", len(jd_text), len(resume_text))
        # BUG 5 FIX: Instead of returning empty extraction (which gives 0/30 score),
        # run a deterministic semantic skill matcher as fallback.
        return _semantic_fallback(jd_text, resume_text)



def _semantic_fallback(jd_text: str, resume_text: str) -> dict:
    """
    BUG 5 FIX: Deterministic semantic skill matcher used when AI extraction fails.

    Instead of returning all zeros, this function:
    1. Extracts skill tokens from the JD
    2. Checks the resume for each skill using synonym expansion
    3. Returns a structured extraction dict that score_keyword_match can use

    This ensures a meaningful score even without API access.
    """
    resume_lower = resume_text.lower()
    jd_lower = jd_text.lower()

    # Skill synonym map for semantic matching
    SYNONYMS: dict = {
        "test automation":    ["automated test", "automation framework", "automated testing", "automation suite"],
        "qa testing":         ["quality assurance", "quality gates", "qa engineer", "sdet", "quality engineering"],
        "manual testing":     ["manual test", "manual and automated", "test cases", "test plans", "test execution"],
        "web testing":        ["web-based application", "web application", "frontend testing", "ui testing"],
        "mobile testing":     ["mobile application", "android testing", "ios testing", "mobile app"],
        "ci/cd pipelines":    ["ci/cd", "jenkins", "continuous integration", "continuous delivery", "github actions"],
        "ci/cd":              ["jenkins", "continuous integration", "continuous delivery", "pipelines"],
        "playwright":         ["playwright"],
        "selenium":           ["selenium"],
        "cypress":            ["cypress"],
        "appium":             ["appium"],
        "javascript":         ["javascript", " js ", "ecmascript"],
        "typescript":         ["typescript", " ts "],
        "node.js":            ["node.js", "nodejs", "node js"],
        "next.js":            ["next.js", "nextjs"],
        "react":              ["react", "reactjs"],
        "python":             ["python"],
        "java":               ["java"],
        "sql":                ["sql"],
        "api testing":        ["rest assured", "api test", "postman", "karate dsl", "api automation"],
        "rest api":           ["rest assured", "restful", "rest api"],
        "docker":             ["docker", "containerization"],
        "kubernetes":         ["kubernetes", "k8s"],
        "aws":                ["amazon web services", "aws", " ec2 ", " s3 ", "lambda"],
        "agile":              ["agile", "scrum", "sprint", "kanban"],
        "git":                ["git", "github", "gitlab", "bitbucket"],
        "ai testing tools":   ["ai testing", "ai-powered test", "cursor", "copilot test", "llm test"],
        "cursor":             ["cursor"],
        "bdd":                ["bdd", "cucumber", "behave", "gherkin", "behavior driven"],
    }

    def _skill_in_resume(skill: str) -> bool:
        """Check if skill or any synonym appears in resume."""
        if skill in resume_lower:
            return True
        for syn in SYNONYMS.get(skill, []):
            if syn in resume_lower:
                return True
        return False

    # Extract required skills from JD using simple tokenization
    import re as _re_local
    skill_patterns = [
        r"[-*\u2022]\s*([^,\r\n]{3,60}?)(?:\r?\n|,|$)",
        r"experience (?:with|in)\s+([^,\r\n]{3,40})",
        r"knowledge of\s+([^,\r\n]{3,40})",
        r"familiarity with\s+([^,\r\n]{3,40})",
        r"expertise in\s+([^,\r\n]{3,40})",
    ]
    raw_skills = set()
    for pat in skill_patterns:
        for m in _re_local.finditer(pat, jd_lower, _re_local.IGNORECASE):
            token = m.group(1).strip().strip(".,;:")
            if 3 <= len(token) <= 50:
                raw_skills.add(token)

    # Also check if known skills from SYNONYMS appear in JD
    jd_required = []
    for skill in SYNONYMS.keys():
        if skill in jd_lower or any(s in jd_lower for s in SYNONYMS[skill]):
            jd_required.append(skill)

    if not jd_required:
        jd_required = list(raw_skills)[:20]

    # Deduplicate
    jd_required = list(dict.fromkeys(jd_required))

    matched = [s for s in jd_required if _skill_in_resume(s)]
    missing = [s for s in jd_required if not _skill_in_resume(s)]

    logger.info(
        "Semantic fallback: %d required skills, %d matched, %d missing",
        len(jd_required), len(matched), len(missing)
    )

    base = _empty_extraction()
    base.update({
        "jd_required_skills": jd_required,
        "matched_skills": matched,
        "missing_skills": missing,
    })
    return base


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

# ─────────────────────────────────────────────────────────────────────────────
# PROMPT 2 — Improvement suggestions
# ─────────────────────────────────────────────────────────────────────────────

_SUGGESTIONS_PROMPT = """You are an expert resume writer and ATS specialist. Your job is to rewrite parts of this candidate's resume so they score higher when analysed against the job description.

ROLE APPLIED FOR: {job_title}
CURRENT ATS SCORE: {score}/100
MISSING REQUIRED SKILLS: {missing}
MATCHED SKILLS: {matched}
JD RESPONSIBILITIES: {responsibilities}
WEAK AREAS: {weak_areas}

ACTUAL RESUME TEXT:
{resume_text}

JOB DESCRIPTION:
{jd_text}

Generate exactly 5 suggestions. Each suggestion must contain a READY-TO-USE rewrite — not advice, but the actual new text the candidate can copy directly into their resume.

Return ONLY valid JSON, no explanation:
{{
  "suggestions": [
    {{
      "area": "exact section (Professional Summary | Skills Section | Experience - [Company Name] | Education)",
      "priority": "high|medium|low",
      "issue": "one sentence: what specific gap this fixes",
      "original": "the exact current text from their resume being replaced (or 'N/A - new addition')",
      "fix": "the complete replacement text, ready to copy-paste into the resume as-is",
      "score_impact": "which score component this improves and by roughly how much (e.g. +5-8pts Keyword Match)"
    }}
  ]
}}

STRICT RULES for the "fix" field:
1. SUMMARY rewrite: Write a complete 2-3 sentence summary that naturally includes the missing skills and mirrors JD language
2. SKILLS addition: List the exact skill names from the JD that are missing — use the JD's exact terminology
3. EXPERIENCE bullet rewrites: Rewrite 2-3 actual bullets from their resume, adding missing keywords and metrics. Use their real job title and context, just add the keywords naturally
4. Keep each fix under 80 words
5. Never say "add X here" or "consider adding" — write the actual content
6. Use exact JD terminology — if JD says "CI/CD pipelines" write "CI/CD pipelines" not "deployment automation"
7. If a skill is missing from their resume, show how to naturally work it into existing experience context"""


def generate_suggestions(
    resume_text:    str,
    jd_text:        str,
    extraction:     dict,
    score:          float,
    weak_areas:     list,
) -> list:
    """
    Generate specific copy-paste resume fixes based on extraction findings.
    Passes full resume + JD context so Claude can rewrite actual content.
    Returns list of suggestion dicts. Falls back to rule-based if AI fails.
    """
    try:
        client = _get_client()

        missing_str       = ", ".join(extraction.get("missing_skills", [])[:12]) or "none"
        matched_str       = ", ".join(extraction.get("matched_skills", [])[:10]) or "none"
        responsibilities  = "; ".join(extraction.get("jd_responsibilities", [])[:5]) or "none"
        title             = extraction.get("job_title", "target role")
        weak_str          = ", ".join(weak_areas) if weak_areas else "keyword placement"

        truncated_resume  = _smart_truncate(resume_text, 3000)
        truncated_jd      = _smart_truncate(jd_text, 2000)

        response = client.messages.create(
            model=_MODEL,
            max_tokens=3000,
            messages=[{
                "role": "user",
                "content": _SUGGESTIONS_PROMPT.format(
                    score=score,
                    job_title=title,
                    missing=missing_str,
                    matched=matched_str,
                    responsibilities=responsibilities,
                    weak_areas=weak_str,
                    resume_text=truncated_resume,
                    jd_text=truncated_jd,
                )
            }]
        )

        raw         = _clean_json(response.content[0].text)
        parsed      = json.loads(raw)
        suggestions = parsed.get("suggestions", [])

        if not suggestions:
            logger.warning("AI returned no suggestions, using fallback")
            return _generate_fallback_suggestions(extraction, weak_areas, score)

        logger.info("Generated %d suggestions (model=%s)", len(suggestions), _MODEL)
        return suggestions

    except Exception as e:
        logger.warning("AI suggestions failed (model=%s): %s", _MODEL, e)
        return _generate_fallback_suggestions(extraction, weak_areas, score)


def _generate_fallback_suggestions(extraction: dict, weak_areas: list, score: float) -> list:
    """Generate rule-based suggestions when AI fails."""
    suggestions = []
    
    missing_skills = extraction.get("missing_skills", [])
    matched_skills = extraction.get("matched_skills", [])
    
    # Suggestion 1: Missing skills (highest priority)
    if missing_skills:
        top_missing = missing_skills[:5]
        suggestions.append({
            "area": "Skills Section",
            "priority": "high",
            "issue": f"Resume is missing {len(missing_skills)} required skills from the job description",
            "fix": f"Add these skills to your Skills section: {', '.join(top_missing)}. Then weave them into your experience bullets with specific examples.",
            "impact": f"Each missing skill reduces your ATS score. Adding these could increase your score by 5-15 points."
        })
    
    # Suggestion 2: Keyword placement
    if "keyword placement" in str(weak_areas).lower():
        if matched_skills:
            top_skills = matched_skills[:3]
            skills_text = ', '.join(top_skills)
            suggestions.append({
                "area": "Professional Summary",
                "priority": "high",
                "issue": "Key skills are only in your Skills section, not in your summary or experience",
                "fix": f"Add this to your Professional Summary: 'Experienced professional with expertise in {skills_text}, delivering impactful solutions in [your domain].'",
                "impact": "ATS systems weight keywords in your Summary 2-3x higher than in a Skills list. This single change could boost your score by 5-10 points."
            })
    
    # Suggestion 3: Quantify achievements
    if "quantified" in str(weak_areas).lower() or "impact" in str(weak_areas).lower():
        suggestions.append({
            "area": "Experience Bullets",
            "priority": "high",
            "issue": "Experience bullets lack measurable results and metrics",
            "fix": "Rewrite 3-5 bullets to include numbers. Examples: 'Improved system performance by 40%', 'Managed team of 8 engineers', 'Reduced costs by $250K annually', 'Delivered project 3 weeks ahead of schedule'",
            "impact": "Resumes with quantified achievements score 15-20% higher in ATS systems. Recruiters spend 2x longer reviewing resumes with metrics."
        })
    
    # Suggestion 4: Section structure
    if "section" in str(weak_areas).lower() or "heading" in str(weak_areas).lower():
        suggestions.append({
            "area": "Document Structure",
            "priority": "medium",
            "issue": "Section headings may not be ATS-friendly or are missing standard sections",
            "fix": "Use these exact headings in this order: 'Professional Summary', 'Professional Experience', 'Education', 'Skills', 'Certifications' (if applicable). Remove creative headings like 'My Journey' or 'About Me'.",
            "impact": "ATS systems can't parse non-standard headings, causing your content to be missed. Standard headings ensure proper parsing."
        })
    
    # Suggestion 5: Generic improvement
    suggestions.append({
        "area": "Overall Resume",
        "priority": "medium",
        "issue": "Resume doesn't mirror job description language closely enough",
        "fix": "Use the exact phrases from the job description. If they say 'project management', use 'project management' (not 'managed projects'). If they say 'cross-functional collaboration', use those exact words.",
        "impact": "ATS systems do literal keyword matching. Using exact JD terminology can increase your score by 10-15 points."
    })
    
    logger.info("Generated %d fallback suggestions", len(suggestions))
    return suggestions[:5]  # Return max 5
