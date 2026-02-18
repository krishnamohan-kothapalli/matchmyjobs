# optimizer.py
import os, re, base64, logging, tempfile
from anthropic import Anthropic
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

logger = logging.getLogger(__name__)
_client = None
_MODEL  = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

def _get_client():
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client

# ── Rewrite prompt ────────────────────────────────────────────────────────────
_REWRITE_PROMPT = """You are editing a resume to improve its ATS keyword score for a specific job. Your job is surgical — add missing keywords naturally, not rewrite the person's story.

TARGET JOB: {job_title}
MISSING KEYWORDS TO WEAVE IN: {missing_skills}
KEYWORDS TO EMPHASIZE: {matched_skills}
KEY JD PHRASES: {responsibilities}
CURRENT SCORE: {current_score}% — target 80%+

ORIGINAL RESUME:
{resume_text}

JOB DESCRIPTION:
{jd_text}

EDITING RULES — follow strictly:

CONTENT:
1. Never change dates, company names, job titles, education — these are facts
2. Never add experience the person does not have
3. Add missing keywords by weaving them into existing bullets where they genuinely fit
4. If a skill truly cannot fit anywhere naturally, add it only to a Skills section
5. Reorder bullets within a role so the most JD-relevant ones come first
6. Add or expand a Skills section with relevant keywords

VOICE — critical for passing AI detection:
7. Keep the candidate's exact writing style and sentence length
8. Keep their verb choices — if they wrote "built" do not change to "architected"
9. Keep their formality level exactly
10. BANNED words (AI red flags): spearheaded, orchestrated, leveraged, robust, dynamic, synergistic, cross-functional, best-in-class, cutting-edge, revolutionized, transformative, holistic, streamlined (unless they used it), catalyzed, paradigm
11. Do not inflate impact — if they wrote "helped build" do not change to "led development of"
12. Do not change passive voice to active if the original used passive

FORMAT:
13. Keep exact same section order as original
14. Keep same number of bullets per role (plus or minus one maximum)
15. Output plain text only — no markdown, no asterisks, no hash headers
16. Use the exact section heading words from the original (e.g. if they wrote "WORK HISTORY" keep that)
17. Use bullet character: •

Return ONLY the edited resume. Start with the candidate's name. No commentary."""

def rewrite_resume(resume_text, jd_text, extraction, current_score):
    missing  = ", ".join(extraction.get("missing_skills", [])[:15]) or "none"
    matched  = ", ".join(extraction.get("matched_skills", [])[:10]) or "none"
    resp_str = "; ".join(extraction.get("jd_responsibilities", [])[:5]) or "see JD"
    title    = extraction.get("job_title", "target role")

    def trunc(t, n):
        return t if len(t) <= n else t[:int(n*.72)] + "\n[...]\n" + t[-int(n*.18):]

    resp = _get_client().messages.create(
        model=_MODEL, max_tokens=4000,
        messages=[{"role": "user", "content": _REWRITE_PROMPT.format(
            job_title=title, missing_skills=missing, matched_skills=matched,
            responsibilities=resp_str, current_score=round(current_score),
            resume_text=trunc(resume_text, 4000), jd_text=trunc(jd_text, 2000),
        )}]
    )
    return resp.content[0].text.strip()

# ── DOCX generation ───────────────────────────────────────────────────────────
_SECTION_WORDS = {
    'experience','work experience','professional experience','employment','work history','career history',
    'education','academic background','qualifications',
    'skills','technical skills','core competencies','competencies',
    'summary','professional summary','profile','objective','career objective','career summary','about me',
    'certifications','certificates','licenses',
    'projects','key projects','selected projects',
    'achievements','accomplishments','awards','honors',
    'publications','research','presentations',
    'volunteer','volunteering','community',
    'languages','interests','hobbies','activities',
    'references','contact','contact information',
}

def _is_section(line):
    clean = line.strip().rstrip(':').lower()
    if clean in _SECTION_WORDS: return True
    s = line.strip().rstrip(':')
    return s.isupper() and 4 <= len(s) <= 35 and not re.search(r'\b(20\d\d|19\d\d)\b', s)

def _is_bullet(line):
    return bool(re.match(r'^[•\-\*·▪►▸‣]\s+', line.strip()))

def _is_contact(line):
    l = line.lower()
    return bool(
        re.search(r'@\w+\.\w+', l) or
        re.search(r'\b\d{3}[\s.\-]\d{3}[\s.\-]\d{4}\b', l) or
        re.search(r'linkedin\.com|github\.com|portfolio|http', l)
    )

