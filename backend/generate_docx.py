"""
generate_docx.py  — Rezi-style DOCX generator (fully self-contained)

Paragraph spec:
  Name        Calibri 18pt bold #2E3D50, line=270, ind left=2880 firstLine=720
  Location    Calibri 11pt #2E3D50, line=270, left=2880
  Contact     Calibri 11pt #2E3D50, line=270
  Heading     Calibri 12pt bold #2E3D50, before=160 after=40 line=270
              top border #D1D5DB, bottom border #2E3D50
  Summary     Calibri 11pt, jc=both, after=60 line=264
  Skill row   numId=1 square-bullet, bold category + w:br + normal items
  Bullet      numId=2 round-bullet, jc=both, after=40 line=264
  Job title   Calibri 11pt bold, before=100 after=0
  Company/dt  Calibri 11pt #2E3D50, right-tab 9360, line=270
  Degree      Calibri 11pt bold #2E3D50, before=80 line=270
  School/dt   Calibri 11pt #2E3D50, line=270
  Cert        bold name + w:br + normal issued, before=80 line=270
"""

import io, re, copy
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import lxml.etree as ET

COLOR  = "2E3D50"
FONT   = "Calibri"
SZ11   = "22"   # 11pt in half-points
SZ12   = "24"   # 12pt
SZ18   = "36"   # 18pt


# ─── XML helpers ──────────────────────────────────────────────────────────────

def _w(tag, **attrs):
    el = OxmlElement(f"w:{tag}")
    for k, v in attrs.items():
        el.set(qn(f"w:{k}"), str(v))
    return el

def _fonts(eastAsia=None):
    f = _w("rFonts", ascii=FONT, hAnsi=FONT, cs=FONT)
    if eastAsia:
        f.set(qn("w:eastAsia"), eastAsia)
    return f

def _rPr(bold=False, color=None, sz=None, eastAsia=None):
    rpr = _w("rPr")
    rpr.append(_fonts(eastAsia))
    if bold:  rpr.append(_w("b")); rpr.append(_w("bCs"))
    if color: rpr.append(_w("color", val=color))
    if sz:    rpr.append(_w("sz", val=sz)); rpr.append(_w("szCs", val=sz))
    return rpr

def _t(text):
    t = _w("t")
    if text.startswith(" ") or text.endswith(" "):
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    return t

def _run(text, bold=False, color=None, sz=None, eastAsia=None):
    r = _w("r")
    r.append(_rPr(bold, color, sz, eastAsia))
    r.append(_t(text))
    return r

def _run_br():
    r = _w("r"); r.append(_rPr()); r.append(_w("br")); return r

def _run_tab(color=None):
    r = _w("r")
    rpr = _w("rPr"); rpr.append(_fonts())
    if color: rpr.append(_w("color", val=color))
    r.append(rpr); r.append(_w("tab")); return r

def _sp(**kw):
    s = _w("spacing")
    for k, v in kw.items(): s.set(qn(f"w:{k}"), str(v))
    return s

def _ind(**kw):
    i = _w("ind")
    for k, v in kw.items(): i.set(qn(f"w:{k}"), str(v))
    return i

def _numPr(numId):
    np = _w("numPr")
    np.append(_w("ilvl", val="0"))
    np.append(_w("numId", val=str(numId)))
    return np

def _pPr(*children):
    ppr = _w("pPr")
    for c in children: ppr.append(c)
    rpr = _w("rPr"); rpr.append(_fonts()); ppr.append(rpr)
    return ppr

def _borders():
    b = _w("pBdr")
    b.append(_w("top",    val="single", sz="4", space="4", color="D1D5DB"))
    b.append(_w("bottom", val="single", sz="4", space="1", color=COLOR))
    return b

def _rtab(pos="9360"):
    t = _w("tabs"); t.append(_w("tab", val="right", pos=pos)); return t

def _para(ppr, *runs):
    p = _w("p"); p.append(ppr)
    for r in runs: p.append(r)
    return p


# ─── Segment parser  "normal **bold** normal" ────────────────────────────────

def _segs(text):
    if "**" not in text: return [(text, False)]
    parts, bold = [], False
    for chunk in re.split(r"\*\*", text):
        if chunk: parts.append((chunk, bold))
        bold = not bold
    return parts


# ─── Paragraph builders ───────────────────────────────────────────────────────

def p_name(text):
    ppr = _pPr(_sp(line="270", lineRule="auto", before="0", after="0"),
               _ind(left="2880", firstLine="720"))
    return _para(ppr, _run(text, bold=True, color=COLOR, sz=SZ18, eastAsia="Merriweather"))

