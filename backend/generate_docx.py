"""
generate_docx.py
════════════════════════════════════════════════════════════════════════════════
Generates a professional Rezi-style DOCX from any parsed resume.
Fully self-contained — no template file needed.

Design spec (reverse-engineered from krishnamohanKothapalli.docx):
  Page:        8.5 x 11", all margins 0.5" (720 twips)
  Base font:   Calibri 11pt, color #2E3D50 for name/headings/company

  Name:        Calibri 18pt bold #2E3D50, line=270, ind left=2880 firstLine=720
  Location:    Calibri 11pt #2E3D50, line=270, ind left=2880
  Contact:     Calibri 11pt bold #2E3D50, line=270
  Heading:     Calibri 12pt bold #2E3D50, before=160 after=40 line=270
               top border light-gray, bottom border navy
  Summary:     Calibri 11pt, jc=both, after=60 line=264
  Skill row:   numId=1 (square bullet), bold category + w:br + normal items
  Bullet:      numId=2 (round bullet), jc=both, mixed bold/normal runs
  Job title:   Calibri 11pt bold, before=100
  Company:     Calibri 11pt #2E3D50, right-tab at 9360, line=270
  Degree:      Calibri 11pt bold #2E3D50, before=80 line=270
  School/date: Calibri 11pt #2E3D50, line=270
  Cert:        bold name + w:br + normal issued, before=80 line=270
"""

import io, re, copy
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import lxml.etree as ET

COLOR_NAVY = "2E3D50"
FONT       = "Calibri"
SZ_NORMAL  = "22"   # 11pt in half-points
SZ_HEADING = "24"   # 12pt
SZ_NAME    = "36"   # 18pt


# ─── Low-level XML ────────────────────────────────────────────────────────────

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


def _rPr_el(bold=False, color=None, sz=None, eastAsia=None):
    rpr = _w("rPr")
    rpr.append(_fonts(eastAsia))
    if bold:
        rpr.append(_w("b"))
        rpr.append(_w("bCs"))
    if color:
        rpr.append(_w("color", val=color))
    if sz:
        rpr.append(_w("sz",   val=str(sz)))
        rpr.append(_w("szCs", val=str(sz)))
    return rpr


def _t(text):
    t = _w("t")
    if text.startswith(" ") or text.endswith(" "):
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    return t


def _run(text, bold=False, color=None, sz=None, eastAsia=None):
    r = _w("r")
    r.append(_rPr_el(bold=bold, color=color, sz=sz, eastAsia=eastAsia))
    r.append(_t(text))
    return r


def _run_br():
    r = _w("r")
    r.append(_rPr_el())
    r.append(_w("br"))
    return r


def _run_tab(color=None):
    r = _w("r")
    rpr = _w("rPr")
    rpr.append(_fonts())
    if color:
        rpr.append(_w("color", val=color))
    r.append(rpr)
    r.append(_w("tab"))
    return r


def _heading_borders():
    bdr = _w("pBdr")
    bdr.append(_w("top",    val="single", sz="4", space="4", color="D1D5DB"))
    bdr.append(_w("bottom", val="single", sz="4", space="1", color=COLOR_NAVY))
    return bdr


def _right_tabs(pos="9360"):
    tabs = _w("tabs")
    tabs.append(_w("tab", val="right", pos=str(pos)))
    return tabs


def _spacing(**kw):
    s = _w("spacing")
    for k, v in kw.items():
        s.set(qn(f"w:{k}"), str(v))
    return s


def _ind(**kw):
    i = _w("ind")
    for k, v in kw.items():
        i.set(qn(f"w:{k}"), str(v))
    return i


def _numPr(numId):
    np = _w("numPr")
    np.append(_w("ilvl", val="0"))
    np.append(_w("numId", val=str(numId)))
    return np


def _pPr(*children, rpr_hint=True):
    ppr = _w("pPr")
    for c in children:
        ppr.append(c)
    if rpr_hint:
        rpr = _w("rPr")
        rpr.append(_fonts())
        ppr.append(rpr)
    return ppr


def _para(ppr, *runs):
    p = _w("p")
    p.append(ppr)
    for r in runs:
        p.append(r)
    return p


# ─── Segment parser ───────────────────────────────────────────────────────────

def _segs(text):
    """[(text, is_bold)] from string with **bold** markers."""
    if "**" not in text:
        return [(text, False)]
    parts, bold = [], False
    for chunk in re.split(r"\*\*", text):
        if chunk:
            parts.append((chunk, bold))
        bold = not bold
    return parts


