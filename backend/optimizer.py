# optimizer.py
# ═══════════════════════════════════════════════════════════════════════════
# Resume Optimizer
#
# DOCX strategy: always edit the original uploaded file in-place.
# We never build a new DOCX from scratch — we load the original, modify
# only the text content of runs, and save. This preserves 100% of the
# original styles, fonts, colors, numbering, spacing, and template.
#
# Rewrite strategy: Claude makes surgical keyword insertions only.
# Voice, structure, sentence length are preserved to pass AI detection.
# ═══════════════════════════════════════════════════════════════════════════

import os, re, base64, logging, io, copy
from anthropic import Anthropic
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import lxml.etree as ET
from generate_docx import generate_docx

logger = logging.getLogger(__name__)
_client = None
_MODEL  = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

def _get_client():
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


# ── Rewrite prompt ─────────────────────────────────────────────────────────
_REWRITE_PROMPT = """You are editing a resume to add missing keywords for a specific job. Make surgical additions only.

TARGET JOB: {job_title}
MISSING KEYWORDS TO WEAVE IN: {missing_skills}
KEYWORDS TO EMPHASIZE: {matched_skills}
CURRENT SCORE: {current_score}% — target 80%+

ORIGINAL RESUME TEXT:
{resume_text}

JOB DESCRIPTION:
{jd_text}

RULES — follow exactly:

NEVER CHANGE:
- Candidate name, company names (exact spelling), job titles held, locations, dates, university names, certification names

WHAT TO CHANGE:
- Weave missing keywords into existing bullet text where they genuinely fit
- Reorder bullets within a role so JD-relevant ones come first
- Add missing keywords to Skills section if they cannot fit naturally in bullets
- Add 2-3 missing keywords to the Professional Summary only

VOICE — critical for AI detection:
- Keep every sentence structure exactly as written
- Keep verb tenses and choices — "built" stays "built"
- Keep sentence length — do not expand short bullets  
- BANNED words: spearheaded, orchestrated, leveraged, robust, dynamic, synergistic, transformative, revolutionized, catalyzed
- Do NOT inflate impact statements

OUTPUT FORMAT — critical:
Return a JSON object where keys are paragraph indices (as strings) and values are the new paragraph text.
Only include paragraphs you actually changed.
For skill paragraphs that use a line break between category and items, use \\n as the separator.
Example: {{"5": "Updated summary text here.", "7": "Automation & Testing\\nSelenium, Java, new skill"}}

Return ONLY the JSON object. No explanation, no markdown code fences."""


def rewrite_resume_json(resume_text, jd_text, extraction, current_score, para_map):
    """
    Ask Claude which paragraphs to change and what to change them to.
    Returns dict of {para_index: new_text}.
    """
    missing  = ", ".join(extraction.get("missing_skills",     [])[:15]) or "none"
    matched  = ", ".join(extraction.get("matched_skills",     [])[:10]) or "none"
    title    = extraction.get("job_title", "target role")

    def trunc(t, n):
        return t if len(t) <= n else t[:int(n*.72)] + "\n[...]\n" + t[-int(n*.18):]

    # Build numbered paragraph map for Claude
    numbered = "\n".join(f"[{i}] {text}" for i, text in para_map.items())

    resp = _get_client().messages.create(
        model=_MODEL, max_tokens=3000,
        messages=[{"role": "user", "content": _REWRITE_PROMPT.format(
            job_title=title,
            missing_skills=missing,
            matched_skills=matched,
            current_score=round(current_score),
            resume_text=trunc(numbered, 4000),
            jd_text=trunc(jd_text, 2000),
        )}]
    )

    import json
    text = resp.content[0].text.strip()
    # Strip any accidental markdown fences
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)

    try:
        changes = json.loads(text)
        return {str(k): v for k, v in changes.items()}
    except json.JSONDecodeError as e:
        logger.error("Claude JSON parse failed: %s\nRaw: %s", e, text[:500])
        return {}


# ── DOCX editing: preserve original, edit runs in place ──────────────────

def _clear_runs(p):
    """Remove all w:r elements from paragraph."""
    for r in list(p._p.findall(qn('w:r'))):
        p._p.remove(r)

def _get_run_template(p):
    """Get the formatting properties XML of the first meaningful run."""
    for r in p.runs:
        if r.text.strip():
            rPr = r._r.find(qn('w:rPr'))
            return rPr
    return None

def _make_run_xml(text, rPr_template=None, bold=False, preserve_space=True):
    """Build a w:r element with given text and optional bold override."""
    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    r_el = OxmlElement('w:r')

    # Copy rPr from template
    if rPr_template is not None:
        rPr = copy.deepcopy(rPr_template)
        # Apply bold override
        b_el  = rPr.find(qn('w:b'))
        bCs_el = rPr.find(qn('w:bCs'))
        if bold:
            if b_el is None:
                b_el = OxmlElement('w:b')
                rPr.insert(0, b_el)
            if bCs_el is None:
                bCs_el = OxmlElement('w:bCs')
                rPr.insert(1, bCs_el)
        else:
            if b_el is not None:  rPr.remove(b_el)
            if bCs_el is not None: rPr.remove(bCs_el)
        r_el.append(rPr)
    else:
        rPr = OxmlElement('w:rPr')
        if bold:
            rPr.append(OxmlElement('w:b'))
            rPr.append(OxmlElement('w:bCs'))
        r_el.append(rPr)

    t_el = OxmlElement('w:t')
    if preserve_space and (text.startswith(' ') or text.endswith(' ')):
        t_el.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    t_el.text = text
    r_el.append(t_el)
    return r_el