def _is_job_header(line):
    return bool(re.search(
        r'\b(20\d\d|19\d\d|present|current|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b',
        line.lower()
    ))

def _rule(doc):
    p = doc.add_paragraph()
    pBdr = OxmlElement('w:pBdr')
    bot  = OxmlElement('w:bottom')
    bot.set(qn('w:val'),'single'); bot.set(qn('w:sz'),'4')
    bot.set(qn('w:space'),'1');    bot.set(qn('w:color'),'1E3A2F')
    pBdr.append(bot)
    p._p.get_or_add_pPr().append(pBdr)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after  = Pt(0)

def _r(p, text, bold=False, size=11.0, color=None, italic=False):
    run = p.add_run(text)
    run.font.name = 'Calibri'; run.font.size = Pt(size)
    run.font.bold = bold; run.font.italic = italic
    if color: run.font.color.rgb = RGBColor(*color)

def generate_docx(resume_text):
    doc = Document()
    for sec in doc.sections:
        sec.top_margin = sec.bottom_margin = Inches(0.75)
        sec.left_margin = sec.right_margin = Inches(1.0)
    n = doc.styles['Normal']
    n.font.name = 'Calibri'; n.font.size = Pt(11)
    n.paragraph_format.space_before = n.paragraph_format.space_after = Pt(0)

    lines        = resume_text.split('\n')
    name_done    = False
    contact_done = False

    for raw in lines:
        line = raw.rstrip()

        if not line.strip():
            p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(4)
            continue

        # Name
        if not name_done:
            name_done = True
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _r(p, line.strip(), bold=True, size=16, color=(15,60,45))
            p.paragraph_format.space_after = Pt(3)
            continue

        # Contact block
        if not contact_done and _is_contact(line):
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _r(p, line.strip(), size=10, color=(80,80,80))
            p.paragraph_format.space_after = Pt(1)
            continue

        if not contact_done and not _is_contact(line):
            contact_done = True

        # Section heading
        if _is_section(line):
            p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(4)
            p = doc.add_paragraph()
            _r(p, line.strip().upper(), bold=True, size=11, color=(15,60,45))
            p.paragraph_format.space_before = Pt(0); p.paragraph_format.space_after = Pt(1)
            _rule(doc)
            continue

        # Bullet
        if _is_bullet(line):
            text = re.sub(r'^[•\-\*·▪►▸‣]\s+', '', line.strip())
            p = doc.add_paragraph(style='List Bullet')
            _r(p, text, size=10.5)
            p.paragraph_format.left_indent  = Inches(0.25)
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after  = Pt(1)
            continue

        # Job header (company / title / dates)
        if _is_job_header(line):
            p = doc.add_paragraph()
            _r(p, line.strip(), bold=True, size=11)
            p.paragraph_format.space_before = Pt(7)
            p.paragraph_format.space_after  = Pt(1)
            continue

        # Regular line
        p = doc.add_paragraph()
        _r(p, line.strip(), size=10.5)
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after  = Pt(1)

    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
        doc.save(tmp.name); path = tmp.name
    with open(path,'rb') as f: data = f.read()
    os.unlink(path)
    return data

# ── Main optimizer ────────────────────────────────────────────────────────────
def optimize_resume(resume_text, jd_text, extraction, original_score, run_analysis_fn, nlp):
    best_text  = resume_text
    best_score = original_score
    iterations = 0

    while best_score < 80 and iterations < 2:
        iterations += 1
        logger.info("Optimizer pass %d — score %.1f", iterations, best_score)
        try:
            rewritten = rewrite_resume(best_text, jd_text, extraction, best_score)
        except Exception as e:
            logger.error("Rewrite failed: %s", e); break
        try:
            result    = run_analysis_fn(rewritten, jd_text, nlp)
            new_score = result.get("score", best_score)
        except Exception as e:
            logger.error("Scoring failed: %s", e); break
        logger.info("Pass %d: %.1f → %.1f", iterations, best_score, new_score)
        if new_score > best_score:
            best_score = new_score; best_text = rewritten
        else:
            break

    docx_b64 = None
    try:
        docx_b64 = base64.b64encode(generate_docx(best_text)).decode('utf-8')
        logger.info("DOCX generated OK")
    except Exception as e:
        logger.error("DOCX failed: %s", e, exc_info=True)

    return {
        "optimized_text": best_text,
        "original_score": round(original_score, 1),
        "new_score":      round(best_score, 1),
        "improvement":    round(best_score - original_score, 1),
        "iterations":     iterations,
        "docx_b64":       docx_b64,
        "target_reached": best_score >= 80,
    }