# ─── Paragraph builders ───────────────────────────────────────────────────────

def p_name(text):
    ppr = _pPr(
        _spacing(line="270", lineRule="auto", before="0", after="0"),
        _ind(left="2880", firstLine="720"),
    )
    return _para(ppr, _run(text, bold=True, color=COLOR_NAVY, sz=SZ_NAME, eastAsia="Merriweather"))


def p_location(text):
    ppr = _pPr(
        _spacing(line="270", lineRule="auto", before="0", after="0"),
        _ind(left="2880"),
    )
    return _para(ppr, _run(text, color=COLOR_NAVY, eastAsia="Merriweather"))


def p_contact(text):
    ppr = _pPr(
        _spacing(line="270", lineRule="auto", before="0", after="0"),
    )
    return _para(ppr, _run(text, bold=True, color=COLOR_NAVY))


def p_section_heading(text):
    ppr = _pPr(
        _heading_borders(),
        _spacing(before="160", after="40", line="270", lineRule="auto"),
    )
    return _para(ppr, _run(text, bold=True, color=COLOR_NAVY, sz=SZ_HEADING, eastAsia="Merriweather"))


def p_summary(text):
    ppr = _pPr(
        _spacing(before="0", after="60", line="264", lineRule="auto"),
        _w("jc", val="both"),
    )
    p = _w("p")
    p.append(ppr)
    for seg, bold in _segs(text):
        p.append(_run(seg, bold=bold))
    return p


def p_skill_row(category, items):
    """Bold category + soft line-break + normal items. numId=1 (square bullet)."""
    ppr = _pPr(
        _numPr(1),
        _spacing(before="0", after="40", line="264", lineRule="auto"),
        _ind(left="360", hanging="180"),
    )
    p = _w("p")
    p.append(ppr)
    if category:
        p.append(_run(category, bold=True))
        p.append(_run_br())
    p.append(_run(items))
    return p


def p_bullet(text):
    """Experience bullet. numId=2 (round bullet). May contain **bold** spans."""
    ppr = _pPr(
        _numPr(2),
        _spacing(before="0", after="40", line="264", lineRule="auto"),
        _ind(left="360", hanging="180"),
        _w("jc", val="both"),
    )
    p = _w("p")
    p.append(ppr)
    for seg, bold in _segs(text):
        p.append(_run(seg, bold=bold))
    return p


def p_job_title(text):
    ppr = _pPr(
        _spacing(before="100", after="0", line="264", lineRule="auto"),
    )
    return _para(ppr, _run(text, bold=True))


def p_company_date(company, date_loc):
    ppr = _pPr(
        _right_tabs("9360"),
        _spacing(before="0", after="0", line="270", lineRule="auto"),
    )
    p = _w("p")
    p.append(ppr)
    p.append(_run(company, color=COLOR_NAVY))
    p.append(_run_tab(color=COLOR_NAVY))
    p.append(_run(date_loc, color=COLOR_NAVY))
    return p


def p_degree(text):
    ppr = _pPr(
        _spacing(before="80", after="0", line="270", lineRule="auto"),
    )
    p = _w("p")
    p.append(ppr)
    for seg, bold in _segs(text):
        p.append(_run(seg, bold=True, color=COLOR_NAVY, eastAsia="Merriweather"))
    return p


def p_school_date(text):
    ppr = _pPr(
        _spacing(before="0", after="0", line="270", lineRule="auto"),
    )
    return _para(ppr, _run(text, color=COLOR_NAVY))


def p_cert(name, issued):
    ppr = _pPr(
        _spacing(before="80", after="0", line="270", lineRule="auto"),
    )
    p = _w("p")
    p.append(ppr)
    p.append(_run(name, bold=True, color=COLOR_NAVY, eastAsia="Merriweather"))
    if issued:
        p.append(_run_br())
        p.append(_run(issued))
    return p


# ─── Embedded XML for numbering and styles ───────────────────────────────────