def p_location(text):
    ppr = _pPr(_sp(line="270", lineRule="auto", before="0", after="0"),
               _ind(left="2880"))
    return _para(ppr, _run(text, color=COLOR))

def p_contact(text):
    ppr = _pPr(_sp(line="270", lineRule="auto", before="0", after="0"))
    return _para(ppr, _run(text, color=COLOR))

def p_heading(text):
    ppr = _pPr(_borders(),
               _sp(before="160", after="40", line="270", lineRule="auto"))
    return _para(ppr, _run(text, bold=True, color=COLOR, sz=SZ12, eastAsia="Merriweather"))

def p_summary(text):
    ppr = _pPr(_sp(before="0", after="60", line="264", lineRule="auto"),
               _w("jc", val="both"))
    p = _w("p"); p.append(ppr)
    for seg, bold in _segs(text): p.append(_run(seg, bold=bold))
    return p

def p_skill_row(category, items):
    ppr = _pPr(_numPr(1),
               _sp(before="0", after="40", line="264", lineRule="auto"),
               _ind(left="360", hanging="180"))
    p = _w("p"); p.append(ppr)
    if category:
        p.append(_run(category, bold=True))
        p.append(_run_br())
    p.append(_run(items))
    return p

def p_bullet(text):
    ppr = _pPr(_numPr(2),
               _sp(before="0", after="40", line="264", lineRule="auto"),
               _ind(left="360", hanging="180"),
               _w("jc", val="both"))
    p = _w("p"); p.append(ppr)
    for seg, bold in _segs(text): p.append(_run(seg, bold=bold))
    return p

def p_job_title(text):
    ppr = _pPr(_sp(before="100", after="0", line="264", lineRule="auto"))
    return _para(ppr, _run(text, bold=True))

def p_company_date(company, date_loc):
    ppr = _pPr(_rtab("9360"),
               _sp(before="0", after="0", line="270", lineRule="auto"))
    p = _w("p"); p.append(ppr)
    p.append(_run(company, color=COLOR))
    p.append(_run_tab(color=COLOR))
    p.append(_run(date_loc, color=COLOR))
    return p

def p_degree(text):
    ppr = _pPr(_sp(before="80", after="0", line="270", lineRule="auto"))
    p = _w("p"); p.append(ppr)
    p.append(_run(text, bold=True, color=COLOR, eastAsia="Merriweather"))
    return p

def p_school_date(text):
    ppr = _pPr(_sp(before="0", after="0", line="270", lineRule="auto"))
    return _para(ppr, _run(text, color=COLOR))

def p_cert(name, issued):
    ppr = _pPr(_sp(before="80", after="0", line="270", lineRule="auto"))
    p = _w("p"); p.append(ppr)
    p.append(_run(name, bold=True, color=COLOR, eastAsia="Merriweather"))
    if issued:
        p.append(_run_br())
        p.append(_run(issued))
    return p


# ─── Embedded numbering & styles ─────────────────────────────────────────────

_NUM_XML = b"""\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="1">
    <w:multiLevelType w:val="singleLevel"/>
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/><w:numFmt w:val="bullet"/>
      <w:lvlText w:val="&#9632;"/><w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="360" w:hanging="180"/></w:pPr>
      <w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"/><w:sz w:val="16"/></w:rPr>
    </w:lvl>
  </w:abstractNum>
  <w:abstractNum w:abstractNumId="2">
    <w:multiLevelType w:val="singleLevel"/>
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/><w:numFmt w:val="bullet"/>
      <w:lvlText w:val="&#8226;"/><w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="360" w:hanging="180"/></w:pPr>
      <w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"/><w:sz w:val="20"/></w:rPr>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="1"/></w:num>
  <w:num w:numId="2"><w:abstractNumId w:val="2"/></w:num>
</w:numbering>"""

_STYLES_XML = b"""\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>
      <w:sz w:val="22"/><w:szCs w:val="22"/>
    </w:rPr>
  </w:style>
  <w:style w:type="character" w:default="1" w:styleId="DefaultParagraphFont">
    <w:name w:val="Default Paragraph Font"/>
    <w:uiPriority w:val="1"/><w:semiHidden/><w:unhideWhenUsed/>
  </w:style>
</w:styles>"""