def _make_linebreak_run(rPr_template=None):
    """Build a w:r containing a w:br (line break)."""
    r_el = OxmlElement('w:r')
    if rPr_template is not None:
        rPr = copy.deepcopy(rPr_template)
        r_el.append(rPr)
    r_el.append(OxmlElement('w:br'))
    return r_el

def _parse_segments(text):
    """
    Parse text with **bold** markers into list of (text, is_bold) tuples.
    Falls back to treating entire string as non-bold if no markers found.
    """
    if '**' not in text:
        return [(text, False)]
    parts = []
    bold = False
    for chunk in re.split(r'\*\*', text):
        if chunk:
            parts.append((chunk, bold))
        bold = not bold
    return parts

def apply_changes_to_docx(original_path, changes):
    """
    Load original DOCX, apply text changes to specified paragraphs,
    preserve all formatting, return bytes of modified DOCX.

    changes: dict of {str(para_index): new_text}
    """
    doc = Document(original_path)

    for idx_str, new_text in changes.items():
        try:
            idx = int(idx_str)
        except ValueError:
            continue

        if idx >= len(doc.paragraphs):
            logger.warning("Para index %d out of range (%d total)", idx, len(doc.paragraphs))
            continue

        p = doc.paragraphs[idx]

        # Skip if text unchanged
        if p.text.strip() == new_text.strip():
            continue

        # Get run formatting template from original paragraph
        rPr_template = _get_run_template(p)

        # Clear existing runs
        _clear_runs(p)

        # Check if this paragraph uses \n (skill category line break)
        if '\n' in new_text:
            parts = new_text.split('\n', 1)
            # Bold category name
            p._p.append(_make_run_xml(parts[0], rPr_template, bold=True))
            # Line break run
            p._p.append(_make_linebreak_run(rPr_template))
            # Normal skills text
            p._p.append(_make_run_xml(parts[1], rPr_template, bold=False))
        else:
            # Parse **bold** markers if Claude used them, otherwise no bolding
            segments = _parse_segments(new_text)
            for text, is_bold in segments:
                if text:
                    p._p.append(_make_run_xml(text, rPr_template, bold=is_bold))

    # Save to bytes
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ── Main optimizer ─────────────────────────────────────────────────────────

def optimize_resume(resume_text, jd_text, extraction, original_score,
                    run_analysis_fn, nlp, original_docx_path=None):
    """
    Full pipeline:
    1. Ask Claude for paragraph-level changes as JSON
    2. Apply changes to original DOCX preserving all formatting
    3. Score the rewritten text
    4. Retry once if still under 80
    5. Return result dict with docx_b64

    original_docx_path: path to the uploaded .docx file.
    If None, falls back to text-only result with no DOCX.
    """
    best_text   = resume_text
    best_score  = original_score
    best_docx   = None
    iterations  = 0

    # Build paragraph map from resume text for Claude's reference
    def build_para_map(text):
        lines = text.split('\n')
        return {str(i): line for i, line in enumerate(lines) if line.strip()}

    while best_score < 80 and iterations < 3:
        iterations += 1
        logger.info("Optimizer pass %d — score %.1f", iterations, best_score)

        para_map = build_para_map(best_text)

        try:
            changes = rewrite_resume_json(best_text, jd_text, extraction,
                                          best_score, para_map)
            logger.info("Claude suggested changes to %d paragraphs", len(changes))
        except Exception as e:
            logger.error("Rewrite failed: %s", e)
            break

        if not changes:
            logger.warning("No changes returned by Claude")
            break

        # Apply changes to text for scoring
        lines = best_text.split('\n')
        for idx_str, new_text in changes.items():
            try:
                idx = int(idx_str)
                if idx < len(lines):
                    lines[idx] = new_text
            except ValueError:
                pass
        rewritten_text = '\n'.join(lines)

        try:
            result    = run_analysis_fn(rewritten_text, jd_text, nlp)
            new_score = result.get("score", best_score)
        except Exception as e:
            logger.error("Scoring failed: %s", e)
            break

        logger.info("Pass %d: %.1f → %.1f", iterations, best_score, new_score)

        if new_score > best_score:
            best_score = new_score
            best_text  = rewritten_text

            # Apply to DOCX
            if original_docx_path and os.path.exists(original_docx_path):
                try:
                    best_docx = apply_changes_to_docx(original_docx_path, changes)
                    logger.info("DOCX edited OK (%d bytes)", len(best_docx))
                except Exception as e:
                    logger.error("DOCX edit failed: %s", e, exc_info=True)
        else:
            break

    # Generate DOCX using the Rezi template from the uploaded original
    docx_b64 = None
    try:
        template = original_docx_path if (original_docx_path and os.path.exists(original_docx_path)) else None
        docx_bytes = generate_docx(best_text, template_path=template)
        docx_b64 = base64.b64encode(docx_bytes).decode('utf-8')
        logger.info("DOCX generated OK (%d bytes)", len(docx_bytes))
    except Exception as e:
        logger.error("DOCX generation failed: %s", e, exc_info=True)

    return {
        "optimized_text": best_text,
        "original_score": round(original_score, 1),
        "new_score":      round(best_score, 1),
        "improvement":    round(best_score - original_score, 1),
        "iterations":     iterations,
        "docx_b64":       docx_b64,
        "target_reached": best_score >= 80,
    }