_NUMBERING_XML = b"""\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="1">
    <w:multiLevelType w:val="singleLevel"/>
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/>
      <w:numFmt w:val="bullet"/>
      <w:lvlText w:val="&#9632;"/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="360" w:hanging="180"/></w:pPr>
      <w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"/><w:sz w:val="16"/></w:rPr>
    </w:lvl>
  </w:abstractNum>
  <w:abstractNum w:abstractNumId="2">
    <w:multiLevelType w:val="singleLevel"/>
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/>
      <w:numFmt w:val="bullet"/>
      <w:lvlText w:val="&#8226;"/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="360" w:hanging="180"/></w:pPr>
      <w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"/><w:sz w:val="20"/></w:rPr>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="1"/></w:num>
  <w:num w:numId="2"><w:abstractNumId w:val="2"/></w:num>
</w:numbering>
"""

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
    <w:uiPriority w:val="1"/>
    <w:semiHidden/><w:unhideWhenUsed/>
  </w:style>
  <w:style w:type="character" w:styleId="Hyperlink">
    <w:name w:val="Hyperlink"/>
    <w:basedOn w:val="DefaultParagraphFont"/>
    <w:rPr><w:color w:val="0563C1"/><w:u w:val="single"/></w:rPr>
  </w:style>
</w:styles>
"""


# ─── Document bootstrapper ───────────────────────────────────────────────────

def _build_doc():
    """Create a fresh Document with custom styles and numbering."""
    from docx.opc.part import Part
    from docx.opc.packuri import PackURI
    from docx.oxml import parse_xml

    doc = Document()

    # Replace styles
    doc.part.styles._element.clear()
    for child in ET.fromstring(_STYLES_XML):
        doc.part.styles._element.append(copy.deepcopy(child))

    # Inject numbering
    NUM_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering"
    NUM_CT  = "application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"
    try:
        num_part = doc.part.part_related_by(NUM_REL)
        num_part._element.clear()
        for child in ET.fromstring(_NUMBERING_XML):
            num_part._element.append(copy.deepcopy(child))
    except Exception:
        num_part = Part(
            PackURI("/word/numbering.xml"),
            NUM_CT,
            parse_xml(_NUMBERING_XML),
            doc.part.package,
        )
        doc.part.relate_to(num_part, NUM_REL)

    # Page margins
    body   = doc.element.body
    sectPr = body.find(qn("w:sectPr"))
    if sectPr is None:
        sectPr = _w("sectPr")
        body.append(sectPr)
    for tag in ("w:pgMar", "w:pgSz"):
        el = sectPr.find(qn(tag))
        if el is not None:
            sectPr.remove(el)
    sectPr.append(_w("pgSz", w="12240", h="15840"))
    sectPr.append(_w("pgMar", top="720", right="720", bottom="720", left="720",
                     header="708", footer="708", gutter="0"))

    # Clear default empty paragraph Word always adds
    for p in list(body.findall(qn("w:p"))):
        body.remove(p)

    return doc


def _add(doc, p_el):
    body   = doc.element.body
    sectPr = body.find(qn("w:sectPr"))
    if sectPr is not None:
        body.insert(list(body).index(sectPr), p_el)
    else:
        body.append(p_el)


# ─── Resume text parser ──────────────────────────────────────────────────────

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


_SEC_RE    = re.compile(
    r"^(PROFESSIONAL SUMMARY|SUMMARY|SKILLS|TECHNICAL SKILLS|CORE COMPETENCIES|"
    r"EXPERIENCE|WORK EXPERIENCE|WORK HISTORY|EMPLOYMENT HISTORY|"
    r"EDUCATION|ACADEMIC BACKGROUND|"
    r"CERTIFICATIONS?|CERTIFICATES?|LICENSES?|"
    r"PROJECTS?|ACHIEVEMENTS?|AWARDS?|PUBLICATIONS?|"
    r"VOLUNTEER|LANGUAGES|INTERESTS|REFERENCES|ADDITIONAL)$",
    re.I,
)
_BULLET_RE = re.compile(r"^[•\-\*·▪►▸‣➢✓○◆]\s*")
_DATE_RE   = re.compile(
    r"\b(20\d\d|19\d\d|present|current|now|"
    r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b", re.I
)


def parse_resume_text(text):
    data  = ResumeData()
    lines = [l.rstrip() for l in text.split("\n")]

    # Locate sections
    sec_order, sec_starts = [], {}
    for i, line in enumerate(lines):
        stripped = line.strip()
        if _SEC_RE.match(stripped):
            key = stripped.upper()
            if key not in sec_starts:
                sec_order.append(key)
                sec_starts[key] = i

    def get_lines(name):
        key = None
        for k in sec_starts:
            if k == name or k.startswith(name):
                key = k; break
        if not key:
            return []
        idx   = sec_order.index(key)
        start = sec_starts[key] + 1
        end   = sec_starts[sec_order[idx+1]] if idx+1 < len(sec_order) else len(lines)
        return [l for l in lines[start:end] if l.strip()]

    # Header
    first_sec = sec_starts[sec_order[0]] if sec_order else len(lines)
    header    = [l.strip() for l in lines[:first_sec] if l.strip()]
    if header:       data.name     = header[0]
    if len(header)>1: data.location = header[1]
    if len(header)>2: data.contacts = header[2:]

    # Summary
    sl = get_lines("PROFESSIONAL SUMMARY") or get_lines("SUMMARY")
    data.summary = " ".join(sl)

    # Skills (three formats: embedded \n, two-line, colon)
    raw = get_lines("SKILLS") or get_lines("TECHNICAL SKILLS") or get_lines("CORE COMPETENCIES")
    si  = 0
    while si < len(raw):
        line = raw[si].strip()
        if "\n" in line:
            cat, items = line.split("\n", 1)
            data.skills.append((cat.strip(), items.strip()))
            si += 1
        elif (":" in line and len(line.split(":")[0]) < 50 and
              "," not in line.split(":")[0] and not _BULLET_RE.match(line)):
            cat, items = line.split(":", 1)
            data.skills.append((cat.strip(), items.strip()))
            si += 1
        elif (si+1 < len(raw) and "," not in line and len(line) < 55
              and not _BULLET_RE.match(line)
              and ("," in raw[si+1] or len(raw[si+1]) > 20)):
            data.skills.append((line, raw[si+1].strip()))
            si += 2
        else:
            data.skills.append(("", line))
            si += 1

    # Experience
    exp = (get_lines("EXPERIENCE") or get_lines("WORK EXPERIENCE") or
           get_lines("WORK HISTORY") or get_lines("EMPLOYMENT HISTORY"))
    cur = None
    for line in exp:
        line = line.strip()
        if not line: continue
        if _BULLET_RE.match(line):
            if cur: cur["bullets"].append(_BULLET_RE.sub("", line).strip())
        elif _DATE_RE.search(line):
            if "\t" in line:
                company, rest = line.split("\t", 1)
            elif "|" in line:
                company, rest = line.split("|", 1)
            else:
                # Try two-space split before date
                m = re.search(r'\s{2,}', line)
                if m:
                    company, rest = line[:m.start()].strip(), line[m.end():].strip()
                else:
                    company, rest = line, ""
            if cur and not cur.get("company"):
                cur["company"]       = company.strip()
                cur["date_location"] = rest.strip()
        else:
            cur = {"title": line, "company": "", "date_location": "", "bullets": []}
            data.jobs.append(cur)

    # Education (alternating degree / school lines)
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
        if "\n" in line:
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


# ─── Public API ───────────────────────────────────────────────────────────────

def generate_docx(resume_text, template_path=None):
    """
    Build a Rezi-style DOCX from resume_text (plain text, **bold** markers optional).
    template_path is accepted but ignored — style is fully self-contained.
    Returns bytes.
    """
    data = parse_resume_text(resume_text)
    doc  = _build_doc()

    if data.name:      _add(doc, p_name(data.name))
    if data.location:  _add(doc, p_location(data.location))
    for c in data.contacts:
        _add(doc, p_contact(c))

    if data.summary:
        _add(doc, p_section_heading("PROFESSIONAL SUMMARY"))
        _add(doc, p_summary(data.summary))

    if data.skills:
        _add(doc, p_section_heading("SKILLS"))
        for cat, items in data.skills:
            if cat or items:
                _add(doc, p_skill_row(cat, items))

    if data.jobs:
        _add(doc, p_section_heading("EXPERIENCE"))
        for job in data.jobs:
            _add(doc, p_job_title(job["title"]))
            if job.get("company"):
                _add(doc, p_company_date(job["company"], job.get("date_location", "")))
            for bullet in job["bullets"]:
                _add(doc, p_bullet(bullet))

    if data.education:
        _add(doc, p_section_heading("EDUCATION"))
        for edu in data.education:
            _add(doc, p_degree(edu["degree"]))
            if edu.get("school_date"):
                _add(doc, p_school_date(edu["school_date"]))

    if data.certs:
        _add(doc, p_section_heading("CERTIFICATIONS"))
        for cert in data.certs:
            _add(doc, p_cert(cert["name"], cert.get("issued", "")))

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