def _build_doc():
    from docx.opc.part import Part
    from docx.opc.packuri import PackURI
    from docx.oxml import parse_xml

    doc = Document()
    doc.part.styles._element.clear()
    for child in ET.fromstring(_STYLES_XML):
        doc.part.styles._element.append(copy.deepcopy(child))

    NUM_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering"
    NUM_CT  = "application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"
    try:
        np = doc.part.part_related_by(NUM_REL)
        np._element.clear()
        for child in ET.fromstring(_NUM_XML):
            np._element.append(copy.deepcopy(child))
    except Exception:
        np = Part(PackURI("/word/numbering.xml"), NUM_CT,
                  parse_xml(_NUM_XML), doc.part.package)
        doc.part.relate_to(np, NUM_REL)

    body   = doc.element.body
    sectPr = body.find(qn("w:sectPr"))
    if sectPr is None:
        sectPr = _w("sectPr"); body.append(sectPr)
    for tag in ("w:pgMar", "w:pgSz"):
        el = sectPr.find(qn(tag))
        if el is not None: sectPr.remove(el)
    sectPr.append(_w("pgSz", w="12240", h="15840"))
    sectPr.append(_w("pgMar", top="720", right="720", bottom="720", left="720",
                     header="708", footer="708", gutter="0"))
    for p in list(body.findall(qn("w:p"))): body.remove(p)
    return doc


def _add(doc, p_el):
    body   = doc.element.body
    sectPr = body.find(qn("w:sectPr"))
    if sectPr is not None: body.insert(list(body).index(sectPr), p_el)
    else:                  body.append(p_el)


# ─── Resume text parser ──────────────────────────────────────────────────────
# IMPORTANT: Experience bullets often have NO bullet character prefix when they
# come from the optimizer. We detect them by:
#   1. Explicit bullet prefix (•, -, *, etc.)
#   2. Context: any line that follows a company/date line and looks like a
#      sentence (starts with capital verb, > 30 chars) is a bullet.

class ResumeData:
    def __init__(self):
        self.name      = ""
        self.location  = ""
        self.contacts  = []
        self.summary   = ""
        self.skills    = []   # [(category, items_str)]
        self.jobs      = []   # [{"title","company","date_location","bullets":[]}]
        self.education = []   # [{"degree","school_date"}]
        self.certs     = []   # [{"name","issued"}]

_SEC_RE = re.compile(
    r"^(PROFESSIONAL SUMMARY|SUMMARY|SKILLS|TECHNICAL SKILLS|CORE COMPETENCIES|"
    r"EXPERIENCE|WORK EXPERIENCE|WORK HISTORY|EMPLOYMENT HISTORY|"
    r"EDUCATION|ACADEMIC BACKGROUND|"
    r"CERTIFICATIONS?|CERTIFICATES?|LICENSES?|"
    r"PROJECTS?|ACHIEVEMENTS?|AWARDS?|PUBLICATIONS?|"
    r"VOLUNTEER|LANGUAGES|INTERESTS|REFERENCES|ADDITIONAL)$",
    re.I,
)

# Lines that start with a bullet character
_BULLET_PREFIX = re.compile(r"^[•\-\*·▪►▸‣➢✓○◆]\s*")

# Lines that look like a company+date (contain a date keyword)
_DATE_RE = re.compile(
    r"\b(20\d\d|19\d\d|present|current|now|"
    r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b", re.I
)

# Action verbs that start experience bullets
_VERB_RE = re.compile(
    r"^(Worked|Designed|Built|Developed|Implemented|Performed|Applied|"
    r"Automated|Validated|Integrated|Identified|Actively|Conducted|Supported|"
    r"Tested|Contributed|Maintained|Analyzed|Promoted|Led|Managed|Created|"
    r"Executed|Delivered|Collaborated|Drove|Established|Oversaw|Directed|"
    r"Achieved|Reduced|Improved|Increased|Deployed|Launched|Migrated|"
    r"Configured|Monitored|Resolved|Ensured|Reviewed|Prepared|Coordinated|"
    r"Mentored|Trained|Assisted|Facilitated|Spearheaded|Owned|Shipped|"
    r"Architected|Defined|Scoped|Tracked|Reported|Documented|Gathered|"
    r"Researched|Evaluated|Assessed|Optimized|Streamlined|Automated|"
    r"Scaled|Refactored|Debugged|Fixed|Patched|Released|Published)\b"
)


def _is_bullet_line(line, in_experience, saw_company):
    """Return True if this line should be rendered as a bullet point."""
    if _BULLET_PREFIX.match(line):
        return True
    # Inside experience section, after a company line, long verb sentences = bullets
    if in_experience and saw_company and len(line) > 35 and _VERB_RE.match(line):
        return True
    return False


