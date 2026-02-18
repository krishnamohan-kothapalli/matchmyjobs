# optimizer.py
# ═══════════════════════════════════════════════════════════════════════════
# Resume Optimizer — rewrites resume to score 80+ against a JD
#
# Flow:
#   1. Claude rewrites resume using extraction data + JD context
#   2. Score the rewrite with the same engine
#   3. If score < 80 and attempts < 2, do one more pass
#   4. Generate DOCX from final text
#   5. Return optimized text + new score + DOCX as base64
# ═══════════════════════════════════════════════════════════════════════════

import os
import re
import json
import base64
import logging
import tempfile
from anthropic import Anthropic
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

logger = logging.getLogger(__name__)

_client = None
_MODEL  = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        _client = Anthropic(api_key=api_key)
    return _client


# ─────────────────────────────────────────────────────────────────────────────
# REWRITE PROMPT
# ─────────────────────────────────────────────────────────────────────────────

_REWRITE_PROMPT = """You are an expert resume writer. Rewrite the candidate's resume to maximize ATS score for the target job.

TARGET JOB: {job_title}
MISSING SKILLS TO ADD: {missing_skills}
MATCHED SKILLS TO EMPHASIZE: {matched_skills}
JD RESPONSIBILITIES: {responsibilities}
CURRENT SCORE: {current_score}/100 — target is 80+

ORIGINAL RESUME:
{resume_text}

JOB DESCRIPTION:
{jd_text}

REWRITE RULES:
1. Preserve ALL real experience, dates, companies, education — never fabricate
2. Add missing skills ONLY where they genuinely fit the candidate's background
3. Use EXACT JD terminology — if JD says "CI/CD pipelines" use that exact phrase
4. Move key skills into Summary and first bullet of each role (ATS weights these 3x)
5. Rewrite weak bullets to include metrics where context allows
6. Add a Skills section if missing, listing all matched + addable missing skills
7. Keep the same overall structure and length — do not add fictional jobs
8. Preserve the candidate's voice — no robotic corporate-speak

Return ONLY the rewritten resume text, no commentary, no markdown headers, no explanation.
Start directly with the candidate's name."""


def rewrite_resume(
    resume_text:  str,
    jd_text:      str,
    extraction:   dict,
    current_score: float,
) -> str:
    """Call Claude to rewrite the resume for better ATS match."""
    client = _get_client()

    missing  = ", ".join(extraction.get("missing_skills", [])[:15]) or "none"
    matched  = ", ".join(extraction.get("matched_skills", [])[:10]) or "none"
    resp_str = "; ".join(extraction.get("jd_responsibilities", [])[:5]) or "none"
    title    = extraction.get("job_title", "target role")

    # Smart truncate
    def _trunc(t, n=4000):
        return t if len(t) <= n else t[:int(n*0.7)] + "\n...\n" + t[-int(n*0.2):]

    response = client.messages.create(
        model=_MODEL,
        max_tokens=4000,
        messages=[{
            "role": "user",
            "content": _REWRITE_PROMPT.format(
                job_title=title,
                missing_skills=missing,
                matched_skills=matched,
                responsibilities=resp_str,
                current_score=round(current_score),
                resume_text=_trunc(resume_text, 4000),
                jd_text=_trunc(jd_text, 2500),
            )
        }]
    )
    return response.content[0].text.strip()


# ─────────────────────────────────────────────────────────────────────────────
# DOCX GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def _add_horizontal_rule(doc):
    """Add a thin green horizontal line."""
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '6')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), '00C896')
    pBdr.append(bottom)
    pPr.append(pBdr)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after  = Pt(4)
    return p


def _set_font(run, bold=False, size=11, color=None):
    run.font.name = 'Calibri'
    run.font.size = Pt(size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)


def _is_section_heading(line: str) -> bool:
    """Detect common resume section headings."""
    headings = {
        'experience', 'work experience', 'professional experience',
        'education', 'skills', 'technical skills', 'summary',
        'professional summary', 'objective', 'certifications',
        'projects', 'achievements', 'awards', 'publications',
        'volunteer', 'languages', 'interests', 'references',
        'contact', 'profile',
    }
    clean = line.strip().rstrip(':').lower()
    return clean in headings or (len(clean) < 40 and clean.upper() == line.strip().rstrip(':'))


def _is_bullet(line: str) -> bool:
    return bool(re.match(r'^[\•\-\*\·▪►]\s+', line.strip()))