def _is_company_line(line):
    """Looks like a company/date line."""
    if not _DATE_RE.search(line):
        return False
    # Must have tab, pipe, or contain company-like text + date
    return "\t" in line or "|" in line or bool(re.search(r"[A-Z].{5,}\s+(?:\w+ \d{4}|present)", line, re.I))


def parse_resume_text(text):
    data  = ResumeData()
    lines = [l.rstrip() for l in text.split("\n")]

    # Find sections
    sec_order, sec_starts = [], {}
    for i, line in enumerate(lines):
        s = line.strip()
        if _SEC_RE.match(s):
            key = s.upper()
            if key not in sec_starts:
                sec_order.append(key)
                sec_starts[key] = i

    def get_lines(name):
        key = None
        for k in sec_starts:
            if k == name or k.startswith(name): key = k; break
        if not key: return []
        idx   = sec_order.index(key)
        start = sec_starts[key] + 1
        end   = sec_starts[sec_order[idx+1]] if idx+1 < len(sec_order) else len(lines)
        return [l for l in lines[start:end] if l.strip()]

    # Header
    first_sec = sec_starts[sec_order[0]] if sec_order else len(lines)
    header    = [l.strip() for l in lines[:first_sec] if l.strip()]
    if header:         data.name     = header[0]
    if len(header) > 1: data.location = header[1]
    if len(header) > 2: data.contacts = header[2:]

    # Summary
    sl = get_lines("PROFESSIONAL SUMMARY") or get_lines("SUMMARY")
    data.summary = " ".join(sl)

    # Skills — handle 3 formats: embedded \n, colon, two-line
    raw = (get_lines("SKILLS") or get_lines("TECHNICAL SKILLS") or
           get_lines("CORE COMPETENCIES"))
    si = 0
    while si < len(raw):
        line = raw[si].strip()
        # Embedded newline (category\nitems in one text block)
        if "\n" in line:
            cat, items = line.split("\n", 1)
            # Items part may STILL be merged with next category — split at known category names
            data.skills.append((cat.strip(), items.strip()))
            si += 1
        # Two-line: short non-comma line followed by items line
        elif (si+1 < len(raw) and "," not in line and len(line) < 55
              and not _BULLET_PREFIX.match(line)
              and ("," in raw[si+1] or len(raw[si+1]) > 20)):
            data.skills.append((line, raw[si+1].strip()))
            si += 2
        # Colon separator
        elif (":" in line and len(line.split(":")[0]) < 50
              and "," not in line.split(":")[0]
              and not _BULLET_PREFIX.match(line)):
            cat, items = line.split(":", 1)
            data.skills.append((cat.strip(), items.strip()))
            si += 1
        # Merged line with no separator (e.g. "CI/CD & DevOpsJenkins, Git")
        # Find the split point: look at ALL lowercase→Capital boundaries,
        # pick the one where the RIGHT side starts with a known tool/skill word.
        # If multiple match, prefer the one with longer left (= more complete category).
        elif re.search(r'[a-z\)]([A-Z])', line):
            KNOWN = re.compile(
                r'^(Java|Python|SQL|Selenium|Jenkins|Git|Jira|JIRA|Agile|Scrum|'
                r'Snowflake|Oracle|MySQL|Postgres|AWS|Azure|GCP|Docker|Kubernetes|'
                r'REST|GraphQL|Node|React|Angular|Spring|Maven|Gradle|Bitbucket|'
                r'GitHub|Tableau|Power|Excel|Spark|Kafka|Mongo|Redis|Postman|'
                r'TestNG|Cucumber|JMeter|Appium|JUnit|Waterfall|Kanban|Design|'
                r'Page|BDD|TDD|API|SOAP|Shell|Fivetran|Matillion|CDC|SCD|'
                r'Automation|Programming|Backend|Data|CI|Frameworks|Defect|'
                r'Methods|Tools|Technical|Core|Domain)'
            )
            best = None
            for m in re.finditer(r'([a-z\)])([A-Z])', line):
                left  = line[:m.start()+1].strip()
                right = line[m.start()+1:].strip()
                if len(left) < 60 and "," not in left:
                    if KNOWN.match(right) or (right and "," in right[:30]):
                        # Prefer LONGER left (last valid boundary = most complete category)
                        if best is None or len(left) > len(best[0]):
                            best = (left, right)
            if best:
                data.skills.append(best)
            else:
                data.skills.append(("", line))
            si += 1
        else:
            data.skills.append(("", line))
            si += 1

    # Experience — detect bullets by prefix OR by action-verb context
    exp = (get_lines("EXPERIENCE") or get_lines("WORK EXPERIENCE") or
           get_lines("WORK HISTORY") or get_lines("EMPLOYMENT HISTORY"))
    cur        = None
    saw_company = False
    for line in exp:
        line = line.strip()
        if not line: continue

        # Explicit bullet prefix
        if _BULLET_PREFIX.match(line):
            if cur: cur["bullets"].append(_BULLET_PREFIX.sub("", line).strip())
            saw_company = True  # bullets only appear after company line
            continue

        # Company/date line
        if _is_company_line(line):
            if "\t" in line:
                company, rest = line.split("\t", 1)
            elif "|" in line:
                company, rest = line.split("|", 1)
            else:
                m = re.search(r'\s{2,}', line)
                company = line[:m.start()].strip() if m else line
                rest    = line[m.end():].strip()    if m else ""
            if cur and not cur.get("company"):
                cur["company"]       = company.strip()
                cur["date_location"] = rest.strip()
            saw_company = True
            continue

        # Action-verb bullet (no prefix) — only when inside a job block
        if cur and saw_company and len(line) > 30 and _VERB_RE.match(line):
            cur["bullets"].append(line)
            continue

        # Otherwise: job title
        cur = {"title": line, "company": "", "date_location": "", "bullets": []}
        data.jobs.append(cur)
        saw_company = False

    # Education
    edu = get_lines("EDUCATION") or get_lines("ACADEMIC BACKGROUND")
    ei  = 0
    while ei < len(edu):
        degree = edu[ei].strip()
        school = edu[ei+1].strip() if ei+1 < len(edu) else ""
        data.education.append({"degree": degree, "school_date": school})
        ei += 2

    # Certifications
    cert_raw = (get_lines("CERTIFICATIONS") or get_lines("CERTIFICATION") or
                get_lines("CERTIFICATES") or get_lines("LICENSES"))
    ci = 0
    while ci < len(cert_raw):
        line = cert_raw[ci].strip()
        # Merged cert+issued in one line: "CERT NAMEIssued: date"
        m = re.search(r'(Issued:?\s+\w)', line, re.I)
        if m and m.start() > 5:
            name   = line[:m.start()].strip()
            issued = line[m.start():].strip()
            data.certs.append({"name": name, "issued": issued})
            ci += 1
        elif "\n" in line:
            n, iss = line.split("\n", 1)
            data.certs.append({"name": n.strip(), "issued": iss.strip()})
            ci += 1
        elif "|" in line:
            n, iss = line.split("|", 1)
            data.certs.append({"name": n.strip(), "issued": iss.strip()})
            ci += 1
        elif (ci+1 < len(cert_raw) and
              cert_raw[ci+1].strip().lower().startswith("issued")):
            data.certs.append({"name": line, "issued": cert_raw[ci+1].strip()})
            ci += 2
        else:
            data.certs.append({"name": line, "issued": ""})
            ci += 1

    return data


# ─── Main API ─────────────────────────────────────────────────────────────────

def generate_docx(resume_text, template_path=None):
    """
    Build Rezi-style DOCX from resume_text (plain text, **bold** markers optional).
    template_path is accepted but ignored — fully self-contained.
    Returns bytes.
    """
    data = parse_resume_text(resume_text)
    doc  = _build_doc()

    if data.name:      _add(doc, p_name(data.name))
    if data.location:  _add(doc, p_location(data.location))
    for c in data.contacts: _add(doc, p_contact(c))

    if data.summary:
        _add(doc, p_heading("PROFESSIONAL SUMMARY"))
        _add(doc, p_summary(data.summary))

    if data.skills:
        _add(doc, p_heading("SKILLS"))
        for cat, items in data.skills:
            if cat or items:
                _add(doc, p_skill_row(cat, items))

    if data.jobs:
        _add(doc, p_heading("EXPERIENCE"))
        for job in data.jobs:
            _add(doc, p_job_title(job["title"]))
            if job.get("company"):
                _add(doc, p_company_date(job["company"], job.get("date_location", "")))
            for bullet in job["bullets"]:
                _add(doc, p_bullet(bullet))

    if data.education:
        _add(doc, p_heading("EDUCATION"))
        for edu in data.education:
            _add(doc, p_degree(edu["degree"]))
            if edu.get("school_date"):
                _add(doc, p_school_date(edu["school_date"]))

    if data.certs:
        _add(doc, p_heading("CERTIFICATIONS"))
        for cert in data.certs:
            _add(doc, p_cert(cert["name"], cert.get("issued", "")))

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