def generate_docx(resume_text: str, candidate_name: str = "") -> bytes:
    """
    Convert plain resume text to a clean, ATS-friendly DOCX.
    Returns bytes of the DOCX file.
    """
    doc = Document()

    # Page margins — 0.75 inch all round
    for section in doc.sections:
        section.top_margin    = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin   = Inches(0.85)
        section.right_margin  = Inches(0.85)

    # Default paragraph spacing
    from docx.oxml.ns import qn as _qn
    style = doc.styles['Normal']
    style.font.name = 'Calibri'
    style.font.size = Pt(11)

    lines = resume_text.split('\n')
    first_line = True

    for raw_line in lines:
        line = raw_line.rstrip()

        # Blank line → small spacer
        if not line.strip():
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after  = Pt(3)
            continue

        # First non-blank line = candidate name
        if first_line:
            first_line = False
            p   = doc.add_paragraph()
            run = p.add_run(line.strip())
            _set_font(run, bold=True, size=18, color=(0, 80, 60))
            p.paragraph_format.space_after  = Pt(2)
            p.paragraph_format.space_before = Pt(0)
            continue

        # Section heading
        if _is_section_heading(line):
            _add_horizontal_rule(doc)
            p   = doc.add_paragraph()
            run = p.add_run(line.strip().upper())
            _set_font(run, bold=True, size=11, color=(0, 100, 75))
            p.paragraph_format.space_before = Pt(8)
            p.paragraph_format.space_after  = Pt(2)
            continue

        # Bullet point
        if _is_bullet(line):
            text = re.sub(r'^[\•\-\*\·▪►]\s+', '', line.strip())
            p    = doc.add_paragraph(style='List Bullet')
            run  = p.add_run(text)
            _set_font(run, size=10.5)
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after  = Pt(1)
            p.paragraph_format.left_indent  = Inches(0.2)
            continue

        # Contact line (emails, phones, URLs — typically short, line 2-4)
        if re.search(r'[@|•|linkedin|github|http|\d{3}[-.\s]\d{3}]', line.lower()) and len(line) < 120:
            p   = doc.add_paragraph()
            run = p.add_run(line.strip())
            _set_font(run, size=10, color=(80, 80, 80))
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after  = Pt(1)
            continue

        # Job title / company line (bold if ALL CAPS or ends with date pattern)
        if re.search(r'\b(20\d\d|present|current)\b', line.lower()) or line.strip() == line.strip().upper():
            p   = doc.add_paragraph()
            run = p.add_run(line.strip())
            _set_font(run, bold=True, size=11)
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after  = Pt(1)
            continue

        # Regular paragraph
        p   = doc.add_paragraph()
        run = p.add_run(line.strip())
        _set_font(run, size=10.5)
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after  = Pt(1)

    # Save to bytes
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
        doc.save(tmp.name)
        tmp_path = tmp.name

    with open(tmp_path, 'rb') as f:
        data = f.read()

    os.unlink(tmp_path)
    return data


# ─────────────────────────────────────────────────────────────────────────────
# MAIN OPTIMIZER FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def optimize_resume(
    resume_text:   str,
    jd_text:       str,
    extraction:    dict,
    original_score: float,
    run_analysis_fn,   # pass scorer's run_analysis to avoid circular import
    nlp,
) -> dict:
    """
    Full optimization pipeline.
    Returns dict with: optimized_text, new_score, docx_b64, iterations
    """
    best_text  = resume_text
    best_score = original_score
    iterations = 0
    MAX_ITER   = 2

    while best_score < 80 and iterations < MAX_ITER:
        iterations += 1
        logger.info("Optimizer pass %d — current score: %.1f", iterations, best_score)

        try:
            rewritten = rewrite_resume(best_text, jd_text, extraction, best_score)
        except Exception as e:
            logger.error("Rewrite failed on pass %d: %s", iterations, e)
            break

        # Score the rewrite
        try:
            result    = run_analysis_fn(rewritten, jd_text, nlp)
            new_score = result.get("score", best_score)
        except Exception as e:
            logger.error("Scoring failed on pass %d: %s", iterations, e)
            break

        logger.info("Pass %d score: %.1f → %.1f", iterations, best_score, new_score)

        if new_score > best_score:
            best_score = new_score
            best_text  = rewritten
        else:
            # No improvement — stop
            break

    # Generate DOCX
    try:
        docx_bytes = generate_docx(best_text)
        docx_b64   = base64.b64encode(docx_bytes).decode('utf-8')
    except Exception as e:
        logger.error("DOCX generation failed: %s", e)
        docx_b64 = None

    return {
        "optimized_text":  best_text,
        "original_score":  round(original_score, 1),
        "new_score":       round(best_score, 1),
        "improvement":     round(best_score - original_score, 1),
        "iterations":      iterations,
        "docx_b64":        docx_b64,
        "target_reached":  best_score >= 80,
    }
